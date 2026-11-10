import importlib.util
import json
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "local_api.py"
SPEC = importlib.util.spec_from_file_location("gpt2_local_api", SOURCE)
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


class FakeModel:
    name = "openai-community/gpt2"

    def reply(self, prompt, max_tokens):
        return "Resposta de teste", 12, min(max_tokens, 4)


class ValidationTests(unittest.TestCase):
    def test_valid_chat(self):
        prompt, limit = api.prepare_request({"messages": [{"role": "user", "content": "Olá"}]})
        self.assertEqual(limit, 64)
        self.assertEqual(prompt, "Usuário: Olá\nAssistente:")

    def test_empty_messages_rejected(self):
        with self.assertRaises(api.RequestError):
            api.prepare_request({"messages": []})

    def test_invalid_role_rejected(self):
        with self.assertRaises(api.RequestError):
            api.prepare_request({"messages": [{"role": "admin", "content": "oi"}]})

    def test_max_tokens_cannot_be_boolean(self):
        with self.assertRaises(api.RequestError):
            api.prepare_request({"messages": [{"role": "user", "content": "oi"}], "max_tokens": True})

    def test_last_role_must_be_user(self):
        with self.assertRaises(api.RequestError):
            api.prepare_request({"messages": [{"role": "assistant", "content": "oi"}]})

    def test_excessive_message_is_rejected(self):
        with self.assertRaises(api.RequestError):
            api.prepare_request({"messages": [{"role": "user", "content": "a" * 4001}]})


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = api.LocalHTTPServer(("127.0.0.1", 0), api.build_handler(FakeModel()))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            data = None if payload is None else json.dumps(payload).encode()
            client.request(method, path, body=data, headers={"Content-Type": "application/json"})
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def test_health(self):
        status, result = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(result["local"])

    def test_models(self):
        status, result = self.request("GET", "/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(result["data"][0]["owned_by"], "openai")

    def test_completion(self):
        status, result = self.request("POST", "/v1/chat/completions", {
            "messages": [{"role": "user", "content": "Olá"}], "max_tokens": 16
        })
        self.assertEqual(status, 200)
        self.assertEqual(result["choices"][0]["message"]["content"], "Resposta de teste")
        self.assertEqual(result["usage"]["completion_tokens"], 4)

    def test_rejects_bad_json(self):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            client.request("POST", "/v1/chat/completions", body="invalid", headers={"Content-Type": "application/json"})
            result = client.getresponse()
            self.assertEqual(result.status, 400)
            result.read()
        finally:
            client.close()

    def test_rejects_unknown_path(self):
        status, _ = self.request("GET", "/unknown")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
