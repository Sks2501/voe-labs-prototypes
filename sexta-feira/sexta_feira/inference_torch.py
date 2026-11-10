"""CPU transcription of openai/gpt-2/src/model.py using original TF tensors.

This independent PyTorch adapter preserves OpenAI matrix layouts, tied output
embeddings, pre-layer norms, tanh GELU and causal attention. Float32 CPU only.
"""
from __future__ import annotations
import importlib.util
import json
import math
from pathlib import Path

_INTEROP_CONFIGURED = False


class GPT2CPU:
    def __init__(self, directory: Path, cpu_threads: int = 1):
        import torch
        from .weights import load_checkpoint
        torch.set_num_threads(cpu_threads)
        global _INTEROP_CONFIGURED
        if not _INTEROP_CONFIGURED:
            torch.set_num_interop_threads(1)
            _INTEROP_CONFIGURED = True
        self.torch = torch
        self.hparams = json.loads((directory / "hparams.json").read_text(encoding="utf-8"))
        if self.hparams not in (
            {"n_vocab": 50257, "n_ctx": 1024, "n_embd": 768, "n_head": 12, "n_layer": 12},
            {"n_vocab": 50257, "n_ctx": 1024, "n_embd": 1024, "n_head": 16, "n_layer": 24},
        ):
            raise ValueError("Checkpoint architecture is not an approved OpenAI GPT-2 configuration")
        arrays = load_checkpoint(directory)
        self.weights = {name: torch.from_numpy(array) for name, array in arrays.items()}
        self._validate_shapes()
        path = Path(__file__).resolve().parents[1] / "openai-gpt2" / "src" / "encoder.py"
        spec = importlib.util.spec_from_file_location("sexta_openai_encoder", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.tokenizer = module.get_encoder(directory.name, str(directory.parent))

    def _validate_shapes(self):
        hp, width = self.hparams, self.hparams["n_embd"]
        expected = {"model/wte": (hp["n_vocab"], width), "model/wpe": (hp["n_ctx"], width),
                    "model/ln_f/g": (width,), "model/ln_f/b": (width,)}
        for index in range(hp["n_layer"]):
            prefix = "model/h%d/" % index
            for norm in ("ln_1", "ln_2"):
                for kind in ("g", "b"):
                    expected[prefix + norm + "/" + kind] = (width,)
            for layer, source, destination in (("attn/c_attn", width, 3 * width),
                                                ("attn/c_proj", width, width),
                                                ("mlp/c_fc", width, 4 * width),
                                                ("mlp/c_proj", 4 * width, width)):
                expected[prefix + layer + "/w"] = (1, source, destination)
                expected[prefix + layer + "/b"] = (destination,)
        if set(self.weights) != set(expected):
            raise ValueError("Unexpected or missing GPT-2 checkpoint tensors")
        for name, shape in expected.items():
            if tuple(self.weights[name].shape) != shape:
                raise ValueError("GPT-2 tensor shape mismatch: " + name)

    def _norm(self, x, name):
        return self.torch.nn.functional.layer_norm(
            x, (self.hparams["n_embd"],), self.weights[name + "/g"], self.weights[name + "/b"], 1e-5)

    def _linear(self, x, name):
        return x @ self.weights[name + "/w"][0] + self.weights[name + "/b"]

    def forward(self, tokens, past=None):
        """Return last-position logits and complete KV cache for one sequence."""
        torch, hp = self.torch, self.hparams
        if tokens.ndim != 2 or tokens.shape[0] != 1 or tokens.shape[1] < 1:
            raise ValueError("Only one nonempty sequence is supported")
        previous_length = 0 if past is None else past[0][0].shape[-2]
        length = tokens.shape[1]
        if previous_length + length > hp["n_ctx"]:
            raise ValueError("GPT-2 context window exceeded")
        positions = torch.arange(previous_length, previous_length + length, device="cpu")
        hidden = self.weights["model/wte"][tokens] + self.weights["model/wpe"][positions]
        presents = []
        head_width = hp["n_embd"] // hp["n_head"]
        for index in range(hp["n_layer"]):
            prefix = "model/h%d/" % index
            qkv = self._linear(self._norm(hidden, prefix + "ln_1"), prefix + "attn/c_attn")
            query, key, value = (part.reshape(1, length, hp["n_head"], head_width).transpose(1, 2)
                                 for part in qkv.split(hp["n_embd"], dim=-1))
            if past is not None:
                key = torch.cat((past[index][0], key), dim=-2)
                value = torch.cat((past[index][1], value), dim=-2)
            presents.append((key, value))
            scores = (query @ key.transpose(-2, -1)) * (head_width ** -0.5)
            # Same lower-right aligned causal mask as original OpenAI code.
            row = torch.arange(length).unsqueeze(1) + previous_length
            column = torch.arange(key.shape[-2]).unsqueeze(0)
            scores.masked_fill_(column > row, -1e10)
            attended = (torch.softmax(scores, dim=-1) @ value).transpose(1, 2).reshape(1, length, hp["n_embd"])
            hidden = hidden + self._linear(attended, prefix + "attn/c_proj")
            intermediate = self._linear(self._norm(hidden, prefix + "ln_2"), prefix + "mlp/c_fc")
            intermediate = 0.5 * intermediate * (1 + torch.tanh(
                (2 / 3.141592653589793) ** 0.5 * (intermediate + 0.044715 * intermediate.pow(3))))
            hidden = hidden + self._linear(intermediate, prefix + "mlp/c_proj")
        hidden = self._norm(hidden[:, -1, :], "model/ln_f")
        return hidden @ self.weights["model/wte"].T, presents

    def generate(self, prompt: str, *, input_limit: int, new_tokens: int, cancelled,
                 temperature: float = 0.76, top_k: int = 40, seed: int | None = None):
        torch = self.torch
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8192:
            raise ValueError("Generation prompt must be nonempty text up to 8192 characters")
        for value, name, maximum in ((input_limit, "input_limit", self.hparams["n_ctx"] - 1),
                                     (new_tokens, "new_tokens", 64),
                                     (top_k, "top_k", self.hparams["n_vocab"])):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(name + " is outside permitted bounds")
        if not isinstance(temperature, (int, float)) or not math.isfinite(temperature) or not 0 < temperature <= 2:
            raise ValueError("temperature must be finite and in (0, 2]")
        if not callable(cancelled):
            raise ValueError("A cancellation checkpoint is required")
        ids = self.tokenizer.encode(prompt)[-min(input_limit, self.hparams["n_ctx"] - new_tokens):]
        if not ids:
            raise ValueError("Empty tokenized context")
        generator = None if seed is None else torch.Generator(device="cpu").manual_seed(seed)
        tokens = torch.tensor([ids], dtype=torch.long, device="cpu")
        output, past = [], None
        with torch.inference_mode():
            for _ in range(new_tokens):
                cancelled()
                logits, past = self.forward(tokens, past)
                values, indices = torch.topk(logits[0] / temperature, min(top_k, logits.numel()))
                sampled = torch.multinomial(torch.softmax(values, dim=-1), 1, generator=generator)
                token_id = int(indices[sampled].item())
                if token_id == self.tokenizer.encoder["<|endoftext|>"]:
                    break
                output.append(token_id)
                tokens = torch.tensor([[token_id]], dtype=torch.long, device="cpu")
        return self.tokenizer.decode(output).strip(), len(output)
