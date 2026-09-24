"""M00 approval impact preview: live-state drift blocks consumption."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import impact, routes
from app.modules.m00_approval_center.service import ApprovalBroadcaster, ApprovalConflictError, Service

T0 = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
PAYLOAD = {"thread_id": "t-1", "to": "prof@example.edu", "body": "Following up on the RA role"}


class Clock:
    now = T0
    def __call__(self):
        return self.now


@pytest.fixture
def world():
    """Stand-in external system the probe reads: a mail thread's live state."""
    return {"t-1": {"last_message_id": "m-3", "reply_count": 2, "subject": "RA role"}}


@pytest.fixture
def registry(world):
    reg = impact.ProbeRegistry()
    reg.register("send_*", lambda payload: dict(world[payload["thread_id"]]), module_id=5)
    return reg


@pytest.fixture
def service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m00.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return Service(session_factory=sessionmaker(bind=engine, expire_on_commit=False),
                   broadcaster=ApprovalBroadcaster(), clock=Clock())


def _approved(service, registry, capture=True):
    view = service.submit(module_id=5, action_type="send_email", payload=PAYLOAD, user_id="udita")
    if capture:
        impact.capture_review_state(service, view["id"], registry=registry)
    service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    return view["id"]


def _consume(service, registry, aid, effect="mail-1"):
    return impact.consume_effect_checked(service, aid, module_id=5, action_type="send_email",
        payload=PAYLOAD, user_id="udita", effect_id=effect, actor="worker", registry=registry)


def test_unchanged_state_consumes_and_reports_hash(service, registry):
    aid = _approved(service, registry)
    preview = impact.impact_preview(service, aid, registry=registry)
    assert preview["verdict"] == "unchanged" and preview["safe_to_consume"] is True
    assert preview["effect"] == PAYLOAD
    permit = _consume(service, registry, aid)
    assert permit["allowed"] and permit["state_verdict"] == "unchanged"
    assert permit["state_hash"] == preview["reviewed"]["state_hash"]


def test_new_reply_after_review_blocks_the_send(service, registry, world):
    aid = _approved(service, registry)
    world["t-1"].update(last_message_id="m-4", reply_count=3)
    preview = impact.impact_preview(service, aid, registry=registry)
    assert preview["verdict"] == "drifted" and preview["safe_to_consume"] is False
    assert {d["path"] for d in preview["drift"]} == {"last_message_id", "reply_count"}
    with pytest.raises(impact.StateDriftError, match="re-review required"):
        _consume(service, registry, aid)
    events = [e["event"] for e in service.audit(aid)]
    assert events[-1] == "effect_blocked_drift" and "effect_consumed" not in events


def test_review_state_is_frozen_once_decided(service, registry):
    aid = _approved(service, registry)
    with pytest.raises(ApprovalConflictError, match="frozen"):
        impact.capture_review_state(service, aid, registry=registry)


def test_missing_probe_after_review_fails_closed(service, registry):
    aid = _approved(service, registry)
    with pytest.raises(ApprovalConflictError, match="cannot verify state"):
        _consume(service, impact.ProbeRegistry(), aid)


def test_no_snapshot_keeps_existing_behaviour(service, registry):
    aid = _approved(service, registry, capture=False)
    assert impact.impact_preview(service, aid, registry=registry)["verdict"] == "no_review_snapshot"
    assert _consume(service, registry, aid)["state_verdict"] == "no_review_snapshot"


def test_payload_tampering_still_rejected_by_hash(service, registry):
    aid = _approved(service, registry)
    with pytest.raises(ApprovalConflictError, match="does not match"):
        impact.consume_effect_checked(service, aid, module_id=5, action_type="send_email",
            payload={**PAYLOAD, "to": "attacker@example.test"}, user_id="udita",
            effect_id="mail-1", actor="worker", registry=registry)


def test_diff_handles_nested_lists_and_removals():
    changes = impact.diff({"a": {"b": [1, 2]}, "gone": 1}, {"a": {"b": [1, 3]}, "new": True})
    assert changes == [
        {"path": "a.b[1]", "change": "changed", "before": 2, "after": 3},
        {"path": "gone", "change": "removed", "before": 1},
        {"path": "new", "change": "added", "after": True},
    ]


def test_most_specific_probe_wins():
    reg = impact.ProbeRegistry()
    reg.register("*", lambda p: {"generic": True})
    reg.register("send_email", lambda p: {"specific": True}, module_id=5)
    assert reg.find(5, "send_email")[1]({}) == {"specific": True}
    assert reg.find(6, "send_email")[1]({}) == {"generic": True}


def test_http_preview_and_drift_409(service, registry, world, monkeypatch):
    monkeypatch.setattr(impact, "PROBES", registry)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_service] = lambda: service
    client = TestClient(app, headers={"x-atlas-tenant": "udita"})
    view = service.submit(module_id=5, action_type="send_email", payload=PAYLOAD, user_id="udita")
    captured = client.post(f"/approval-center/requests/{view['id']}/review-state",
                           json={"state": dict(world["t-1"])})
    assert captured.status_code == 200 and captured.json()["probe"] == "explicit"
    service.decide(view["id"], ApprovalStatus.APPROVED, decided_by="udita")
    world["t-1"]["reply_count"] = 5
    monkeypatch.setattr(routes, "impact_preview", lambda svc, aid: impact.impact_preview(svc, aid, registry=registry))
    monkeypatch.setattr(routes, "consume_effect_checked", lambda svc, aid, **k: impact.consume_effect_checked(svc, aid, registry=registry, **k))
    preview = client.get(f"/approval-center/requests/{view['id']}/impact-preview").json()
    assert preview["verdict"] == "drifted" and preview["drift"][0]["path"] == "reply_count"
    blocked = client.post(f"/approval-center/requests/{view['id']}/consume",
        json={"module_id": 5, "action_type": "send_email", "payload": PAYLOAD, "effect_id": "mail-9"})
    assert blocked.status_code == 409 and blocked.json()["detail"]["drift"][0]["after"] == 5
    other = TestClient(app, headers={"x-atlas-tenant": "someone-else"})
    assert other.get(f"/approval-center/requests/{view['id']}/impact-preview").status_code == 404
