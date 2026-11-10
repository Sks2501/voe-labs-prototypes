import tempfile
import unittest
from pathlib import Path
from sexta_feira.storage import Storage, cleaned

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

if __name__ == "__main__":
    unittest.main()
