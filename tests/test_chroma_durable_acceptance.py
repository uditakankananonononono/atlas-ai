"""Real Chroma persistence and tenant separation across interpreter restarts."""
import os
import subprocess
import sys
import json


def test_real_chroma_restart_preserves_tenant_scoped_memory(tmp_path):
    code = '''
import json,sys
from app.platform.integrations import ChromaMemory
path,mode=sys.argv[1:]
a=ChromaMemory('tenant-a',path=path);b=ChromaMemory('tenant-b',path=path)
if mode=='write':
 a.upsert([{'id':'same-id','text':'a-private-canary','embedding':[1.,0.],'metadata':{'kind':'note'}}])
 b.upsert([{'id':'same-id','text':'b-private-canary','embedding':[0.,1.],'metadata':{'kind':'note'}}])
else:
 ra=a.query([1.,0.],limit=1);rb=b.query([0.,1.],limit=1)
 assert ra['ids']==[['same-id']] and rb['ids']==[['same-id']]
 assert ra['documents']==[['a-private-canary']]
 assert rb['documents']==[['b-private-canary']]
 print(json.dumps({'a':ra['documents'],'b':rb['documents']}))
'''
    env={**os.environ,'ANONYMIZED_TELEMETRY':'False'}
    for mode in ['write','read','read']:
        result=subprocess.run([sys.executable,'-c',code,str(tmp_path/'chroma'),mode],
                              env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        if mode=='read':
            assert json.loads(result.stdout)=={'a':[['a-private-canary']],'b':[['b-private-canary']]}
    assert (tmp_path/'chroma'/'chroma.sqlite3').exists()
