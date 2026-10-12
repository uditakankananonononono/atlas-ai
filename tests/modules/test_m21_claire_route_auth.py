"""Claire goal and device routes are behind require_tenant through the include in app.main.

Checked by behavior (no header: 401/403; header: handler reached), which does not depend on
how the installed FastAPI represents included routers."""
from fastapi.testclient import TestClient
from app.main import app

CLAIRE_PREFIX = "/api/v1/claire"


def test_goal_and_device_routes_exist_and_work_with_tenant_header():
    c = TestClient(app)
    h = {"x-atlas-tenant": "t1", "x-atlas-actor": "a1"}
    assert c.get(CLAIRE_PREFIX + "/devices", headers=h).status_code == 200
    assert c.post(CLAIRE_PREFIX + "/devices/pairing-challenge", headers=h).status_code == 200
    # no cognitive service bound for this tenant: a clean 503 from the dependency, not a 500
    assert c.post(CLAIRE_PREFIX + "/goals", headers=h, json={"goal": "x", "acceptance": ["y"], "limits": {}}).status_code == 503
    assert c.delete(CLAIRE_PREFIX + "/devices/missing", headers=h).status_code == 404


def test_goal_and_pairing_endpoints_reject_unauthenticated_requests(monkeypatch):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    c = TestClient(app)
    calls = [("post", "/goals", {"goal": "x", "acceptance": ["y"], "limits": []}),
             ("post", "/goals/g1/realize", None),
             ("post", "/goals/g1/environment-changes", {"operation": "o", "preview": {}}),
             ("post", "/devices/pairing-challenge", None),
             ("post", "/devices/pair", {"server_nonce": "n", "code": "c", "name": "d", "certificate_fingerprint": "f", "capabilities": []}),
             ("get", "/devices", None),
             ("delete", "/devices/d1", None),
             ("post", "/devices/d1/verify-receipt", {"events": [{}]})]
    for method, path, body in calls:
        r = getattr(c, method)(CLAIRE_PREFIX + path, **({"json": body} if body is not None else {}))
        assert r.status_code in (401, 403), (method, path, r.status_code)


def test_goals_and_pairing_state_are_per_tenant(monkeypatch):
    from app.modules.m20_general_cognitive_worker import routes as gcw
    from app.modules.m21_claire import routes as claire
    monkeypatch.setitem(gcw._services, "t1", object())
    monkeypatch.setitem(gcw._services, "t2", object())
    monkeypatch.setattr(claire, "_services", {})
    monkeypatch.setattr(claire, "_pairings", {})
    c = TestClient(app)
    h1 = {"x-atlas-tenant": "t1", "x-atlas-actor": "a"}
    h2 = {"x-atlas-tenant": "t2", "x-atlas-actor": "a"}
    r = c.post(CLAIRE_PREFIX + "/goals", headers=h1, json={"goal": "plan x", "acceptance": ["y"], "limits": {}})
    assert r.status_code == 201
    gid = r.json()["id"]
    assert c.post(CLAIRE_PREFIX + f"/goals/{gid}/environment-changes", headers=h2, json={"operation": "bogus", "preview": {}}).status_code == 404
    assert c.post(CLAIRE_PREFIX + f"/goals/{gid}/environment-changes", headers=h1, json={"operation": "bogus", "preview": {}}).status_code == 422
    ch = c.post(CLAIRE_PREFIX + "/devices/pairing-challenge", headers=h1).json()
    assert ch["server_nonce"]
    assert len(claire._pairings) == 1 and set(claire._pairings) == {"t1"}
    assert c.get(CLAIRE_PREFIX + "/devices", headers=h2).json() == []
