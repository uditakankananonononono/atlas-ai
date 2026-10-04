"""Operator-owned env credentials are not a grant for every tenant (m17 collectors, m06 platform tokens, core helper).
Dev-mode tenant headers = TEST MODE. Fixtures only; no network."""
import pytest
from fastapi.testclient import TestClient
from app.core.operator_accounts import operator_account_granted
from app.main import app
import app.modules.m06_social_media_manager.routes as M06
import app.modules.m17_narrative_architect.routes as M17
from app.modules.m17_narrative_architect.service import Service as NService

def test_core_helper_exact_ids_only_no_wildcard(monkeypatch):
    monkeypatch.setenv("ATLAS_OPERATOR_ACCOUNT_TENANTS"," t1 , t2 ,*")
    assert operator_account_granted("t1") and operator_account_granted("t2")
    assert not operator_account_granted("t3") and not operator_account_granted("") and not operator_account_granted(None)
    assert not operator_account_granted("anything")      # '*' is just a literal id, not a wildcard
    monkeypatch.delenv("ATLAS_OPERATOR_ACCOUNT_TENANTS"); assert not operator_account_granted("t1")

def test_m06_env_tokens_only_reach_granted_tenants(monkeypatch):
    for k in ("ATLAS_META_ACCESS_TOKEN","ATLAS_X_BEARER_TOKEN","ATLAS_LINKEDIN_ACCESS_TOKEN","ATLAS_TIKTOK_ACCESS_TOKEN"): monkeypatch.setenv(k,"FIXTURE-NOT-A-REAL-TOKEN")
    monkeypatch.setenv("ATLAS_OPERATOR_ACCOUNT_TENANTS","granted")
    assert M06._env_credentials("granted").x_bearer_token=="FIXTURE-NOT-A-REAL-TOKEN"
    for t in ("other",None,""):
        c=M06._env_credentials(t)
        assert (c.meta_access_token,c.x_bearer_token,c.linkedin_access_token,c.tiktok_access_token)==(None,None,None,None)

def test_m06_adapter_factory_and_worker_pass_the_tenant(monkeypatch):
    seen=[]
    monkeypatch.setattr(M06,"build_adapter",lambda name,creds:seen.append((name,creds.x_bearer_token)) or object())
    monkeypatch.setenv("ATLAS_X_BEARER_TOKEN","FIXTURE-NOT-A-REAL-TOKEN"); monkeypatch.setenv("ATLAS_OPERATOR_ACCOUNT_TENANTS","granted")
    class P: value="x"
    M06._EnvAdapterFactory("other").for_platform(P()); M06._EnvAdapterFactory("granted").for_platform(P())
    assert seen==[("x",None),("x","FIXTURE-NOT-A-REAL-TOKEN")]

@pytest.mark.asyncio
async def test_m17_credentialed_platform_needs_grant_and_public_does_not(monkeypatch):
    from app.modules.m17_narrative_architect.schemas import CollectIn
    class Col:
        calls=0
        async def collect(self,q,l): Col.calls+=1; return []
    monkeypatch.delenv("ATLAS_OPERATOR_ACCOUNT_TENANTS",raising=False)
    s=NService(generate=None,collectors={"youtube":Col(),"pinterest":Col(),"reddit":Col()})
    for p in ("youtube","pinterest"):
        with pytest.raises(PermissionError): await s.collect(CollectIn(query="college essay",platforms=[p],owner_id="t-no"))
    assert Col.calls==0
    await s.collect(CollectIn(query="college essay",platforms=["reddit"],owner_id="t-no")); assert Col.calls==1   # public: not gated
    monkeypatch.setenv("ATLAS_OPERATOR_ACCOUNT_TENANTS","t-yes")
    await s.collect(CollectIn(query="college essay",platforms=["youtube"],owner_id="t-yes")); assert Col.calls==2

def test_m17_route_maps_to_403(monkeypatch):
    class Col:
        async def collect(self,q,l): return []
    monkeypatch.delenv("ATLAS_OPERATOR_ACCOUNT_TENANTS",raising=False)
    monkeypatch.setattr(M17,"_service",NService(generate=None,collectors={"youtube":Col()}))
    r=TestClient(app,raise_server_exceptions=False).post("/api/v1/narrative-architect/advice",json={"query":"college essay","platforms":["youtube"]},headers={"x-atlas-tenant":"t-no","x-atlas-actor":"u"})
    assert r.status_code==403,r.text
