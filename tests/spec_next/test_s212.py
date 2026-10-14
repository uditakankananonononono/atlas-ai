from fastapi.testclient import TestClient
from app.main import app

def test_persona_exact_features_and_nonimpersonation(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        path='/api/v1/c33/persona';r={'field':'science','samples':['However robots learn. Therefore robots reason.']};h=oidc_auth_headers()
        assert c.post(path,json=r).status_code==401
        out=c.post(path,json=r,headers=h);assert out.status_code==200,out.text
        voice=out.json()['voice']
        assert voice=={'avg_sentence_length':3.0,'tone':'formal','formal_markers':2,'informal_markers':0,'top_words':['robots','however','learn','reason','therefore']}
        assert out.json()['sample_count']==1 and 'not impersonation' in out.json()['guidance']
        bad=dict(r,real_person='someone')
        response=c.post(path,json=bad,headers=h)
        assert response.status_code==400 and response.json()['detail']=='SOCIAL_REFUSED_IMPERSONATE'
        assert c.post(path,json=dict(r,extra=True),headers=h).status_code==400
