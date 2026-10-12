"""Row 61 deepening: SocialReader behavior with fakes only (no browser, no platform access, no database).
Standalone so it collects on Python 3.10; the older pinterest block tests live in test_instinct_doc_56_66_runtime.py,
which does not collect on 3.10 and so is not part of this battery."""
import asyncio

import pytest

from app.modules.m06_social_media_manager.social_reading.reader import SocialReader, _parse_iso
from app.modules.m13_browser_agent.session_bridge.protocol import BlockKind, PlatformBlocked

SESSION = "pc.dev1.main"


class Store:
    def __init__(self):
        self.runs, self.people, self.works = {}, [], []

    def start_run(self, tenant, platform, op, session):
        self.runs[len(self.runs) + 1] = {"state": "running"}
        return len(self.runs)

    def finish_run(self, run_id, state, detail):
        self.runs[run_id] = {"state": state, "detail": detail}

    def upsert_person(self, tenant, **kw):
        self.people.append(kw)

    def record_work(self, tenant, **kw):
        self.works.append(kw)
        return len(self.works), True


class Resp:
    def __init__(self, status): self.status = status


class Page:
    def __init__(self, url, status, html):
        self.final_url, self.status, self.html, self.url = url, status, html, "about:blank"

    async def goto(self, target, wait_until=None):
        self.url = self.final_url
        return Resp(self.status)

    async def content(self):
        return self.html


class Sessions:
    def __init__(self, page=None, social=None):
        self._page, self.social, self.calls = page, social, []

    async def page(self, *a):
        return self._page

    async def _execute(self, tenant, device, local, kind, args, timeout=60.0):
        self.calls.append(args)
        return self.social


def run(coro):
    return asyncio.run(coro)


def pin_page(n, url="https://www.pinterest.com/", status=200, extra=""):
    cards = "".join('<a href="/pin/%d/"><img alt="Pin number %d"></a>' % (i + 1, i + 1) for i in range(n))
    return Page(url, status, cards + extra)


def reader(page=None, social=None):
    s = Store()
    return SocialReader(Sessions(page, social), s), s


def test_only_paired_pc_sessions_and_known_platforms_are_accepted():
    r, s = reader()
    with pytest.raises(ValueError):
        run(r.run("t", platform="linkedin", operation="feed", session_id="plain-session"))
    with pytest.raises(ValueError, match="unsupported platform"):
        run(r.run("t", platform="tiktok", operation="feed", session_id=SESSION))
    assert s.runs[1]["state"] == "failed"
    with pytest.raises(ValueError, match="unsupported linkedin operation"):
        run(r.run("t", platform="linkedin", operation="dms", session_id=SESSION))


def test_blocked_and_failed_runs_are_recorded_with_distinct_states():
    r, s = reader(pin_page(1, status=429))
    with pytest.raises(PlatformBlocked) as e:
        run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))
    assert e.value.kind is BlockKind.RATE_LIMIT
    assert s.runs[1]["state"] == "blocked" and s.runs[1]["detail"]["block"] == "rate_limit"
    r, s = reader(pin_page(1))
    with pytest.raises(ValueError):
        run(r.run("t", platform="pinterest", operation="followers", session_id=SESSION))
    assert s.runs[1]["state"] == "failed" and "visible feed" in s.runs[1]["detail"]["error"]
    r, s = reader(pin_page(1))
    out = run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))
    assert s.runs[out["run_id"]]["state"] == "complete"


@pytest.mark.parametrize("url,status,kind", [
    ("https://www.pinterest.com/", 403, BlockKind.POLICY),
    ("https://www.pinterest.com/", 429, BlockKind.RATE_LIMIT),
    ("https://evil.example/", 200, BlockKind.POLICY),
    ("https://www.pinterest.com/login/", 200, BlockKind.LOGIN_WALL),
    ("https://www.pinterest.com/signup/", 200, BlockKind.LOGIN_WALL),
])
def test_pinterest_blocks_kind_by_cause_and_records_nothing(url, status, kind):
    r, s = reader(pin_page(2, url=url, status=status))
    with pytest.raises(PlatformBlocked) as e:
        run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))
    assert e.value.kind is kind and s.works == []


def test_pinterest_challenge_and_password_form_block():
    r, s = reader(pin_page(2, extra='<iframe src="https://x/captcha"></iframe>'))
    with pytest.raises(PlatformBlocked) as e:
        run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))
    assert e.value.kind is BlockKind.CHALLENGE and s.works == []
    r, s = reader(pin_page(2, extra='<form action="/login"><input type="password"></form>'))
    with pytest.raises(PlatformBlocked) as e:
        run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))
    assert e.value.kind is BlockKind.LOGIN_WALL and s.works == []


def test_pinterest_limit_must_be_an_integer_1_to_500_and_is_applied():
    for bad in (0, 501, True, "5", 2.5):
        r, s = reader(pin_page(3))
        with pytest.raises(ValueError, match="limit must be integer"):
            run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION, limit=bad))
    r, s = reader(pin_page(5))
    out = run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION, limit=2))
    assert out["count"] == 2 and len(s.works) == 2


def test_pinterest_records_honest_provenance_and_reports_status():
    r, s = reader(pin_page(2))
    out = run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))
    assert out["status"] == "observed" and out["new"] == 2
    assert out["summary"]["continuous_monitoring_configured"] is False
    w = s.works[0]
    assert w["detail"] == {"author_verified": False, "published_at_unknown": True, "sample": "visible_feed"}
    assert w["handle"] == "" and w["kind"] == "pin"
    r, s = reader(pin_page(0))
    assert run(r.run("t", platform="pinterest", operation="feed", session_id=SESSION))["status"] == "no_visible_pins"


LI_CONN = ''.join('<li class="mn-connection-card"><a class="mn-connection-card__link" href="/in/p%d/">'
                  '<span class="mn-connection-card__name">Person %d</span></a></li>' % (i, i) for i in range(4))
LI_FEED = ''.join('<div class="feed-shared-update-v2" data-urn="urn:li:activity:%d"><span class="update-components-actor__name">P</span>'
                  '<div class="update-components-text">Post %d text</div></div>' % (i, i) for i in range(4))


def test_linkedin_limits_are_applied():
    r, s = reader(Page("https://www.linkedin.com/mynetwork/invite-connect/connections/", 200, LI_CONN))
    out = run(r.run("t", platform="linkedin", operation="connections", session_id=SESSION, limit=2))
    assert out["count"] == 2 and len(s.people) == 2
    r, s = reader(Page("https://www.linkedin.com/feed/", 200, LI_FEED))
    out = run(r.run("t", platform="linkedin", operation="feed", session_id=SESSION, limit=3))
    assert out["count"] == 3 and out["new"] == 3 and len(s.works) == 3


def test_instagram_requires_username_sets_relation_and_reports_truncation():
    r, s = reader()
    with pytest.raises(ValueError, match="instagram_username"):
        run(r.run("t", platform="instagram", operation="followers", session_id=SESSION))
    ppl = {"people": [{"handle": "a"}], "truncated": True}
    r, s = reader(social=ppl)
    out = run(r.run("t", platform="instagram", operation="followers", session_id=SESSION, instagram_username="u"))
    assert out["truncated"] is True and out["summary"]["truncated"] is True and s.people[0]["relation"] == "follower"
    r, s = reader(social=ppl)
    run(r.run("t", platform="instagram", operation="following", session_id=SESSION, instagram_username="u"))
    assert s.people[0]["relation"] == "following"


def test_parse_iso_handles_naive_aware_and_bad_values():
    from datetime import timezone
    assert _parse_iso("2026-09-01T10:00:00").tzinfo is timezone.utc
    assert _parse_iso("2026-09-01T10:00:00+05:30").utcoffset().total_seconds() == 19800
    assert _parse_iso("garbage") is None and _parse_iso(None) is None and _parse_iso("") is None
