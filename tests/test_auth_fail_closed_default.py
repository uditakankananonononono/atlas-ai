from fastapi.testclient import TestClient
from app.main import app
BASE='/api/v1/api/modules/20/optimization-story-235-280/admm'


def test_unset_environment_requires_auth_even_with_forged_headers(monkeypatch):
 monkeypatch.delenv('ATLAS_ENV',raising=False);monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
 c=TestClient(app)
 assert c.post(BASE,headers={'X-Atlas-Tenant':'a','X-Atlas-Actor':'b'},json={'payload':{}}).status_code==401


def test_development_label_alone_does_not_disable_auth(monkeypatch):
 monkeypatch.setenv('ATLAS_ENV','development');monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==401


def test_explicit_insecure_opt_in_warns_and_never_overrides_production(monkeypatch,caplog):
 monkeypatch.delenv('ATLAS_ENV',raising=False);monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1')
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==422
 assert 'INSECURE DEVELOPMENT AUTH BYPASS' in caplog.text
 monkeypatch.setenv('ATLAS_ENV','production')
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==401
