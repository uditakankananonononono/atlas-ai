from fastapi.testclient import TestClient
from app.main import app

def test_tool_mount_and_generated_csv_oracle(oidc_auth_headers,monkeypatch,tmp_path):
    import os,subprocess,sys
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    request={'as_of':'2026-10-15','requested_by_owner':True,'company':'Named Example',
             'need':{'id':'columns','type':'csv_transform','description':'retain specified columns','fields':['name','score']}}
    with TestClient(app) as c:
        path='/api/v1/c34/tool';h=oidc_auth_headers()
        assert c.post(path,json=request).status_code==401
        r=c.post(path,json=request,headers=h);assert r.status_code==200,r.text
        out=r.json();assert out['draft'] is True and out['file_count']==2
        for filename,source in out['files'].items():(tmp_path/filename).write_text(source)
        # Generated-code execution only in test, never exposed by HTTP handler.
        script="import tool_columns as t; assert t.render([{'name':'Ada','score':7,'extra':'drop'}]) == 'name,score\\nAda,7\\n'; assert t.parse('name,score\\nAda,7\\n') == [{'name':'Ada','score':'7'}]"
        result=subprocess.run([sys.executable,'-I','-c','import sys;sys.path.insert(0,sys.argv[1]);'+script,str(tmp_path)],capture_output=True,text=True,timeout=10)
        assert result.returncode==0,result.stderr
        result=subprocess.run([sys.executable,str(tmp_path/'test_tool_columns.py')],cwd=tmp_path,capture_output=True,text=True,timeout=10)
        assert result.returncode==0,result.stderr
        bad=dict(request,requested_by_owner=False)
        r=c.post(path,json=bad,headers=h)
        assert r.status_code==400 and r.json()['detail']=='PROTO_REFUSED_UNSOLICITED'
