"""Slice 14 (Step 2A): /claire/devices/* are tenant-scoped. Base 8a13da2e had one global PairingService for every tenant.

SCOPE LIMITS (verbatim): still in-memory and per-process (no persistence or mTLS issuance); NO role restriction, so any authenticated member WITHIN a tenant
can pair, revoke and list that tenant's devices - this is not an owner-only device-control guarantee; no actor binding; the receipt hash chain
authenticates neither OS execution nor payload truth; local_action token enforcement is Step 2B and is untouched. Probes with the dev-auth opt-in
(suite fixture) and a dependency override prove the tenant logic, not production credentials/roles/deployment.
Labels: PROTECTION = pre-existing behaviour that must hold (verified GREEN on base, incl. exact response key sets). NEW = failed on base. CONVERTED = the audit CHARACTERIZATION, now a protection.
"""
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from app.auth.context import TenantContext, require_tenant
from app.main import app
from app.modules.m21_claire import routes as claire_routes
from app.modules.m21_claire.local_client_protocol import AuditChain, PairingService


def pair(p, tenant):
    c = p.challenge(tenant_id=tenant)
    return p.confirm(c.server_nonce, c.code, "pc", "fp", {"commands"}, tenant_id=tenant)


# ---- library: required-tenant mode and legacy namespace -------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, "", "   ", 7])
def test_NEW_required_tenant_mode_fails_before_any_lookup_or_mutation_for_every_method(bad):
    p = PairingService(require_tenant=True)
    good = pair(p, "t1")
    before = (dict(p.pending), {k: v.revoked for k, v in p.devices.items()})
    with pytest.raises(ValueError, match="tenant is required"):
        p.challenge(tenant_id=bad)
    with pytest.raises(ValueError, match="tenant is required"):
        p.confirm("n", "1", "pc", "fp", {"c"}, tenant_id=bad)
    with pytest.raises(ValueError, match="tenant is required"):
        p.list_devices(bad)
    with pytest.raises(ValueError, match="tenant is required"):
        p.revoke(good.id, tenant_id=bad)
    with pytest.raises(ValueError, match="tenant is required"):
        p.verify_receipt(good.id, [{}], tenant_id=bad)
    assert (dict(p.pending), {k: v.revoked for k, v in p.devices.items()}) == before


def test_NEW_blank_tenant_string_is_rejected_even_in_library_mode_but_none_is_the_legacy_namespace():
    p = PairingService()
    with pytest.raises(ValueError, match="tenant is required"):
        p.challenge(tenant_id="")
    assert pair(p, None).tenant_id is None


def test_NEW_legacy_none_namespace_is_never_a_wildcard_over_scoped_records_on_the_same_service():
    p = PairingService()
    scoped, legacy = pair(p, "t1"), pair(p, None)
    assert [d.id for d in p.list_devices(None)] == [legacy.id]
    assert [d.id for d in p.list_devices("t1")] == [scoped.id]
    with pytest.raises(KeyError):
        p.revoke(scoped.id)                       # legacy caller cannot reach a scoped device
    with pytest.raises(KeyError):
        p.revoke(legacy.id, tenant_id="t1")       # scoped caller cannot reach a legacy device
    assert not scoped.revoked and not legacy.revoked


def test_NEW_foreign_nonce_is_refused_like_an_unknown_one_and_does_not_consume_the_rightful_challenge():
    p = PairingService(require_tenant=True)
    c = p.challenge(tenant_id="t1")
    with pytest.raises(KeyError):
        p.confirm(c.server_nonce, c.code, "pc", "fp", {"c"}, tenant_id="t2")
    with pytest.raises(KeyError):
        p.confirm("unknown-nonce", c.code, "pc", "fp", {"c"}, tenant_id="t2")
    assert c.server_nonce in p.pending
    assert p.confirm(c.server_nonce, c.code, "pc", "fp", {"c"}, tenant_id="t1").tenant_id == "t1"


def test_NEW_foreign_revoke_and_receipt_are_denied_before_any_flag_or_fingerprint():
    p = PairingService(require_tenant=True)
    d = pair(p, "t1")
    chain = AuditChain(d.id)
    chain.append("a", "completed", {"ok": True})
    events = [asdict(x) for x in chain.events]
    with pytest.raises(KeyError):
        p.revoke(d.id, tenant_id="t2")
    with pytest.raises(KeyError):
        p.verify_receipt(d.id, events, tenant_id="t2")
    assert d.revoked is False
    assert p.verify_receipt(d.id, events, tenant_id="t1")["certificate_fingerprint"] == "fp"


def test_PROTECTION_existing_library_use_without_tenant_is_unchanged():
    p = PairingService()
    c = p.challenge()
    d = p.confirm(c.server_nonce, c.code, "lab-pc", "sha256:fingerprint", {"commands"})
    chain = AuditChain(d.id)
    chain.append("a", "completed", {"exit_code": 0})
    assert p.verify_receipt(d.id, [asdict(x) for x in chain.events])["receipt_complete"]
    p.revoke(d.id)
    with pytest.raises(ValueError, match="revoked"):
        p.verify_receipt(d.id, [asdict(x) for x in chain.events])


# ---- routes ---------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def client():
    claire_routes._pairing.pending.clear()
    claire_routes._pairing.devices.clear()
    who = {"ctx": TenantContext("t1", "u1")}
    app.dependency_overrides[require_tenant] = lambda: who["ctx"]
    c = TestClient(app)
    c.who = who
    yield c
    app.dependency_overrides.pop(require_tenant, None)
    claire_routes._pairing.pending.clear()
    claire_routes._pairing.devices.clear()


def route_pair(c):
    ch = c.post("/api/v1/claire/devices/pairing-challenge").json()
    body = {"server_nonce": ch["server_nonce"], "code": ch["code"], "name": "pc", "certificate_fingerprint": "fp", "capabilities": ["commands"]}
    return ch, body


def test_NEW_other_tenant_cannot_list_revoke_or_verify_and_all_denials_share_one_404_body(client):
    ch, body = route_pair(client)
    dev = client.post("/api/v1/claire/devices/pair", json=body).json()
    client.who["ctx"] = TenantContext("t2", "u2")
    assert client.get("/api/v1/claire/devices").json() == []                      # CONVERTED: audit CHARACTERIZATION_device_pairing_routes_*
    chain = AuditChain(dev["id"])
    chain.append("a", "completed", {"ok": True})
    ev = {"events": [asdict(x) for x in chain.events]}
    foreign = [client.delete(f"/api/v1/claire/devices/{dev['id']}"), client.post(f"/api/v1/claire/devices/{dev['id']}/verify-receipt", json=ev)]
    unknown = [client.delete("/api/v1/claire/devices/nope"), client.post("/api/v1/claire/devices/nope/verify-receipt", json=ev)]
    assert {(r.status_code, str(r.json())) for r in foreign + unknown} == {(404, "{'detail': 'device not found'}")}
    client.who["ctx"] = TenantContext("t1", "u1")
    assert [d["revoked"] for d in client.get("/api/v1/claire/devices").json()] == [False]   # t1's device untouched
    assert client.delete(f"/api/v1/claire/devices/{dev['id']}").status_code == 200           # same-tenant revoke still works
    client.who["ctx"] = TenantContext("t2", "u2")
    revoked_foreign = client.delete(f"/api/v1/claire/devices/{dev['id']}")                   # foreign REVOKED id: same body as unknown
    assert (revoked_foreign.status_code, revoked_foreign.json()) == (404, {"detail": "device not found"})


def test_NEW_foreign_nonce_body_equals_unknown_nonce_body_and_rightful_confirm_still_succeeds(client):
    ch, body = route_pair(client)
    client.who["ctx"] = TenantContext("t2", "u2")
    foreign = client.post("/api/v1/claire/devices/pair", json=body)
    unknown = client.post("/api/v1/claire/devices/pair", json={**body, "server_nonce": "nope"})
    assert (foreign.status_code, foreign.json()) == (unknown.status_code, unknown.json()) == (422, {"detail": "pairing challenge not found"})
    client.who["ctx"] = TenantContext("t1", "u1")
    assert client.post("/api/v1/claire/devices/pair", json=body).status_code == 200


def test_PROTECTION_public_projections_keep_the_exact_key_sets_and_never_expose_tenant_id(client):
    ch, body = route_pair(client)
    assert set(ch) == {"server_nonce", "code", "expires_at"}
    dev = client.post("/api/v1/claire/devices/pair", json=body).json()
    assert set(dev) == {"id", "name", "certificate_fingerprint", "capabilities", "revoked"}
    assert set(client.get("/api/v1/claire/devices").json()[0]) == set(dev)
    chain = AuditChain(dev["id"])
    chain.append("a", "completed", {"ok": True})
    rec = client.post(f"/api/v1/claire/devices/{dev['id']}/verify-receipt", json={"events": [asdict(x) for x in chain.events]}).json()
    assert "tenant_id" not in rec and {"device_id", "certificate_fingerprint", "events_verified", "chain_head", "terminal_phase", "receipt_complete", "boundary"} <= set(rec)


def test_NEW_route_service_is_in_required_tenant_mode_and_handlers_fail_on_a_missing_tenant_before_any_lookup(client):
    assert claire_routes._pairing.require_tenant is True
    dev = claire_routes._pairing.confirm(*(lambda c: (c.server_nonce, c.code, "pc", "fp", {"c"}))(claire_routes._pairing.challenge(tenant_id="t1")), tenant_id="t1")
    for blank in (TenantContext("", "u"), TenantContext("  ", "u")):
        with pytest.raises(ValueError, match="tenant is required"):
            claire_routes.devices(tenant=blank)
        with pytest.raises(ValueError, match="tenant is required"):
            claire_routes.revoke_device(dev.id, tenant=blank)
        with pytest.raises(ValueError, match="tenant is required"):
            claire_routes.pairing_challenge(tenant=blank)
    assert dev.revoked is False


def test_PROTECTION_unauthenticated_device_calls_are_401_with_deployment_auth_defaults(monkeypatch):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.delenv("ATLAS_ENV", raising=False)
    app.dependency_overrides.pop(require_tenant, None)
    c = TestClient(app)
    assert [c.get("/api/v1/claire/devices").status_code, c.post("/api/v1/claire/devices/pairing-challenge").status_code,
            c.delete("/api/v1/claire/devices/x").status_code] == [401, 401, 401]
