import importlib.util
import hashlib
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from sexta_feira.brain import (InferenceEngine, InferenceBusy, InferenceTimeout,
                               InferenceUnavailable, build_prompt)
from sexta_feira.weights import checkpoint_entries, verify_weights, digest_file


class InferenceLimitsTests(unittest.TestCase):
    def test_prompt_limits_and_relevance(self):
        with self.assertRaises(ValueError):
            build_prompt(" ", [], [])
        with self.assertRaises(ValueError):
            build_prompt("x" * 2401, [], [])
        result = build_prompt("bicicleta azul", [], [{"content": "bicicleta favorita azul"},
                                                    {"content": "senha confidencial"}])
        self.assertIn("bicicleta favorita", result)
        self.assertNotIn("senha confidencial", result)

    def test_queue_bounded_and_shutdown(self):
        engine = InferenceEngine()
        entered, release = threading.Event(), threading.Event()
        class Fake:
            tokenizer = None
            def generate(self, prompt, *, cancelled, **kwargs):
                entered.set()
                while not release.wait(0.01):
                    cancelled()
                return "ok", 1
        engine._model, engine._model_size = Fake(), "small"
        errors, replies = [], []
        def submit():
            try:
                replies.append(engine.submit("public", "small"))
            except InferenceUnavailable as exc:
                errors.append(exc)
        with patch.object(engine, "_memory_guard"):
            callers = [threading.Thread(target=submit) for _ in range(3)]
            callers[0].start()
            self.assertTrue(entered.wait(2))
            for caller in callers[1:]:
                caller.start()
            deadline = time.monotonic() + 2
            while engine._queue.qsize() < 2 and time.monotonic() < deadline:
                time.sleep(0.005)
            with self.assertRaises(InferenceBusy):
                engine.submit("overflow", "small")
            release.set()
            for caller in callers:
                caller.join(3)
            engine.close()
        self.assertEqual(replies, ["ok", "ok", "ok"])
        self.assertEqual(errors, [])
        self.assertFalse(engine._thread.is_alive())

    def test_cancel_does_not_start_second_worker(self):
        engine = InferenceEngine()
        entered = threading.Event()
        class Fake:
            tokenizer = None
            def generate(self, prompt, *, cancelled, **kwargs):
                entered.set()
                while True:
                    cancelled()
                    time.sleep(0.005)
        engine._model, engine._model_size = Fake(), "small"
        with patch.object(engine, "_memory_guard"):
            with self.assertRaises(InferenceTimeout):
                engine.submit("public", "small", timeout=0.03)
            worker = engine._thread
            engine.close()
        self.assertTrue(entered.is_set())
        self.assertIs(engine._thread, worker)
        self.assertFalse(worker.is_alive())

    def test_memory_reserve_blocks_model_loading(self):
        engine = InferenceEngine()
        with patch("sexta_feira.brain.available_memory_bytes", return_value=512 * 1024 * 1024):
            with self.assertRaises(InferenceUnavailable):
                engine.load()
        self.assertFalse(engine.status()["loaded"])
        engine.close()

    def test_concurrent_initialization_loads_once(self):
        engine = InferenceEngine()
        loads = []
        class Fake:
            tokenizer = None
            def __init__(self, directory, threads):
                time.sleep(0.02)
                loads.append(directory)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "124M"
            directory.mkdir()
            (directory / "integrity.json").write_text("{}")
            with patch.dict("os.environ", {"SEXTA_MODEL_DIR": tmp}), patch.object(engine, "_memory_guard"), \
                 patch("sexta_feira.inference_torch.GPT2CPU", Fake):
                callers = [threading.Thread(target=engine.load) for _ in range(4)]
                for caller in callers:
                    caller.start()
                for caller in callers:
                    caller.join(2)
                self.assertEqual(len(loads), 1)
                with self.assertRaises(InferenceUnavailable):
                    engine.load("medium")
        engine.close()

    def test_checkpoint_rejects_malformed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.ckpt.index"
            path.write_bytes(b"invalid")
            with self.assertRaises(ValueError):
                checkpoint_entries(path)

    def test_cancel_before_submission_does_not_start_worker(self):
        engine = InferenceEngine()
        event = threading.Event()
        event.set()
        with self.assertRaises(InferenceTimeout):
            engine.submit("cancelled", "small", cancel_event=event)
        self.assertIsNone(engine._thread)
        engine.close()


class ProvenanceTests(unittest.TestCase):
    def test_preserved_original_sources_match_recorded_sha256(self):
        root = Path(__file__).resolve().parents[1] / "openai-gpt2/upstream-original"
        manifest = json.loads((root / "PROVENANCE.json").read_text())
        self.assertEqual(manifest["repository"], "https://github.com/openai/gpt-2")
        for filename, digest in manifest["sha256"].items():
            self.assertEqual(hashlib.sha256((root / filename).read_bytes()).hexdigest(), digest)
        self.assertEqual((root / "LICENSE").read_text(), (root.parent / "LICENSE").read_text())

    def test_download_size_limit_retry_and_offline_tamper_detection(self):
        from sexta_feira.weights import download_weights
        import sexta_feira.weights as weights
        content = b"abc"
        md5 = base64.b64encode(hashlib.md5(content, usedforsecurity=False).digest()).decode()
        sha = hashlib.sha256(content).hexdigest()
        class Response(io.BytesIO):
            headers = {"Content-Length": "3"}
            def geturl(self):
                return "https://openaipublic.blob.core.windows.net/gpt-2/models/124M/checkpoint"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(weights, "FILES", ("checkpoint",)), \
             patch.object(weights, "OFFICIAL_124M", {"checkpoint": (3, md5)}), \
             patch.object(weights, "OFFICIAL_124M_SHA256", {"checkpoint": sha}):
            directory = Path(tmp) / "124M"
            with patch("urllib.request.urlopen", return_value=Response(b"abcd")):
                with self.assertRaisesRegex(ValueError, "exceeded"):
                    download_weights(Path(tmp))
            self.assertFalse((directory / "checkpoint").exists())
            self.assertEqual(len(list(directory.glob("*.part.*"))), 1)
            with patch("urllib.request.urlopen", return_value=Response(content)):
                download_weights(Path(tmp))
            self.assertEqual((directory / "checkpoint").read_bytes(), content)
            self.assertEqual(len(list(directory.glob("*.part.*"))), 1)
            with patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden")):
                self.assertEqual(verify_weights(directory)["files"]["checkpoint"]["sha256"], sha)
                download_weights(Path(tmp))
            (directory / "checkpoint").write_bytes(b"abd")
            with self.assertRaises(ValueError):
                verify_weights(directory)


if __name__ == "__main__":
    unittest.main()
