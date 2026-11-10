import tempfile
import json
import unittest
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pathlib import Path
from sexta_feira.storage import Storage, CapacityError, ExportTooLarge, cleaned, identifier

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.dir.name) / "data.db")

    def tearDown(self):
        self.dir.cleanup()

    def test_messages(self):
        self.db.save_message("user", "Oi")
        self.db.save_message("assistant", "Olá")
        result = self.db.history()
        self.assertEqual([x["content"] for x in result], ["Oi", "Olá"])

    def test_memory_create_and_delete(self):
        item_id = self.db.add_memory("Meu compromisso é terça")
        self.assertEqual(self.db.memories()[0]["id"], item_id)
        self.assertTrue(self.db.delete_memory(item_id))
        self.assertEqual(self.db.memories(), [])

    def test_task_toggle(self):
        item_id = self.db.add_task("Estudar")
        self.assertEqual(self.db.tasks()[0]["completed"], 0)
        self.assertTrue(self.db.toggle_task(item_id))
        self.assertEqual(self.db.tasks()[0]["completed"], 1)

    def test_reject_invalid_input(self):
        for value in ("", " ", "a" * 2401, None):
            with self.assertRaises(ValueError):
                cleaned(value)
        with self.assertRaises(ValueError):
            self.db.save_message("admin", "olá")

    def test_backup_recovery_and_integrity(self):
        self.db.add_memory("Dado privado")
        destination = Path(self.dir.name) / "backup.sqlite3"
        self.db.backup(destination)
        restored = Storage(destination)
        self.assertEqual(restored.integrity(), "ok")
        self.assertEqual(restored.memories()[0]["content"], "Dado privado")
        with self.assertRaises(ValueError):
            self.db.backup(destination)

    def test_existing_schema_migrates_without_data_loss(self):
        self.db.add_task("Preservar")
        reopened = Storage(self.db.path)
        self.assertEqual(reopened.tasks()[0]["content"], "Preservar")
        self.assertEqual(reopened.preferences()["language"], "pt-BR")
        with reopened._connect() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_concurrent_writes_are_persisted(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            ids = list(workers.map(lambda i: self.db.add_task("Tarefa " + str(i)), range(16)))
        self.assertEqual(len(set(ids)), 16)
        self.assertEqual(len(self.db.tasks()), 16)
        self.assertEqual(self.db.integrity(), "ok")

    def test_exchange_atomic_validation(self):
        with self.assertRaises(ValueError):
            self.db.save_exchange("válido", "")
        self.assertEqual(self.db.history(), [])
        self.db.save_exchange("Oi", "Olá")
        rows = self.db.history(1)
        self.assertEqual(rows[0]["role"], "assistant")
        self.assertEqual(self.db.history(1, before=rows[0]["id"])[0]["role"], "user")

    def test_identifiers_and_preferences_strict_types(self):
        for item in (True, -1, 0, 1.5, "1.0", "001", "1 OR 1=1", None):
            with self.assertRaises(ValueError):
                identifier(item)
        self.db.set_preferences({"voice_rate": 0.5, "voice_enabled": True})
        self.assertTrue(Storage(self.db.path).preferences()["voice_enabled"])
        for data in ({"command": "rm"}, {"voice_rate": float("nan")}, {"voice_enabled": 1}):
            with self.assertRaises(ValueError):
                self.db.set_preferences(data)

    def test_session_expiry_and_hashed_storage(self):
        now = time.time()
        self.db.create_session("hash-only", "user", now + 5, now)
        self.assertIsNotNone(self.db.find_session("hash-only", now))
        self.assertIsNone(self.db.find_session("hash-only", now + 6))
        self.assertTrue(self.db.revoke_session(token_hash="hash-only"))

    def test_future_schema_refused_and_old_version_bumped(self):
        with self.db._connect() as connection:
            connection.execute("UPDATE metadata SET value='9' WHERE key='schema_version'")
        unchanged = self.db.path.read_bytes()
        with self.assertRaises(ValueError):
            Storage(self.db.path)
        self.assertEqual(self.db.path.read_bytes(), unchanged)
        with self.db._connect() as connection:
            connection.execute("UPDATE metadata SET value='1' WHERE key='schema_version'")
        Storage(self.db.path)
        with self.db._connect() as connection:
            self.assertEqual(connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0], "2")

    def test_capacity_atomic_and_legacy_pages_preserved(self):
        with self.db._connect() as connection:
            connection.executemany("INSERT INTO memories(content,created_at) VALUES (?,?)",
                                   [("Memória " + str(i), "2026-11-10") for i in range(105)])
            connection.executemany("INSERT INTO tasks(content,created_at) VALUES (?,?)",
                                   [("Tarefa " + str(i), "2026-11-10") for i in range(199)])
        with self.assertRaises(CapacityError):
            self.db.add_memory("Não esconder registros")
        page = self.db.memories()
        self.assertEqual(len(page), 100)
        older = self.db.memories(before=page[-1]["id"])
        self.assertEqual(len(older), 5)
        self.assertEqual(self.db.counts()["memories"], 105)
        def attempt(i):
            try:
                self.db.add_task("concorrente " + str(i))
                return True
            except CapacityError:
                return False
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(attempt, range(4)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.db.counts()["tasks"], 200)

    def test_export_size_guard_before_materializing_and_snapshot(self):
        self.db.add_memory("Conteúdo privado " * 10)
        with patch("sexta_feira.storage.EXPORT_MAX_BYTES", 600):
            with self.assertRaises(ExportTooLarge):
                self.db.export()
        exported = self.db.export()
        self.assertEqual(exported["memories"][0]["content"], "Conteúdo privado " * 9 + "Conteúdo privado")
        self.assertEqual(exported["preferences"]["language"], "pt-BR")
        self.assertLess(len(json.dumps(exported, ensure_ascii=False).encode()), 5 * 1024 * 1024)

if __name__ == "__main__":
    unittest.main()
