"""Opt-in real OpenAI checkpoint tests; require local CPU torch and ~1 GB RAM.

SEXTA_RUN_MODEL_TESTS=1 python -m unittest discover -s tests -p test_inference_model.py
"""
import importlib.util
import os
from pathlib import Path
import unittest


def numpy_reference(model, token_ids):
    """Independent NumPy forward matching the equations in OpenAI model.py."""
    import numpy as np
    hp = model.hparams
    weights = {name: tensor.numpy() for name, tensor in model.weights.items()}
    def norm(value, name):
        centered = value - value.mean(axis=-1, keepdims=True)
        variance = (centered * centered).mean(axis=-1, keepdims=True)
        return centered / np.sqrt(variance + np.float32(1e-5)) * weights[name + "/g"] + weights[name + "/b"]
    def linear(value, name):
        return np.matmul(value, weights[name + "/w"].reshape(value.shape[-1], -1)) + weights[name + "/b"]
    ids = np.asarray([token_ids], dtype=np.int64)
    hidden = weights["model/wte"][ids] + weights["model/wpe"][np.arange(len(token_ids))]
    length, heads, width = len(token_ids), hp["n_head"], hp["n_embd"]
    for index in range(hp["n_layer"]):
        name = "model/h%d/" % index
        qkv = np.split(linear(norm(hidden, name + "ln_1"), name + "attn/c_attn"), 3, axis=-1)
        q, k, v = [part.reshape(1, length, heads, width // heads).transpose(0, 2, 1, 3) for part in qkv]
        scores = np.matmul(q, k.swapaxes(-2, -1)) / np.float32(np.sqrt(width // heads))
        mask = np.tril(np.ones((length, length), dtype=np.float32))
        scores = scores * mask - np.float32(1e10) * (1 - mask)
        exponent = np.exp(scores - scores.max(axis=-1, keepdims=True))
        probabilities = exponent / exponent.sum(axis=-1, keepdims=True)
        attended = np.matmul(probabilities, v).transpose(0, 2, 1, 3).reshape(1, length, width)
        hidden = hidden + linear(attended, name + "attn/c_proj")
        expanded = linear(norm(hidden, name + "ln_2"), name + "mlp/c_fc")
        gelu = np.float32(0.5) * expanded * (1 + np.tanh(np.float32(np.sqrt(2 / np.pi)) * (
            expanded + np.float32(0.044715) * expanded ** 3)))
        hidden = hidden + linear(gelu, name + "mlp/c_proj")
    return np.matmul(norm(hidden, "model/ln_f")[:, -1, :], weights["model/wte"].T)


@unittest.skipUnless(os.environ.get("SEXTA_RUN_MODEL_TESTS") == "1", "Real checkpoint tests are opt-in")
class RealModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sexta_feira.brain import load_model
        cls.tokenizer, cls.model = load_model()

    def test_logits_match_numpy_reference(self):
        import numpy as np
        import torch
        ids = self.tokenizer.encode("The capital of France is")
        with torch.inference_mode():
            actual, _ = self.model.forward(torch.tensor([ids]))
        expected = numpy_reference(self.model, ids)
        np.testing.assert_allclose(actual.numpy(), expected, rtol=0.0005, atol=0.0005)
        self.assertEqual(actual.argmax().item(), int(expected.argmax()))

    def test_cached_logits_match_full_context(self):
        import numpy as np
        import torch
        ids = self.tokenizer.encode("OpenAI released GPT-2 in 2019.")
        with torch.inference_mode():
            full, _ = self.model.forward(torch.tensor([ids]))
            _, past = self.model.forward(torch.tensor([ids[:-1]]))
            cached, _ = self.model.forward(torch.tensor([[ids[-1]]]), past)
        np.testing.assert_allclose(full.numpy(), cached.numpy(), rtol=0.0005, atol=0.0005)

    def test_tokenizer_matches_upstream(self):
        path = Path(__file__).resolve().parents[1] / "openai-gpt2/upstream-original/src/encoder.py"
        spec = importlib.util.spec_from_file_location("original_encoder", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module.Encoder(self.tokenizer.encoder, list(self.tokenizer.bpe_ranks))
        for text in ("Olá, Brasil!", "The capital of France is", "\n\t123", "🚲 SEXTA-FEIRA"):
            self.assertEqual(self.tokenizer.encode(text), original.encode(text))
            self.assertEqual(self.tokenizer.decode(self.tokenizer.encode(text)), text)

    def test_generation_and_context_limits(self):
        reply, tokens = self.model.generate("The capital of France is", input_limit=32,
                                            new_tokens=8, cancelled=lambda: None, seed=7)
        self.assertIsInstance(reply, str)
        self.assertGreater(tokens, 0)
        self.assertLessEqual(tokens, 8)

    def test_invalid_generation_parameters_are_rejected(self):
        for options in ({"temperature": float("nan")}, {"new_tokens": 65},
                        {"input_limit": 0}, {"top_k": 0}, {"temperature": 0}):
            values = {"input_limit": 32, "new_tokens": 8, "temperature": 1, "top_k": 40}
            values.update(options)
            with self.assertRaises(ValueError):
                self.model.generate("public", cancelled=lambda: None, **values)


if __name__ == "__main__":
    unittest.main()
