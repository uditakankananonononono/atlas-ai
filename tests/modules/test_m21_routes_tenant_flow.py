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
