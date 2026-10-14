from fastapi.testclient import TestClient
from app.main import app

def test_mounted_auth_and_real_evidence(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        path='/api/v1/c32/psyche'
        assert c.post(path,json={'text':'happy'}).status_code==401
        text='Made saddle. not happy. happy friend goal control'
        r=c.post(path,json={'text':text},headers=oidc_auth_headers())
        assert r.status_code==200,r.text
        out=r.json()
        assert out['emotions']['anger']==out['emotions']['sadness']==0
        assert out['emotions']['joy']==1
        assert out['motives']=={'achievement':1,'affiliation':1,'power':1}
        hits=out['evidence']['emotions']['joy']
        assert [h['negated'] for h in hits]==[True,False]
        assert all(text[h['start']:h['end']].lower()==h['cue'] for h in hits)
        assert out['claims_feeling'] is False and out['validity_limits']
        assert c.post(path,json={'text':'happy','extra':True},headers=oidc_auth_headers()).status_code==400
