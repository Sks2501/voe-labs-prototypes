"""Persistência SQLite local, transacional e com conexões independentes."""
from __future__ import annotations
import sqlite3
import json
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .settings import DB_PATH, MAX_TEXT_LENGTH

MEMORY_LIMIT = 100
TASK_LIMIT = 200
EXPORT_MAX_BYTES = 5 * 1024 * 1024
EXPORT_MAX_ROWS = 10000
PROFILE_FIELDS = {"preferred_name": 80, "about_me": 480, "goals": 400, "response_style": 160}


def thread_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Conversa inválida.")
    return value

class CapacityError(RuntimeError):
    """Explicit capacity protects RAM and keeps records visible in the default UI."""
    pass

class ExportTooLarge(RuntimeError):
    pass

def cleaned(value: str, limit: int = MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str):
        raise ValueError("O valor precisa ser texto.")
    result = value.strip()
    if not result or len(result) > limit or "\x00" in result:
        raise ValueError(f"O texto deve ter entre 1 e {limit} caracteres.")
    return result

def identifier(value) -> int:
    if isinstance(value, bool):
        raise ValueError("Identificador inválido.")
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Identificador inválido.") from None
    if str(result) != str(value) or not 0 < result < 2**63:
        raise ValueError("Identificador inválido.")
    return result

class Storage:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._check_schema_version()
        with self._connect() as db:
            db.executescript("""
                BEGIN IMMEDIATE;
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
                CREATE TABLE IF NOT EXISTS preferences (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metadata (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  token_hash TEXT NOT NULL UNIQUE,
                  role TEXT NOT NULL CHECK(role IN ('user','admin')),
                  created_at TEXT NOT NULL, expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
                INSERT INTO metadata(key,value) VALUES ('schema_version','2')
                  ON CONFLICT(key) DO UPDATE SET value=excluded.value;
                COMMIT;
            """)

    def _check_schema_version(self) -> None:
        # Refuse newer or corrupt versions before changing even journal settings.
        if not self.path.exists():
            return
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone():
                row = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
                if row is not None:
                    version = int(row[0])
                    if version < 1 or version > 2:
                        raise ValueError("Versão do banco não suportada; preserve os dados e use a versão correspondente do aplicativo.")
        finally:
            db.close()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA cache_size=-2048")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_message(self, role: str, text: str) -> int:
        if role not in ("user", "assistant"):
            raise ValueError("Papel inválido.")
        text = cleaned(text, 6000)
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO messages (role,content,created_at) VALUES (?,?,?)",
                (role, text, datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def history(self, limit: int = 8, before: int | None = None) -> list[dict]:
        limit = max(1, min(100, int(limit)))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,role,content,created_at FROM messages " +
                ("WHERE id<? " if before is not None else "") + "ORDER BY id DESC LIMIT ?",
                (identifier(before), limit) if before is not None else (limit,)).fetchall()
            result = [dict(row) for row in reversed(rows)]
            self._attach_message_metadata(db, result)
        return result

    @staticmethod
    def _attach_message_metadata(db, messages):
        for offset in range(0, len(messages), 250):
            batch = messages[offset:offset + 250]
            keys = [prefix + str(item["id"]) for item in batch for prefix in ("message-source:", "message-thread:")]
            if not keys:
                continue
            rows = db.execute("SELECT key,value FROM metadata WHERE key IN (" + ",".join("?" for _ in keys) + ")", keys)
            metadata = {}
            for row in rows:
                try:
                    if row["key"].startswith("message-thread:"):
                        metadata[row["key"]] = thread_identifier(row["value"])
                        continue
                    value = json.loads(row["value"])
                    if value.get("source") in ("gpt2", "local_model", "tool"):
                        metadata[row["key"]] = value
                except (ValueError, TypeError, AttributeError):
                    pass
            for item in batch:
                thread_id = metadata.get("message-thread:" + str(item["id"]))
                if thread_id:
                    item["thread_id"] = thread_id
                value = metadata.get("message-source:" + str(item["id"]))
                if value and item["role"] == "assistant":
                    item["source"] = value["source"]
                    if isinstance(value.get("model"), str):
                        item["model"] = value["model"][:120]

    def add_memory(self, text: str) -> int:
        text = cleaned(text, 480)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM memories").fetchone()[0] >= MEMORY_LIMIT:
                raise CapacityError("Limite de 100 memórias atingido. Exporte ou exclua uma memória antes de adicionar outra.")
            cur = db.execute(
                "INSERT INTO memories(content,created_at) VALUES (?,?)",
                (text, datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def memories(self, limit: int = 100, before: int | None = None) -> list[dict]:
        limit = max(1, min(100, int(limit)))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,content,created_at FROM memories " +
                ("WHERE id<? " if before is not None else "") + "ORDER BY id DESC LIMIT ?",
                (identifier(before), limit) if before is not None else (limit,)).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, item_id: int) -> bool:
        with self._connect() as db:
            cur = db.execute("DELETE FROM memories WHERE id=?", (identifier(item_id),))
            return cur.rowcount > 0

    def add_task(self, text: str) -> int:
        text = cleaned(text, 480)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM tasks").fetchone()[0] >= TASK_LIMIT:
                raise CapacityError("Limite de 200 tarefas atingido. Exporte ou exclua uma tarefa antes de adicionar outra.")
            cur = db.execute(
                "INSERT INTO tasks(content,created_at) VALUES (?,?)",
                (text, datetime.now(timezone.utc).isoformat()))
            return int(cur.lastrowid)

    def tasks(self, limit: int = 200, before: int | None = None) -> list[dict]:
        limit = max(1, min(200, int(limit)))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,content,completed,created_at FROM tasks " +
                ("WHERE id<? " if before is not None else "") + "ORDER BY id DESC LIMIT ?",
                (identifier(before), limit) if before is not None else (limit,)).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict:
        with self._connect() as db:
            return {name: db.execute("SELECT count(*) FROM " + name).fetchone()[0]
                    for name in ("messages", "memories", "tasks")}

    def toggle_task(self, item_id: int) -> bool:
        with self._connect() as db:
            cur = db.execute(
                "UPDATE tasks SET completed=1-completed WHERE id=?", (identifier(item_id),))
            return cur.rowcount > 0

    def create_thread(self, title="Nova conversa"):
        title = cleaned(title, 80)
        now = datetime.now(timezone.utc).isoformat()
        item = {"id": uuid.uuid4().hex, "title": title, "created_at": now, "updated_at": now}
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM metadata WHERE key GLOB 'conversation:*'").fetchone()[0] >= 100:
                raise CapacityError("Limite de 100 conversas. Exporte e exclua uma conversa para continuar.")
            db.execute("INSERT INTO metadata(key,value) VALUES (?,?)", ("conversation:" + item["id"], json.dumps(item)))
        return item

    def threads(self):
        with self._connect() as db:
            items = [json.loads(row[0]) for row in db.execute("SELECT value FROM metadata WHERE key GLOB 'conversation:*' LIMIT 100")]
        return sorted(items, key=lambda item: item["updated_at"], reverse=True)

    def thread(self, item_id):
        with self._connect() as db:
            row = db.execute("SELECT value FROM metadata WHERE key=?", ("conversation:" + thread_identifier(item_id),)).fetchone()
        if not row:
            raise ValueError("Conversa não encontrada.")
        return json.loads(row[0])

    def thread_history(self, item_id, limit=100, before=None):
        item_id = thread_identifier(item_id)
        self.thread(item_id)
        limit = max(1, min(100, int(limit)))
        with self._connect() as db:
            rows = db.execute("SELECT m.id,m.role,m.content,m.created_at FROM metadata t JOIN messages m "
                "ON t.key='message-thread:'||m.id WHERE t.value=? " + ("AND m.id<? " if before is not None else "") +
                "ORDER BY m.id DESC LIMIT ?", (item_id, identifier(before), limit) if before is not None else (item_id, limit)).fetchall()
            result = [dict(row) for row in reversed(rows)]
            self._attach_message_metadata(db, result)
        return result

    def rename_thread(self, item_id, title):
        item_id, title = thread_identifier(item_id), cleaned(title, 80)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM metadata WHERE key=?", ("conversation:" + item_id,)).fetchone()
            if not row:
                raise ValueError("Conversa não encontrada.")
            item = json.loads(row[0]); item["title"] = title
            db.execute("UPDATE metadata SET value=? WHERE key=?", (json.dumps(item), "conversation:" + item_id))
        return item

    def delete_thread(self, item_id):
        item_id = thread_identifier(item_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT m.id FROM messages m JOIN metadata t ON t.key='message-thread:'||m.id WHERE t.value=?", (item_id,)).fetchall()
            for row in rows:
                db.execute("DELETE FROM messages WHERE id=?", (row[0],))
                db.execute("DELETE FROM metadata WHERE key IN (?,?)", ("message-source:" + str(row[0]), "message-thread:" + str(row[0])))
            return db.execute("DELETE FROM metadata WHERE key=?", ("conversation:" + item_id,)).rowcount > 0

    def save_exchange(self, message: str, reply: str, *, source=None, model=None, thread_id=None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [("user", cleaned(message, 1600), now), ("assistant", cleaned(reply, 6000), now)]
        if source is not None and source not in ("gpt2", "local_model", "tool"):
            raise ValueError("Fonte de resposta inválida.")
        if model is not None:
            model = cleaned(model, 120)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            conversation = None
            if thread_id is not None:
                thread_id = thread_identifier(thread_id)
                row = db.execute("SELECT value FROM metadata WHERE key=?", ("conversation:" + thread_id,)).fetchone()
                if not row:
                    raise ValueError("Conversa não encontrada.")
                conversation = json.loads(row[0])
            user = db.execute("INSERT INTO messages(role,content,created_at) VALUES (?,?,?)", rows[0])
            cursor = db.execute("INSERT INTO messages(role,content,created_at) VALUES (?,?,?)", rows[1])
            if source is not None:
                db.execute("INSERT INTO metadata(key,value) VALUES (?,?)",
                           ("message-source:" + str(cursor.lastrowid), json.dumps({"source": source, "model": model})))
            if conversation:
                db.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", [("message-thread:" + str(i), thread_id) for i in (user.lastrowid, cursor.lastrowid)])
                conversation["updated_at"] = now
                db.execute("UPDATE metadata SET value=? WHERE key=?", (json.dumps(conversation), "conversation:" + thread_id))

    def delete_history(self) -> int:
        with self._connect() as db:
            count = db.execute("DELETE FROM messages").rowcount
            db.execute("DELETE FROM metadata WHERE key LIKE 'message-source:%'")
            db.execute("DELETE FROM metadata WHERE key GLOB 'message-thread:*' OR key GLOB 'conversation:*'")
            return count

    def update_memory(self, item_id: int, content: str) -> bool:
        with self._connect() as db:
            return db.execute("UPDATE memories SET content=? WHERE id=?",
                              (cleaned(content, 480), identifier(item_id))).rowcount > 0

    def update_task(self, item_id: int, *, content=None, completed=None) -> bool:
        if content is None and completed is None:
            raise ValueError("Informe content ou completed.")
        fields, args = [], []
        if content is not None:
            fields.append("content=?")
            args.append(cleaned(content, 480))
        if completed is not None:
            if not isinstance(completed, bool):
                raise ValueError("completed deve ser booleano.")
            fields.append("completed=?")
            args.append(int(completed))
        args.append(identifier(item_id))
        with self._connect() as db:
            return db.execute("UPDATE tasks SET " + ",".join(fields) + " WHERE id=?", args).rowcount > 0

    def delete_task(self, item_id: int) -> bool:
        with self._connect() as db:
            return db.execute("DELETE FROM tasks WHERE id=?", (identifier(item_id),)).rowcount > 0

    def preferences(self) -> dict:
        defaults = {"voice_enabled": False, "voice_rate": 1.0, "language": "pt-BR", **{key: "" for key in PROFILE_FIELDS}}
        with self._connect() as db:
            for row in db.execute("SELECT key,value FROM preferences"):
                defaults[row["key"]] = json.loads(row["value"])
        return defaults

    def set_preferences(self, values: dict) -> dict:
        if not isinstance(values, dict) or not values or set(values) - ({"voice_enabled", "voice_rate", "language"} | PROFILE_FIELDS.keys()):
            raise ValueError("Preferências desconhecidas ou vazias.")
        if "voice_enabled" in values and not isinstance(values["voice_enabled"], bool):
            raise ValueError("voice_enabled deve ser booleano.")
        rate = values.get("voice_rate", 1.0)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0.5 <= rate <= 2.0:
            raise ValueError("voice_rate deve estar entre 0.5 e 2.0.")
        if values.get("language", "pt-BR") != "pt-BR":
            raise ValueError("Idioma suportado: pt-BR.")
        values = dict(values)
        for key, limit in PROFILE_FIELDS.items():
            if key in values:
                value = values[key]
                if not isinstance(value, str) or len(value) > limit or "\x00" in value:
                    raise ValueError(f"{key} precisa ser texto com até {limit} caracteres.")
                values[key] = value.strip()
        with self._connect() as db:
            db.executemany("INSERT INTO preferences(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           [(k, json.dumps(v)) for k, v in values.items()])
        return self.preferences()

    def create_session(self, token_hash: str, role: str, expires_at: float, now: float) -> int:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 100:
                raise ValueError("Limite de sessões atingido; revogue uma sessão.")
            cur = db.execute("INSERT INTO sessions(token_hash,role,created_at,expires_at) VALUES (?,?,?,?)",
                             (token_hash, role, datetime.now(timezone.utc).isoformat(), expires_at))
            return int(cur.lastrowid)

    def find_session(self, token_hash: str, now: float) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT id,role,expires_at FROM sessions WHERE token_hash=? AND expires_at>?",
                             (token_hash, now)).fetchone()
        return dict(row) if row else None

    def sessions(self, now: float) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT id,role,created_at,expires_at FROM sessions WHERE expires_at>? ORDER BY id DESC LIMIT 100",
                              (now,)).fetchall()
        return [dict(row) for row in rows]

    def revoke_session(self, *, token_hash=None, item_id=None) -> bool:
        with self._connect() as db:
            if token_hash:
                return db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,)).rowcount > 0
            return db.execute("DELETE FROM sessions WHERE id=?", (identifier(item_id),)).rowcount > 0

    def export(self) -> dict:
        result = {"schema_version": 2, "exported_at": datetime.now(timezone.utc).isoformat()}
        with self._connect() as db:
            # Estimate before materializing rows, in the same SQLite snapshot.
            # JSON can expand one control byte into six bytes; allow that worst case
            # plus generous object/key/integer overhead for each row.
            db.execute("BEGIN")
            estimated = 512
            meta_size = db.execute("SELECT coalesce(sum(length(CAST(value AS BLOB))+128),0) FROM metadata WHERE key GLOB 'message-source:*' OR key GLOB 'conversation:*'").fetchone()[0]
            estimated += meta_size * 6
            for name in ("messages", "memories", "tasks"):
                text_columns = ("content", "created_at", "role") if name == "messages" else ("content", "created_at")
                lengths = "+".join("length(CAST(" + column + " AS BLOB))" for column in text_columns)
                count, size = db.execute("SELECT count(*),coalesce(sum(" + lengths + "),0) FROM " + name).fetchone()
                if count > EXPORT_MAX_ROWS:
                    raise ExportTooLarge("Exportação excede 10.000 registros por tabela. Use backup administrativo.")
                estimated += size * 6 + count * 256
            pref_count, pref_size = db.execute("SELECT count(*),coalesce(sum(length(CAST(key AS BLOB))+length(CAST(value AS BLOB))),0) FROM preferences").fetchone()
            estimated += pref_size * 6 + pref_count * 128
            if estimated > EXPORT_MAX_BYTES:
                raise ExportTooLarge("Exportação JSON excede o limite conservador de 5 MiB. Use backup administrativo.")
            for name in ("messages", "memories", "tasks"):
                columns = {"messages": "id,role,content,created_at", "memories": "id,content,created_at",
                           "tasks": "id,content,completed,created_at"}[name]
                result[name] = [dict(row) for row in db.execute("SELECT " + columns + " FROM " + name + " ORDER BY id")]
                if name == "messages":
                    self._attach_message_metadata(db, result[name])
            preferences = {"voice_enabled": False, "voice_rate": 1.0, "language": "pt-BR"}
            for row in db.execute("SELECT key,value FROM preferences"):
                preferences[row["key"]] = json.loads(row["value"])
            result["preferences"] = preferences
            result["threads"] = [json.loads(row[0]) for row in db.execute("SELECT value FROM metadata WHERE key GLOB 'conversation:*' LIMIT 100")]
        return result

    def integrity(self) -> str:
        with self._connect() as db:
            return db.execute("PRAGMA integrity_check").fetchone()[0]

    def backup(self, destination: Path) -> Path:
        destination = Path(destination)
        if destination.exists() or destination.resolve() == self.path.resolve():
            raise ValueError("O destino do backup já existe.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source:
            target = sqlite3.connect(str(destination))
            try:
                source.backup(target, pages=128)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Falha de integridade no backup.")
            finally:
                target.close()
        return destination
