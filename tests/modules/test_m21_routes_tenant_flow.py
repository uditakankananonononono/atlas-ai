"""Booted-app Claire routes, per tenant. Dev-mode tenant headers = TEST MODE (not production auth proof)."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
import app.modules.m21_claire.routes as R

A={"x-atlas-tenant":"cl-a","x-atlas-actor":"a"}; B={"x-atlas-tenant":"cl-b","x-atlas-actor":"b"}
@pytest.fixture
def c(monkeypatch):
    monkeypatch.setattr(R,"_services",{}); monkeypatch.setattr(R,"_pairings",{}); monkeypatch.setattr(R,"_service",None)
    return TestClient(app,raise_server_exceptions=False)

def test_goal_intake_works_in_booted_app_and_is_tenant_scoped(c):
    r=c.post("/api/v1/claire/goals",json={"goal":"Draft a weekly study plan","acceptance":["5 days"],"limits":{}},headers=A)
    assert r.status_code==201,r.text
    gid=r.json().get("id") or r.json().get("goal_id"); assert gid
    # tenant B never saw A's goal
    assert c.post(f"/api/v1/claire/goals/{gid}/realize",headers=B).status_code==404
    assert c.post(f"/api/v1/claire/goals/{gid}/environment-changes",json={"operation":"x","preview":{}},headers=B).status_code==404

def test_device_list_is_per_tenant(c):
    ch=c.post("/api/v1/claire/devices/pairing-challenge",headers=A); assert ch.status_code==200
    assert c.get("/api/v1/claire/devices",headers=B).json()==[]
    assert c.post("/api/v1/claire/devices/pair",json={"server_nonce":ch.json()["server_nonce"],"code":ch.json()["code"],"name":"d","certificate_fingerprint":"f","capabilities":["x"]},headers=B).status_code==422  # B cannot complete A's challenge

def test_tenant_service_cap_fails_closed(c,monkeypatch):
    monkeypatch.setattr(R,"MAX_TENANT_SERVICES",1)
    assert c.post("/api/v1/claire/goals",json={"goal":"Draft a weekly study plan 1","acceptance":["5 days"]},headers=A).status_code==201
    assert c.post("/api/v1/claire/goals",json={"goal":"Draft a weekly study plan 2","acceptance":["5 days"]},headers=B).status_code==503
    assert c.post("/api/v1/claire/goals",json={"goal":"Draft a weekly study plan 3","acceptance":["5 days"]},headers=A).status_code==201


def test_tenant_var_is_reset_after_dependency_and_not_reused_across_requests(c):
    import asyncio
    from app.modules.m20_general_cognitive_worker.routes import _tenant_var
    from app.auth.context import TenantContext
    async def run():
        assert _tenant_var.get() is None
        gen=R.get_service(TenantContext("cl-x","x"))
        svc=await gen.__anext__()
        assert _tenant_var.get()=="cl-x"
        with pytest.raises(StopAsyncIteration): await gen.__anext__()
        assert _tenant_var.get() is None  # reset in finally
        g2=R.get_service(TenantContext("cl-y","y")); s2=await g2.__anext__()
        assert s2 is not svc  # distinct per tenant, same-context reuse does not leak
        await g2.aclose()
    asyncio.run(run())


def test_environment_change_approval_is_owned_by_the_requesting_tenant_and_not_decidable_by_another(c):
    from app.core.approvals import approvals
    from app.core.models import ApprovalStatus
    gid=c.post("/api/v1/claire/goals",json={"goal":"Draft a weekly study plan","acceptance":["5 days"]},headers=A).json()
    gid=gid.get("id") or gid.get("goal_id")
    r=c.post(f"/api/v1/claire/goals/{gid}/environment-changes",json={"operation":"write_file","preview":{"path":"FIXTURE.txt"}},headers=A)
    assert r.status_code==201,r.text
    aid=r.json()["id"]
    assert approvals.get(aid,user_id="cl-a") is not None
    assert approvals.get(aid,user_id="cl-b") is None                       # B cannot read it
    assert aid not in [x.id for x in approvals.list(user_id="cl-b")]
    assert approvals.decide(aid,ApprovalStatus.APPROVED,user_id="cl-b") is None   # B cannot decide it
    assert approvals.get(aid,user_id="cl-a").status!=ApprovalStatus.APPROVED
    assert approvals.decide(aid,ApprovalStatus.DENIED,user_id="cl-a") is not None  # owner control: works
