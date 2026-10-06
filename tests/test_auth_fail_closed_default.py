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
 monkeypatch.setenv('ATLAS_ENV','development');monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1')
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==422
 assert 'INSECURE DEVELOPMENT AUTH BYPASS' in caplog.text
 monkeypatch.setenv('ATLAS_ENV','production')
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==401


import pytest
@pytest.mark.parametrize('environment',[None,'','prod','staging','live','production ','production','garbage'])
def test_opt_in_cannot_bypass_unknown_or_deployed_environment(monkeypatch,environment):
 monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1')
 if environment is None:monkeypatch.delenv('ATLAS_ENV',raising=False)
 else:monkeypatch.setenv('ATLAS_ENV',environment)
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==401

@pytest.mark.parametrize('environment',['development','local',' local '])
def test_only_explicit_local_environments_can_use_opt_in(monkeypatch,environment):
 monkeypatch.setenv('ATLAS_DEV_NO_AUTH','1');monkeypatch.setenv('ATLAS_ENV',environment)
 assert TestClient(app).post(BASE,json={'payload':{}}).status_code==422

def test_platform_default_and_auth_share_fail_closed_environment_policy():
 from app.auth.environment import atlas_environment,insecure_development_auth_enabled
 from app.platform.config import ProductionConfig,ConfigError
 assert atlas_environment({})=='production'
 assert not insecure_development_auth_enabled({'ATLAS_DEV_NO_AUTH':'1'})
 with pytest.raises(ConfigError):ProductionConfig.from_env({})
