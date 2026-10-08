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


import re

SECRET_VALUE_PATTERNS = (
    re.compile(r"bearer\s+[a-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"\bsk-[a-z0-9_-]{12,}", re.I),
    re.compile(r"\bgh[pousr]_[a-z0-9]{20,}", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[a-z0-9-]{10,}", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"eyJ[a-z0-9_-]{10,}\.[a-z0-9_-]{10,}\.[a-z0-9_-]{5,}", re.I),
    re.compile(r"(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S{6,}", re.I),
)


def secret_findings(obj, path="$"):
    """Structural walk over keys, string values and nested dict/list/tuple/set members."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            if any(w in ks.lower() for w in SECRET_KEYS):
                out.append((f"{path}.{ks}", "key"))
            out += secret_findings(k, f"{path}.<key {ks}>") if not isinstance(k, str) else []
            out += secret_findings(v, f"{path}.{ks}")
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for n, v in enumerate(obj):
            out += secret_findings(v, f"{path}[{n}]")
    elif isinstance(obj, str):
        if any(p.search(obj) for p in SECRET_VALUE_PATTERNS):
            out.append((path, "value"))
    return out


def test_secret_scan_catches_planted_secrets_in_keys_values_and_lists():
    """Negative control: the scan must flag each planted shape, or the pin below proves nothing."""
    assert secret_findings({"api_key": "x"})
    assert secret_findings({"copy": "call with Bearer abcdefgh12345678"})
    assert secret_findings({"a": {"b": ["ok", "sk-abcdefghijklmnop1234"]}})
    assert secret_findings({"a": [{"c": ("ghp_" + "a" * 24,)}]})
    assert secret_findings({"n": "password=hunter22xyz"})
    assert secret_findings({"k": "-----BEGIN RSA PRIVATE KEY-----"})
    assert not secret_findings({"copy": "Our pilot cut waits by 38% [1]", "n": [1, 2, {"x": "plain"}]})


def test_payload_and_entries_have_no_secret_like_keys_or_values():
    """STRUCTURAL check only (key names + known secret-shaped value patterns, recursive).

    It is NOT a proof the payload is secret-free: an unrecognised secret format,
    an encoded/obfuscated value, or a secret inside user-authored copy that does
    not match these patterns will pass.
    """
    svc, store, sch, repo, *_ = _build()
    reqs = svc.request_schedule("p1", NOW, references=REFS)
    assert secret_findings(reqs[0].payload) == []
    assert secret_findings(reqs[0].model_dump(mode="json") if hasattr(reqs[0], "model_dump") else reqs[0].payload) == []
    for e in repo.list_schedules():
        assert secret_findings({k: str(v) for k, v in vars(e).items()}) == []
    assert reqs[0].payload["api"] and reqs[0].payload["publish_at"]


def test_aware_offset_preserves_instant():
    from datetime import timezone as tz
    ist = tz(timedelta(hours=5, minutes=30))
    svc, store, sch, repo, adapter, dec = _build()
    when = datetime(2026, 10, 8, 17, 30, tzinfo=ist)  # == 12:00Z
    reqs = svc.request_schedule("p1", when, references=REFS)
    assert datetime.fromisoformat(reqs[0].payload["publish_at"]) == NOW
