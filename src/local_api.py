#!/usr/bin/env python3
"""Local CPU HTTP API for the original OpenAI GPT-2 model.

The original TensorFlow GPT-2 source remains unchanged except for a CPU
thread-control patch in interactive_conditional_samples.py. This optional
API runs the original OpenAI GPT-2 weights through current CPU libraries.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_BODY_BYTES = 32_768
MAX_MESSAGE_CHARS = 4_000
MAX_MESSAGES = 8
MAX_NEW_TOKENS = 128
DEFAULT_MODEL = "openai-community/gpt2"


class RequestError(ValueError):
    """Invalid request submitted to the local API."""


def prepare_request(payload: Any) -> tuple[str, int]:
    if not isinstance(payload, dict):
        raise RequestError("O corpo da solicitação deve ser um objeto JSON.")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise RequestError("Envie entre 1 e 8 mensagens.")
    max_tokens = payload.get("max_tokens", 64)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
        raise RequestError("max_tokens deve ser um número inteiro.")
    if not 1 <= max_tokens <= MAX_NEW_TOKENS:
        raise RequestError("max_tokens deve estar entre 1 e 128.")

    transcript: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            raise RequestError("Cada mensagem deve ser um objeto.")
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system"}:
            raise RequestError("Função de mensagem desconhecida.")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            raise RequestError("A mensagem deve conter de 1 a 4000 caracteres.")
        label = {"user": "Usuário", "assistant": "Assistente", "system": "Contexto"}[role]
        transcript.append(f"{label}: {content.strip()}")

    if messages[-1]["role"] != "user":
        raise RequestError("A última mensagem deve ser do usuário.")
    return "\n".join(transcript) + "\nAssistente:", max_tokens


class LocalModel:
    def __init__(self, model_name: str, threads: int, offline: bool) -> None:
        if offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.set_num_threads(threads)
        torch.set_num_interop_threads(1)
        self.torch = torch
        self.name = model_name
        self.lock = threading.Lock()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=offline)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            local_files_only=offline,
            use_safetensors=True,
        )
        self.model.to("cpu").eval()
        self.context_size = int(getattr(self.model.config, "n_positions", 1024))
        self.end_id = self.tokenizer.eos_token_id

    def reply(self, prompt: str, max_tokens: int) -> tuple[str, int, int]:
        with self.lock, self.torch.inference_mode():
            encoded = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=max(64, self.context_size - max_tokens - 1),
            )
            input_ids = encoded["input_ids"]
            result = self.model.generate(
                input_ids=input_ids,
                attention_mask=encoded["attention_mask"],
                max_new_tokens=max_tokens,
                do_sample=False,
                repetition_penalty=1.12,
                pad_token_id=self.end_id,
                use_cache=True,
            )
            generated = result[0, input_ids.shape[1]:]
            answer = self.tokenizer.decode(generated, skip_special_tokens=True)
            for delimiter in ("\nUsuário:", "\nAssistente:", "\nContexto:"):
                answer = answer.split(delimiter, 1)[0]
            return answer.strip(), int(input_ids.shape[1]), int(generated.shape[0])


class LocalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4


def build_handler(model: Any) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _json(self, status: int, response: dict[str, Any]) -> None:
            payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path == "/health":
                return self._json(200, {"status": "ok", "model": model.name, "local": True})
            if self.path == "/v1/models":
                return self._json(200, {"object": "list", "data": [
                    {"id": model.name, "object": "model", "owned_by": "openai"}
                ]})
            self._json(404, {"error": {"message": "Rota não encontrada."}})

        def do_POST(self) -> None:
            if self.path != "/v1/chat/completions":
                return self._json(404, {"error": {"message": "Rota não encontrada."}})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY_BYTES:
                    raise RequestError("Tamanho de requisição inválido.")
                content = self.rfile.read(size)
                data = json.loads(content.decode("utf-8"))
                prompt, max_tokens = prepare_request(data)
            except (RequestError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                return self._json(400, {"error": {"message": str(exc)}})
            try:
                answer, used_prompt, used_completion = model.reply(prompt, max_tokens)
            except Exception:
                logging.exception("Erro durante a inferência local")
                return self._json(500, {"error": {"message": "Erro de inferência local."}})
            self._json(200, {
                "id": "chatcmpl-" + uuid.uuid4().hex,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model.name,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": used_prompt, "completion_tokens": used_completion,
                          "total_tokens": used_prompt + used_completion},
            })

        def log_message(self, fmt: str, *args: Any) -> None:
            logging.info("HTTP %s - %s", self.client_address[0], fmt % args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="API local para o GPT-2 original da OpenAI.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo GPT-2 ou pasta local")
    parser.add_argument("--threads", type=int, default=2, help="Threads de CPU para inferência")
    parser.add_argument("--port", type=int, default=8765, help="Porta local HTTP")
    parser.add_argument("--offline", action="store_true", help="Usa somente pesos já armazenados")
    args = parser.parse_args()
    if not 1 <= args.threads <= 16:
        parser.error("--threads deve estar entre 1 e 16")
    if not 1024 <= args.port <= 65535:
        parser.error("--port deve estar entre 1024 e 65535")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    model = LocalModel(args.model, args.threads, args.offline)
    server = LocalHTTPServer(("127.0.0.1", args.port), build_handler(model))
    logging.info("Modelo carregado: %s; API local em http://127.0.0.1:%s", args.model, args.port)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
