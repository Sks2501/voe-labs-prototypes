"""Servidor HTTP de uso local, sem frameworks, sem telemetria e sem execução de shell."""
from __future__ import annotations
import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .brain import generate_reply
from .settings import DEFAULT_MODEL
from .storage import Storage, cleaned

WEB_DIR = Path(__file__).parent / "web"

class AssistantServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, token: str, model_size: str, storage: Storage):
        super().__init__(address, AssistantHandler)
        self.token = token
        self.model_size = model_size
        self.storage = storage

class AssistantHandler(BaseHTTPRequestHandler):
    server: AssistantServer
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self';"
            " img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        offered = self.headers.get("X-Session-Token", "")
        return bool(offered) and hmac.compare_digest(offered, self.server.token)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlsplit(origin)
        return parsed.scheme in ("http", "https") and parsed.netloc == self.headers.get("Host", "")

    def do_GET(self) -> None:
        pathname = urlsplit(self.path).path
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8")
        }
        if pathname in assets:
            filename, kind = assets[pathname]
            try:
                self._send(200, (WEB_DIR / filename).read_bytes(), kind)
            except OSError:
                self._json(500, {"error": "Interface não encontrada."})
            return
        if pathname == "/api/health":
            self._json(200, {"ok": True, "model": self.server.model_size, "local": True})
            return
        if pathname == "/api/state":
            if not self._authorized():
                self._json(401, {"error": "Token inválido."})
                return
            self._json(200, {
                "history": self.server.storage.history(12),
                "memories": self.server.storage.memories(),
                "tasks": self.server.storage.tasks()
            })
            return
        self._json(404, {"error": "Rota inexistente."})

    def do_POST(self) -> None:
        if not self._same_origin():
            self._json(403, {"error": "Origem não autorizada."})
            return
        if not self._authorized():
            self._json(401, {"error": "Token inválido."})
            return
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            self._json(415, {"error": "Conteúdo deve ser JSON."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Comprimento inválido."})
            return
        if not 0 < length <= 8192:
            self.close_connection = True
            self._json(413, {"error": "Requisição muito grande."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Objeto JSON necessário.")
            path = urlsplit(self.path).path
            if path == "/api/chat":
                message = cleaned(payload.get("message"), 1600)
                history = self.server.storage.history(8)
                memories = self.server.storage.memories()
                reply = generate_reply(message, history, memories, self.server.model_size)
                self.server.storage.save_message("user", message)
                self.server.storage.save_message("assistant", reply)
                self._json(200, {"reply": reply})
            elif path == "/api/memory":
                item_id = self.server.storage.add_memory(payload.get("content"))
                self._json(201, {"id": item_id})
            elif path == "/api/memory/delete":
                self._json(200, {"deleted": self.server.storage.delete_memory(int(payload["id"]))})
            elif path == "/api/task":
                item_id = self.server.storage.add_task(payload.get("content"))
                self._json(201, {"id": item_id})
            elif path == "/api/task/toggle":
                self._json(200, {"updated": self.server.storage.toggle_task(int(payload["id"]))})
            else:
                self._json(404, {"error": "Rota inexistente."})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self.log_error("Internal error while handling %s", self.path)
            self._json(503, {
                "error": "Não consegui executar o modelo. Verifique a instalação, o download e a memória disponível."
            })

def serve(host: str = "127.0.0.1", port: int = 8765, token: str | None = None,
          model_size: str = DEFAULT_MODEL) -> None:
    if not (1024 <= port <= 65535):
        raise ValueError("A porta deve estar entre 1024 e 65535.")
    if host not in ("127.0.0.1", "localhost", "0.0.0.0"):
        raise ValueError("Host inválido.")
    if host == "0.0.0.0" and (not token or len(token) < 16):
        raise ValueError("O acesso por outros aparelhos exige token de pelo menos 16 caracteres.")
    access_token = token or secrets.token_urlsafe(24)
    with AssistantServer((host, port), access_token, model_size, Storage()) as server:
        print(f"SEXTA-FEIRA: http://127.0.0.1:{port}")
        print(f"Token de acesso (não publique): {access_token}")
        if host == "0.0.0.0":
            print("Modo LAN: utilize somente em uma rede privada confiável; HTTP não criptografa o tráfego.")
        try:
            server.serve_forever(poll_interval=0.4)
        except KeyboardInterrupt:
            print("\nSEXTA-FEIRA encerrada.")
