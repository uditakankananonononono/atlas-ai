"""M12 receipt inbox + beat-driven checkpoint worker loop: due-only claims, verify, fail path, tenants."""
import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.m12_ai_research_lab.asymmetric_resume_verification import SignedProviderReceipt
from app.modules.m12_ai_research_lab.checkpoint_loop import (
    CheckpointLoop, InboxError, InboxNotFound, ReceiptInbox, tenants_with_queued_checkpoints,
)
from app.modules.m12_ai_research_lab.checkpoint_queue import CheckpointQueue, CheckpointQueueRow
from app.modules.m12_ai_research_lab.checkpoint_worker import CheckpointLeaseRow, CheckpointWorker
from app.modules.m12_ai_research_lab.provider_key_registry import ProviderKeyRegistry, RegisterProviderKey

T0 = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
ISSUED = datetime(2030, 1, 1, tzinfo=timezone.utc)  # after key registration (registry stamps real now)


def payload(run_id, sha, statuses):
    return {"run_id": run_id, "checkpoint_sha256": sha, "resume_from_node_id": None,
            "nodes": [{"node_id": n, "status": s} for n, s in statuses.items()]}


@pytest.fixture
def env():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    sf = sessionmaker(bind=e, expire_on_commit=False)
    now = [T0]
    keys = {}
    for tenant in ("ta", "tb"):
        priv = Ed25519PrivateKey.generate()
        ProviderKeyRegistry(tenant, sf).register(RegisterProviderKey(provider="hf", key_id=f"k-{tenant}", public_key_base64=base64.b64encode(
            priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()))
        keys[tenant] = priv
    return sf, now, keys


def receipt(priv, node, key_id, provider="hf"):
    meta = {"node_id": node, "provider": provider, "model": "m", "input_sha256": "c" * 64, "output_sha256": "d" * 64,
            "spent_cents": 7, "issued_at": ISSUED.isoformat().replace("+00:00", "Z"), "key_id": key_id}
    r = SignedProviderReceipt(**meta, signature_base64="x")
    canonical = json.dumps(r.model_dump(mode="json", exclude={"signature_base64"}), sort_keys=True, separators=(",", ":")).encode()
    return SignedProviderReceipt(**meta, signature_base64=base64.b64encode(priv.sign(canonical)).decode())


def loop(sf, now, tenant, **kw):
    clock = lambda: now[0]
    return CheckpointLoop(tenant, sf, worker=CheckpointWorker(tenant, sf, max_attempts=2, clock=clock),
                          worker_id=f"beat-{tenant}", clock=clock, **kw)


def state(sf, run_id, tenant="ta"):
    with sf() as db:
        return db.scalar(select(CheckpointQueueRow.state).where(CheckpointQueueRow.tenant_id == tenant, CheckpointQueueRow.run_id == run_id))


def test_only_fully_covered_checkpoints_are_claimed_and_completed(env):
    sf, now, keys = env
    q = CheckpointQueue("ta", sf)
    q.enqueue(payload("r1", "a" * 64, {"n0": "completed", "n1": "failed", "n2": "queued"}))
    q.enqueue(payload("r2", "b" * 64, {"n1": "running"}))
    inbox = ReceiptInbox("ta", sf)
    st = inbox.post("r1", [receipt(keys["ta"], "n1", "k-ta")])
    assert st["required"] == ["n1", "n2"] and st["missing"] == ["n2"] and not st["due"]
    with pytest.raises(InboxError, match="not awaiting"):
        inbox.post("r1", [receipt(keys["ta"], "n0", "k-ta")])  # completed node needs no receipt
    with pytest.raises(InboxNotFound):
        inbox.post("nope", [receipt(keys["ta"], "n1", "k-ta")])
    result = loop(sf, now, "ta").run_once()
    assert result["completed"] == [] and result["failed"] == [] and result["provider_calls"] == 0
    with sf() as db:  # waiting checkpoints were never leased, so no attempts burned
        assert db.scalars(select(CheckpointLeaseRow)).all() == []
    assert inbox.post("r1", [receipt(keys["ta"], "n2", "k-ta")])["due"] is True
    result = loop(sf, now, "ta").run_once()
    assert [c["run_id"] for c in result["completed"]] == ["r1"] and result["completed"][0]["receipts_verified"] == 2
    assert state(sf, "r1") == "completed" and state(sf, "r2") == "queued"
    with pytest.raises(InboxNotFound):
        inbox.status("r1")  # no longer queued


def test_bad_signature_fails_clears_receipts_and_marks_failed_after_max_attempts(env):
    sf, now, keys = env
    CheckpointQueue("ta", sf).enqueue(payload("r1", "a" * 64, {"n1": "failed"}))
    inbox = ReceiptInbox("ta", sf)
    forged = Ed25519PrivateKey.generate()
    inbox.post("r1", [receipt(forged, "n1", "k-ta")])
    r = loop(sf, now, "ta").run_once()
    assert r["failed"][0]["state"] == "queued" and r["failed"][0]["attempts"] == 1
    assert "signature" in r["failed"][0]["error"]
    assert inbox.status("r1")["received"] == []  # rejected receipts cleared; waits for new ones
    assert loop(sf, now, "ta").run_once()["failed"] == []  # not retried with nothing in the inbox
    inbox.post("r1", [receipt(forged, "n1", "k-ta")])
    r = loop(sf, now, "ta").run_once()
    assert r["failed"][0]["state"] == "failed" and r["failed"][0]["attempts"] == 2
    assert state(sf, "r1") == "failed"
    # a retired key is also a verification failure, not a completion
    CheckpointQueue("ta", sf).enqueue(payload("r3", "c" * 64, {"n1": "queued"}))
    inbox.post("r3", [receipt(keys["ta"], "n1", "k-ta")])
    ProviderKeyRegistry("ta", sf).retire("hf", "k-ta")
    assert "retired" in loop(sf, now, "ta").run_once()["failed"][0]["error"]


def test_beat_loop_does_not_race_an_external_worker(env):
    sf, now, keys = env
    CheckpointQueue("ta", sf).enqueue(payload("r1", "a" * 64, {"n1": "queued"}))
    ReceiptInbox("ta", sf).post("r1", [receipt(keys["ta"], "n1", "k-ta")])
    external = CheckpointWorker("ta", sf, clock=lambda: now[0]).claim("external", 60)
    assert external["run_id"] == "r1"
    r = loop(sf, now, "ta").run_once()
    assert r["completed"] == [] and r["skipped"][0]["run_id"] == "r1"
    now[0] = T0 + timedelta(seconds=61)  # external lease expired: the beat takes over
    r = loop(sf, now, "ta").run_once()
    assert [c["run_id"] for c in r["completed"]] == ["r1"]


def test_tenants_are_isolated(env):
    sf, now, keys = env
    CheckpointQueue("ta", sf).enqueue(payload("shared-run", "a" * 64, {"n1": "queued"}))
    CheckpointQueue("tb", sf).enqueue(payload("shared-run", "b" * 64, {"n1": "queued"}))
    CheckpointQueue("tb", sf).enqueue(payload("b-only", "e" * 64, {"n1": "queued"}))
    with pytest.raises(InboxNotFound):
        ReceiptInbox("ta", sf).post("b-only", [receipt(keys["ta"], "n1", "k-ta")])
    # tenant B's receipt signed with B's key lands only in B's inbox, and A's checkpoint stays waiting
    ReceiptInbox("tb", sf).post("shared-run", [receipt(keys["tb"], "n1", "k-tb")])
    assert ReceiptInbox("ta", sf).status("shared-run")["received"] == []
    assert loop(sf, now, "ta").run_once()["completed"] == []
    assert [c["run_id"] for c in loop(sf, now, "tb").run_once()["completed"]] == ["shared-run"]
    assert state(sf, "shared-run", "ta") == "queued" and state(sf, "shared-run", "tb") == "completed"
    # A's inbox with B's key id: A has no such registered key, so verification fails in A only
    ReceiptInbox("ta", sf).post("shared-run", [receipt(keys["tb"], "n1", "k-tb")])
    assert "no registered key" in loop(sf, now, "ta").run_once()["failed"][0]["error"]
    assert tenants_with_queued_checkpoints(sf) == ["ta", "tb"]


def test_beat_task_runs_every_tenant_and_routes(env, monkeypatch):
    sf, now, keys = env
    import app.modules.m12_ai_research_lab.checkpoint_loop as mod
    from app.workers import celery_app as capp
    from app.workers.tasks import run_m12_checkpoint_worker
    assert capp.celery_app.conf.beat_schedule["run-m12-checkpoint-worker"]["task"] == "atlas.m12.run_checkpoint_worker"
    for t in ("ta", "tb"):
        CheckpointQueue(t, sf).enqueue(payload("r1", "a" * 64, {"n1": "queued"}))
        ReceiptInbox(t, sf).post("r1", [receipt(keys[t], "n1", f"k-{t}")])
    CheckpointQueue("tb", sf).enqueue(payload("r2", "b" * 64, {"n1": "queued"}))  # waiting
    real_loop, real_tenants = mod.CheckpointLoop, mod.tenants_with_queued_checkpoints
    monkeypatch.setattr(mod, "CheckpointLoop", lambda tenant_id: real_loop(tenant_id, sf))
    monkeypatch.setattr(mod, "tenants_with_queued_checkpoints", lambda: real_tenants(sf))
    assert run_m12_checkpoint_worker() == {"tenants": 2, "completed": 2, "failed": 0, "skipped": 0, "provider_calls": 0}
    assert state(sf, "r2", "tb") == "queued"
    # routes: post receipts, status, tick (tenant-scoped)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.m12_ai_research_lab import routes
    app.dependency_overrides[routes.get_receipt_inbox] = lambda: ReceiptInbox("tb", sf)
    app.dependency_overrides[routes.get_checkpoint_loop] = lambda: real_loop("tb", sf)
    try:
        c = TestClient(app); H = {"X-Atlas-Tenant": "tb", "X-Atlas-Actor": "u"}; base = "/api/v1/ai-research-lab/reproducible-run"
        assert c.get(f"{base}/r2/receipts", headers=H).json()["missing"] == ["n1"]
        body = {"provider_receipts": [receipt(keys["tb"], "n1", "k-tb").model_dump(mode="json")]}
        posted = c.post(f"{base}/r2/receipts", json=body, headers=H)
        assert posted.status_code == 202 and posted.json()["due"] is True
        assert c.post(f"{base}/missing/receipts", json=body, headers=H).status_code == 404
        bad = {"provider_receipts": [receipt(keys["tb"], "zz", "k-tb").model_dump(mode="json")]}
        assert c.post(f"{base}/r2/receipts", json=bad, headers=H).status_code == 422
        tick = c.post(f"{base}/worker/tick", headers=H).json()
        assert [x["run_id"] for x in tick["completed"]] == ["r2"] and tick["provider_calls"] == 0
    finally:
        app.dependency_overrides.clear()
