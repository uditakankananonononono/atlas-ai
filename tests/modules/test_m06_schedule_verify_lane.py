"""Independent verification of M06 request_schedule -> approval -> scheduler gate.

Probes behaviour only; asserts what actually happens, including known gaps.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.schemas import ScheduleIn
from app.modules.m06_social_media_manager.scheduler import STATUS_PUBLISHED, Scheduler
from app.modules.m06_social_media_manager.service import (
    DraftComplianceError,
)
from app.modules.m06_social_media_manager.adapters import PublishResult

SRC = "Our pilot cut clinic wait times by 38% across 12 sites [1]."
REFS = {1: {"url": "https://health.example.gov/study", "title": "District Health Study"}}
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
SECRET_KEYS = ("token", "secret", "password", "credential", "api_key", "authorization")


class Decisions:
    def __init__(self):
        self.s = {}

    def status_of(self, i):
        return self.s.get(i)


class Adapter:
    def __init__(self):
        self.published = []

    async def publish(self, request):
        self.published.append(request)
        return PublishResult(platform=request.platform, external_id="x1", url="https://x.example/1")


class Factory:
    def __init__(self, a):
        self.a = a

    def for_platform(self, p):
        return self.a


def _build():
    from tests.modules.test_m06_adaptation import _gate_service
    svc, store = _gate_service([(Platform.LINKEDIN, "article_post", SRC)])
    repo = svc._repository
    adapter, dec = Adapter(), Decisions()
    sch = Scheduler(repository=repo, decisions=dec, adapter_factory=Factory(adapter), clock=lambda: NOW)
    svc._scheduler = sch
    return svc, store, sch, repo, adapter, dec


def test_schedule_requires_approval_before_any_publish():
    svc, store, sch, repo, adapter, dec = _build()
    reqs = svc.request_schedule("p1", NOW - timedelta(hours=1), references=REFS)
    assert len(reqs) == 1 and reqs[0].payload["schedule_id"]
    assert sch.execute_due(NOW) == [] and adapter.published == []
    dec.s[reqs[0].id] = "approved"
    sch.sync_decisions()
    recs = sch.execute_due(NOW)
    assert len(recs) == 1 and len(adapter.published) == 1
    assert repo.get_schedule(reqs[0].payload["schedule_id"]).status == STATUS_PUBLISHED


def test_future_publish_at_does_not_publish_even_when_approved():
    svc, store, sch, repo, adapter, dec = _build()
    reqs = svc.request_schedule("p1", NOW + timedelta(hours=2), references=REFS)
    dec.s[reqs[0].id] = "approved"
    sch.sync_decisions()
    assert sch.execute_due(NOW) == [] and adapter.published == []


def test_denied_never_publishes():
    svc, store, sch, repo, adapter, dec = _build()
    reqs = svc.request_schedule("p1", NOW - timedelta(hours=1), references=REFS)
    dec.s[reqs[0].id] = "denied"
    sch.sync_decisions()
    assert sch.execute_due(NOW) == [] and adapter.published == []


def test_blocked_request_files_nothing_and_creates_no_entry():
    from tests.modules.test_m06_adaptation import _gate_service
    svc, store = _gate_service([(Platform.TWITTER, "thread", "Pilot cut waits 50%!")])
    repo = svc._repository
    svc._scheduler = Scheduler(repository=repo, decisions=Decisions(), adapter_factory=Factory(Adapter()), clock=lambda: NOW)
    with pytest.raises(DraftComplianceError):
        svc.request_schedule("p1", NOW, references=REFS)
    assert store.items == [] and repo.list_schedules() == []


def test_payload_has_no_secret_like_keys():
    svc, store, *_ = _build()
    reqs = svc.request_schedule("p1", NOW, references=REFS)
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield str(k).lower(); yield from keys(v)
    assert not [k for k in keys(reqs[0].payload) if any(s in k for s in SECRET_KEYS)]
    assert reqs[0].payload["api"] and reqs[0].payload["publish_at"]


def test_aware_offset_preserves_instant():
    from datetime import timezone as tz
    ist = tz(timedelta(hours=5, minutes=30))
    svc, store, sch, repo, adapter, dec = _build()
    when = datetime(2026, 10, 8, 17, 30, tzinfo=ist)  # == 12:00Z
    reqs = svc.request_schedule("p1", when, references=REFS)
    assert datetime.fromisoformat(reqs[0].payload["publish_at"]) == NOW


def test_naive_publish_at_current_behaviour_is_silently_utc():
    """KNOWN GAP probe: naive input is accepted and treated as UTC, no error."""
    svc, store, sch, repo, adapter, dec = _build()
    naive = datetime(2026, 10, 8, 17, 30)  # user may mean IST
    reqs = svc.request_schedule("p1", naive, references=REFS)
    stored = reqs[0].payload["publish_at"]
    assert "+" not in stored and not stored.endswith("Z")  # offset lost in approval payload
    assert repo.get_schedule(reqs[0].payload["schedule_id"]).publish_at.tzinfo is None
    assert ScheduleIn(publish_at="2026-10-08T17:30:00").publish_at.tzinfo is None
    dec.s[reqs[0].id] = "approved"
    sch.sync_decisions()
    assert sch.execute_due(datetime(2026, 10, 8, 17, 30, tzinfo=timezone.utc))  # published as 17:30 UTC
