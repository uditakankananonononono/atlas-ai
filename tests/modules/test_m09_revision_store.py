import base64
import hashlib
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m09_knowledge_workspace.contradiction_revisions import DecisionRevision
from app.modules.m09_knowledge_workspace.revision_store import (KeyGovernanceError, RevisionConflict, RevisionRejected,
                                                                RevisionRow, RevisionStore, SourceBlobRow, SourceBlobStore,
                                                                enrollment_statement, key_id_for, revision_sha256,
                                                                rotation_statement, verify_sources)

T0 = datetime(2026, 9, 24, tzinfo=timezone.utc)
A, B = b"paper A says n=40", b"paper B says n=44"


def rev(i, prev=None, actor="owner", action="retain_both"):
    return DecisionRevision.model_validate({
        "revision_id": f"r{i}", "claim_key": "Sample size", "action": action,
        "preferred_evidence_id": "e1" if action == "prefer" else None, "rationale": "review",
        "decided_at": f"2026-09-2{i}T08:00:00Z", "actor_id": actor, "previous_revision_sha256": prev,
        "source_snapshots": [{"evidence_id": "e1", "content_sha256": hashlib.sha256(A).hexdigest()},
                             {"evidence_id": "e2", "content_sha256": hashlib.sha256(B).hexdigest()}]})


@pytest.fixture
def sf(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'r.db'}"); Base.metadata.create_all(e)
    return sessionmaker(bind=e)


def store(sf, tenant="t1", actor="owner", clock=None, roles=frozenset()):
    return RevisionStore(tenant, actor, session_factory=sf, clock=clock or (lambda: T0), roles=roles)


def pubkey(priv):
    return base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def proof(priv, pub, tenant="t1", actor="owner"):
    return base64.b64encode(priv.sign(enrollment_statement(tenant, actor, key_id_for(pub)))).decode()


def sign(priv, r):
    return base64.b64encode(priv.sign(revision_sha256(r).encode())).decode()


def test_compare_and_append_and_chain(sf):
    s = store(sf)
    r1 = rev(1); out = s.append(r1)
    assert out["seq"] == 1 and out["sha256"] == revision_sha256(r1)
    with pytest.raises(RevisionConflict, match="stale head"):
        s.append(rev(2, prev=None))
    s.append(rev(2, prev=out["sha256"], action="prefer"))
    with pytest.raises(RevisionConflict):  # duplicate revision_id on a fresh claim chain position
        s.append(rev(2, prev=s.chain("sample size")["head_sha256"], action="prefer"))
    c = s.chain("  SAMPLE SIZE ")
    assert c["valid"] and c["revision_count"] == 2 and c["latest_decision"]["action"] == "prefer"
    with pytest.raises(LookupError):
        store(sf, tenant="t2").chain("sample size")


def test_actor_binding_and_tamper_detection(sf):
    with pytest.raises(RevisionRejected, match="authenticated actor"):
        store(sf).append(rev(1, actor="someone_else"))
    s = store(sf); s.append(rev(1))
    with sf.begin() as db:
        db.execute(update(RevisionRow).values(payload=rev(1).model_dump(mode="json") | {"rationale": "edited later"}))
    c = s.chain("sample size")
    assert not c["valid"] and "no longer matches" in c["problems"][0]


def test_signatures_required_once_key_registered(sf):
    priv = Ed25519PrivateKey.generate()
    pub = base64.b64encode(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    s = store(sf)
    with pytest.raises(RevisionRejected, match="no registered key"):
        s.append(rev(1), signature_b64=base64.b64encode(b"x" * 64).decode())
    assert len(s.register_key(pub, proof(priv, pub))["key_id"]) == 32
    with pytest.raises(RevisionRejected, match="must be signed"):
        s.append(rev(1))
    other = Ed25519PrivateKey.generate()
    r1 = rev(1)
    bad = base64.b64encode(other.sign(revision_sha256(r1).encode())).decode()
    with pytest.raises(RevisionRejected, match="does not verify"):
        s.append(r1, signature_b64=bad)
    good = base64.b64encode(priv.sign(revision_sha256(r1).encode())).decode()
    assert s.append(r1, signature_b64=good)["signed_key_id"]
    assert s.chain("sample size")["valid"]
    with pytest.raises(RevisionRejected):
        s.register_key("not-a-key", "x")


def test_verify_sources_with_injected_fetch():
    pages = {"https://a.test/p": A, "https://b.test/p": b"paper B was edited"}
    def fetch(u):
        if u not in pages: raise OSError("down")
        return pages[u]
    out = verify_sources(rev(1), {"e1": "https://a.test/p", "e2": "https://b.test/p"}, fetch=fetch)
    assert [x["status"] for x in out["sources"]] == ["match", "mismatch"] and not out["all_match"]
    out = verify_sources(rev(1), {"e1": "https://gone.test/"}, fetch=fetch)
    assert [x["status"] for x in out["sources"]] == ["unreachable", "no_uri"]


def test_real_fetch_blocks_private_hosts():
    out = verify_sources(rev(1), {"e1": "http://127.0.0.1/secret", "e2": "http://169.254.169.254/latest"})
    assert all(x["status"] == "unreachable" for x in out["sources"])


def test_http_routes(sf, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m09_knowledge_workspace import routes
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t1", actor_id="owner")
    app.dependency_overrides[routes.get_revision_store] = lambda: store(sf)
    cl = TestClient(app)
    r1 = rev(1).model_dump(mode="json")
    ok = cl.post("/knowledge-workspace/contradiction-revisions", json={"revision": r1})
    assert ok.status_code == 201, ok.text
    assert cl.post("/knowledge-workspace/contradiction-revisions", json={"revision": rev(2).model_dump(mode="json")}).status_code == 409
    c = cl.get("/knowledge-workspace/contradiction-revisions/chain", params={"claim_key": "sample size"})
    assert c.status_code == 200 and c.json()["valid"]
    assert cl.get("/knowledge-workspace/contradiction-revisions/chain", params={"claim_key": "none"}).status_code == 404


# ---------------------------------------------------------------- key governance
class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def test_enrollment_needs_proof_of_possession_and_binding(sf):
    priv, s = Ed25519PrivateKey.generate(), store(sf)
    pub = pubkey(priv)
    with pytest.raises(KeyGovernanceError, match="required"):
        s.register_key(pub, None)
    with pytest.raises(KeyGovernanceError, match="does not verify"):  # proof made for another actor
        s.register_key(pub, proof(priv, pub, actor="mallory"))
    mallory = store(sf, actor="mallory")
    with pytest.raises(KeyGovernanceError, match="only actor"):
        mallory.register_key(pub, proof(priv, pub), actor_id="owner")
    assert s.register_key(pub, proof(priv, pub))["already_enrolled"] is False
    assert s.register_key(pub, proof(priv, pub))["already_enrolled"] is True
    other = Ed25519PrivateKey.generate()
    with pytest.raises(RevisionConflict, match="rotate instead"):
        s.register_key(pubkey(other), proof(other, pubkey(other)))
    events = [e["event"] for e in s.key_events("owner")]
    assert events == ["enroll_refused", "enroll_refused", "enroll_refused", "enrolled"]


def test_admin_can_enroll_for_actor_with_actor_key_proof(sf):
    priv = Ed25519PrivateKey.generate(); pub = pubkey(priv)
    admin = store(sf, actor="admin", roles=frozenset({"atlas-admin"}))
    assert admin.register_key(pub, proof(priv, pub), actor_id="owner")["actor_id"] == "owner"
    assert store(sf).list_keys("owner")[0]["enrolled_by"] == "admin"


def test_rotation_with_endorsement_retires_old_key_forever(sf):
    clock = Clock(); s = store(sf, clock=clock)
    k1 = Ed25519PrivateKey.generate(); p1 = pubkey(k1)
    s.register_key(p1, proof(k1, p1))
    r1 = rev(1)
    s.append(r1, sign(k1, r1))
    k2 = Ed25519PrivateKey.generate(); p2 = pubkey(k2)
    with pytest.raises(KeyGovernanceError, match="endorsement"):
        s.rotate_key(p2, proof(k2, p2))
    bad = base64.b64encode(k2.sign(rotation_statement("t1", "owner", key_id_for(p1), key_id_for(p2)))).decode()
    with pytest.raises(KeyGovernanceError, match="old-key endorsement"):
        s.rotate_key(p2, proof(k2, p2), bad)
    clock.now = T0.replace(hour=5)
    endorse = base64.b64encode(k1.sign(rotation_statement("t1", "owner", key_id_for(p1), key_id_for(p2)))).decode()
    out = s.rotate_key(p2, proof(k2, p2), endorse)
    assert out["mode"] == "continuity" and out["retired_key_id"] == key_id_for(p1)
    r2 = rev(2, prev=revision_sha256(r1))
    with pytest.raises(RevisionRejected, match="retired key"):
        s.append(r2, sign(k1, r2))
    assert s.append(r2, sign(k2, r2))["signed_key_id"] == key_id_for(p2)
    c = s.chain("sample size")
    assert c["valid"], c["problems"]
    assert [x["signature_status"] for x in c["revisions"]] == ["retired_key_stored_before_cutoff", "active_key"]
    with pytest.raises(RevisionConflict, match="retired"):
        s.register_key(p1, proof(k1, p1))
    keys = {k["key_id"]: k for k in s.list_keys("owner")}
    assert keys[key_id_for(p1)]["replaced_by_key_id"] == key_id_for(p2) and "continuity" in keys[key_id_for(p1)]["retire_reason"]


def test_admin_recovery_rotation_is_recorded(sf):
    s = store(sf); k1 = Ed25519PrivateKey.generate(); p1 = pubkey(k1)
    s.register_key(p1, proof(k1, p1))
    admin = store(sf, actor="admin", roles=frozenset({"atlas-admin"}))
    k2 = Ed25519PrivateKey.generate(); p2 = pubkey(k2)
    assert admin.rotate_key(p2, proof(k2, p2), actor_id="owner")["mode"] == "recovery"
    mallory = store(sf, actor="mallory")
    k3 = Ed25519PrivateKey.generate(); p3 = pubkey(k3)
    with pytest.raises(KeyGovernanceError):
        mallory.rotate_key(p3, proof(k3, p3), actor_id="owner")
    assert "rotate_refused" in [e["event"] for e in s.key_events("owner")]


def test_retire_needs_reason_and_blocks_all_signing(sf):
    s = store(sf); k1 = Ed25519PrivateKey.generate(); p1 = pubkey(k1)
    s.register_key(p1, proof(k1, p1))
    with pytest.raises(RevisionRejected, match="reason"):
        s.retire_key(key_id_for(p1), "")
    with pytest.raises(KeyGovernanceError):
        store(sf, actor="mallory").retire_key(key_id_for(p1), "i want to", actor_id="owner")
    s.retire_key(key_id_for(p1), "left the project")
    r1 = rev(1)
    with pytest.raises(RevisionRejected, match="all retired"):
        s.append(r1, sign(k1, r1))
    with pytest.raises(RevisionRejected, match="must be signed"):  # retiring does not switch signing off
        s.append(r1)


def test_leaked_key_effective_from_invalidates_later_revisions(sf):
    clock = Clock(); s = store(sf, clock=clock)
    k1 = Ed25519PrivateKey.generate(); p1 = pubkey(k1)
    s.register_key(p1, proof(k1, p1))
    r1 = rev(1)
    clock.now = T0.replace(hour=1); s.append(r1, sign(k1, r1))
    r2 = rev(2, prev=revision_sha256(r1))
    clock.now = T0.replace(hour=3); s.append(r2, sign(k1, r2))
    clock.now = T0.replace(hour=6)
    out = s.retire_key(key_id_for(p1), "laptop stolen", effective_from=T0.replace(hour=2))
    assert out["effective_from"].startswith("2026-09-24T02:00")
    c = s.chain("sample size")
    assert not c["valid"] and "stored after its retirement took effect" in c["problems"][0]
    assert [x["signature_status"] for x in c["revisions"]] == ["retired_key_stored_before_cutoff", "retired_key_after_cutoff"]
    # a later report can only move the cutoff earlier, never later
    assert s.retire_key(key_id_for(p1), "actually later", effective_from=T0.replace(hour=5))["effective_from"].startswith("2026-09-24T02:00")
    assert s.retire_key(key_id_for(p1), "even earlier", effective_from=T0.replace(minute=30))["effective_from"].startswith("2026-09-24T00:30")
    assert not s.chain("sample size")["revisions"][0]["signature_status"].endswith("before_cutoff")
    assert [e["event"] for e in s.key_events("owner")][-1] == "effective_from_moved_earlier"


# ---------------------------------------------------------------- stored source bytes
def test_matching_bytes_are_stored_and_used_when_url_goes_away(sf):
    blobs = SourceBlobStore("t1", sf, clock=lambda: T0)
    pages = {"https://a.test/p": A, "https://b.test/p": B}
    def fetch(u):
        if u not in pages: raise OSError("down")
        return pages[u]
    uris = {"e1": "https://a.test/p", "e2": "https://b.test/p"}
    first = verify_sources(rev(1), uris, fetch=fetch, blobs=blobs)
    assert first["all_match"] and all(x["stored_copy"]["stored"] for x in first["sources"])
    again = verify_sources(rev(1), uris, fetch=fetch, blobs=blobs)
    assert all(x["stored_copy"]["already_stored"] for x in again["sources"])
    pages.clear()  # both URLs are gone
    later = verify_sources(rev(1), uris, fetch=fetch, blobs=blobs)
    assert [x["status"] for x in later["sources"]] == ["stored_match", "stored_match"]
    assert later["all_verified"] and not later["all_match"]
    assert later["sources"][0]["live_status"] == "unreachable" and later["sources"][0]["stored_copy"]["first_uri"] == "https://a.test/p"
    no_uri = verify_sources(rev(1), {}, fetch=fetch, blobs=blobs)
    assert [x["status"] for x in no_uri["sources"]] == ["stored_match", "stored_match"]


def test_changed_source_is_still_mismatch_and_not_stored(sf):
    blobs = SourceBlobStore("t1", sf)
    out = verify_sources(rev(1), {"e1": "https://a.test/p"}, fetch=lambda u: b"edited page", blobs=blobs)
    e1 = out["sources"][0]
    assert e1["status"] == "mismatch" and e1["stored_copy"] == {"status": "none"}
    with sf() as db:
        assert db.query(SourceBlobRow).count() == 0  # only bytes matching a captured hash are kept


def test_stored_copy_is_tenant_scoped_immutable_and_tamper_checked(sf):
    blobs = SourceBlobStore("t1", sf)
    verify_sources(rev(1), {"e1": "https://a.test/p"}, fetch=lambda u: A, blobs=blobs)
    assert SourceBlobStore("t2", sf).get(hashlib.sha256(A).hexdigest()) is None
    assert blobs.put(A, "https://other.test/")["already_stored"]
    assert blobs.get(hashlib.sha256(A).hexdigest())[1]["first_uri"] == "https://a.test/p"
    with sf.begin() as db:
        db.query(SourceBlobRow).update({"content": b"swapped"})
    out = verify_sources(rev(1), {}, blobs=blobs)
    assert out["sources"][0]["status"] == "no_uri" and out["sources"][0]["stored_copy"]["status"] == "corrupt"


def test_governance_and_source_byte_routes(sf):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m09_knowledge_workspace import routes
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext(tenant_id="t1", actor_id="owner")
    app.dependency_overrides[routes.get_revision_store] = lambda: store(sf)
    app.dependency_overrides[routes.get_source_blobs] = lambda: SourceBlobStore("t1", sf)
    cl = TestClient(app)
    base = "/knowledge-workspace/contradiction-revisions"
    k1 = Ed25519PrivateKey.generate(); p1 = pubkey(k1)
    assert cl.post(f"{base}/keys", json={"public_key_b64": p1, "proof_signature_b64": base64.b64encode(b"x" * 64).decode()}).status_code == 403
    assert cl.post(f"{base}/keys", json={"public_key_b64": p1, "proof_signature_b64": proof(k1, p1)}).status_code == 201
    k2 = Ed25519PrivateKey.generate(); p2 = pubkey(k2)
    assert cl.post(f"{base}/keys", json={"public_key_b64": p2, "proof_signature_b64": proof(k2, p2)}).status_code == 409
    endorse = base64.b64encode(k1.sign(rotation_statement("t1", "owner", key_id_for(p1), key_id_for(p2)))).decode()
    r = cl.post(f"{base}/keys/rotate", json={"new_public_key_b64": p2, "proof_signature_b64": proof(k2, p2), "endorsement_signature_b64": endorse})
    assert r.status_code == 200 and r.json()["mode"] == "continuity"
    r = cl.post(f"{base}/keys/{key_id_for(p2)}/retire", json={"reason": "compromised", "effective_from": "2026-09-24T00:00:00Z"})
    assert r.status_code == 200 and r.json()["active"] is False
    assert cl.post(f"{base}/keys/nope/retire", json={"reason": "whatever"}).status_code == 404
    assert [k["active"] for k in cl.get(f"{base}/keys", params={"actor_id": "owner"}).json()] == [False, False]
    assert "retired" in [e["event"] for e in cl.get(f"{base}/keys/events", params={"actor_id": "owner"}).json()]
    # source bytes
    def fetch(u):
        return {"https://a.test/p": A}[u]
    app.dependency_overrides[routes.get_source_fetcher] = lambda: fetch
    v = cl.post(f"{base}/verify-sources", json={"revision": rev(1).model_dump(mode="json"), "source_uris": {"e1": "https://a.test/p"}})
    assert v.status_code == 200 and v.json()["sources"][0]["stored_copy"]["stored"]
    got = cl.get(f"{base}/source-bytes/{hashlib.sha256(A).hexdigest()}")
    assert got.status_code == 200 and got.content == A and got.headers["x-atlas-first-uri"] == "https://a.test/p"
    assert cl.get(f"{base}/source-bytes/{hashlib.sha256(B).hexdigest()}").status_code == 404
    assert cl.get(f"{base}/source-bytes/NOTHEX").status_code == 422
