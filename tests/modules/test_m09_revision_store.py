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
from app.modules.m09_knowledge_workspace.revision_store import (RevisionConflict, RevisionRejected, RevisionRow,
                                                                RevisionStore, revision_sha256, verify_sources)

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


def store(sf, tenant="t1", actor="owner"):
    return RevisionStore(tenant, actor, session_factory=sf, clock=lambda: T0)


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
    assert len(s.register_key(pub)["key_id"]) == 32
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
        s.register_key("not-a-key")


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
