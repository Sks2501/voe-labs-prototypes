import json
import socket
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from sexta_feira.storage import Storage
from sexta_feira.server import AssistantServer, AssistantHandler

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.server = AssistantServer(
            ("127.0.0.1", 0), "token-de-acesso-para-teste", "small",
            Storage(Path(self.dir.name) / "db.sqlite3"))
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.dir.cleanup()

    def call(self, method, path, body=None, token=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if token:
            headers["X-Session-Token"] = token
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body)
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = json.loads(response.read())
        status = response.status
        conn.close()
        return status, payload

    def test_health_without_token(self):
        status, body = self.call("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["local"])

    def test_protect_state(self):
        status, _ = self.call("GET", "/api/state")
        self.assertEqual(status, 401)

    def test_authenticated_memory(self):
        token = "token-de-acesso-para-teste"
        status, _ = self.call("POST", "/api/memory", {"content": "Moro no Brasil"}, token)
        self.assertEqual(status, 201)
        status, state = self.call("GET", "/api/state", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(state["memories"][0]["content"], "Moro no Brasil")

    def test_reject_oversized_post(self):
        token = "token-de-acesso-para-teste"
        status, _ = self.call("POST", "/api/task", {"content": "x" * 10000}, token)
        self.assertEqual(status, 413)

if __name__ == "__main__":
    unittest.main()
