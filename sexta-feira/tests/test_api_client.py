"""Credential transport checks for the optional API-only client."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest

spec = importlib.util.spec_from_file_location("sexta_api_client", Path(__file__).resolve().parents[1] / "scripts" / "api_client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class APIClientTests(unittest.TestCase):
    def frame(self, **changes):
        result = {"token": "test-only-" + "x" * 32, "method": "GET", "path": "/api/v1/health", "body": None}
        result.update(changes)
        return result

    def test_refuses_cleartext_remote_origin_and_invalid_frames(self):
        with self.assertRaises(ValueError):
            client.call_http("http://example.invalid", self.frame())
        for changes in ({"path": "https://example.invalid"}, {"method": "CONNECT"},
                        {"path": "/api/v1/health\r\nX: invalid"}, {"token": "short"},
                        {"method": "POST", "body": {"message": "x" * 9000}}):
            with self.subTest(changes=tuple(changes)):
                with self.assertRaises(ValueError):
                    client.call_http("http://127.0.0.1:1", self.frame(**changes))

    def test_never_follows_redirect_with_credential(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                received.append(self.path)
                self.send_response(302)
                self.send_header("Location", "/credential-destination")
                self.end_headers()
                self.wfile.write(b"{}")
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                response = client.call_http(f"http://127.0.0.1:{server.server_port}", self.frame())
                self.assertEqual(response["status"], 302)
                self.assertEqual(received, ["/api/v1/health"])
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_utf8_json_and_authentication_reach_only_selected_api(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                received.append((self.path, self.headers.get("Authorization"),
                                 json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"reply": "Olá, ação verificada."}).encode())
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                frame = self.frame(method="POST", path="/api/v1/conversations", body={"message": "Olá, ação."})
                result = client.call_http(f"http://127.0.0.1:{server.server_port}", frame)
                self.assertEqual(result["body"]["reply"], "Olá, ação verificada.")
                self.assertEqual(received, [(frame["path"], "Bearer " + frame["token"], frame["body"])])
            finally:
                server.shutdown()
                thread.join(timeout=2)
