import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sexta_feira import brain
from sexta_feira.inference_llama import LocalChatEngine, NativeEndpoint


def stream_response(text="Olá, posso ajudar.", done=True):
    events = [{"choices":[{"delta":{"content":text}}]}, {"usage":{"completion_tokens":5},"choices":[]}]
    return io.BytesIO(b"".join(b"data: "+json.dumps(event,ensure_ascii=False).encode()+b"\n\n" for event in events)
                      + (b"data: [DONE]\n\n" if done else b""))


class NativeInferenceTests(unittest.TestCase):
    def endpoint(self):
        endpoint = NativeEndpoint.__new__(NativeEndpoint)
        endpoint.json_call = lambda path, data: {"prompt":"formatted"} if path=="/apply-template" else {"tokens":[1,2,3]}
        return endpoint

    def test_endpoint_rejects_remote_origins_before_reading_credential(self):
        for url in ("https://api.openai.com", "http://example.invalid:80", "http://127.0.0.1:99/evil", "http://user:pass@127.0.0.1:99"):
            with self.assertRaises(ValueError):
                NativeEndpoint(url, Path("nonexistent-token"))

    def test_structured_context_omits_pre_cutover_history_and_limits_memory(self):
        with patch.dict(os.environ,{"SEXTA_HISTORY_AFTER_ID":"100"}):
            engine = LocalChatEngine()
        messages = json.loads(engine.build_messages("Minha bicicleta",[
            {"id":99,"role":"assistant","content":"old broken model"},
            {"id":101,"role":"user","content":"Olá"},
            {"id":102,"role":"assistant","content":"Bom dia"}],
            [{"content":"Minha bicicleta é azul"},{"content":"Assunto diferente"}]))
        self.assertNotIn("old broken model", json.dumps(messages))
        self.assertIn("Minha bicicleta é azul", messages[0]["content"])
        self.assertNotIn("Assunto diferente", messages[0]["content"])
        self.assertEqual([m["role"] for m in messages],["system","user","assistant","user"])
        self.assertEqual(engine._queue.maxsize,2)
        self.assertGreaterEqual(engine._reserve_mb,2048)

    def test_stream_utf8_and_usage(self):
        endpoint=self.endpoint()
        with patch.object(endpoint,"open",return_value=stream_response()) as opened:
            result,count=endpoint.generate(json.dumps([{"role":"user","content":"Olá"}]),input_limit=50,new_tokens=20,cancelled=lambda:None)
        self.assertEqual(result,"Olá, posso ajudar.")
        self.assertEqual(count,5)
        self.assertEqual(opened.call_args.args[1]["max_tokens"],20)

    def test_context_trimming_and_oversized_message_rejection(self):
        endpoint=self.endpoint()
        seen=[]
        def metadata(path,data):
            if path=="/apply-template":
                seen.append(len(data["messages"]))
                return {"prompt":str(len(data["messages"]))}
            return {"tokens":[0]*(100 if int(data["content"])>2 else 5)}
        endpoint.json_call=metadata
        with patch.object(endpoint,"open",return_value=stream_response()):
            endpoint.generate(json.dumps([{"role":"system"},{"role":"user"},{"role":"assistant"},{"role":"user"}]),input_limit=10,new_tokens=20,cancelled=lambda:None)
        self.assertEqual(seen,[4,2])
        endpoint.json_call=lambda path,data:{"prompt":"long"} if path=="/apply-template" else {"tokens":[0]*100}
        with self.assertRaises(ValueError):
            endpoint.generate(json.dumps([{"role":"system"},{"role":"user"}]),input_limit=10,new_tokens=20,cancelled=lambda:None)

    def test_cancelled_stream_is_closed_and_incomplete_stream_rejected(self):
        endpoint=self.endpoint()
        response=stream_response()
        count=0
        def cancel():
            nonlocal count
            count+=1
            if count>=4:raise brain.InferenceTimeout("cancelled")
        with patch.object(endpoint,"open",return_value=response):
            with self.assertRaises(brain.InferenceTimeout):
                endpoint.generate("[]",input_limit=10,new_tokens=20,cancelled=cancel)
        self.assertTrue(response.closed)
        with patch.object(endpoint,"open",return_value=stream_response(done=False)):
            with self.assertRaises(brain.InferenceUnavailable):
                endpoint.generate("[]",input_limit=10,new_tokens=20,cancelled=lambda:None)

    def test_saved_reply_source_survives_history_export_and_reopen(self):
        from sexta_feira.storage import Storage
        with tempfile.TemporaryDirectory() as directory:
            store=Storage(Path(directory)/"source.sqlite3")
            store.save_exchange("Olá","Olá, sou a SEXTA-FEIRA.",source="local_model",model="Gemma 3 4B")
            reopened=Storage(store.path)
            self.assertEqual(reopened.history()[-1]["source"],"local_model")
            self.assertEqual(reopened.export()["messages"][-1]["model"],"Gemma 3 4B")
            self.assertEqual(reopened.delete_history(),2)
            with reopened._connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM metadata WHERE key LIKE 'message-source:%'").fetchone()[0],0)
