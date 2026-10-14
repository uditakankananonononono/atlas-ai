from fastapi.testclient import TestClient
from app.main import app

def test_niche_cartesian_count_ranking_and_auth(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    request={'taxonomy':['garden','lamp'],'audiences':['students','makers'],
             'formats':['app','guide'],'scores':{'garden':{'trend':9,'competition':2},'lamp':{'trend':4,'competition':3}}}
    with TestClient(app) as c:
        path='/api/v1/c33/niches';headers=oidc_auth_headers()
        assert c.post(path,json=request).status_code==401
        r=c.post(path,json=request,headers=headers)
        assert r.status_code==200,r.text
        out=r.json();assert out['niche_count']==8
        assert [n['score'] for n in out['niches']]==[7]*4+[1]*4
        assert {n['niche'] for n in out['niches']}=={f'{t} for {a} as {f}' for t in ['garden','lamp'] for a in ['students','makers'] for f in ['app','guide']}
        assert 'virality guarantees' in out['scope']['not_implemented']
        bad=dict(request,extra=True)
        assert c.post(path,json=bad,headers=headers).status_code==400
        big={'taxonomy':[f't{i}' for i in range(20)],'audiences':[f'a{i}' for i in range(20)],'formats':[f'f{i}' for i in range(20)]}
        r=c.post(path,json=big,headers=headers);assert r.status_code==200
        assert r.json()['niche_count']==8000
