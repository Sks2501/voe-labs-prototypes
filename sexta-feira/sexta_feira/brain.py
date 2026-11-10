"""Motor de inferência local para pesos originais GPT-2 da OpenAI.

A implementação TensorFlow original acompanha a distribuição em openai-gpt2/.
Este adaptador usa a versão PyTorch dos MESMOS pesos, evitando TensorFlow 1.x
e permitindo Windows recente. Não utiliza API paga nem Ollama.
"""
from __future__ import annotations
import os
import threading
from functools import lru_cache
from .settings import DEFAULT_MODEL, MAX_INPUT_TOKENS, MAX_NEW_TOKENS, MODELS

_GENERATION_LOCK = threading.Lock()

@lru_cache(maxsize=1)
def load_model(model_size: str = DEFAULT_MODEL):
    if model_size not in MODELS:
        raise ValueError("Modelo inválido: use small, medium ou large.")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 2)))
    torch.set_num_interop_threads(1)
    model_id = MODELS[model_size]
    offline = os.environ.get("SEXTA_OFFLINE") == "1"
    tokenizer = AutoTokenizer.from_pretrained(
        model_id, local_files_only=offline, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, local_files_only=offline, trust_remote_code=False)
    model.to("cpu")
    model.eval()
    return tokenizer, model

def build_prompt(message: str, history: list[dict], memories: list[dict]) -> str:
    relevant = [m["content"][:140] for m in memories[:5]]
    parts = [
        "SEXTA-FEIRA é uma assistente pessoal educada, breve e prestativa.",
        "Conversa em português. Quando não sabe a resposta, informa que não sabe.",
    ]
    if relevant:
        parts.append("Memórias do usuário: " + " | ".join(relevant))
    for item in history[-5:]:
        role = "Usuário" if item["role"] == "user" else "SEXTA-FEIRA"
        parts.append(role + ": " + item["content"][:260])
    parts.append("Usuário: " + message)
    parts.append("SEXTA-FEIRA:")
    return "\n".join(parts)

def generate_reply(message: str, history: list[dict], memories: list[dict], model_size: str = DEFAULT_MODEL) -> str:
    import torch
    tokenizer, model = load_model(model_size)
    prompt = build_prompt(message, history, memories)
    inputs = tokenizer(
        prompt, return_tensors="pt", truncation=True,
        max_length=MAX_INPUT_TOKENS)
    with _GENERATION_LOCK, torch.inference_mode():
        output = model.generate(
            input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"],
            max_new_tokens=MAX_NEW_TOKENS, do_sample=True,
            temperature=0.76, top_k=40, top_p=0.9,
            repetition_penalty=1.18, no_repeat_ngram_size=3,
            pad_token_id=tokenizer.eos_token_id,
            use_cache=True)
    generated = output[0, inputs["input_ids"].shape[1]:]
    result = tokenizer.decode(generated, skip_special_tokens=True).strip()
    for delimiter in ("\nUsuário:", "\nSEXTA-FEIRA:", "\nUser:", "\nAssistant:"):
        result = result.split(delimiter, 1)[0].strip()
    return result[:1200] or "Não consegui gerar uma resposta útil. Pode reformular a pergunta?"
