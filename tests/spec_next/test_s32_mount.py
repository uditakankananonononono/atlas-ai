from fastapi.testclient import TestClient
from app.main import app

def request():
    return {'brand':{'name':'Atlas Studio','palette':{'bg':'#FFFFFF','fg':'#111111','accent':'#333333'},'font_stack':'Georgia, serif','scale':1.25,'base_px':16},
            'pages':[{'slug':'index','title':'Build with evidence','sections':[{'kind':'hero','heading':'Small tools. Clear results.','body':'Prototype ideas from supplied facts. Review every claim before release.'},
             {'kind':'grid','heading':'Our process','cards':[{'heading':'Observe','body':'Start with supplied evidence.'},{'heading':'Test','body':'Use an independent expected result.'},{'heading':'Review','body':'Keep limits visible.'}]}]}]}

def test_site_mount_source_checks_and_auth(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        path='/api/v1/c34/site';h=oidc_auth_headers()
        assert c.post(path,json=request()).status_code==401
        r=c.post(path,json=request(),headers=h);assert r.status_code==200,r.text
        out=r.json();assert set(out['files'])=={'style.css','index.html'}
        assert all(x['pass'] for x in out['checks'])
        assert out['visual_quality']=='unverified'


def test_authenticated_invalid_payload_maps_valueerror_to_400(oidc_auth_headers,monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        r=request();r['brand']['palette']['fg']='red'
        out=c.post('/api/v1/c34/site',json=r,headers=oidc_auth_headers())
        assert out.status_code==400
        assert out.json()=={'detail':'PROTO_REFUSED_UNSAFE:css'}


def test_authenticated_typeerror_maps_to_400(oidc_auth_headers,monkeypatch):
    from app.modules.c34 import site_routes
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    def fail(_):raise TypeError('SITE_TEST_TYPE_ERROR')
    monkeypatch.setattr(site_routes,'run',fail)
    with TestClient(app) as c:
        out=c.post('/api/v1/c34/site',json=request(),headers=oidc_auth_headers())
        assert out.status_code==400
        assert out.json()=={'detail':'SITE_TEST_TYPE_ERROR'}
