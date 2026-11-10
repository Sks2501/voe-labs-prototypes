"""Credenciais nunca entram em URLs, cookies, logs ou no banco em texto claro."""
from __future__ import annotations
import hashlib
import hmac
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from .settings import RATE_LIMIT_REQUESTS, RATE_LIMIT_SECONDS, SESSION_TTL_SECONDS


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    role: str
    token_hash: str
    session_id: int | None = None


class Authentication:
    def __init__(self, storage, admin_token: str, user_token: str | None = None):
        if not isinstance(admin_token, str) or not 24 <= len(admin_token) <= 256:
            raise ValueError("O token administrativo deve ter entre 24 e 256 caracteres.")
        if any(ord(char) < 33 or ord(char) > 126 for char in admin_token):
            raise ValueError("O token deve conter somente caracteres ASCII sem espaços.")
        self.storage = storage
        self._admin_hash = digest(admin_token)
        if user_token and (len(user_token) < 24 or user_token == admin_token):
            raise ValueError("Token de usuário inválido.")
        self._user_hash = digest(user_token) if user_token else None

    def authenticate(self, token: str) -> Principal | None:
        if not isinstance(token, str) or not 1 <= len(token) <= 256:
            return None
        offered = digest(token)
        if hmac.compare_digest(offered, self._admin_hash):
            return Principal("admin", offered)
        if self._user_hash and hmac.compare_digest(offered, self._user_hash):
            return Principal("user", offered)
        found = self.storage.find_session(offered, time.time())
        return Principal(found["role"], offered, found["id"]) if found else None

    def create_session(self, principal: Principal, role: str = "user") -> dict:
        if role not in ("user", "admin"):
            raise ValueError("Papel inválido.")
        if role == "admin" and principal.role != "admin":
            raise PermissionError("Apenas administradores podem criar sessões administrativas.")
        token = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + SESSION_TTL_SECONDS
        session_id = self.storage.create_session(digest(token), role, expires_at, now)
        return {"id": session_id, "token": token, "role": role, "expires_at": expires_at}


class RateLimiter:
    """Fixed windows with an upper bound on tracked clients; never an unbounded map."""
    def __init__(self, limit=RATE_LIMIT_REQUESTS, period=RATE_LIMIT_SECONDS, capacity=1024):
        self.limit, self.period, self.capacity = limit, period, capacity
        self._clients = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            started, count = self._clients.pop(key, (now, 0))
            if now - started >= self.period:
                started, count = now, 0
            accepted = count < self.limit
            self._clients[key] = (started, count + 1)
            while len(self._clients) > self.capacity:
                self._clients.popitem(last=False)
            return accepted
