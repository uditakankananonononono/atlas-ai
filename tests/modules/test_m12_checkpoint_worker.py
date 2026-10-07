import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.m12_ai_research_lab.asymmetric_resume_verification import SignedProviderReceipt
from app.modules.m12_ai_research_lab.checkpoint_queue import CheckpointQueue
from app.modules.m12_ai_research_lab.checkpoint_worker import CheckpointWorker, LeaseError
from app.modules.m12_ai_research_lab.provider_key_registry import ProviderKeyRegistry, RegisterProviderKey

T0 = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def env():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    sf = sessionmaker(bind=e, expire_on_commit=False)
    now = [T0]
    q = CheckpointQueue("t", sf)
    q.enqueue({"run_id": "r1", "checkpoint_sha256": "a" * 64, "nodes": []})
    q.enqueue({"run_id": "r2", "checkpoint_sha256": "b" * 64, "nodes": []})
    priv = Ed25519PrivateKey.generate()
    reg = ProviderKeyRegistry("t", sf)
    reg.register(RegisterProviderKey(provider="hf", key_id="k1", public_key_base64=base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()))
    return CheckpointWorker("t", sf, max_attempts=2, clock=lambda: now[0]), now, priv, reg, sf


def receipt(priv, provider="hf", key_id="k1", issued=None):
    meta = {"node_id": "n1", "provider": provider, "model": "m", "input_sha256": "c" * 64, "output_sha256": "d" * 64,
            "spent_cents": 0, "issued_at": (issued or datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "key_id": key_id}
    r = SignedProviderReceipt(**meta, signature_base64="x")
    canonical = json.dumps(r.model_dump(mode="json", exclude={"signature_base64"}), sort_keys=True, separators=(",", ":")).encode()
    return SignedProviderReceipt(**meta, signature_base64=base64.b64encode(priv.sign(canonical)).decode())


def test_claim_order_exclusivity_and_expiry(env):
    w, now, *_ = env
    a = w.claim("w1", 60); b = w.claim("w2", 60)
    assert (a["run_id"], b["run_id"]) == ("r1", "r2") and w.claim("w3", 60) is None
    w.heartbeat(a["lease_token"], 120)
    now[0] = T0 + timedelta(seconds=90)
    c = w.claim("w3", 60)
    assert c["run_id"] == "r2" and c["attempt"] == 2  # r2 expired, r1 still heartbeated
    with pytest.raises(LeaseError, match="superseded"):
        w.heartbeat(b["lease_token"])


def test_fail_retries_then_marks_failed(env):
    w, now, *_ = env
    a = w.claim("w1", 60)
    assert w.fail(a["lease_token"], "oom")["state"] == "queued"
    a2 = w.claim("w1", 60)
    assert a2["run_id"] == "r1" and a2["attempt"] == 2
    assert w.fail(a2["lease_token"], "oom again")["state"] == "failed"
    assert w.claim("w1", 60)["run_id"] == "r2"


def test_complete_needs_registered_key_for_that_provider(env):
    w, now, priv, reg, _ = env
    a = w.claim("w1", 60)
    with pytest.raises(LeaseError, match="no registered key"):
        w.complete(a["lease_token"], [receipt(priv, provider="openai")], "n1")
    with pytest.raises(LeaseError, match="invalid provider receipt signature"):
        w.complete(a["lease_token"], [receipt(Ed25519PrivateKey.generate())], "n1")
    with pytest.raises(LeaseError, match="predates"):
        w.complete(a["lease_token"], [receipt(priv, issued=datetime(2020, 1, 1, tzinfo=timezone.utc))], "n1")
    out = w.complete(a["lease_token"], [receipt(priv)], "n1")
    assert out["state"] == "completed" and out["receipts_verified"] == 1
    with pytest.raises(LeaseError, match="no longer queued"):
        w.heartbeat(a["lease_token"])
    b = w.claim("w1", 60)
    reg.retire("hf", "k1")
    with pytest.raises(LeaseError, match="retired"):
        w.complete(b["lease_token"], [receipt(priv)], "n1")


def test_routes(env):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.m12_ai_research_lab import routes
    w, now, priv, *_ = env
    app.dependency_overrides[routes.get_checkpoint_worker] = lambda: w
    try:
        c = TestClient(app); H = {"X-Atlas-Tenant": "t", "X-Atlas-Actor": "u"}; base = "/api/v1/ai-research-lab/reproducible-run/worker"
        got = c.post(f"{base}/claim", json={"worker_id": "w1", "lease_seconds": 60}, headers=H).json()
        assert got["claimed"] and got["lease"]["run_id"] == "r1"
        tok = got["lease"]["lease_token"]
        r = c.post(f"{base}/complete", json={"lease_token": tok, "resume_from_node_id": "n1",
                                             "provider_receipts": [receipt(priv).model_dump(mode="json")]}, headers=H)
        assert r.status_code == 200 and r.json()["state"] == "completed", r.text
        assert c.post(f"{base}/heartbeat", json={"lease_token": tok}, headers=H).status_code == 409
    finally:
        app.dependency_overrides.clear()


def _resigned(priv, base, node_id):
    r = SignedProviderReceipt(**{**base.model_dump(mode="json", exclude={"signature_base64"}), "node_id": node_id,
                                 "signature_base64": "x"})
    canonical = json.dumps(r.model_dump(mode="json", exclude={"signature_base64"}), sort_keys=True, separators=(",", ":")).encode()
    return SignedProviderReceipt(**{**r.model_dump(mode="json", exclude={"signature_base64"}),
                                    "signature_base64": base64.b64encode(priv.sign(canonical)).decode()})


def test_complete_rejects_key_id_reused_across_providers(env):
    # Structural guard: one key_id naming two different providers in a single
    # completion must be rejected as reuse, not surface as a later signature
    # failure after its trusted-key entry was silently overwritten. Order of
    # the receipts must not matter.
    w, now, priv, reg, _ = env
    other = Ed25519PrivateKey.generate()
    reg.register(RegisterProviderKey(provider="openai", key_id="k1", public_key_base64=base64.b64encode(
        other.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()))
    hf_n1 = receipt(priv, provider="hf", key_id="k1")
    openai_n2 = _resigned(other, receipt(other, provider="openai", key_id="k1"), "n2")
    a = w.claim("w1", 60)
    with pytest.raises(LeaseError, match="reused across providers"):
        w.complete(a["lease_token"], [hf_n1, openai_n2], "n1")
    b = w.claim("w1", 60)
    with pytest.raises(LeaseError, match="reused across providers"):
        w.complete(b["lease_token"], [openai_n2, hf_n1], "n2")


def test_complete_allows_one_provider_key_across_many_nodes(env):
    # Regression pin: the normal case is one provider key signing receipts for
    # several nodes; the reuse guard must not reject same-provider key reuse.
    w, now, priv, reg, _ = env
    a = w.claim("w1", 60)
    out = w.complete(a["lease_token"], [receipt(priv), _resigned(priv, receipt(priv), "n2")], "n1")
    assert out["state"] == "completed" and out["receipts_verified"] == 2
