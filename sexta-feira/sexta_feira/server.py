"""API REST privada em loopback, sem telemetria nem execução de shell.

O proxy HTTPS deve ser configurado separadamente. Credenciais Bearer são
explícitas, não cookies: requisições cross-origin não recebem CORS e são negadas.
"""
from __future__ import annotations
import json
import hashlib
import logging
import os
import re
from pathlib import Path
import shutil
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from . import brain
from .settings import (DATA_DIR, DEFAULT_MODEL, MAX_HTTP_CONNECTIONS,
                       MAX_REQUEST_BYTES, MODELS, TOKEN_FILE)
from .security import Authentication, RateLimiter
from .storage import Storage, CapacityError, ExportTooLarge, cleaned, identifier
from .tools import execute_tool, execute_chat_command
from .observability import configure_logging, resource_snapshot, native_resource_snapshot

WEB_DIR = Path(__file__).parent / "web"
LOGGER = logging.getLogger("sexta_feira.http")


def read_access_token() -> str:
    token = os.environ.get("SEXTA_ACCESS_TOKEN")
    if not token:
        try:
            token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            raise ValueError("Credencial não configurada. Prepare o arquivo privado access.token com o instalador.") from None
    return token


def model_status() -> dict:
    status = getattr(brain, "engine_status", None)
    return status() if status else {"state": "not_initialized", "device": "cpu"}


class AssistantServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 8

    def __init__(self, address, token: str, model_size: str, storage: Storage, *,
                 public_origin: str | None = None, rate_limit: int = 60):
        if model_size not in MODELS:
            raise ValueError("Modelo inválido.")
        self.storage = storage
        self.auth = Authentication(storage, token, os.environ.get("SEXTA_USER_TOKEN"))
        self.model_size = model_size
        self._connections = threading.BoundedSemaphore(MAX_HTTP_CONNECTIONS)
        self.limiter = RateLimiter(limit=rate_limit)
        self._stats_lock = threading.Lock()
        self.backup_lock = threading.Lock()
        self.export_lock = threading.Lock()
        self.stats = {"requests": 0, "errors": 0, "duration_seconds": 0.0}
        self.started_at = time.monotonic()
        public_origin = public_origin or os.environ.get("SEXTA_PUBLIC_ORIGIN")
        self.public_origin = None
        if public_origin:
            parsed = urlsplit(public_origin)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                    parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
                raise ValueError("SEXTA_PUBLIC_ORIGIN deve ser uma origem HTTPS exata, sem caminho ou credenciais.")
            self.public_origin = "https://" + parsed.netloc.lower()
        super().__init__(address, AssistantHandler)
        port = self.server_address[1]
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.allowed_origins = {f"http://{host}" for host in self.allowed_hosts}
        if self.public_origin:
            self.allowed_origins.add(self.public_origin)
            self.allowed_hosts.add(urlsplit(self.public_origin).netloc)

    def process_request(self, request, client_address):
        if not self._connections.acquire(blocking=False):
            try:
                # Drain only bounded headers, otherwise Windows can reset the
                # connection on close before the client receives the 503.
                request.settimeout(0.2)
                headers = b""
                deadline = time.monotonic() + 0.2
                while b"\r\n\r\n" not in headers and len(headers) < 8192 and time.monotonic() < deadline:
                    chunk = request.recv(8192 - len(headers))
                    if not chunk:
                        break
                    headers += chunk
            except OSError:
                pass
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 5\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connections.release()

    def handle_error(self, request, client_address):
        LOGGER.error("http_worker_error")

    def metrics(self) -> dict:
        with self._stats_lock:
            result = dict(self.stats)
        result["uptime_seconds"] = round(time.monotonic() - self.started_at, 3)
        result["model"] = model_status()
        result.update(resource_snapshot(self.storage.path.parent))
        if result["model"].get("backend") == "llama.cpp":
            native = native_resource_snapshot(self.storage.path.parent)
            if native:
                result["api_process_rss_bytes"] = result.get("process_rss_bytes", 0)
                result["process_rss_bytes"] = result["api_process_rss_bytes"] + native["inference_process_rss_bytes"]
                result["process_cpu_seconds"] += native.get("inference_process_cpu_seconds", 0)
                own_cpu, model_cpu = result.get("process_cpu_percent"), native.get("inference_process_cpu_percent")
                result["process_cpu_percent"] = round(own_cpu + model_cpu, 2) if own_cpu is not None and model_cpu is not None else None
                result.update(native)
        return result


class HTTPError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class AssistantHandler(BaseHTTPRequestHandler):
    server: AssistantServer
    protocol_version = "HTTP/1.1"
    server_version = "SextaFeira"
    sys_version = ""

    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def log_message(self, format, *args):
        # Base implementation logs URLs, query strings and attacker-controlled text.
        pass

    def log_request(self, code="-", size="-"):
        LOGGER.info("http_response status=%s", code)

    def log_error(self, format, *args):
        LOGGER.warning("http_protocol_error")

    def _send(self, status: int, data: bytes, content_type: str, *, download_name=None) -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            self.send_header("Content-Disposition", 'attachment; filename="' + download_name + '"')
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                         "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if status in (429, 503):
            self.send_header("Retry-After", "5")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="SEXTA-FEIRA"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _android_release(self):
        """Public installer only. No token, database or arbitrary filesystem route."""
        directory = self.server.storage.path.parent / "android-release"
        try:
            with (directory / "android-release.json").open("rb") as stream:
                raw = stream.read(8193)
            if len(raw) > 8192 or directory.is_symlink():
                raise ValueError("Invalid release descriptor")
            release = json.loads(raw)
            filename = release["filename"]
            if not isinstance(filename, str) or not re.fullmatch(r"sexta-feira-android-\d+\.\d+\.\d+\.apk", filename):
                raise ValueError("Invalid APK name")
            if not re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}", release["version"]):
                raise ValueError("Invalid release version")
            if release["package"] != "online.teambike.sextafeira" or release["min_sdk"] != 26:
                raise ValueError("Unexpected Android application")
            if isinstance(release["bytes"], bool) or not isinstance(release["bytes"], int) or not 0 < release["bytes"] <= 10 * 1024**2:
                raise ValueError("APK exceeds release size limit")
            if not re.fullmatch(r"[a-f0-9]{64}", release["sha256"]) or not re.fullmatch(r"[a-f0-9]{64}", release["certificate_sha256"]):
                raise ValueError("Invalid release hash")
            path = (directory / filename).resolve()
            if not path.is_relative_to(directory.resolve()) or path.stat().st_size != release["bytes"]:
                raise ValueError("Release path/size mismatch")
            with path.open("rb") as stream:
                data = stream.read(10 * 1024**2 + 1)
            if len(data) != release["bytes"] or hashlib.sha256(data).hexdigest() != release["sha256"]:
                raise ValueError("APK integrity mismatch")
            return release, data
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPError(503, "android_not_ready", "O instalador Android ainda não está disponível.") from None

    def _json(self, code: int, obj: dict | list) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _payload(self) -> dict:
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
            raise HTTPError(400, "invalid_length", "Informe um Content-Length único; streaming não é aceito.")
        try:
            length = int(self.headers["Content-Length"])
        except (ValueError, TypeError):
            raise HTTPError(400, "invalid_length", "Comprimento inválido.") from None
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise HTTPError(413, "request_too_large", "O corpo deve ter entre 1 e 8192 bytes.")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPError(415, "json_required", "Conteúdo deve ser JSON.")
        def invalid_constant(_):
            raise ValueError("Número JSON inválido.")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise HTTPError(400, "incomplete_body", "Corpo incompleto.")
        data = json.loads(raw, parse_constant=invalid_constant)
        if not isinstance(data, dict):
            raise ValueError("Objeto JSON necessário.")
        return data

    @staticmethod
    def _fields(payload: dict, allowed: set[str], required: set[str] = frozenset()):
        if set(payload) - allowed or required - set(payload):
            raise ValueError("Campos desconhecidos ou obrigatórios ausentes.")

    def _principal(self):
        authorization = self.headers.get("Authorization", "")
        offered = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not authorization:
            offered = self.headers.get("X-Session-Token", "")  # migration compatibility
        principal = self.server.auth.authenticate(offered)
        if principal is None:
            raise HTTPError(401, "unauthorized", "Credencial ausente, inválida ou expirada.")
        return principal

    @staticmethod
    def _admin(principal):
        if principal.role != "admin":
            raise HTTPError(403, "admin_required", "Operação exclusiva de administrador.")

    def _dispatch(self):
        started = time.monotonic()
        failed = False
        try:
            host = self.headers.get("Host", "").lower()
            if host not in self.server.allowed_hosts:
                raise HTTPError(421, "host_not_allowed", "Host não autorizado.")
            origin = self.headers.get("Origin")
            if origin and origin not in self.server.allowed_origins:
                raise HTTPError(403, "origin_not_allowed", "Origem não autorizada.")
            if not self.server.limiter.allow(self.client_address[0]):
                raise HTTPError(429, "rate_limited", "Limite de requisições atingido. Aguarde.")
            parsed = urlsplit(self.path)
            path = self._canonical_path(parsed.path)
            self.query = {}
            if parsed.fragment or (parsed.query and ((path not in ("/api/v1/history", "/api/v1/memories", "/api/v1/tasks") and not path.startswith("/api/v1/threads/")) or self.command != "GET")):
                raise HTTPError(400, "query_not_supported", "Parâmetros de consulta não são aceitos.")
            if parsed.query:
                self.query = parse_qs(parsed.query, strict_parsing=True)
                if set(self.query) - {"limit", "before"} or any(len(v) != 1 for v in self.query.values()):
                    raise ValueError("Parâmetros inválidos.")
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/android-icon.svg": ("android-icon.svg", "image/svg+xml")}
            if self.command in ("GET", "HEAD") and path in ("/android", "/android/release.json", "/downloads/sexta-feira-android.apk"):
                release, apk = self._android_release()
                if path == "/downloads/sexta-feira-android.apk":
                    self._send(200, apk, "application/vnd.android.package-archive", download_name=release["filename"])
                elif path == "/android/release.json":
                    self._json(200, {key: release[key] for key in ("version", "package", "bytes", "min_sdk", "sha256", "certificate_sha256")})
                else:
                    html = (WEB_DIR / "android.html").read_text(encoding="utf-8")
                    for key, value in {"VERSION": release["version"], "SIZE": str(round(len(apk) / 1024)),
                                       "SHA256": release["sha256"], "CERTIFICATE": release["certificate_sha256"]}.items():
                        html = html.replace("{{" + key + "}}", value)
                    self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if self.command == "GET" and path in assets:
                filename, kind = assets[path]
                self._send(200, (WEB_DIR / filename).read_bytes(), kind)
                return
            principal = self._principal()
            if self.command == "GET":
                self._get(path, principal)
            elif self.command in ("POST", "PATCH"):
                self._write(path, self._payload(), principal)
            elif self.command == "DELETE":
                self._delete(path, principal)
            else:
                raise HTTPError(405, "method_not_allowed", "Método não permitido.")
        except HTTPError as exc:
            failed = True
            self._json(exc.status, {"error": exc.message, "code": exc.code})
        except CapacityError as exc:
            failed = True
            self._json(409, {"error": str(exc), "code": "capacity_reached"})
        except ExportTooLarge as exc:
            failed = True
            self._json(413, {"error": str(exc), "code": "export_too_large"})
        except (ValueError, TypeError, KeyError, UnicodeError):
            failed = True
            self._json(400, {"error": "Parâmetros inválidos. Consulte o esquema da API.", "code": "validation_error"})
        except PermissionError:
            failed = True
            self._json(403, {"error": "Operação não autorizada.", "code": "forbidden"})
        except (BrokenPipeError, ConnectionResetError, TimeoutError, socket.timeout):
            failed = True
        except Exception as exc:
            failed = True
            name = type(exc).__name__
            if name == "InferenceBusy":
                self._json(429, {"error": "Fila de inferência cheia.", "code": "inference_busy"})
            elif name == "InferenceTimeout":
                self._json(504, {"error": "Tempo limite de inferência atingido.", "code": "inference_timeout"})
            elif name == "InferenceUnavailable":
                self._json(503, {"error": "Modelo local indisponível. Verifique o diagnóstico administrativo.", "code": "model_unavailable"})
            else:
                LOGGER.error("request_failure type=%s", name)
                self._json(503, {"error": "Operação indisponível; consulte o diagnóstico administrativo.", "code": "unavailable"})
        finally:
            with self.server._stats_lock:
                self.server.stats["requests"] += 1
                self.server.stats["errors"] += int(failed)
                self.server.stats["duration_seconds"] += time.monotonic() - started

    @staticmethod
    def _canonical_path(path: str) -> str:
        aliases = {"/api/chat": "/api/v1/conversations", "/api/memory": "/api/v1/memories",
                   "/api/task": "/api/v1/tasks"}
        if path in aliases:
            return aliases[path]
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            return "/api/v1/" + path[5:]
        return path

    def _get(self, path, principal):
        db = self.server.storage
        if path == "/api/v1/health":
            self._json(200, {"ok": True, "local": True})
        elif path == "/api/v1/state":
            self._json(200, {"history": db.history(30), "memories": db.memories(),
                             "tasks": db.tasks(), "preferences": db.preferences(),
                             "model": model_status(), "role": principal.role, "counts": db.counts(), "threads": db.threads(),
                             "limits": {"memories": 100, "tasks": 200}})
        elif path == "/api/v1/model":
            self._json(200, model_status())
        elif path == "/api/v1/threads":
            self._json(200, {"threads": db.threads()})
        elif path.startswith("/api/v1/threads/"):
            item_id = path.rsplit("/", 1)[1]
            limit, before = self._paging(100)
            self._json(200, {"thread": db.thread(item_id), "history": db.thread_history(item_id, limit, before)})
        elif path == "/api/v1/history":
            limit = identifier(self.query.get("limit", ["30"])[0])
            if limit > 100:
                raise ValueError("Limite máximo: 100.")
            before = identifier(self.query["before"][0]) if "before" in self.query else None
            self._json(200, {"history": db.history(limit, before)})
        elif path == "/api/v1/memories":
            limit, before = self._paging(100)
            self._json(200, {"memories": db.memories(limit, before), "total": db.counts()["memories"]})
        elif path == "/api/v1/tasks":
            limit, before = self._paging(200)
            self._json(200, {"tasks": db.tasks(limit, before), "total": db.counts()["tasks"]})
        elif path == "/api/v1/preferences":
            self._json(200, db.preferences())
        elif path == "/api/v1/export":
            if not self.server.export_lock.acquire(blocking=False):
                raise HTTPError(429, "export_busy", "Uma exportação já está em andamento. Aguarde.")
            try:
                self._json(200, db.export())
            finally:
                self.server.export_lock.release()
        elif path == "/api/v1/metrics":
            self._admin(principal)
            self._json(200, self.server.metrics())
        elif path == "/api/v1/sessions":
            self._admin(principal)
            self._json(200, {"sessions": db.sessions(time.time())})
        elif path == "/api/v1/admin/integrity":
            self._admin(principal)
            self._json(200, {"integrity": db.integrity()})
        elif path == "/api/v1/openapi.json":
            self._json(200, openapi_document())
        else:
            raise HTTPError(404, "not_found", "Rota inexistente.")

    def _write(self, path, data, principal):
        db = self.server.storage
        if path == "/api/v1/sessions" and self.command == "POST":
            self._fields(data, {"role"})
            self._json(201, self.server.auth.create_session(principal, data.get("role", "user")))
        elif path == "/api/v1/threads" and self.command == "POST":
            self._fields(data, {"title"})
            self._json(201, db.create_thread(data.get("title", "Nova conversa")))
        elif path.startswith("/api/v1/threads/") and self.command == "PATCH":
            self._fields(data, {"title"}, {"title"})
            self._json(200, db.rename_thread(path.rsplit("/", 1)[1], data["title"]))
        elif path in ("/api/v1/conversations", "/api/v1/chat") and self.command == "POST":
            self._fields(data, {"message", "context_after", "thread_id"}, {"message"})
            message = cleaned(data["message"], 1600)
            context_after = identifier(data["context_after"]) if "context_after" in data else None
            thread_id = data.get("thread_id")
            if "thread_id" in data:
                db.thread(thread_id)
            result = execute_chat_command(message, db)
            if result is None:
                history = db.thread_history(thread_id, 8) if thread_id is not None else db.history(8)
                if context_after is not None:
                    history = [item for item in history if item["id"] > context_after]
                reply = brain.generate_reply(message, history, db.memories(), self.server.model_size, preferences=db.preferences())
                result = {"reply": reply, "source": brain.generated_source(), "generated": True,
                          "action_executed": False, "model": model_status().get("model")}
            db.save_exchange(message, result["reply"], source=result.get("source"), model=result.get("model"), thread_id=thread_id)
            if thread_id:
                result["thread_id"] = thread_id
            self._json(200, result)
        elif path == "/api/v1/memories" and self.command == "POST":
            self._fields(data, {"content"}, {"content"})
            self._json(201, {"id": db.add_memory(data["content"])})
        elif path == "/api/v1/tasks" and self.command == "POST":
            self._fields(data, {"content"}, {"content"})
            self._json(201, {"id": db.add_task(data["content"])})
        elif path.startswith("/api/v1/memories/") and self.command == "PATCH":
            self._fields(data, {"content"}, {"content"})
            self._updated(db.update_memory(identifier(path.rsplit("/", 1)[1]), data["content"]))
        elif path.startswith("/api/v1/tasks/") and self.command == "PATCH":
            self._fields(data, {"content", "completed"})
            self._updated(db.update_task(identifier(path.rsplit("/", 1)[1]), **data))
        elif path == "/api/v1/preferences" and self.command == "PATCH":
            self._json(200, db.set_preferences(data))
        elif path == "/api/v1/tools" and self.command == "POST":
            self._fields(data, {"name", "parameters"}, {"name", "parameters"})
            self._json(200, execute_tool(data["name"], data["parameters"], db))
        elif path == "/api/v1/admin/backup" and self.command == "POST":
            self._admin(principal)
            self._fields(data, set())
            with self.server.backup_lock:
                backups = db.path.parent / "backups"
                if backups.exists() and len(list(backups.glob("sexta-*.sqlite3"))) >= 10:
                    raise HTTPError(409, "backup_limit", "Limite de dez backups atingido. Arquive os antigos manualmente.")
                if shutil.disk_usage(db.path.parent).free < db.path.stat().st_size * 2 + 64 * 1024 * 1024:
                    raise HTTPError(507, "insufficient_storage", "Espaço insuficiente para backup seguro.")
                filename = f"sexta-{time.time_ns()}.sqlite3"
                db.backup(backups / filename)
            self._json(201, {"backup": filename, "integrity": "ok"})
        elif path == "/api/v1/memory/delete" and self.command == "POST":
            self._fields(data, {"id"}, {"id"})
            self._json(200, {"deleted": db.delete_memory(identifier(data["id"]))})
        elif path == "/api/v1/task/toggle" and self.command == "POST":
            self._fields(data, {"id"}, {"id"})
            self._json(200, {"updated": db.toggle_task(identifier(data["id"]))})
        else:
            raise HTTPError(404, "not_found", "Rota inexistente ou método inválido.")

    def _updated(self, changed):
        if not changed:
            raise HTTPError(404, "not_found", "Registro não encontrado.")
        self._json(200, {"updated": True})

    def _paging(self, maximum):
        limit = identifier(self.query.get("limit", [str(maximum)])[0])
        if limit > maximum:
            raise ValueError("Limite da página excedido.")
        before = identifier(self.query["before"][0]) if "before" in self.query else None
        return limit, before

    def _delete(self, path, principal):
        db = self.server.storage
        if path == "/api/v1/sessions/current":
            if principal.session_id is None:
                raise HTTPError(409, "bootstrap_token", "Credencial de instalação deve ser rotacionada no arquivo privado.")
            self._json(200, {"deleted": db.revoke_session(token_hash=principal.token_hash)})
        elif path.startswith("/api/v1/sessions/"):
            self._admin(principal)
            self._updated(db.revoke_session(item_id=identifier(path.rsplit("/", 1)[1])))
        elif path.startswith("/api/v1/memories/"):
            self._updated(db.delete_memory(identifier(path.rsplit("/", 1)[1])))
        elif path.startswith("/api/v1/tasks/"):
            self._updated(db.delete_task(identifier(path.rsplit("/", 1)[1])))
        elif path.startswith("/api/v1/threads/"):
            self._updated(db.delete_thread(path.rsplit("/", 1)[1]))
        elif path == "/api/v1/history":
            self._json(200, {"deleted": db.delete_history()})
        else:
            raise HTTPError(404, "not_found", "Rota inexistente.")

    do_GET = _dispatch
    do_HEAD = _dispatch
    do_POST = _dispatch
    do_PATCH = _dispatch
    do_DELETE = _dispatch
    do_OPTIONS = _dispatch
    do_PUT = _dispatch


def openapi_document() -> dict:
    """Self-contained OpenAPI; clients need no external CDN or remote documentation."""
    schemas = {
        "Message": {"type": "object", "required": ["message"], "additionalProperties": False,
                    "properties": {"message": {"type": "string", "minLength": 1, "maxLength": 1600},
                                   "context_after": {"type": "integer", "minimum": 1},
                                   "thread_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"}}},
        "Thread": {"type": "object", "additionalProperties": False,
                   "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 80}}},
        "ThreadUpdate": {"type": "object", "additionalProperties": False, "required": ["title"],
                         "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 80}}},
        "Content": {"type": "object", "required": ["content"], "additionalProperties": False,
                    "properties": {"content": {"type": "string", "minLength": 1, "maxLength": 480}}},
        "TaskUpdate": {"type": "object", "minProperties": 1, "additionalProperties": False,
                       "properties": {"content": {"type": "string", "minLength": 1, "maxLength": 480},
                                      "completed": {"type": "boolean"}}},
        "Session": {"type": "object", "additionalProperties": False,
                    "properties": {"role": {"type": "string", "enum": ["user", "admin"], "default": "user"}}},
        "Preferences": {"type": "object", "minProperties": 1, "additionalProperties": False,
                        "properties": {"voice_enabled": {"type": "boolean"},
                                       "voice_rate": {"type": "number", "minimum": 0.5, "maximum": 2},
                                       "language": {"type": "string", "enum": ["pt-BR"]},
                                       "preferred_name": {"type": "string", "maxLength": 80},
                                       "about_me": {"type": "string", "maxLength": 480},
                                       "goals": {"type": "string", "maxLength": 400},
                                       "response_style": {"type": "string", "maxLength": 160}}},
        "Tool": {"type": "object", "required": ["name", "parameters"], "additionalProperties": False,
                 "properties": {"name": {"type": "string", "enum": ["system_time", "list_tasks", "create_task", "list_memories", "save_memory"]},
                                "parameters": {"type": "object"}}},
        "Empty": {"type": "object", "additionalProperties": False},
        "Error": {"type": "object", "required": ["error", "code"],
                  "properties": {"error": {"type": "string"}, "code": {"type": "string"}}},
    }
    routes = {
        "/health": {"get": None}, "/state": {"get": None}, "/model": {"get": None},
        "/conversations": {"post": "Message"}, "/history": {"get": None, "delete": None},
        "/threads": {"get": None, "post": "Thread"},
        "/threads/{id}": {"get": None, "patch": "ThreadUpdate", "delete": None},
        "/memories": {"get": None, "post": "Content"},
        "/memories/{id}": {"patch": "Content", "delete": None},
        "/tasks": {"get": None, "post": "Content"},
        "/tasks/{id}": {"patch": "TaskUpdate", "delete": None},
        "/preferences": {"get": None, "patch": "Preferences"},
        "/sessions": {"get": None, "post": "Session"},
        "/sessions/current": {"delete": None}, "/sessions/{id}": {"delete": None},
        "/tools": {"post": "Tool"}, "/metrics": {"get": None}, "/export": {"get": None},
        "/admin/integrity": {"get": None}, "/admin/backup": {"post": "Empty"},
        "/openapi.json": {"get": None},
    }
    paths = {}
    for route, methods in routes.items():
        entry = {}
        for method, schema in methods.items():
            status = "201" if method == "post" and route in ("/sessions", "/threads", "/memories", "/tasks", "/admin/backup") else "200"
            operation = {"responses": {status: {"description": "Operação concluída"},
                                        "default": {"description": "Erro consistente", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}}}
            if schema:
                operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/" + schema}}}}
            if "{id}" in route:
                operation["parameters"] = [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}}]
                if route == "/threads/{id}":
                    operation["parameters"][0]["schema"] = {"type": "string", "pattern": "^[a-f0-9]{32}$"}
            if route in ("/history", "/memories", "/tasks", "/threads/{id}") and method == "get":
                operation.setdefault("parameters", []).extend([
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 200 if route == "/tasks" else 100}},
                    {"name": "before", "in": "query", "schema": {"type": "integer", "minimum": 1}}])
            if route.startswith("/admin/") or route == "/metrics" or (route == "/sessions" and method == "get") or route == "/sessions/{id}":
                operation["description"] = "Requer papel admin."
            entry[method] = operation
        paths[route] = entry
    return {"openapi": "3.1.0", "info": {"title": "SEXTA-FEIRA API privada", "version": "1.0.0",
            "description": "Assistente experimental local, um proprietário, sem cobrança de inferência. Bearer obrigatório; sessões expiram em 12 horas."},
            "servers": [{"url": "/api/v1"}], "security": [{"bearerAuth": []}],
            "paths": paths, "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}, "schemas": schemas}}


def serve(host: str = "127.0.0.1", port: int = 8765, token: str | None = None,
          model_size: str = DEFAULT_MODEL) -> None:
    if not 1024 <= port <= 65535:
        raise ValueError("A porta deve estar entre 1024 e 65535.")
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Este serviço privado deve escutar apenas em loopback. Use um túnel HTTPS autenticado.")
    configure_logging(DATA_DIR)
    with AssistantServer((host, port), token or read_access_token(), model_size, Storage()) as server:
        LOGGER.info("server_started model=%s device=cpu", model_size)
        print(f"SEXTA-FEIRA: http://127.0.0.1:{port} (autenticação obrigatória)")
        try:
            server.serve_forever(poll_interval=0.4)
        except KeyboardInterrupt:
            pass
        finally:
            shutdown = getattr(brain, "shutdown_engine", None)
            if shutdown:
                shutdown()
            LOGGER.info("server_stopped")
