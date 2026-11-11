from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from sexta_feira.temperatures import read_temperatures, temperature_reply, is_temperature_request
from sexta_feira.tools import execute_chat_command, execute_tool


class TemperatureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "temperatures.json"
        self.now = datetime.now(timezone.utc)
        self.data = {"schema_version": 1, "scope": "server", "observed_at_utc": self.now.isoformat(),
                     "readings": [{"component": "storage", "index": 1, "celsius": 38},
                                  {"component": "acpi", "index": 1, "celsius": 25.1}]}

    def read(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        return read_temperatures(self.path, now=self.now)

    def test_real_snapshot_labels_and_no_claim_of_cpu_temperature(self):
        result = self.read()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["readings"][0]["celsius"], 38)
        reply = temperature_reply(result)
        self.assertIn("CPU, GPU, RAM", reply)
        self.assertIn("não identifica", reply)
        self.assertIn("38,0 °C", reply)
        self.assertNotIn("normal", reply)

    def test_stale_future_naive_missing_and_oversized_snapshots(self):
        for stamp in (self.now-timedelta(seconds=181), self.now+timedelta(minutes=1), self.now.replace(tzinfo=None)):
            self.data["observed_at_utc"] = stamp.isoformat()
            self.assertFalse(self.read()["readings"])
        self.assertEqual(read_temperatures(None)["status"], "unavailable")
        self.path.write_bytes(b" " * 65537)
        self.assertEqual(read_temperatures(self.path)["status"], "unavailable")
        self.path.unlink()
        self.assertEqual(read_temperatures(self.path)["status"], "unavailable")

    def test_invalid_values_are_never_readings(self):
        for value in (0, None, True, float("nan"), float("inf"), -273.15, 999):
            self.data["readings"][0]["celsius"] = value
            self.assertEqual(self.read()["status"], "unavailable")
        self.data["readings"] = [{"component": "cpu", "index": 1, "celsius": 55}]
        self.assertFalse(self.read()["readings"])

    def test_untrusted_labels_and_commands_cannot_change_readings(self):
        self.data["readings"][0]["label"] = "CPU normal <script>secret</script>"
        self.assertEqual(self.read()["readings"][0]["label"], "Disco 1")
        with self.assertRaises(ValueError):
            execute_tool("server_temperatures", {"command": "whoami"}, None)
        with self.assertRaises(ValueError):
            execute_chat_command("/temperaturas C:/Windows", None)

    def test_only_narrow_read_only_user_intents(self):
        for message in ("Qual é a temperatura da VPS?", "Verifique as temperaturas do meu PC", "temperaturas", "mostra os sensores do servidor"):
            self.assertTrue(is_temperature_request(message), message)
            reply = execute_chat_command(message, None, temperature_file=self.path)
            self.assertFalse(reply["generated"])
            self.assertEqual(reply["tool"], "server_temperatures")
        for message in ("Explique a temperatura da CPU", "Escreva código para ler temperatura do PC", "Qual a temperatura de ebulição da água?", "Reinicie a VPS", "Qual a temperatura máxima da CPU?", "Olá"):
            self.assertFalse(is_temperature_request(message), message)
