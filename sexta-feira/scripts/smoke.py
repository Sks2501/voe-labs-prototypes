"""Conservative real-inference and API smoke in an isolated temporary database."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='sexta-smoke-',dir=os.environ.get('TEMP')) as folder:
        os.environ['SEXTA_DATA_DIR']=folder
        os.environ['SEXTA_OFFLINE']='1'
        from sexta_feira.server import AssistantServer
        from sexta_feira.storage import Storage
        from sexta_feira.brain import shutdown_engine
        token=secrets.token_urlsafe(48)
        with AssistantServer(('127.0.0.1',args.port),token,'small',Storage()) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base='http://127.0.0.1:'+str(server.server_port)+'/api/v1'
            def call(path,body=None,method=None,authorized=True):
                headers={'Authorization':'Bearer '+token} if authorized else {}
                data=None
                if body is not None:
                    headers['Content-Type']='application/json'
                    data=json.dumps(body).encode()
                req=urllib.request.Request(base+path,data=data,headers=headers,method=method)
                with urllib.request.urlopen(req,timeout=150) as response:
                    return response.status,json.load(response)
            start=time.perf_counter()
            try:
                try:
                    call('/state',authorized=False)
                    raise AssertionError('Unauthorized state was accessible')
                except urllib.error.HTTPError as exc:
                    assert exc.code==401,exc.code
                assert call('/health')[0]==200
                session=call('/sessions',{'role':'user'})[1]
                token=session['token']
                memory=call('/memories',{'content':'Smoke test only; temporary database.'})[1]
                call('/memories/'+str(memory['id']),None,'DELETE')
                task=call('/tasks',{'content':'Temporary smoke task'})[1]
                call('/tasks/'+str(task['id']),{'completed':True},'PATCH')
                call('/tasks/'+str(task['id']),None,'DELETE')
                before=time.process_time()
                status,reply=call('/conversations',{'message':'Olá, apresente-se em uma frase.'})
                assert status==200 and isinstance(reply.get('reply'),str) and reply['reply'].strip()
                elapsed=time.perf_counter()-start
                model=call('/model')[1]
                print(json.dumps({'smoke':'passed','elapsed_seconds':round(elapsed,3),'process_cpu_seconds':round(time.process_time()-before,3),'model':model,'database':'isolated_temporary','unauthorized':'blocked'},ensure_ascii=False))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                shutdown_engine()

if __name__=='__main__':main()
