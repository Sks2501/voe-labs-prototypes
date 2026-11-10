"""Persistência SQLite local, transacional e com conexões independentes."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .settings import DB_PATH, MAX_TEXT_LENGTH

def cleaned(value: str, limit: int = MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str):
        raise ValueError("O valor precisa ser texto.")
    result = value.strip()
    if not result or len(result) > limit:
        raise ValueError(f"O texto deve ter entre 1 e {limit} caracteres.")
    return result

class Storage:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                  content TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  content TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  content TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def save_message(self, role: str, text: str) -> int:
        if role not in ("user", "assistant"):
            raise ValueError("Papel inválido.")
        text = cleaned(text, 6000)
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO messages (role,content,created_at) VALUES (?,?,?)",
                (role, text, datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def history(self, limit: int = 8) -> list[dict]:
        limit = max(1, min(30, int(limit)))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,role,content,created_at FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_memory(self, text: str) -> int:
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO memories(content,created_at) VALUES (?,?)",
                (cleaned(text, 480), datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def memories(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,content,created_at FROM memories ORDER BY id DESC LIMIT 100"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, item_id: int) -> bool:
        with self._connect() as db:
            cur = db.execute("DELETE FROM memories WHERE id=?", (int(item_id),))
            return cur.rowcount > 0

    def add_task(self, text: str) -> int:
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO tasks(content,created_at) VALUES (?,?)",
                (cleaned(text, 480), datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def tasks(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,content,completed,created_at FROM tasks ORDER BY completed,id DESC LIMIT 200"
            ).fetchall()
        return [dict(row) for row in rows]

    def toggle_task(self, item_id: int) -> bool:
        with self._connect() as db:
            cur = db.execute(
                "UPDATE tasks SET completed=1-completed WHERE id=?", (int(item_id),))
            return cur.rowcount > 0
