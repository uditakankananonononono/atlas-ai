import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.architecture_decision_records705 import architecture_decision_records705
from app.modules.m20_general_cognitive_worker.comment_audit706 import audit
from app.modules.m20_general_cognitive_worker.naming_checker707 import check_naming
from app.modules.m20_general_cognitive_worker.code_formatting708 import run

ADR={'title':'Pick local','context':'Supplied tradeoff','decision':'Use local','consequences':['Keep records'],'status':'accepted'}
COMMENTS={'source':'# explains intent\nx = 1\n'}
NAMING={'source':'def BadName():\n    pass\n','rules':{'rules':[{'id':'fn','kinds':['function'],'style':'snake_case'}]}}
FORMATTING={'style':{'name':'team-style-a','indent':'spaces','indent_width':4,'max_line_length':40,'line_ending':'lf','final_newline':True},'files':[{'path':'a.py','before':'x=1\n','after':'x = 1\n'}]}
CASES=[('/architecture-decisions/705/record',ADR,architecture_decision_records705),
       ('/code-comments/706/audit',COMMENTS,audit),
       ('/naming-conventions/707/check',NAMING,lambda d:check_naming(d['source'],d['rules'])),
       ('/code-formatting/708/inspect',FORMATTING,run)]

@pytest.mark.parametrize('path,data,engine',CASES)
def test_four_mounted_engines_real_parity(monkeypatch,oidc_auth_headers,path,data,engine):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    path='/api/v1/api/modules/20'+path
    assert client.post(path,json={'data':data}).status_code==401
    for tenant,actor in [('a','owner'),('b','other')]:
        result=client.post(path,headers=oidc_auth_headers(tenant,actor),json={'data':data})
        assert result.status_code==200,result.text
        assert result.json()=={**engine(data),'tenant_id':tenant,'actor_id':actor}
    headers=oidc_auth_headers('a','owner')
    for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
        assert client.post(path,headers=headers,json={'data':data,**extra}).status_code==403
    assert client.post(path,headers=headers,json={'data':{}}).status_code==422
    assert client.post(path,headers={**headers,'Content-Type':'application/json'},content=json.dumps({'data':{'source':'\ud800'}})).status_code==422

@pytest.mark.parametrize('path,data,engine',CASES)
def test_resource_refs_cap_boundary(monkeypatch,oidc_auth_headers,path,data,engine):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    path='/api/v1/api/modules/20'+path
    headers=oidc_auth_headers('a','owner')
    refs=[{'tenant_id':'a','actor_id':'owner','id':str(i)}for i in range(64)]
    ok=client.post(path,headers=headers,json={'data':data,'resource_refs':refs})
    assert ok.status_code==200,ok.text
    assert client.post(path,headers=headers,json={'data':data,'resource_refs':refs+[{'tenant_id':'a','actor_id':'owner','id':'65'}]}).status_code==422

@pytest.mark.parametrize('path,data,engine',CASES)
def test_explicit_null_identity_fields_treated_as_absent(monkeypatch,oidc_auth_headers,path,data,engine):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    r=client.post('/api/v1/api/modules/20'+path,headers=oidc_auth_headers('a','owner'),json={'data':data,'tenant_id':None,'actor_id':None})
    assert r.status_code==200,r.text
    assert r.json()['tenant_id']=='a' and r.json()['actor_id']=='owner'
