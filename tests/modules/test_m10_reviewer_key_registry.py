"""M10 reviewer key governance: identity binding, proof-of-possession, rotation, retirement, audit."""
import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import app
from app.modules.m10_email_assistant import reviewer_key_registry as rk
from app.modules.m10_email_assistant.routes import get_reviewer_key_registry

C = TestClient(app)
U = "/api/v1/email-assistant/promise-state-reconciliation/reviewer-keys"
V = "/api/v1/email-assistant/promise-state-reconciliation/evidence/verify"
OWNER = {"X-Atlas-Tenant": "t", "X-Atlas-Actor": "owner"}
OTHER = {"X-Atlas-Tenant": "t", "X-Atlas-Actor": "mallory"}
SESSIONS = {}


def setup_function():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    SESSIONS["s"] = sessionmaker(bind=e, expire_on_commit=False)
    roles = {"admin": frozenset({"atlas-admin"})}

    def dep(request_actor=None):
        return None

    from fastapi import Header

    def override(x_atlas_actor: str = Header(default="local-user"), x_atlas_role: str | None = Header(default=None)):
        return rk.ReviewerKeyRegistry("t", SESSIONS["s"], actor_id=x_atlas_actor, roles=roles.get(x_atlas_role or "", frozenset()))

    app.dependency_overrides[get_reviewer_key_registry] = override


def teardown_function():
    app.dependency_overrides.clear()


def keypair():
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private, raw, hashlib.sha256(raw).hexdigest()


def b64(x):
    return base64.b64encode(x).decode()


def enroll_body(private, raw, fp, reviewer="owner", key_id="v1", tenant="t"):
    proof = private.sign(rk.enrollment_statement(tenant, reviewer, key_id, fp))
    return {"reviewer_id": reviewer, "key_id": key_id, "public_key_base64": b64(raw), "proof_signature_base64": b64(proof)}


def attestation(private, reviewer="owner", key_id="v1"):
    a = {"reviewer_id": reviewer, "decision_sha256": "a" * 64, "key_id": key_id}
    a["signature_base64"] = b64(private.sign(json.dumps(a, sort_keys=True, separators=(",", ":")).encode()))
    msg = b"I sent it"
    return {"messages": [{"message_id": "m", "content_base64": b64(msg), "content_sha256": hashlib.sha256(msg).hexdigest()}],
            "attestations": [a]}


def test_self_enrollment_with_proof_then_verification_uses_registry():
    k, raw, fp = keypair()
    r = C.post(U, json=enroll_body(k, raw, fp), headers=OWNER)
    assert r.status_code == 200 and r.json()["fingerprint_sha256"] == fp and r.json()["enrolled_by"] == "owner"
    assert C.post(U, json=enroll_body(k, raw, fp), headers=OWNER).status_code == 200  # idempotent
    r = C.post(V, json=attestation(k), headers=OWNER)
    assert r.status_code == 200 and r.json()["reviewers"][0]["signature_verified"] is True


def test_caller_supplied_keys_are_not_trusted():
    k, raw, fp = keypair()
    body = attestation(k)
    body["trusted_reviewer_public_keys"] = {"v1": b64(raw)}  # old bypass: bring your own key
    r = C.post(V, json=body, headers=OWNER)
    assert r.status_code == 422 and "untrusted reviewer key" in r.text


def test_cannot_enroll_for_someone_else_or_without_holding_key():
    k, raw, fp = keypair()
    r = C.post(U, json=enroll_body(k, raw, fp), headers=OTHER)
    assert r.status_code == 403 and "only reviewer" in r.text
    other, _, _ = keypair()
    bad = enroll_body(k, raw, fp)
    bad["proof_signature_base64"] = b64(other.sign(rk.enrollment_statement("t", "owner", "v1", fp)))
    r = C.post(U, json=bad, headers=OWNER)
    assert r.status_code == 403 and "proof-of-possession" in r.text
    # proof for a different tenant does not replay here
    r = C.post(U, json=enroll_body(k, raw, fp, tenant="other-tenant"), headers=OWNER)
    assert r.status_code == 403
    events = [e["event"] for e in C.get(f"{U}/owner/events", headers=OWNER).json()]
    assert events.count("enroll_refused") == 3


def test_admin_can_enroll_for_reviewer():
    k, raw, fp = keypair()
    r = C.post(U, json=enroll_body(k, raw, fp), headers={**OTHER, "X-Atlas-Role": "admin"})
    assert r.status_code == 200 and r.json()["enrolled_by"] == "mallory"


def test_attestation_must_match_key_owner():
    k, raw, fp = keypair()
    C.post(U, json=enroll_body(k, raw, fp), headers=OWNER)
    # mallory signs claiming to be owner with owner's key id: key lookup is by (reviewer, key)
    m, mraw, mfp = keypair()
    C.post(U, json=enroll_body(m, mraw, mfp, reviewer="mallory", key_id="m1"), headers=OTHER)
    r = C.post(V, json=attestation(m, reviewer="owner", key_id="m1"), headers=OWNER)
    assert r.status_code == 422 and "untrusted reviewer key" in r.text
    r = C.post(V, json=attestation(m, reviewer="owner", key_id="v1"), headers=OWNER)
    assert r.status_code == 422 and "invalid reviewer signature" in r.text


def test_one_active_key_and_rotation_with_continuity():
    k1, raw1, fp1 = keypair()
    C.post(U, json=enroll_body(k1, raw1, fp1), headers=OWNER)
    k2, raw2, fp2 = keypair()
    r = C.post(U, json=enroll_body(k2, raw2, fp2, key_id="v2"), headers=OWNER)
    assert r.status_code == 409 and "rotate instead" in r.text
    rot = {"new_key_id": "v2", "new_public_key_base64": b64(raw2),
           "proof_signature_base64": b64(k2.sign(rk.enrollment_statement("t", "owner", "v2", fp2))),
           "endorsement_signature_base64": b64(k1.sign(rk.rotation_statement("t", "owner", "v1", "v2", fp2)))}
    r = C.post(f"{U}/owner/rotate", json=rot, headers=OWNER)
    assert r.status_code == 200 and r.json()["mode"] == "continuity" and r.json()["old_key_id"] == "v1"
    keys = {k["key_id"]: k for k in C.get(U, params={"reviewer_id": "owner"}, headers=OWNER).json()}
    assert keys["v1"]["active"] is False and keys["v1"]["replaced_by_key_id"] == "v2" and keys["v2"]["active"] is True
    assert C.post(V, json=attestation(k1, key_id="v1"), headers=OWNER).status_code == 422  # retired key never verifies
    assert C.post(V, json=attestation(k2, key_id="v2"), headers=OWNER).status_code == 200


def test_rotation_without_endorsement_needs_admin_and_is_recorded_as_recovery():
    k1, raw1, fp1 = keypair()
    C.post(U, json=enroll_body(k1, raw1, fp1), headers=OWNER)
    k2, raw2, fp2 = keypair()
    rot = {"new_key_id": "v2", "new_public_key_base64": b64(raw2),
           "proof_signature_base64": b64(k2.sign(rk.enrollment_statement("t", "owner", "v2", fp2)))}
    r = C.post(f"{U}/owner/rotate", json=rot, headers=OWNER)
    assert r.status_code == 403 and "endorsement" in r.text
    wrong = {**rot, "endorsement_signature_base64": b64(k2.sign(rk.rotation_statement("t", "owner", "v1", "v2", fp2)))}
    assert C.post(f"{U}/owner/rotate", json=wrong, headers=OWNER).status_code == 403  # new key can't endorse itself
    r = C.post(f"{U}/owner/rotate", json=rot, headers={**OTHER, "X-Atlas-Role": "admin"})
    assert r.status_code == 200 and r.json()["mode"] == "recovery"
    events = C.get(f"{U}/owner/events", headers=OWNER).json()
    assert any(e["event"] == "rotated" and e["details"]["mode"] == "recovery" and e["actor"] == "mallory" for e in events)


def test_retire_with_reason_blocks_verification_and_reenrollment():
    k, raw, fp = keypair()
    C.post(U, json=enroll_body(k, raw, fp), headers=OWNER)
    assert C.post(f"{U}/owner/v1/retire", json={"reason": "laptop stolen"}, headers=OTHER).status_code == 403
    r = C.post(f"{U}/owner/v1/retire", json={"reason": "laptop stolen"}, headers=OWNER)
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["retire_reason"] == "laptop stolen"
    r = C.post(V, json=attestation(k), headers=OWNER)
    assert r.status_code == 422 and "retired" in r.text
    r = C.post(U, json=enroll_body(k, raw, fp), headers=OWNER)
    assert r.status_code == 409 and "cannot be re-enrolled" in r.text
    assert C.post(f"{U}/owner/nope/retire", json={"reason": "gone"}, headers=OWNER).status_code == 404


def test_rejects_rebinding_and_invalid_length():
    k, raw, fp = keypair()
    assert C.post(U, json=enroll_body(k, raw, fp), headers=OWNER).status_code == 200
    k2, raw2, fp2 = keypair()
    r = C.post(U, json=enroll_body(k2, raw2, fp2), headers=OWNER)
    assert r.status_code == 409 and "different public key bytes" in r.text
    body = enroll_body(k, raw, fp)
    body["public_key_base64"] = b64(b"short")
    r = C.post(U, json=body, headers=OWNER)
    assert r.status_code == 409 and "must be 32 bytes" in r.text


def test_tenant_isolation():
    k, raw, fp = keypair()
    SESSIONS_T2 = SESSIONS["s"]
    a = rk.ReviewerKeyRegistry("t", SESSIONS_T2, actor_id="owner")
    a.register(rk.RegisterReviewerKey(**enroll_body(k, raw, fp)))
    b = rk.ReviewerKeyRegistry("t2", SESSIONS_T2, actor_id="owner")
    with pytest.raises(LookupError):
        b.active_public_key("owner", "v1")
