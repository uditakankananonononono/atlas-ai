"""Tests for Module 0 (Human Approval Center).

The module performs no network or LLM calls, so there is nothing to mock;
every test runs offline against a throwaway SQLite database with an
injected clock.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import routes
from app.modules.m00_approval_center.service import (
    ApprovalBroadcaster,
    ApprovalConflictError,
    ApprovalNotFoundError,
    Service,
    request_approval,
)

T0 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    """A controllable clock: tests advance it by mutating clock.now."""
    class FakeClock:
        now = T0
        def __call__(self):
            return self.now
    return FakeClock()


@pytest.fixture
def service(tmp_path, clock):
    engine = create_engine(f"sqlite:///{tmp_path}/m00.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return Service(session_factory=factory, broadcaster=ApprovalBroadcaster(), clock=clock)


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    return TestClient(app)


def submit(service, **overrides):
    params = dict(
        module_id=5,
        action_type="send_email",
        payload={"to": "prof@example.edu", "subject": "Summer research"},
        user_id="udita",
    )
    params.update(overrides)
    return service.submit(**params)


def test_submit_creates_pending_request_with_audit_and_broadcast(service):
    subscriber = service.broadcaster.subscribe()
    view = submit(service, ttl_seconds=600)

    assert view["status"] == ApprovalStatus.PENDING
    assert view["module_id"] == 5
    assert view["expires_at"] == T0 + timedelta(seconds=600)
    assert [event["event"] for event in service.audit(view["id"])] == ["created"]

    event = subscriber.get_nowait()
    assert event["type"] == "approval_request"
    assert event["approval"]["id"] == view["id"]


def test_submit_rejects_unknown_module_id(service):
    with pytest.raises(ValueError, match="unknown module id"):
        submit(service, module_id=999)


def test_decision_is_final_and_fully_audited(service):
    view = submit(service)
    decided = service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")

    assert decided["status"] == ApprovalStatus.APPROVED
    assert decided["approved_by"] == "udita"
    assert decided["decided_at"] == T0
    with pytest.raises(ApprovalConflictError):
        service.decide(view["id"], ApprovalStatus.DENIED, decided_by="udita")
    assert [event["event"] for event in service.audit(view["id"])] == ["created", "approved"]


def test_expired_request_cannot_be_decided(service, clock):
    view = submit(service, ttl_seconds=60)
    clock.now = T0 + timedelta(seconds=120)

    with pytest.raises(ApprovalConflictError, match="expired"):
        service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    assert service.get(view["id"])["status"] == ApprovalStatus.EXPIRED
    assert [event["event"] for event in service.audit(view["id"])] == ["created", "expired"]


def test_expire_overdue_sweeps_only_overdue(service, clock):
    overdue = submit(service, ttl_seconds=60)
    fresh = submit(service, ttl_seconds=3600)
    no_ttl = submit(service)
    clock.now = T0 + timedelta(seconds=120)

    assert service.expire_overdue() == [overdue["id"]]
    assert service.get(overdue["id"])["status"] == ApprovalStatus.EXPIRED
    assert service.get(fresh["id"])["status"] == ApprovalStatus.PENDING
    assert service.get(no_ttl["id"])["status"] == ApprovalStatus.PENDING


def test_wait_for_decision_blocks_until_human_decides(service):
    view = submit(service)
    threading.Thread(
        target=lambda: (time.sleep(0.2), service.decide(view["id"], ApprovalStatus.DENIED, decided_by="udita")),
        daemon=True,
    ).start()

    result = service.wait_for_decision(view["id"], timeout_seconds=5, poll_interval_seconds=0.05)
    assert result["status"] == ApprovalStatus.DENIED


def test_wait_for_decision_times_out(service):
    view = submit(service)
    with pytest.raises(TimeoutError):
        service.wait_for_decision(view["id"], timeout_seconds=0.15, poll_interval_seconds=0.05)


def test_callback_fires_on_decision(service):
    view = submit(service)
    received = []
    service.register_callback(view["id"], received.append)
    service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    assert [item["id"] for item in received] == [view["id"]]


def test_request_approval_sdk_uses_default_service(service, monkeypatch):
    monkeypatch.setattr("app.modules.m00_approval_center.service.default_service", lambda: service)
    view = request_approval(module_id=3, action_type="submit_application", payload={"grant": "NSF GRFP"})
    assert view["status"] == ApprovalStatus.PENDING
    assert service.get(view["id"])["module_id"] == 3


def test_routes_full_approval_flow(client):
    created = client.post("/approval-center/requests", json={
        "module_id": 5,
        "action_type": "send_email",
        "payload": {"to": "prof@example.edu"},
        "ttl_seconds": 600,
    })
    assert created.status_code == 201
    approval_id = created.json()["id"]

    assert any(item["id"] == approval_id for item in client.get("/approval-center/requests").json())
    assert client.get(f"/approval-center/requests/{approval_id}").json()["status"] == "pending"

    decided = client.post(f"/approval-center/requests/{approval_id}/decision",
                          json={"decision": "approved", "decided_by": "udita"})
    assert decided.status_code == 200
    assert decided.json()["approved_by"] == "local-user"

    replay = client.post(f"/approval-center/requests/{approval_id}/decision",
                         json={"decision": "denied", "decided_by": "udita"})
    assert replay.status_code == 409

    events = client.get(f"/approval-center/requests/{approval_id}/audit").json()
    assert [event["event"] for event in events] == ["created", "approved"]


def test_routes_missing_and_invalid_requests(client):
    assert client.get("/approval-center/requests/nope").status_code == 404
    assert client.get("/approval-center/requests/nope/audit").status_code == 404
    assert client.post("/approval-center/requests/nope/decision",
                       json={"decision": "approved", "decided_by": "udita"}).status_code == 404
    assert client.post("/approval-center/requests",
                       json={"module_id": 999, "action_type": "send_email"}).status_code == 422


def test_policy_fail_closed_precedence_and_conditions(service):
    service.upsert_policy(policy_id="allow", name="low risk", module_id=5,
        action_pattern="send_*", effect="allow", actor="admin", priority=10,
        conditions={"risk.level": "low"})
    service.upsert_policy(policy_id="deny", name="deny tie", module_id=5,
        action_pattern="send_*", effect="deny", actor="admin", priority=10,
        conditions={"risk.level": "low"})
    effect, picked = service.evaluate_policy(module_id=5, action_type="send_email",
                                             context={"risk": {"level": "low"}})
    assert (effect, picked["id"]) == ("deny", "deny")
    assert service.evaluate_policy(module_id=5, action_type="unknown")[0] == "review"


def test_gate_idempotency_does_not_duplicate_reviews(service):
    first = service.gate(module_id=5, action_type="send_email", payload={"to": "a@b.test"},
                         user_id="udita", idempotency_key="job:1")
    second = service.gate(module_id=5, action_type="send_email", payload={"to": "a@b.test"},
                          user_id="udita", idempotency_key="job:1")
    assert first["approval"]["id"] == second["approval"]["id"]
    with pytest.raises(ApprovalConflictError, match="another request"):
        service.gate(module_id=5, action_type="send_email", payload={"to": "other@b.test"},
                     user_id="udita", idempotency_key="job:1")


def test_effect_gate_is_exact_idempotent_and_one_shot(service):
    payload = {"to": "prof@example.edu", "subject": "Research"}
    pending = service.gate(module_id=5, action_type="send_email", payload=payload, user_id="udita")
    approval_id = pending["approval"]["id"]
    service.decide(approval_id, ApprovalStatus.APPROVED, decided_by="udita")
    with pytest.raises(ApprovalConflictError, match="does not match"):
        service.consume_effect(approval_id, module_id=5, action_type="send_email",
            payload={"to": "attacker@example.test"}, user_id="udita",
            effect_id="mail-1", actor="worker")
    permit = service.consume_effect(approval_id, module_id=5, action_type="send_email",
        payload=payload, user_id="udita", effect_id="mail-1", actor="worker")
    assert permit["allowed"] is True
    replay = service.consume_effect(approval_id, module_id=5, action_type="send_email",
        payload=payload, user_id="udita", effect_id="mail-1", actor="worker")
    assert replay["effect_id"] == "mail-1"
    with pytest.raises(ApprovalConflictError, match="already been consumed"):
        service.consume_effect(approval_id, module_id=5, action_type="send_email",
            payload=payload, user_id="udita", effect_id="mail-2", actor="worker")
    assert [e["event"] for e in service.audit(approval_id)] == ["created", "approved", "effect_consumed"]


def test_unapproved_effect_is_blocked(service):
    view = submit(service)
    with pytest.raises(ApprovalConflictError, match="not approved"):
        service.consume_effect(view["id"], module_id=view["module_id"],
            action_type=view["action_type"], payload=view["payload"], user_id=view["user_id"],
            effect_id="mail-1", actor="worker")


def test_policy_and_gate_routes(client):
    policy = {"id": "allow-safe", "name": "safe", "module_id": 5,
              "action_pattern": "read_*", "effect": "allow", "priority": 1,
              "conditions": {}, "review_ttl_seconds": 60}
    assert client.put("/approval-center/policies/allow-safe", json=policy).status_code == 200
    result = client.post("/approval-center/gate", json={"module_id": 5,
        "action_type": "read_public", "payload": {}})
    assert result.status_code == 200 and result.json()["allowed"] is True


def test_routes_enforce_tenant_scope_and_identity(client):
    created = client.post("/approval-center/requests", headers={"x-atlas-tenant": "tenant-a"},
        json={"module_id": 5, "action_type": "send_email", "payload": {}, "user_id": "spoof"})
    assert created.status_code == 201
    item = created.json()
    assert item["user_id"] == "tenant-a"
    approval_id = item["id"]
    # Cross-tenant reads use 404 so ids cannot be enumerated.
    assert client.get(f"/approval-center/requests/{approval_id}",
                      headers={"x-atlas-tenant": "tenant-b"}).status_code == 404
    decided = client.post(f"/approval-center/requests/{approval_id}/decision",
        headers={"x-atlas-tenant": "tenant-a", "x-atlas-actor": "reviewer-7"},
        json={"decision": "approved", "decided_by": "spoof"})
    assert decided.status_code == 200
    assert decided.json()["approved_by"] == "reviewer-7"
