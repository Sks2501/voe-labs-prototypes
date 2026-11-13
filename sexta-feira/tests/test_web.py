import json
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.client import HTTPConnection
from pathlib import Path
from sexta_feira.storage import Storage
from sexta_feira.server import AssistantServer, AssistantHandler
from sexta_feira import brain
from sexta_feira.security import RateLimiter

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.server = AssistantServer(
            ("127.0.0.1", 0), "token-de-acesso-para-teste", "small",
            Storage(Path(self.dir.name) / "db.sqlite3"))
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.dir.cleanup()

    def call(self, method, path, body=None, token=None, extra_headers=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body)
        headers.update(extra_headers or {})
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = json.loads(response.read())
        status = response.status
        conn.close()
        return status, payload

    def test_thread_api_authentication_context_and_profile(self):
        token = "token-de-acesso-para-teste"
        self.assertEqual(self.call("GET", "/api/v1/threads")[0], 401)
        status, a = self.call("POST", "/api/v1/threads", {"title":"A"}, token)
        self.assertEqual(status, 201)
        _, b = self.call("POST", "/api/v1/threads", {"title":"B"}, token)
        self.server.storage.save_exchange("other conversation secret", "B", thread_id=b["id"])
        self.call("PATCH", "/api/v1/preferences", {"preferred_name":"Criador", "about_me":"Criei esta IA."}, token)
        with patch.object(brain, "generate_reply", return_value="Olá, Criador.") as model:
            status, result = self.call("POST", "/api/v1/conversations", {"message":"Oi", "thread_id":a["id"]}, token)
            self.assertEqual(status, 200)
            self.assertEqual(model.call_args.args[1], [])
            self.assertEqual(model.call_args.kwargs["preferences"]["preferred_name"], "Criador")
            self.assertEqual(result["thread_id"], a["id"])
        status, result = self.call("GET", "/api/v1/threads/"+a["id"]+"?limit=1", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(len(result["history"]), 1)
        self.assertEqual(self.call("PATCH", "/api/v1/threads/"+a["id"], {"title":"Renamed"}, token)[0], 200)
        self.assertEqual(self.call("DELETE", "/api/v1/threads/"+a["id"], token=token)[0], 200)
        self.assertEqual(len(self.server.storage.thread_history(b["id"])), 2)
        self.assertEqual(self.call("POST", "/api/v1/conversations", {"message":"x", "thread_id":"not-an-id"}, token)[0], 400)

    def test_temperature_api_authentication_and_chat_bypass_model(self):
        token = "token-de-acesso-para-teste"
        self.assertEqual(self.call("GET", "/api/v1/temperatures")[0], 401)
        self.server.temperature_file = Path(self.dir.name)/"sensors.json"
        from datetime import datetime, timezone
        self.server.temperature_file.write_text(json.dumps({"schema_version":1,"scope":"server",
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "readings":[{"component":"storage","index":1,"celsius":38}]}),encoding="utf-8")
        _, session = self.call("POST", "/api/v1/sessions", {"role":"user"}, token)
        status, result = self.call("GET", "/api/v1/temperatures", token=session["token"])
        self.assertEqual(status, 200)
        self.assertEqual(result["scope"], "server")
        self.assertEqual(result["readings"][0]["celsius"], 38)
        with patch.object(brain,"generate_reply",side_effect=AssertionError("Thermal request must not use model")):
            for message in ("/temperaturas", "Qual é a temperatura da VPS?"):
                status, result = self.call("POST", "/api/v1/conversations", {"message":message}, session["token"])
                self.assertEqual(status, 200)
                self.assertEqual(result["tool"], "server_temperatures")
                self.assertIn("38,0",result["reply"])
        _, schema = self.call("GET", "/api/v1/openapi.json", token=token)
        self.assertIn("/temperatures",schema["paths"])

    def test_owner_hardware_is_authenticated_and_filtered(self):
        admin="token-de-acesso-para-teste"
        self.assertEqual(self.call("GET","/api/v1/hardware")[0],401)
        _,session=self.call("POST","/api/v1/sessions",{"role":"user"},admin)
        with patch.object(self.server,"metrics",return_value={"cpu_logical":4,"system_cpu_percent":10,"pid":123,"token":"SECRET","requests":100}):
            status,result=self.call("GET","/api/v1/hardware",token=session["token"])
            self.assertEqual(status,200)
            self.assertEqual(result["resources"]["system_cpu_percent"],10)
            self.assertNotIn("SECRET",json.dumps(result))
            self.assertNotIn("pid",result["resources"])
            with patch.object(brain,"generate_reply",side_effect=AssertionError("Operational query must not use model")):
                status,result=self.call("POST","/api/v1/conversations",{"message":"Como está o servidor?"},session["token"])
                self.assertEqual(status,200)
                self.assertEqual(result["tool"],"server_hardware")
        self.assertEqual(self.call("GET","/api/v1/metrics",token=session["token"])[0],403)

    def test_research_is_authenticated_explicit_and_preserves_source_links(self):
        admin="token-de-acesso-para-teste"
        self.assertEqual(self.call("POST","/api/v1/research",{"query":"topic"})[0],401)
        result={"reply":"Found sources:\nhttps://example.com/article","source":"tool","generated":False,"action_executed":True,"tool":"web_research"}
        with patch.object(self.server.research,"run",return_value=result) as web,patch.object(brain,"generate_reply",return_value="local answer") as model:
            status,_=self.call("POST","/api/v1/conversations",{"message":"Olá"},admin)
            self.assertEqual(status,200);web.assert_not_called();model.assert_called_once()
            status,answer=self.call("POST","/api/v1/conversations",{"message":"pesquise topic"},admin)
            self.assertEqual(status,200);self.assertEqual(answer['tool'],'web_research');web.assert_called_with(query='topic')
            self.assertIn('https://example.com/article',self.server.storage.history()[-1]['content'])
            self.call("POST","/api/v1/conversations",{"message":"topic","research":True},admin)
            web.assert_called_with(query='topic')
            self.assertEqual(self.call("POST","/api/v1/conversations",{"message":"topic","research":"yes"},admin)[0],400)
        status,schema=self.call('GET','/api/v1/openapi.json',token=admin)
        self.assertIn('/research',schema['paths'])

    def test_health_requires_authentication(self):
        status, body = self.call("GET", "/api/health")
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], "unauthorized")
        status, body = self.call("GET", "/api/v1/health", token="token-de-acesso-para-teste")
        self.assertEqual(status, 200)
        self.assertTrue(body["local"])

    def test_protect_state(self):
        status, _ = self.call("GET", "/api/state")
        self.assertEqual(status, 401)

    def test_authenticated_memory(self):
        token = "token-de-acesso-para-teste"
        status, _ = self.call("POST", "/api/memory", {"content": "Moro no Brasil"}, token)
        self.assertEqual(status, 201)
        status, state = self.call("GET", "/api/state", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(state["memories"][0]["content"], "Moro no Brasil")

    def test_reject_oversized_post(self):
        token = "token-de-acesso-para-teste"
        status, _ = self.call("POST", "/api/task", {"content": "x" * 10000}, token)
        self.assertEqual(status, 413)

    def test_session_lifecycle_and_roles(self):
        admin = "token-de-acesso-para-teste"
        status, session = self.call("POST", "/api/v1/sessions", {"role": "user"}, admin)
        self.assertEqual(status, 201)
        token = session["token"]
        self.assertGreater(len(token), 32)
        self.assertEqual(self.call("GET", "/api/v1/state", token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/metrics", token=token)[0], 403)
        self.assertEqual(self.call("GET", "/api/v1/sessions", token=token)[0], 403)
        self.assertEqual(self.call("POST", "/api/v1/sessions", {"role": "admin"}, token)[0], 403)
        self.assertEqual(self.call("DELETE", "/api/v1/sessions/current", token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/state", token=token)[0], 401)
        # No plaintext session credential is persisted.
        self.assertNotIn(token.encode(), self.server.storage.path.read_bytes())

    def test_admin_sessions_and_backup(self):
        token = "token-de-acesso-para-teste"
        status, _ = self.call("POST", "/api/v1/sessions", {"role": "admin"}, token)
        self.assertEqual(status, 201)
        status, data = self.call("GET", "/api/v1/sessions", token=token)
        self.assertEqual(status, 200)
        self.assertNotIn("token_hash", data["sessions"][0])
        status, data = self.call("POST", "/api/v1/admin/backup", {}, token)
        self.assertEqual(status, 201)
        self.assertTrue((self.server.storage.path.parent / "backups" / data["backup"]).is_file())
        self.assertEqual(self.call("GET", "/api/v1/admin/integrity", token=token)[1], {"integrity": "ok"})

    def test_memory_correction_and_deletion(self):
        token = "token-de-acesso-para-teste"
        _, data = self.call("POST", "/api/v1/memories", {"content": "Minha cidade é A"}, token)
        path = "/api/v1/memories/" + str(data["id"])
        self.assertEqual(self.call("PATCH", path, {"content": "Minha cidade é B"}, token)[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/memories", token=token)[1]["memories"][0]["content"], "Minha cidade é B")
        self.assertEqual(self.call("DELETE", path, token=token)[0], 200)
        self.assertEqual(self.call("DELETE", path, token=token)[0], 404)

    def test_task_update_and_preferences(self):
        token = "token-de-acesso-para-teste"
        _, data = self.call("POST", "/api/v1/tasks", {"content": "Estudar"}, token)
        path = "/api/v1/tasks/" + str(data["id"])
        self.assertEqual(self.call("PATCH", path, {"content": "Estudar Python", "completed": True}, token)[0], 200)
        task = self.call("GET", "/api/v1/tasks", token=token)[1]["tasks"][0]
        self.assertEqual((task["content"], task["completed"]), ("Estudar Python", 1))
        self.assertEqual(self.call("PATCH", path, {"completed": 1}, token)[0], 400)
        self.assertEqual(self.call("PATCH", "/api/v1/preferences", {"voice_enabled": True, "voice_rate": 1.2}, token)[0], 200)
        self.assertTrue(self.call("GET", "/api/v1/preferences", token=token)[1]["voice_enabled"])
        self.assertEqual(self.call("PATCH", "/api/v1/preferences", {"voice_rate": 999}, token)[0], 400)

    def test_chat_persists_exchange_only_after_success(self):
        token = "token-de-acesso-para-teste"
        # HTTP and persistence verification is independent of the real-model smoke test.
        with patch.object(brain, "generate_reply", return_value="Olá, sou a SEXTA-FEIRA."):
            status, data = self.call("POST", "/api/v1/conversations", {"message": "Olá"}, token)
        self.assertEqual(status, 200)
        self.assertFalse(data["action_executed"])
        self.assertEqual([x["role"] for x in self.server.storage.history()], ["user", "assistant"])
        self.assertEqual(self.server.storage.memories(), [])
        for exception, expected in [(brain.InferenceBusy("busy"), 429), (brain.InferenceTimeout("timeout"), 504), (brain.InferenceUnavailable("missing"), 503)]:
            with patch.object(brain, "generate_reply", side_effect=exception):
                self.assertEqual(self.call("POST", "/api/v1/conversations", {"message": "Teste"}, token)[0], expected)
        self.assertEqual(len(self.server.storage.history()), 2)

    def test_reject_cross_origin_host_and_unknown_fields(self):
        token = "token-de-acesso-para-teste"
        self.assertEqual(self.call("GET", "/api/v1/state", token=token, extra_headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.call("GET", "/api/v1/state", token=token, extra_headers={"Host": "evil.example"})[0], 421)
        self.assertEqual(self.call("POST", "/api/v1/tasks", {"content": "safe", "command": "whoami"}, token)[0], 400)

    def test_rate_limit_is_enforced(self):
        self.server.limiter = RateLimiter(limit=2)
        token = "token-de-acesso-para-teste"
        self.assertEqual(self.call("GET", "/api/v1/health", token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/health", token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/v1/health", token=token)[0], 429)

    def test_tools_are_explicit_and_allowlisted(self):
        token = "token-de-acesso-para-teste"
        status, result = self.call("POST", "/api/v1/tools", {"name": "system_time", "parameters": {}}, token)
        self.assertEqual(status, 200)
        self.assertTrue(result["executed"])
        self.assertEqual(self.call("POST", "/api/v1/tools", {"name": "shell", "parameters": {"command": "whoami"}}, token)[0], 400)
        self.assertEqual(self.call("POST", "/api/v1/tools", {"name": "create_task", "parameters": {"content": "Telefonar"}}, token)[0], 200)

    def test_openapi_export_and_paged_history(self):
        token = "token-de-acesso-para-teste"
        status, schema = self.call("GET", "/api/v1/openapi.json", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(schema["openapi"], "3.1.0")
        self.assertIn("/conversations", schema["paths"])
        self.assertIn("bearerAuth", schema["components"]["securitySchemes"])
        self.server.storage.save_exchange("Oi", "Olá")
        status, data = self.call("GET", "/api/v1/history?limit=1", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(self.call("GET", "/api/v1/history?limit=999", token=token)[0], 400)
        status, data = self.call("GET", "/api/v1/export", token=token)
        self.assertEqual(status, 200)
        self.assertNotIn("sessions", data)
        self.assertEqual(len(data["messages"]), 2)

    def test_logs_exclude_private_input_and_urls(self):
        with self.assertLogs("sexta_feira.http", level="INFO") as captured:
            self.call("GET", "/api/v1/state?token=VERY_PRIVATE_TOKEN", token="token-de-acesso-para-teste")
            self.call("POST", "/api/v1/tasks", {"content": "VERY_PRIVATE_CONTENT"}, "token-de-acesso-para-teste")
        logged = "\n".join(captured.output)
        self.assertNotIn("VERY_PRIVATE", logged)
        self.assertNotIn("token-de-acesso", logged)

    def test_bounded_connection_slots(self):
        # Saturation is simulated without keeping 16 real idle sockets open.
        acquired = []
        while self.server._connections.acquire(blocking=False):
            acquired.append(True)
        try:
            connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
            connection.request("GET", "/")
            response = connection.getresponse()
            self.assertEqual(response.status, 503)
            response.read()
            connection.close()
        finally:
            for _ in acquired:
                self.server._connections.release()

    def test_capacity_returns_conflict_and_legacy_pages(self):
        token = "token-de-acesso-para-teste"
        with self.server.storage._connect() as connection:
            connection.executemany("INSERT INTO memories(content,created_at) VALUES (?,?)",
                                   [("Memória " + str(i), "2026-11-10") for i in range(102)])
        status, body = self.call("POST", "/api/v1/memories", {"content": "Nova"}, token)
        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "capacity_reached")
        status, page = self.call("GET", "/api/v1/memories?limit=100", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(page["total"], 102)
        cursor = page["memories"][-1]["id"]
        _, older = self.call("GET", "/api/v1/memories?before=" + str(cursor), token=token)
        self.assertEqual(len(older["memories"]), 2)

    def test_export_is_bounded_and_only_one_runs_at_a_time(self):
        token = "token-de-acesso-para-teste"
        self.server.storage.add_memory("Dados")
        with patch("sexta_feira.storage.EXPORT_MAX_BYTES", 600):
            status, body = self.call("GET", "/api/v1/export", token=token)
            self.assertEqual(status, 413)
            self.assertEqual(body["code"], "export_too_large")
        entered, release = threading.Event(), threading.Event()
        original = self.server.storage.export
        def slow_export():
            entered.set()
            self.assertTrue(release.wait(3))
            return original()
        results = []
        with patch.object(self.server.storage, "export", side_effect=slow_export):
            caller = threading.Thread(target=lambda: results.append(self.call("GET", "/api/v1/export", token=token)))
            caller.start()
            self.assertTrue(entered.wait(2))
            try:
                status, body = self.call("GET", "/api/v1/export", token=token)
                self.assertEqual(status, 429)
                self.assertEqual(body["code"], "export_busy")
            finally:
                release.set()
                caller.join(3)
        self.assertEqual(results[0][0], 200)
        self.assertEqual(self.call("GET", "/api/v1/export", token=token)[0], 200)

    def test_explicit_slash_commands_execute_without_model(self):
        token = "token-de-acesso-para-teste"
        with patch.object(brain, "generate_reply", side_effect=AssertionError("Model must not execute for a user command")) as model:
            for command in ("/hora", "/tarefa Revisar documentos", "/lembrar Gosto de café", "/tarefas", "/memorias"):
                status, result = self.call("POST", "/api/v1/conversations", {"message": command}, token)
                self.assertEqual(status, 200)
                self.assertEqual(result["source"], "tool")
                self.assertFalse(result["generated"])
                self.assertTrue(result["action_executed"])
            model.assert_not_called()
        self.assertEqual(self.server.storage.tasks()[0]["content"], "Revisar documentos")
        self.assertEqual(self.server.storage.memories()[0]["content"], "Gosto de café")
        self.assertEqual(len(self.server.storage.history(100)), 10)
        with patch.object(brain, "generate_reply", return_value="/tarefa Não executar"):
            _, result = self.call("POST", "/api/v1/conversations", {"message": "Escreva um exemplo de comando"}, token)
        self.assertEqual(result["source"], "gpt2")
        self.assertTrue(result["generated"])
        self.assertFalse(result["action_executed"])
        self.assertEqual(len(self.server.storage.tasks()), 1)

    def test_invalid_slash_command_never_reaches_model(self):
        token = "token-de-acesso-para-teste"
        with patch.object(brain, "generate_reply") as model:
            for command in ("/shell whoami", "/tarefa", "/hora argumento"):
                self.assertEqual(self.call("POST", "/api/v1/conversations", {"message": command}, token)[0], 400)
            model.assert_not_called()
        self.assertEqual(self.server.storage.history(), [])

if __name__ == "__main__":
    unittest.main()
