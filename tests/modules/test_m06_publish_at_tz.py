"""Pins for M06 publish_at timezone handling (input + direct-caller boundary).

Route schemas reject naive publish_at (unknown provenance); the Scheduler's
direct-caller boundary rejects it too, so bypassing the route cannot sneak a
naive instant in. Aware inputs keep their offset end to end: schedule_data
serializes with isoformat and fromisoformat restores it, so the INSTANT
survives the JSON row untouched. Legacy pre-policy rows stored naive still
load; the documented convention treats them as UTC.

Establishes input validation and instant preservation only; no publish gate,
approval, or adapter semantics change.
"""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m06_social_media_manager.models import ContentPlan, Platform, PlatformDraft
from app.modules.m06_social_media_manager.scheduler import Scheduler, ScheduleEntry
from app.modules.m06_social_media_manager.schemas import RescheduleIn, ScheduleIn
from app.modules.m06_social_media_manager.service import MemorySocialRepository
from app.modules.m06_social_media_manager.sql_repository import SqlSocialRepository

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
OFFSET = timezone(timedelta(hours=5, minutes=30))

def test_route_schemas_reject_naive_publish_at():
    with pytest.raises(ValidationError, match="timezone-aware"):
        ScheduleIn(publish_at=datetime(2026, 10, 8, 15, 0))
    with pytest.raises(ValidationError, match="timezone-aware"):
        RescheduleIn(publish_at=datetime(2026, 10, 8, 15, 0))
    assert ScheduleIn(publish_at=datetime(2026, 10, 8, 15, 0, tzinfo=OFFSET)).publish_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert ScheduleIn().publish_at is None  # omitted stays allowed

def _scheduler():
    class _Decisions:
        def status_of(self, approval_id): return None
    class _Adapters:
        def for_platform(self, platform): raise AssertionError("no publish in these pins")
    repo = MemorySocialRepository()
    return Scheduler(repository=repo, decisions=_Decisions(), adapter_factory=_Adapters(), clock=lambda: NOW), repo

def _plan():
    return ContentPlan(id="p1", brief="b", drafts=[PlatformDraft(platform=Platform.TWITTER, format="post", post_copy="hi")], created_at=NOW)

def test_scheduler_direct_caller_rejects_naive_publish_at():
    scheduler, _ = _scheduler()
    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.create_entries(_plan(), publish_at=datetime(2026, 10, 8, 15, 0),
                                 approval_ids={Platform.TWITTER: "a1"})
    entry = scheduler.create_entries(_plan(), publish_at=NOW + timedelta(days=1),
                                     approval_ids={Platform.TWITTER: "a1"})[0]
    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.reschedule(entry.id, datetime(2026, 10, 9, 15, 0))

def _sql_repo():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return SqlSocialRepository("tenant-1", session_factory=sessionmaker(bind=engine, expire_on_commit=False))

def test_aware_offset_publish_at_survives_sql_round_trip():
    # 15:00+05:30 IS 09:30Z: the loaded instant must stay 09:30Z, not 15:00Z.
    repo = _sql_repo()
    entry = ScheduleEntry(id="s1", plan_id="p1", platform=Platform.TWITTER, format="post",
                          text="hi", publish_at=datetime(2026, 10, 8, 15, 0, tzinfo=OFFSET),
                          approval_id="a1")
    repo.save_schedule(entry)
    loaded = repo.get_schedule("s1")
    assert loaded.publish_at == datetime(2026, 10, 8, 9, 30, tzinfo=timezone.utc)
    assert loaded.publish_at.tzinfo is not None

def test_legacy_naive_row_loads_and_compares_as_utc():
    # Characterization of the documented legacy convention: a pre-policy row
    # stored with a naive publish_at loads naive and due_entries treats it as
    # UTC. This documents the assumption; it does not bless new naive writes.
    repo = _sql_repo()
    legacy = ScheduleEntry(id="s2", plan_id="p1", platform=Platform.TWITTER, format="post",
                           text="hi", publish_at=datetime(2026, 9, 20, 11, 0),  # naive, pre-policy
                           approval_id="a1", status="approved")
    repo.save_schedule(legacy)
    loaded = repo.get_schedule("s2")
    assert loaded.publish_at.tzinfo is None
    scheduler, _ = _scheduler()
    scheduler._repository = repo
    assert [e.id for e in scheduler.due_entries(NOW)] == ["s2"]  # 11:00 naive treated as 11:00Z
