"""Naive publish_at must be rejected everywhere it enters (pinned fail-then-pass)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.modules.m06_social_media_manager.models import ContentPlan, Platform, PlatformDraft
from app.modules.m06_social_media_manager.schemas import RescheduleIn, ScheduleIn
from app.modules.m06_social_media_manager.scheduler import NaivePublishTimeError, Scheduler
from app.modules.m06_social_media_manager.service import MemorySocialRepository
from tests.modules.test_m06_schedule_verify_lane import Adapter, Decisions, Factory, NOW, REFS, _build

NAIVE = datetime(2026, 10, 8, 17, 30)
IST = timezone(timedelta(hours=5, minutes=30))


def test_service_rejects_naive_before_any_side_effect():
    svc, store, sch, repo, adapter, dec = _build()
    with pytest.raises(NaivePublishTimeError):
        svc.request_schedule("p1", NAIVE, references=REFS)
    assert store.items == [] and repo.list_schedules() == []
    assert svc.get_plan("p1").status == "draft"


def test_service_naive_rejected_even_without_scheduler_wired():
    svc, store, *_ = _build()
    svc._scheduler = None
    with pytest.raises(NaivePublishTimeError):
        svc.request_schedule("p1", NAIVE, references=REFS)
    assert store.items == []


def test_none_still_means_now_and_aware_still_works():
    svc, store, sch, repo, adapter, dec = _build()
    r = svc.request_schedule("p1", None, references=REFS)
    assert datetime.fromisoformat(r[0].payload["publish_at"]).tzinfo is not None
    r2 = svc.request_schedule("p1", datetime(2026, 10, 8, 17, 30, tzinfo=IST), references=REFS)
    assert datetime.fromisoformat(r2[0].payload["publish_at"]) == NOW


def test_scheduler_create_entries_and_reschedule_reject_naive():
    repo = MemorySocialRepository()
    sch = Scheduler(repository=repo, decisions=Decisions(), adapter_factory=Factory(Adapter()), clock=lambda: NOW)
    plan = ContentPlan(id="q", brief="b", created_at=NOW,
                       drafts=[PlatformDraft(Platform.LINKEDIN, "article_post", "hello")])
    with pytest.raises(NaivePublishTimeError):
        sch.create_entries(plan, publish_at=NAIVE, approval_ids={Platform.LINKEDIN: "a1"})
    assert repo.list_schedules() == []
    e = sch.create_entries(plan, publish_at=NOW, approval_ids={Platform.LINKEDIN: "a1"})[0]
    with pytest.raises(NaivePublishTimeError):
        sch.reschedule(e.id, NAIVE)
    assert repo.get_schedule(e.id).publish_at == NOW


def test_schemas_reject_naive_but_accept_offset_and_z():
    for cls in (ScheduleIn, RescheduleIn):
        with pytest.raises(ValidationError):
            cls(publish_at="2026-10-08T17:30:00")
        assert cls(publish_at="2026-10-08T17:30:00+05:30").publish_at.utcoffset() == timedelta(hours=5, minutes=30)
        assert cls(publish_at="2026-10-08T12:00:00Z").publish_at.tzinfo is not None
    assert ScheduleIn().publish_at is None


def test_legacy_stored_naive_entry_is_still_treated_as_utc_when_due():
    """Legacy provenance: rows saved before this guard may be naive; due-scan reads them as UTC."""
    repo = MemorySocialRepository()
    dec, ad = Decisions(), Adapter()
    sch = Scheduler(repository=repo, decisions=dec, adapter_factory=Factory(ad), clock=lambda: NOW)
    plan = ContentPlan(id="q", brief="b", created_at=NOW,
                       drafts=[PlatformDraft(Platform.LINKEDIN, "article_post", "hello")])
    e = sch.create_entries(plan, publish_at=NOW - timedelta(hours=1), approval_ids={Platform.LINKEDIN: "a1"})[0]
    e.publish_at = datetime(2026, 10, 8, 11, 0)  # simulate legacy naive row
    repo.save_schedule(e)
    dec.s["a1"] = "approved"
    sch.sync_decisions()
    assert len(sch.execute_due(NOW)) == 1  # 11:00 naive == 11:00Z <= 12:00Z
    e2 = sch.create_entries(plan, publish_at=NOW - timedelta(hours=1), approval_ids={Platform.LINKEDIN: "a2"})[0]
    e2.publish_at = datetime(2026, 10, 8, 13, 0)
    repo.save_schedule(e2)
    dec.s["a2"] = "approved"
    sch.sync_decisions()
    assert sch.execute_due(NOW) == []  # 13:00Z in the future
