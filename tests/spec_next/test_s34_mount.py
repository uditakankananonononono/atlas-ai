from fastapi.testclient import TestClient
from app.main import app

def test_hierarchy_route_hand_coverage_oracle(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    r={'taxonomy':[{'code':'R','name':'Root','parent':None},{'code':'A','name':'Alpha','parent':'R'},{'code':'B','name':'Beta','parent':'R'}],
       'touched':[{'code':'A','unit_id':'u','evidence':'supplied proof'}],
       'needs':[],'capabilities':[],'min_gap_severity':0}
    with TestClient(app) as c:
        path='/api/v1/c34/industry';h=oidc_auth_headers()
        assert c.post(path,json=r).status_code==401
        result=c.post(path,json=r,headers=h);assert result.status_code==200,result.text
        out=result.json()
        assert out['coverage']=={'touched':2,'total':3,'coverage_percent':66.7}
        assert out['leaf_coverage']=={'touched':1,'total':2,'coverage_percent':50.0}
        assert out['rolled_touched_codes']==['A','R']
        assert out['source_evidence_verified'] is False
        bad=dict(r,coverage_assertion={'word':'all','coverage_percent':100})
        result=c.post(path,json=bad,headers=h)
        assert result.status_code==400 and result.json()['detail']=='PROTO_REFUSED_OVERCLAIM'
