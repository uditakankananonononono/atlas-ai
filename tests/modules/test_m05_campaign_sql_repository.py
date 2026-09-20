"""Durable SQL tests for the campaign repository: tenant scoping + audit."""

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m05_outreach_manager.campaigns import (
    Campaign,
    MessageEvent,
    OutreachMessage,
)
from app.modules.m05_outreach_manager.sql_repository import SqlCampaignRepository


def repo(tmp_path, tenant):
    engine = create_engine(f"sqlite:///{tmp_path/'campaigns.db'}")
    Base.metadata.create_all(engine)
    return SqlCampaignRepository(tenant, sessionmaker(bind=engine, expire_on_commit=False))


def make_campaign(now):
    return Campaign(
        id="camp-1", project_id="atlas", name="Summer", goal="Find supervisors",
        audience="professor", status="active", max_follow_ups=2,
        follow_up_window_days=5, created_at=now, updated_at=now,
    )


def make_message(now, **overrides):
    base = dict(
        id="msg-1", campaign_id="camp-1", contact_id="c1", sequence=1, kind="initial",
        subject="Hi", body="Body", status="draft", approval_id=None, provider=None,
        model=None, thread_id=None, sent_at=None, created_at=now, updated_at=now, version=1,
    )
    base.update(overrides)
    return OutreachMessage(**base)


def test_campaigns_are_durable_and_tenant_scoped(tmp_path):
    now = datetime.now(timezone.utc)
    a = repo(tmp_path, "a")
    b = repo(tmp_path, "b")
    a.save_campaign(make_campaign(now))
    assert a.get_campaign("camp-1").goal == "Find supervisors"
    assert b.get_campaign("camp-1") is None
    assert [c.id for c in a.list_campaigns(project_id="atlas")] == ["camp-1"]
    assert a.list_campaigns(project_id="other") == []


def test_messages_and_events_are_durable_and_tenant_scoped(tmp_path):
    now = datetime.now(timezone.utc)
    a = repo(tmp_path, "a")
    b = repo(tmp_path, "b")
    a.save_campaign(make_campaign(now))
    message = make_message(now)
    a.save_message(message, MessageEvent(message_id="msg-1", event="drafted", actor=None, at=now, details={}))
    sent = message.model_copy(update={"status": "sent", "sent_at": now, "version": 2})
    a.save_message(sent, MessageEvent(message_id="msg-1", event="sent", actor=None, at=now, details={"thread_id": "t-1"}))

    stored = a.get_message("msg-1")
    assert stored.status == "sent" and stored.version == 2 and stored.sent_at == now
    assert b.get_message("msg-1") is None
    assert [m.id for m in a.list_messages(status="sent")] == ["msg-1"]
    assert a.list_messages(status="draft") == []
    events = a.events("msg-1")
    assert [e.event for e in events] == ["drafted", "sent"]
    assert events[1].details == {"thread_id": "t-1"}
    assert b.events("msg-1") == []
