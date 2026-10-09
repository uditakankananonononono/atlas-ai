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
from app.auth.context import TenantContext, require_admin, require_worker
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
    client.app.dependency_overrides[require_admin] = lambda: TenantContext("local", "admin-1", frozenset({"atlas-admin"}))
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


def test_admin_worker_routes_reject_ordinary_user(client):
    assert client.put("/approval-center/policies/x", json={"id":"x","name":"x","action_pattern":"*","effect":"deny","conditions":{}}).status_code == 403
    assert client.get("/approval-center/policies").status_code == 403
    assert client.post("/approval-center/expire").status_code == 403

def test_expire_accepts_internal_worker(client):
    client.app.dependency_overrides[require_worker] = lambda: TenantContext("system", "worker-1", frozenset({"atlas-worker"}))
    assert client.post("/approval-center/expire").status_code == 200


def test_policies_are_tenant_isolated(service):
    service.upsert_policy(policy_id="send", name="A allows", module_id=5,
        action_pattern="send_*", effect="allow", actor="admin-a", tenant_id="tenant-a")
    service.upsert_policy(policy_id="send", name="B denies", module_id=5,
        action_pattern="send_*", effect="deny", actor="admin-b", tenant_id="tenant-b")
    assert service.evaluate_policy(module_id=5, action_type="send_email", tenant_id="tenant-a")[0] == "allow"
    assert service.evaluate_policy(module_id=5, action_type="send_email", tenant_id="tenant-b")[0] == "deny"
    assert service.evaluate_policy(module_id=5, action_type="send_email", tenant_id="tenant-c")[0] == "review"
    assert [p["tenant_id"] for p in service.list_policies(tenant_id="tenant-a")] == ["tenant-a"]


def test_rejected_expired_decision_persists_expiry_without_readback(service, clock):
    view = submit(service, ttl_seconds=1)
    callbacks = []
    subscriber = service.broadcaster.subscribe()
    service.register_callback(view['id'], callbacks.append)
    clock.now = T0 + timedelta(seconds=2)
    with pytest.raises(ApprovalConflictError, match='expired'):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    # Inspect durable state directly. Service.get would mask a rolled-back
    # expiry by lazily applying it again in a different transaction.
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with service._sessions() as db:
        assert db.get(ApprovalRequestRow, view['id']).status == ApprovalStatus.EXPIRED.value
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'expired']
    assert len(callbacks) == 1 and callbacks[0]['status'] == ApprovalStatus.EXPIRED
    assert subscriber.get_nowait()['type'] == 'approval_expired'
    with pytest.raises(ApprovalConflictError):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    assert len(callbacks) == 1
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'expired']


def test_stale_decision_cannot_overwrite_committed_competing_decision(service):
    view = submit(service)
    original_fetch = service._fetch
    raced = []

    def fetch_then_compete(db, approval_id):
        row = original_fetch(db, approval_id)
        if not raced:
            raced.append(True)
            service.decide(approval_id, ApprovalStatus.DENIED, decided_by='winner')
        return row

    service._fetch = fetch_then_compete
    with pytest.raises(ApprovalConflictError):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='loser')
    service._fetch = original_fetch
    assert service.get(view['id'])['status'] == ApprovalStatus.DENIED
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'denied']

def test_lazy_expiry_cannot_overwrite_competing_approved_decision(service, clock):
    view = submit(service, ttl_seconds=10)
    fetch = service._fetch
    raced = []

    def stale_fetch(db, aid):
        row = fetch(db, aid)
        if not raced:
            raced.append(True)
            service.decide(aid, ApprovalStatus.APPROVED, decided_by='winner')
            clock.now = T0 + timedelta(seconds=20)
        return row

    service._fetch = stale_fetch
    result = service.get(view['id'])
    service._fetch = fetch
    assert result['status'] == ApprovalStatus.APPROVED
    assert service.get(view['id'])['status'] == ApprovalStatus.APPROVED
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'approved']


@pytest.mark.parametrize('path', ['get', 'list', 'sweep', 'overdue_decision'])
def test_combined_expiry_paths_refresh_competing_decision(service, clock, path):
    view = submit(service, ttl_seconds=10)
    clock.now = T0 + timedelta(seconds=20)
    expire = service._expire
    raced = []
    callbacks = []
    service.register_callback(view['id'], callbacks.append)

    def expire_after_winner(db, row, now):
        if not raced:
            raced.append(True)
            clock.now = T0
            service.decide(view['id'], ApprovalStatus.DENIED, decided_by='winner')
            clock.now = now
        return expire(db, row, now)

    service._expire = expire_after_winner
    if path == 'get':
        assert service.get(view['id'])['status'] == ApprovalStatus.DENIED
    elif path == 'list':
        assert service.list()[0]['status'] == ApprovalStatus.DENIED
    elif path == 'sweep':
        assert service.expire_overdue() == []
    else:
        with pytest.raises(ApprovalConflictError):
            service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='loser')
    service._expire = expire
    assert service.get(view['id'])['status'] == ApprovalStatus.DENIED
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'denied']
    assert len(callbacks) == 1 and callbacks[0]['status'] == ApprovalStatus.DENIED


def test_combined_stale_decision_loses_to_committed_expiry(service, clock):
    view = submit(service, ttl_seconds=10)
    fetch = service._fetch
    raced = []
    callbacks = []
    service.register_callback(view['id'], callbacks.append)

    def fetch_then_expire(db, aid):
        row = fetch(db, aid)
        if not raced:
            raced.append(True)
            clock.now = T0 + timedelta(seconds=20)
            assert service.expire_overdue() == [aid]
        return row

    service._fetch = fetch_then_expire
    with pytest.raises(ApprovalConflictError):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='loser')
    service._fetch = fetch
    assert service.get(view['id'])['status'] == ApprovalStatus.EXPIRED
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'expired']
    assert len(callbacks) == 1 and callbacks[0]['status'] == ApprovalStatus.EXPIRED


@pytest.mark.parametrize('winner_effect', ['winner', 'loser'])
def test_consume_insert_race_returns_winner_or_conflict(service, monkeypatch, winner_effect):
    from sqlalchemy.orm import Session
    from app.modules.m00_approval_center.service import ApprovalEffectRow
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    kwargs = dict(module_id=view['module_id'], action_type=view['action_type'],
                  payload=view['payload'], user_id=view['user_id'], actor='worker')
    flush = Session.flush
    raced = []

    def competing_flush(db, *args, **kw):
        if not raced and any(isinstance(row, ApprovalEffectRow) for row in db.new):
            raced.append(True)
            service.consume_effect(view['id'], effect_id=winner_effect, **kwargs)
        return flush(db, *args, **kw)

    monkeypatch.setattr(Session, 'flush', competing_flush)
    if winner_effect == 'loser':
        assert service.consume_effect(view['id'], effect_id='loser', **kwargs)['allowed']
    else:
        with pytest.raises(ApprovalConflictError, match='consumed'):
            service.consume_effect(view['id'], effect_id='loser', **kwargs)
    with service._sessions() as db:
        from sqlalchemy import select
        assert [row.effect_id for row in db.scalars(select(ApprovalEffectRow))] == [winner_effect]
    assert [e['event'] for e in service.audit(view['id'])] == ['created', 'approved', 'effect_consumed']


def test_consume_unrelated_integrity_error_is_not_fake_consumption(service, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from app.modules.m00_approval_center.service import ApprovalEffectRow
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    flush = Session.flush

    def fail(db, *args, **kwargs):
        if any(isinstance(row, ApprovalEffectRow) for row in db.new):
            raise IntegrityError('fixture', {}, RuntimeError('unrelated'))
        return flush(db, *args, **kwargs)

    monkeypatch.setattr(Session, 'flush', fail)
    with pytest.raises(IntegrityError):
        service.consume_effect(view['id'], module_id=view['module_id'], action_type=view['action_type'],
                               payload=view['payload'], user_id=view['user_id'], effect_id='none', actor='worker')
    assert [e['event'] for e in service.audit(view['id'])] == ['created', 'approved']


def test_overdue_consume_refusal_persists_expiry_without_lazy_read(service, clock):
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    view = submit(service, ttl_seconds=1)
    clock.now = T0 + timedelta(seconds=2)
    with pytest.raises(ApprovalConflictError, match='expired'):
        service.consume_effect(view['id'], module_id=view['module_id'], action_type=view['action_type'],
                               payload=view['payload'], user_id=view['user_id'], effect_id='unused', actor='worker')
    with service._sessions() as db:
        assert db.get(ApprovalRequestRow, view['id']).status == ApprovalStatus.EXPIRED.value
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'expired']
def test_status_lists_classify_lazy_expiry_before_limit(service, clock):
    fresh = submit(service, ttl_seconds=100)
    clock.now = T0 + timedelta(seconds=1)
    overdue = submit(service, ttl_seconds=1)
    clock.now = T0 + timedelta(seconds=3)
    assert [v['id'] for v in service.list(status=ApprovalStatus.PENDING, limit=1)] == [fresh['id']]
    assert [v['id'] for v in service.list(status=ApprovalStatus.EXPIRED, limit=1)] == [overdue['id']]
    assert [event['event'] for event in service.audit(overdue['id'])] == ['created', 'expired']


@pytest.mark.parametrize('winner', [ApprovalStatus.APPROVED, ApprovalStatus.DENIED])
@pytest.mark.parametrize('loser', [ApprovalStatus.APPROVED, ApprovalStatus.DENIED])
def test_expiry_composition_decision_winner_loser_pairs(service, winner, loser):
    view = submit(service)
    fetch = service._fetch
    raced = []
    def fetch_then_decide(db, aid):
        row = fetch(db, aid)
        if not raced:
            raced.append(True)
            service.decide(aid, winner, decided_by='winner')
        return row
    service._fetch = fetch_then_decide
    with pytest.raises(ApprovalConflictError):
        service.decide(view['id'], loser, decided_by='loser')
    service._fetch = fetch
    assert service.get(view['id'])['status'] == winner
    assert [event['event'] for event in service.audit(view['id'])] == ['created', winner.value]


@pytest.mark.parametrize('case', ['same', 'different_effect', 'different_payload', 'occupied_elsewhere'])
def test_expiry_composition_permit_exactness(service, case):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='winner')
    kwargs = dict(module_id=view['module_id'], action_type=view['action_type'],
                  payload=view['payload'], user_id=view['user_id'], actor='worker')
    service.consume_effect(view['id'], effect_id='used', **kwargs)
    if case == 'same':
        assert service.consume_effect(view['id'], effect_id='used', **kwargs)['allowed']
    elif case == 'different_effect':
        with pytest.raises(ApprovalConflictError):
            service.consume_effect(view['id'], effect_id='other', **kwargs)
    elif case == 'different_payload':
        with pytest.raises(ApprovalConflictError):
            service.consume_effect(view['id'], effect_id='used', **{**kwargs, 'payload': {'changed': True}})
    else:
        other = submit(service)
        service.decide(other['id'], ApprovalStatus.APPROVED, decided_by='winner')
        with pytest.raises(ApprovalConflictError, match='effect id'):
            service.consume_effect(other['id'], effect_id='used', **kwargs)
        assert [e['event'] for e in service.audit(other['id'])] == ['created', 'approved']
    assert [e['event'] for e in service.audit(view['id'])] == ['created', 'approved', 'effect_consumed']


@pytest.mark.parametrize('same_payload', [True, False])
def test_gate_insert_race_retains_only_committed_winner(service, monkeypatch, same_payload):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.modules.m00_approval_center.service import ApprovalIdempotencyRow, ApprovalRequestRow
    subscriber = service.broadcaster.subscribe()
    flush = Session.flush
    winners = []
    args = dict(module_id=5, action_type='send_email', user_id='udita', idempotency_key='race')

    def compete(db, *a, **kw):
        if not winners and any(isinstance(row, ApprovalIdempotencyRow) for row in db.new):
            winners.append(None)
            winners[0] = service.gate(payload={'to': 'winner@test'}, **args)
        return flush(db, *a, **kw)

    monkeypatch.setattr(Session, 'flush', compete)
    if same_payload:
        result = service.gate(payload={'to': 'winner@test'}, **args)
        assert result['approval']['id'] == winners[0]['approval']['id']
    else:
        with pytest.raises(ApprovalConflictError, match='another request'):
            service.gate(payload={'to': 'loser@test'}, **args)
    with service._sessions() as db:
        assert [row.id for row in db.scalars(select(ApprovalRequestRow))] == [winners[0]['approval']['id']]
    assert subscriber.get_nowait()['approval']['id'] == winners[0]['approval']['id']
    import queue
    with pytest.raises(queue.Empty):
        subscriber.get_nowait()
    assert [event['event'] for event in service.audit(winners[0]['approval']['id'])] == ['created']
    from app.modules.m00_approval_center.service import ApprovalEventRow
    with service._sessions() as db:
        assert len(list(db.scalars(select(ApprovalEventRow)))) == 1


def test_gate_unrelated_integrity_rethrows_and_leaves_no_request_event_or_signal(service, monkeypatch):
    import queue
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from app.modules.m00_approval_center.service import (
        ApprovalIdempotencyRow, ApprovalRequestRow, ApprovalEventRow,
    )
    subscriber = service.broadcaster.subscribe()
    original = Session.flush
    failure = IntegrityError('fixture insert', {}, RuntimeError('unrelated fixture failure'))

    def fail_key_insert(db, *args, **kwargs):
        if any(isinstance(row, ApprovalIdempotencyRow) for row in db.new):
            raise failure
        return original(db, *args, **kwargs)

    monkeypatch.setattr(Session, 'flush', fail_key_insert)
    with pytest.raises(IntegrityError) as raised:
        service.gate(module_id=5, action_type='send_email', payload={'to': 'fixture@test'},
                     user_id='udita', idempotency_key='failed-key')
    assert raised.value is failure
    with service._sessions() as db:
        for model in (ApprovalRequestRow, ApprovalEventRow, ApprovalIdempotencyRow):
            assert list(db.scalars(select(model))) == []
    with pytest.raises(queue.Empty):
        subscriber.get_nowait()


@pytest.mark.parametrize('limit', [-1, 0, True, 1.5, 1001])
def test_list_refuses_noninteger_or_unbounded_limits(service, limit):
    with pytest.raises(ValueError, match='limit'):
        service.list(limit=limit)


def test_list_limit_negative_does_not_return_entire_sqlite_queue(client, service):
    from app.auth.context import require_tenant
    client.app.dependency_overrides[require_tenant] = lambda: TenantContext(
        tenant_id='udita', actor_id='udita', roles=frozenset({'owner'}))
    submit(service)
    response = client.get('/approval-center/requests?limit=-1')
    assert response.status_code == 422


@pytest.mark.parametrize('ttl', [0, -1, True, 1.5])
def test_direct_submit_refuses_invalid_ttl_without_persisting(service, ttl):
    from sqlalchemy import select
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    with pytest.raises(ValueError, match='ttl_seconds'):
        submit(service, ttl_seconds=ttl)
    with service._sessions() as db:
        assert list(db.scalars(select(ApprovalRequestRow))) == []


@pytest.mark.parametrize('ttl', [True, 1.5])
def test_policy_review_ttl_requires_actual_integer(service, ttl):
    with pytest.raises(ValueError, match='review_ttl_seconds'):
        service.upsert_policy(policy_id='invalid', name='Fixture', action_pattern='*',
                              effect='review', actor='fixture', review_ttl_seconds=ttl)


def test_keyed_gate_refuses_legacy_zero_ttl_policy(service):
    from app.modules.m00_approval_center.service import ApprovalPolicyRow
    service.upsert_policy(policy_id='legacy', name='Fixture', action_pattern='*',
                          effect='review', actor='fixture', review_ttl_seconds=10, tenant_id='local')
    with service._sessions.begin() as db:
        db.get(ApprovalPolicyRow, ('local', 'legacy')).review_ttl_seconds = 0
    with pytest.raises(ValueError, match='ttl'):
        service.gate(module_id=5, action_type='send_email', payload={}, user_id='local',
                     idempotency_key='legacy-policy')


@pytest.mark.parametrize('limit', [1, 1000])
def test_list_accepts_documented_limit_boundaries(service, limit):
    view = submit(service)
    assert [row['id'] for row in service.list(limit=limit)] == [view['id']]


def test_submit_unrepresentable_ttl_is_validation_error(service):
    with pytest.raises(ValueError, match='ttl_seconds'):
        submit(service, ttl_seconds=10**30)


def test_keyed_gate_unrepresentable_policy_ttl_is_validation_error(service, monkeypatch):
    monkeypatch.setattr(service, 'evaluate_policy', lambda **kwargs: (
        'review', {'id': 'fixture', 'review_ttl_seconds': 10**30}))
    with pytest.raises(ValueError, match='ttl'):
        service.gate(module_id=5, action_type='send_email', payload={}, user_id='local',
                     idempotency_key='huge-ttl')


def test_allow_policy_does_not_authorize_unknown_module(service):
    service.upsert_policy(policy_id='allow-all', name='Fixture', action_pattern='*',
                          effect='allow', actor='fixture', tenant_id='udita')
    with pytest.raises(ValueError, match='unknown module'):
        service.gate(module_id=999999, action_type='send_email', payload={}, user_id='udita')


@pytest.mark.parametrize('module', [999999, True, 1.0])
def test_policy_refuses_unknown_or_noninteger_module(service, module):
    with pytest.raises(ValueError, match='module'):
        service.upsert_policy(policy_id='invalid', name='Fixture', action_pattern='*',
                              effect='allow', actor='fixture', module_id=module)


@pytest.mark.parametrize('field,value', [('action_type', ''), ('action_type', '   '),
                                         ('user_id', ''), ('user_id', '   ')])
def test_submit_refuses_empty_action_or_owner(service, field, value):
    with pytest.raises(ValueError, match='action_type|user_id'):
        submit(service, **{field: value})


@pytest.mark.parametrize('field', ['policy_id', 'name', 'action_pattern', 'actor'])
def test_policy_refuses_empty_identifiers(service, field):
    kwargs = dict(policy_id='fixture', name='Fixture', action_pattern='*', effect='review', actor='fixture')
    kwargs[field] = '   '
    with pytest.raises(ValueError, match=field):
        service.upsert_policy(**kwargs)


@pytest.mark.parametrize('context', [[], 'invalid', 1])
def test_gate_refuses_nonobject_context_before_allow(service, context):
    service.upsert_policy(policy_id='allow', name='Fixture', action_pattern='*',
                          effect='allow', actor='fixture', tenant_id='udita')
    with pytest.raises(ValueError, match='context'):
        service.gate(module_id=5, action_type='send_email', payload={}, user_id='udita', context=context)


@pytest.mark.parametrize('payload', [[], 'invalid', None])
def test_gate_refuses_nonobject_payload_before_allow(service, payload):
    service.upsert_policy(policy_id='allow', name='Fixture', action_pattern='*',
                          effect='allow', actor='fixture', tenant_id='udita')
    with pytest.raises(ValueError, match='payload'):
        service.gate(module_id=5, action_type='send_email', payload=payload, user_id='udita')


@pytest.mark.parametrize('field', ['action_type', 'user_id'])
def test_gate_refuses_empty_action_or_owner_before_allow(service, monkeypatch, field):
    kwargs = dict(module_id=5, action_type='send_email', payload={}, user_id='udita')
    kwargs[field] = '   '
    monkeypatch.setattr(service, 'evaluate_policy', lambda **kwargs: ('allow', {'id': 'fixture'}))
    with pytest.raises(ValueError, match=field):
        service.gate(**kwargs)


@pytest.mark.parametrize('module', [True, 1.0])
def test_submit_refuses_noninteger_catalog_identity(service, module):
    with pytest.raises(ValueError, match='module'):
        submit(service, module_id=module)


@pytest.mark.parametrize('payload', [[], None, 'invalid'])
def test_submit_refuses_nonobject_payload(service, payload):
    with pytest.raises(ValueError, match='payload'):
        submit(service, payload=payload)


@pytest.mark.parametrize('conditions', [[], 'invalid', 1])
def test_policy_refuses_nonobject_conditions(service, conditions):
    with pytest.raises(ValueError, match='conditions'):
        service.upsert_policy(policy_id='fixture', name='Fixture', action_pattern='*',
                              effect='review', actor='fixture', conditions=conditions)


@pytest.mark.parametrize('actor', ['', '   ', None])
def test_decide_refuses_empty_actor_without_changing_pending(service, actor):
    view = submit(service)
    with pytest.raises(ValueError, match='decided_by'):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by=actor)
    assert service.get(view['id'])['status'] == ApprovalStatus.PENDING
    assert [e['event'] for e in service.audit(view['id'])] == ['created']


@pytest.mark.parametrize('key', [1, '', '  '])
def test_policy_refuses_nonstring_or_empty_condition_keys(service, key):
    with pytest.raises(ValueError, match='condition keys'):
        service.upsert_policy(policy_id='fixture', name='Fixture', action_pattern='*',
                              effect='review', actor='fixture', conditions={key: 'value'})


@pytest.mark.parametrize('field', ['actor', 'effect_id'])
def test_consume_refuses_empty_identity_before_permit(service, field):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    kwargs = dict(module_id=view['module_id'], action_type=view['action_type'], payload=view['payload'],
                  user_id=view['user_id'], effect_id='fixture', actor='worker')
    kwargs[field] = '   '
    with pytest.raises(ValueError, match=field):
        service.consume_effect(view['id'], **kwargs)
    assert [e['event'] for e in service.audit(view['id'])] == ['created', 'approved']


def test_submit_nonserializable_payload_does_not_persist_partial_proposal(service):
    from sqlalchemy import select
    from app.modules.m00_approval_center.service import ApprovalRequestRow, ApprovalEventRow
    with pytest.raises(ValueError, match="payload") :
        submit(service, payload={'not_json': object()})
    with service._sessions() as db:
        assert list(db.scalars(select(ApprovalRequestRow))) == []
        assert list(db.scalars(select(ApprovalEventRow))) == []


@pytest.mark.parametrize('field,value', [('action_type', 'a'*101), ('user_id', 'u'*121)])
def test_submit_rejects_identity_exceeding_http_contract(service, field, value):
    with pytest.raises(ValueError, match=field):
        submit(service, **{field: value})


@pytest.mark.parametrize('field,value', [('action_type', 'a'*101), ('user_id', 'u'*121)])
def test_gate_refuses_overlong_identity_before_allow(service, monkeypatch, field, value):
    monkeypatch.setattr(service, 'evaluate_policy', lambda **kwargs: ('allow', {'id': 'fixture'}))
    kwargs = dict(module_id=5, action_type='send_email', payload={}, user_id='udita')
    kwargs[field] = value
    with pytest.raises(ValueError, match=field):
        service.gate(**kwargs)


@pytest.mark.parametrize('field,value', [('effect_id', 'e'*201), ('actor', 'a'*121)])
def test_consume_refuses_overlong_identity(service, field, value):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    kwargs = dict(module_id=view['module_id'], action_type=view['action_type'], payload=view['payload'],
                  user_id=view['user_id'], effect_id='fixture', actor='worker')
    kwargs[field] = value
    with pytest.raises(ValueError, match=field):
        service.consume_effect(view['id'], **kwargs)


def test_existing_permit_replay_does_not_accept_changed_request(service):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    kwargs = dict(module_id=view['module_id'], action_type=view['action_type'], payload=view['payload'],
                  user_id=view['user_id'], effect_id='fixture', actor='worker')
    service.consume_effect(view['id'], **kwargs)
    kwargs['payload'] = {'changed': True}
    with pytest.raises(ApprovalConflictError):
        service.consume_effect(view['id'], **kwargs)


def test_direct_identity_valid_length_boundaries(service):
    view = submit(service, action_type='a'*100, user_id='u'*120)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='a'*120)
    assert service.consume_effect(view['id'], module_id=view['module_id'], action_type=view['action_type'],
                                  payload=view['payload'], user_id=view['user_id'], effect_id='e'*200,
                                  actor='a'*120)['allowed']


def test_decision_actor_rejects_overlong_identity(service):
    view = submit(service)
    with pytest.raises(ValueError, match='decided_by'):
        service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='a'*121)


@pytest.mark.parametrize('field,ceiling', [('policy_id',120), ('name',200), ('action_pattern',200), ('actor',120)])
def test_policy_rejects_overlong_identifier(service, field, ceiling):
    kwargs = dict(policy_id='fixture', name='Fixture', action_pattern='*', effect='review', actor='fixture')
    kwargs[field] = 'a'*(ceiling+1)
    with pytest.raises(ValueError, match=field):
        service.upsert_policy(**kwargs)


def test_valid_policy_nested_conditions_and_wildcards_remain_supported(service):
    service.upsert_policy(policy_id='fixture', name='Fixture', action_pattern='send_*', effect='allow',
                          actor='fixture', conditions={'recipient.role': ['colleague', 'friend']}, tenant_id='udita')
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'recipient': {'role': 'friend'}}, tenant_id='udita')[0] == 'allow'
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'recipient': {'role': 'stranger'}}, tenant_id='udita')[0] == 'review'


@pytest.mark.parametrize('tenant', [None, 1, 't'*121])
def test_policy_refuses_invalid_tenant_identity(service, tenant):
    with pytest.raises(ValueError, match='tenant_id'):
        service.upsert_policy(policy_id='fixture', name='Fixture', action_pattern='*', effect='review',
                              actor='fixture', tenant_id=tenant)


def test_filtered_lists_do_not_cross_owner_boundary(service):
    own = submit(service, user_id='owner-a')
    submit(service, user_id='owner-b')
    assert [row['id'] for row in service.list(user_id='owner-a')] == [own['id']]


@pytest.mark.parametrize('field,value', [('module_id', 6), ('action_type', 'publish'), ('user_id', 'other')])
def test_permit_hash_refuses_changed_request_identity(service, field, value):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    kwargs = dict(module_id=view['module_id'], action_type=view['action_type'], payload=view['payload'],
                  user_id=view['user_id'], effect_id='fixture', actor='worker')
    kwargs[field] = value
    with pytest.raises(ApprovalConflictError, match='does not match'):
        service.consume_effect(view['id'], **kwargs)


def test_gate_refuses_key_exceeding_http_and_column_bound(service):
    with pytest.raises(ValueError, match='idempotency_key'):
        service.gate(module_id=5, action_type='send_email', payload={}, user_id='udita', idempotency_key='k'*201)


@pytest.mark.parametrize('field,value', [('priority', True), ('priority', 1.5), ('enabled', 'false'), ('enabled', 1)])
def test_policy_refuses_wrong_priority_or_enabled_type(service, field, value):
    kwargs = dict(policy_id='fixture', name='Fixture', action_pattern='*', effect='review', actor='fixture')
    kwargs[field] = value
    with pytest.raises(ValueError, match=field):
        service.upsert_policy(**kwargs)


def test_direct_decision_refuses_nonenum_with_validation_error(service):
    view = submit(service)
    with pytest.raises(ValueError, match='decision'):
        service.decide(view['id'], 'approved', decided_by='udita')


@pytest.mark.parametrize('number', [float('nan'), float('inf'), float('-inf')])
def test_gate_refuses_nonfinite_json_payload(service, number):
    with pytest.raises(ValueError):
        service.gate(module_id=5, action_type='send_email', payload={'number': number}, user_id='udita')


@pytest.mark.parametrize('number', [float('nan'), float('inf'), float('-inf')])
def test_submit_refuses_nonfinite_payload_before_storage(service, number):
    with pytest.raises(ValueError):
        submit(service, payload={'number': number})


def test_allow_gate_refuses_nonfinite_payload(service):
    service.upsert_policy(policy_id='allow', name='Fixture', action_pattern='*', effect='allow',
                          actor='fixture', tenant_id='udita')
    with pytest.raises(ValueError, match='payload'):
        service.gate(module_id=5, action_type='send_email', payload={'number': float('nan')}, user_id='udita')


def test_policy_max_identifiers_and_strict_valid_types(service):
    policy = service.upsert_policy(policy_id='p'*120, name='n'*200, action_pattern='a'*200,
                                   effect='review', actor='a'*120, tenant_id='t'*120,
                                   priority=-1, enabled=False)
    assert policy['priority'] == -1 and policy['enabled'] is False


def test_policy_creation_race_error_contract(service, monkeypatch):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    from app.modules.m00_approval_center.service import ApprovalPolicyRow
    original = Session.flush
    entered = []
    kwargs = dict(policy_id='race', name='Fixture', action_pattern='*', effect='review', actor='fixture')
    def compete(db, *args, **kw):
        if not entered and any(isinstance(row, ApprovalPolicyRow) for row in db.new):
            entered.append(True)
            service.upsert_policy(**kwargs)
        return original(db, *args, **kw)
    monkeypatch.setattr(Session, 'flush', compete)
    with pytest.raises(IntegrityError):
        service.upsert_policy(**kwargs)
    assert len(service.list_policies()) == 1


def test_policy_refuses_nonfinite_condition_value(service):
    with pytest.raises(ValueError, match='conditions'):
        service.upsert_policy(policy_id='fixture', name='Fixture', action_pattern='*', effect='review',
                              actor='fixture', conditions={'quantity': float('nan')})






def test_policy_http_unknown_module_maps_to_validation_response(client, service):
    client.app.dependency_overrides[require_admin] = lambda: TenantContext('local', 'admin', frozenset({'atlas-admin'}))
    response = client.put('/approval-center/policies/invalid', json={
        'id': 'invalid', 'name': 'Fixture', 'action_pattern': '*', 'effect': 'review', 'module_id': 999999})
    assert response.status_code == 422


def test_callback_exception_does_not_undo_committed_decision(service):
    view = submit(service)
    def fail(view):
        raise RuntimeError('fixture callback failure')
    service.register_callback(view['id'], fail)
    assert service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')['status'] == ApprovalStatus.APPROVED
    assert [event['event'] for event in service.audit(view['id'])] == ['created', 'approved']


def test_consume_http_whitespace_effect_maps_to_422(client, service):
    from app.auth.context import require_tenant
    client.app.dependency_overrides[require_tenant] = lambda: TenantContext('udita', 'udita')
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    response = client.post(f"/approval-center/requests/{view['id']}/consume", json={
        'module_id': view['module_id'], 'action_type': view['action_type'],
        'payload': view['payload'], 'user_id': view['user_id'], 'effect_id': '   '})
    assert response.status_code == 422


@pytest.mark.parametrize('value', ['false', 1])
def test_policy_list_requires_actual_enabled_only_boolean(service, value):
    with pytest.raises(ValueError, match='enabled_only'):
        service.list_policies(enabled_only=value)


def test_submit_refuses_colliding_json_keys(service):
    with pytest.raises(ValueError, match='payload'):
        submit(service, payload={1: 'first', '1': 'second'})


def test_submit_refuses_nested_nonstring_keys(service):
    with pytest.raises(ValueError, match='payload'):
        submit(service, payload={'nested': [{1: 'value'}]})


def test_review_gate_refuses_nonstring_json_payload_keys(service):
    with pytest.raises(ValueError, match='payload'):
        service.gate(module_id=5, action_type='send_email', payload={1: 'value'}, user_id='udita')


def test_mutating_returned_request_payload_does_not_change_durable_approval(service):
    view = submit(service, payload={'nested': {'recipient': 'original@test'}})
    view['payload']['nested']['recipient'] = 'changed@test'
    assert service.get(view['id'])['payload']['nested']['recipient'] == 'original@test'


def test_request_broadcast_payload_is_not_mutated_by_returned_view(service):
    subscriber = service.broadcaster.subscribe()
    view = submit(service, payload={'nested': {'recipient': 'original@test'}})
    view['payload']['nested']['recipient'] = 'changed@test'
    assert subscriber.get_nowait()['approval']['payload']['nested']['recipient'] == 'original@test'


def test_broadcast_subscribers_do_not_share_mutable_approval_payload():
    broadcaster = ApprovalBroadcaster()
    first = broadcaster.subscribe()
    second = broadcaster.subscribe()
    broadcaster.publish({'approval': {'payload': {'recipient': 'original@test'}}})
    first.get_nowait()['approval']['payload']['recipient'] = 'changed@test'
    assert second.get_nowait()['approval']['payload']['recipient'] == 'original@test'


@pytest.mark.parametrize('size', [0, -1, True, 1.5])
def test_broadcaster_queue_size_must_be_positive_integer(size):
    with pytest.raises(ValueError, match='max_queue_size'):
        ApprovalBroadcaster(max_queue_size=size)


def test_callback_cannot_mutate_next_callback_or_returned_decision(service):
    view = submit(service, payload={'nested': {'recipient': 'original@test'}})
    calls = []
    def mutate(result):
        result['payload']['nested']['recipient'] = 'changed@test'
    service.register_callback(view['id'], mutate)
    service.register_callback(view['id'], calls.append)
    decided = service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    assert calls[0]['payload']['nested']['recipient'] == 'original@test'
    assert decided['payload']['nested']['recipient'] == 'original@test'


def test_full_subscriber_queue_does_not_block_other_subscriber():
    broadcaster = ApprovalBroadcaster(max_queue_size=1)
    full = broadcaster.subscribe()
    fresh = broadcaster.subscribe()
    broadcaster.publish({'value': 1})
    fresh.get_nowait()
    broadcaster.publish({'value': 2})
    assert full.get_nowait()['value'] == 1
    assert fresh.get_nowait()['value'] == 2


@pytest.mark.parametrize('field,value', [('timeout_seconds', float('nan')),
                                        ('timeout_seconds', float('inf')),
                                        ('poll_interval_seconds', 0), ('poll_interval_seconds', -1)])
def test_wait_refuses_invalid_parameters_even_for_terminal_request(service, field, value):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    with pytest.raises(ValueError, match=field):
        service.wait_for_decision(view['id'], **{field: value})


def test_pending_nan_wait_is_rejected_before_poll_loop(tmp_path):
    import subprocess
    import sys
    import os
    script = '''
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m00_approval_center.service import Service
import sys
engine=create_engine('sqlite:///'+sys.argv[1])
Base.metadata.create_all(engine)
s=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False))
a=s.submit(module_id=5,action_type='send_email',payload={},user_id='fixture')
try:s.wait_for_decision(a['id'],timeout_seconds=float('nan'),poll_interval_seconds=.01)
except ValueError:sys.exit(0)
sys.exit(2)
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path/'wait.db')],
                            env={**os.environ, 'PYTHONPATH': 'backend'}, capture_output=True, timeout=3)
    assert result.returncode == 0, result.stderr.decode()


def test_wait_timeout_does_not_sleep_past_remaining_deadline(service):
    view = submit(service)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        service.wait_for_decision(view['id'], timeout_seconds=.1, poll_interval_seconds=1)
    assert time.monotonic()-started < .5


def test_wait_rejects_unrepresentable_integer_timeout_cleanly(service):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    with pytest.raises(ValueError, match='timeout_seconds'):
        service.wait_for_decision(view['id'], timeout_seconds=10**1000)


def test_register_callback_requires_callable(service):
    view = submit(service)
    with pytest.raises(ValueError, match='callback'):
        service.register_callback(view['id'], 'not callable')


def test_broadcast_failure_after_submit_leaves_committed_request(service, monkeypatch):
    from sqlalchemy import select
    from app.modules.m00_approval_center.service import ApprovalRequestRow
    def fail(event):
        raise RuntimeError('fixture broadcast failure')
    monkeypatch.setattr(service.broadcaster, 'publish', fail)
    with pytest.raises(RuntimeError, match='broadcast failure'):
        submit(service)
    with service._sessions() as db:
        rows = list(db.scalars(select(ApprovalRequestRow)))
        assert len(rows) == 1
        aid = rows[0].id
    assert [e['event'] for e in service.audit(aid)] == ['created']


def test_callback_registered_after_decision_is_not_replayed(service):
    view = submit(service)
    service.decide(view['id'], ApprovalStatus.APPROVED, decided_by='udita')
    calls = []
    service.register_callback(view['id'], calls.append)
    assert calls == []


def test_valid_http_policy_write_and_list(client):
    client.app.dependency_overrides[require_admin] = lambda: TenantContext('local', 'admin', frozenset({'atlas-admin'}))
    response = client.put('/approval-center/policies/fixture', json={
        'id': 'fixture', 'name': 'Fixture', 'action_pattern': 'send_*', 'effect': 'review',
        'module_id': 5, 'conditions': {'recipient.role': ['friend']}})
    assert response.status_code == 200
    assert client.get('/approval-center/policies?enabled_only=true').json()[0]['id'] == 'fixture'


def test_empty_nested_condition_segment_remains_exact_lookup(service):
    service.upsert_policy(policy_id='fixture', name='Fixture', action_pattern='*', effect='allow',
                          actor='fixture', tenant_id='udita', conditions={'recipient..role': 'friend'})
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'recipient': {'role': 'friend'}}, tenant_id='udita')[0] == 'review'


@pytest.mark.parametrize('wanted,current', [(True, 1), ([True], 1),
                                           ({'flag': True}, {'flag': 1}),
                                           ([{'flags': [False]}], {'flags': [0]})])
def test_allow_policy_never_matches_json_boolean_as_number(service, wanted, current):
    service.upsert_policy(policy_id='bool-boundary', name='Fixture', action_pattern='*',
                          effect='allow', actor='fixture', tenant_id='udita', conditions={'value': wanted})
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'value': current}, tenant_id='udita')[0] == 'review'


def test_condition_exact_values_preserve_numeric_and_nested_membership_controls(service):
    service.upsert_policy(policy_id='bool-boundary', name='Fixture', action_pattern='*',
                          effect='allow', actor='fixture', tenant_id='udita',
                          conditions={'number': 1, 'nested': [{'flags': [True, False]}]})
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'number': 1.0, 'nested': {'flags': [True, False]}},
                                   tenant_id='udita')[0] == 'allow'


@pytest.mark.parametrize('conditions', [{'value': {1: 'value'}},
                                       {'value': [{1: 'value'}]},
                                       {'value': {'nested': {1: 'value'}}}])
def test_policy_refuses_nested_nonstring_condition_keys(service, conditions):
    with pytest.raises(ValueError, match='conditions'):
        service.upsert_policy(policy_id='key-boundary', name='Fixture', action_pattern='*',
                              effect='allow', actor='fixture', conditions=conditions)
    assert service.list_policies() == []


def test_policy_nested_string_key_conditions_roundtrip_unchanged(service):
    conditions = {'value': [{'nested': {'1': 'value', '': 'empty string key'}}]}
    policy = service.upsert_policy(policy_id='key-boundary', name='Fixture', action_pattern='*',
                                   effect='allow', actor='fixture', conditions=conditions)
    assert policy['conditions'] == conditions
    assert service.list_policies()[0]['conditions'] == conditions


@pytest.mark.parametrize('effect', ['deny', 'review'])
@pytest.mark.parametrize('wanted,current', [(True, 1), (False, 0)])
def test_deny_review_boolean_rules_do_not_match_numbers_and_keep_real_booleans(service, effect, wanted, current):
    service.upsert_policy(policy_id='fallback', name='Fallback', action_pattern='*', effect='allow',
                          actor='fixture', tenant_id='udita', priority=0)
    service.upsert_policy(policy_id='typed', name='Typed', action_pattern='*', effect=effect,
                          actor='fixture', tenant_id='udita', priority=10, conditions={'value': wanted})
    actual = service.evaluate_policy(module_id=5, action_type='send_email',
                                     context={'value': wanted}, tenant_id='udita')
    assert actual[0] == effect and actual[1]['id'] == 'typed'
    numeric = service.evaluate_policy(module_id=5, action_type='send_email',
                                      context={'value': current}, tenant_id='udita')
    assert numeric[0] == 'allow' and numeric[1]['id'] == 'fallback'


@pytest.mark.parametrize('top_effect', ['allow', 'deny', 'review'])
def test_policy_priority_precedes_effect_severity_for_numeric_equivalence(service, top_effect):
    for effect in ['allow', 'deny', 'review']:
        service.upsert_policy(policy_id=effect, name=effect, action_pattern='*', effect=effect,
                              actor='fixture', tenant_id='udita', conditions={'number': 1},
                              priority=10 if effect == top_effect else 0)
    selected = service.evaluate_policy(module_id=5, action_type='send_email',
                                        context={'number': 1.0}, tenant_id='udita')
    assert selected[0] == top_effect and selected[1]['id'] == top_effect


@pytest.mark.parametrize('effects,expected', [(['allow', 'deny', 'review'], 'deny'),
                                             (['allow', 'review'], 'review')])
def test_equal_priority_policy_severity_remains_deny_then_review_then_allow(service, effects, expected):
    for effect in effects:
        service.upsert_policy(policy_id=effect, name=effect, action_pattern='*', effect=effect,
                              actor='fixture', tenant_id='udita', conditions={'number': 1}, priority=10)
    selected = service.evaluate_policy(module_id=5, action_type='send_email',
                                        context={'number': 1.0}, tenant_id='udita')
    assert selected[0] == expected and selected[1]['id'] == expected


def test_policy_write_and_list_views_do_not_mutate_persisted_conditions(service):
    conditions = {'value': {'nested': [True, False]}}
    written = service.upsert_policy(policy_id='alias', name='Fixture', action_pattern='*',
                                    effect='review', actor='fixture', conditions=conditions)
    written['conditions']['value']['nested'][0] = 'changed'
    listed = service.list_policies()
    assert listed[0]['conditions'] == {'value': {'nested': [True, False]}}
    listed[0]['conditions']['value']['nested'][1] = 'changed'
    assert service.list_policies()[0]['conditions'] == {'value': {'nested': [True, False]}}


def test_policy_tuple_condition_write_returns_pre_storage_representation(service):
    conditions = {'value': {'sequence': (1, 2)}}
    written = service.upsert_policy(policy_id='representation', name='Fixture', action_pattern='*',
                                    effect='review', actor='fixture', conditions=conditions)
    assert written['conditions'] == {'value': {'sequence': (1, 2)}}
    assert service.list_policies()[0]['conditions'] == {'value': {'sequence': [1, 2]}}


def test_same_policy_id_across_tenants_shares_unscoped_event_identity(service):
    from sqlalchemy import select
    from app.modules.m00_approval_center.service import ApprovalEventRow
    for tenant in ['tenant-a', 'tenant-b']:
        service.upsert_policy(policy_id='shared', name='Fixture', action_pattern='*', effect='review',
                              actor='admin-' + tenant, tenant_id=tenant)
    with service._sessions() as db:
        events = list(db.scalars(select(ApprovalEventRow).where(ApprovalEventRow.approval_id == 'policy:shared')))
    assert len(events) == 2
    assert {event.actor for event in events} == {'admin-tenant-a', 'admin-tenant-b'}
    assert [policy['tenant_id'] for policy in service.list_policies(tenant_id='tenant-a')] == ['tenant-a']
    assert [policy['tenant_id'] for policy in service.list_policies(tenant_id='tenant-b')] == ['tenant-b']


def test_policy_long_valid_identity_exceeds_shared_event_column_width(service):
    from sqlalchemy import select
    from app.modules.m00_approval_center.service import ApprovalEventRow
    policy_id = 'p'*120
    service.upsert_policy(policy_id=policy_id, name='Fixture', action_pattern='*',
                          effect='review', actor='admin', tenant_id='tenant-a')
    with service._sessions() as db:
        event = db.scalar(select(ApprovalEventRow).where(ApprovalEventRow.approval_id == 'policy:' + policy_id))
    assert len(event.approval_id) == 127
    assert ApprovalEventRow.__table__.c.approval_id.type.length == 36


def test_policy_priority_sqlite_overflow_rolls_back_policy_and_event(service):
    from sqlalchemy import select
    from app.modules.m00_approval_center.service import ApprovalEventRow
    with pytest.raises(OverflowError):
        service.upsert_policy(policy_id='priority-boundary', name='Fixture', action_pattern='*',
                              effect='review', actor='fixture', priority=2**63)
    assert service.list_policies() == []
    with service._sessions() as db:
        assert list(db.scalars(select(ApprovalEventRow))) == []


def test_policy_event_is_sdk_readable_but_has_no_request_audit_http_route(client, service):
    from app.auth.context import require_tenant
    service.upsert_policy(policy_id='audit', name='Fixture', action_pattern='*',
                          effect='review', actor='admin', tenant_id='udita')
    assert [event['event'] for event in service.audit('policy:audit')] == ['policy_created']
    client.app.dependency_overrides[require_tenant] = lambda: TenantContext('udita', 'admin', frozenset({'atlas-admin'}))
    assert client.get('/approval-center/requests/policy:audit/audit').status_code == 404


def test_policy_input_mutation_after_commit_does_not_change_stored_matching(service):
    conditions = {'value': {'flag': True}}
    service.upsert_policy(policy_id='input-alias', name='Fixture', action_pattern='*',
                          effect='allow', actor='fixture', tenant_id='udita', conditions=conditions)
    conditions['value']['flag'] = False
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'value': {'flag': True}}, tenant_id='udita')[0] == 'allow'
    assert service.evaluate_policy(module_id=5, action_type='send_email',
                                   context={'value': {'flag': False}}, tenant_id='udita')[0] == 'review'


def test_actual_sqlite_policy_migration_keeps_id_only_primary_key(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path('migrations/versions/20260922_m00_policy_tenant_isolation.py')
    spec = importlib.util.spec_from_file_location('m00_policy_tenant_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f"sqlite:///{tmp_path}/migrated.db")
    metadata = sa.MetaData()
    table = sa.Table('m00_approval_policies', metadata,
                     sa.Column('id', sa.String(120), primary_key=True),
                     sa.Column('name', sa.String(200), nullable=False))
    metadata.create_all(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
    assert sa.inspect(engine).get_pk_constraint('m00_approval_policies')['constrained_columns'] == ['id']
    migrated = sa.Table('m00_approval_policies', sa.MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(migrated.insert().values(id='shared', name='A', tenant_id='tenant-a'))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(migrated.insert().values(id='shared', name='B', tenant_id='tenant-b'))
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
    assert 'tenant_id' not in [column['name'] for column in sa.inspect(engine).get_columns('m00_approval_policies')]


def test_full_clean_sqlite_migration_retains_single_policy_primary_key(tmp_path):
    import os
    import sqlite3
    import subprocess
    import sys
    database = tmp_path / 'full-chain.db'
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                            env={**os.environ, 'ATLAS_DATABASE_URL': f'sqlite:///{database}'},
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database) as db:
        columns = db.execute("pragma table_info('m00_approval_policies')").fetchall()
    assert {column[1] for column in columns if column[5]} == {'id'}
    assert 'tenant_id' in {column[1] for column in columns}
    from app.modules.m00_approval_center.service import ApprovalPolicyRow
    assert {column.name for column in ApprovalPolicyRow.__table__.primary_key} == {'tenant_id', 'id'}
