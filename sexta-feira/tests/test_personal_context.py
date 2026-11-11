import json
from pathlib import Path
import tempfile
import unittest
from sexta_feira.storage import Storage, CapacityError, PROFILE_FIELDS
from sexta_feira.inference_llama import LocalChatEngine


class PersonalContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Storage(Path(self.directory.name) / "test.sqlite3")

    def tearDown(self):
        self.directory.cleanup()

    def test_conversations_isolate_messages_and_survive_reopen(self):
        a, b = self.store.create_thread("Bicicleta"), self.store.create_thread("Trabalho")
        self.store.save_exchange("azul", "certo", source="local_model", model="test", thread_id=a["id"])
        self.store.save_exchange("prazo", "amanhã", source="tool", thread_id=b["id"])
        reopened = Storage(self.store.path)
        self.assertEqual([x["content"] for x in reopened.thread_history(a["id"])], ["azul", "certo"])
        self.assertEqual(reopened.thread_history(a["id"])[-1]["source"], "local_model")
        exported = reopened.export()
        self.assertEqual(len(exported["threads"]), 2)
        self.assertEqual(exported["messages"][0]["thread_id"], a["id"])
        self.assertEqual(len(reopened.history()), 4)
        self.assertEqual(reopened.threads()[0]["id"], b["id"])
        self.assertEqual(reopened.integrity(), "ok")

    def test_rename_and_delete_only_selected_conversation(self):
        a, b = self.store.create_thread(), self.store.create_thread()
        self.store.save_exchange("a", "A", source="tool", thread_id=a["id"])
        self.store.save_exchange("b", "B", thread_id=b["id"])
        self.store.save_exchange("legacy", "preserved")
        self.assertEqual(self.store.rename_thread(a["id"], "Novo título")["title"], "Novo título")
        self.assertTrue(self.store.delete_thread(a["id"]))
        self.assertEqual(len(self.store.history()), 4)
        self.assertEqual(len(self.store.thread_history(b["id"])), 2)
        with self.store._connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM metadata WHERE key='message-source:2'").fetchone()[0], 0)

    def test_invalid_ids_never_write_an_exchange_and_capacity_is_bounded(self):
        for value in (None, 1, "' OR 1=1", "A"*32, "../", "0"*32):
            with self.assertRaises(ValueError):
                self.store.save_exchange("x", "y", thread_id=value if value is not None else "invalid")
        self.assertEqual(self.store.history(), [])
        for _ in range(100):
            self.store.create_thread()
        with self.assertRaises(CapacityError):
            self.store.create_thread()
        self.assertEqual(len(self.store.threads()), 100)

    def test_history_pagination_and_clear_remove_group_metadata(self):
        a = self.store.create_thread()
        for i in range(4):
            self.store.save_exchange(str(i), str(i), thread_id=a["id"])
        latest = self.store.thread_history(a["id"], 3)
        earlier = self.store.thread_history(a["id"], 3, latest[0]["id"])
        self.assertLess(earlier[-1]["id"], latest[0]["id"])
        self.assertEqual(self.store.delete_history(), 8)
        self.assertEqual(self.store.threads(), [])

    def test_profile_validation_clear_export_and_reopen(self):
        values = {"preferred_name": "Criador", "about_me": "Sou o criador da SEXTA-FEIRA.", "goals": "", "response_style": "Objetiva"}
        self.store.set_preferences(values)
        self.assertEqual(Storage(self.store.path).preferences()["preferred_name"], "Criador")
        self.assertEqual(self.store.export()["preferences"]["about_me"], values["about_me"])
        for key, limit in PROFILE_FIELDS.items():
            for value in (None, 123, "x"*(limit+1), "\x00"):
                with self.assertRaises(ValueError):
                    self.store.set_preferences({key:value})
        self.store.set_preferences({key:"" for key in PROFILE_FIELDS})
        self.assertEqual(self.store.preferences()["preferred_name"], "")

    def test_profile_is_available_without_keyword_match_and_persona_keeps_tool_boundary(self):
        engine = LocalChatEngine()
        profile = {"preferred_name":"Criador", "about_me":"Criei esta assistente.", "goals":"Organizar a rotina"}
        messages = json.loads(engine.build_messages("Olá", [], [], profile))
        self.assertIn("Criei esta assistente.", messages[0]["content"])
        self.assertIn("Tony Stark", messages[0]["content"])
        self.assertIn("não executa ações", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "Olá")
