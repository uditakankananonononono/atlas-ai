"""Mounted end-to-end tests for the opportunity application browser workflow (M1/M2/M13).

A fake Playwright page drives the full mounted FastAPI surface: owner-driven
login pause/resume, grounded staging, exact approvals, one-shot submit, and
honest blocked states. No real browser, network, or credentials are involved.
"""
from __future__ import annotations

import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.context import require_tenant
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalService
from app.modules.m02_competition_manager.application_routes import get_application_flow
from app.modules.m02_competition_manager.routes import get_service, router as m02_router
from app.modules.m02_competition_manager.schemas import Competition, RuleSet, SubmissionStatus
from app.modules.m02_competition_manager.service import DictCompetitionRepository, Service as CompetitionService
from app.modules.m13_browser_agent.application_flow import (
    ApplicationFlow,
    assert_no_credentials,
    CredentialRejectedError,
    extract_field_descriptors,
    probe_auth,
    probe_captcha,
)
from app.modules.m13_browser_agent.application_store import InMemoryApplicationSessionStore
from app.modules.m13_browser_agent.service import Service as BrowserService
from app.modules.m02_competition_manager import application_routes


class _EmptyDiscovery:
    """Hermetic stand-in for the Module 1 lookup: no shared database writes."""

    def get_opportunity(self, opportunity_id):
        return None


LOGIN_URL = "https://example.com/login"
FORM_URL = "https://example.com/apply"
DONE_URL = "https://example.com/apply/thanks"

LOGIN_HTML = """
<html><body><h1>Sign in to continue</h1>
<form action="/login" method="post">
<input id="u" name="username" type="text"><input id="p" name="password" type="password">
</form></body></html>
"""

FORM_HTML = """
<html><body><h1>Application</h1><form>
<label for="f-name">Full name</label><input id="f-name" name="full_name" type="text" required>
<label for="f-email">Email address</label><input id="f-email" name="email" type="email" required>
<label for="f-essay">Essay</label><textarea id="f-essay" name="essay" placeholder="Your essay"></textarea>
<input id="f-pass" name="password" type="password">
<button id="submit-btn" type="submit">Submit application</button>
</form></body></html>
"""

CAPTCHA_HTML = """
<html><body><div class="g-recaptcha" data-sitekey="x"></div>
<p>Verify you are human</p><script src="https://www.google.com/recaptcha/api.js"></script>
</body></html>
"""

THANKS_HTML = "<html><body><h1>Thanks - your application was received.</h1></body></html>"


class FakeLocator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector

    async def fill(self, value):
        self.page.filled[self.selector] = value

    async def input_value(self):
        if self.selector not in self.page.filled:
            raise RuntimeError(f"element not found: {self.selector}")
        return self.page.filled[self.selector]

    async def click(self):
        if self.page.fail_click:
            raise RuntimeError("click did not land")
        self.page.clicked.append(self.selector)
        self.page.url = self.page.after_submit_url
        self.page.html = self.page.after_submit_html


class FakePage:
    def __init__(self):
        self.url = LOGIN_URL
        self.html = LOGIN_HTML
        self.after_submit_url = DONE_URL
        self.after_submit_html = THANKS_HTML
        self.filled: dict[str, str] = {}
        self.clicked: list[str] = []
        self.fail_click = False
        self.shot_bytes = b"redacted-png-v1"
        self.mouse = self

    def locator(self, selector):
        return FakeLocator(self, selector)

    async def goto(self, url, **kwargs):
        self.url = url
        return type("Response", (), {"status": 200})()

    async def content(self):
        return self.html

    async def screenshot(self, path, full_page=True, mask=None):
        self.last_mask = mask
        Path(path).write_bytes(self.shot_bytes)

    async def wheel(self, x, y):
        pass


class FakeSessions:
    def __init__(self, page):
        self._page = page

    async def page(self, *args, **kwargs):
        return self._page

    async def close_session(self, tenant_id, session_id):
        return True


class FakeAuditStore:
    def __init__(self):
        self.events = []
        self.consumed: set[str] = set()

    async def append_audit(self, event):
        self.events.append(event)

    async def was_consumed(self, approval_id):
        return approval_id in self.consumed

    async def consume(self, approval_id, tenant_id):
        if approval_id in self.consumed:
            raise PermissionError("approval was already consumed")
        self.consumed.add(approval_id)


@pytest.fixture()
def dns_guard(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
    ])


@pytest.fixture()
def rig(tmp_path, dns_guard):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = [datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)]
    approvals = ApprovalService(sessionmaker(bind=engine, expire_on_commit=False), clock=lambda: now[0])

    page = FakePage()
    audit = FakeAuditStore()
    browser = BrowserService(FakeSessions(page), approvals, audit, str(tmp_path), {"example.com"})
    flow = ApplicationFlow(browser, InMemoryApplicationSessionStore(), approvals, clock=lambda: now[0])

    competition = Competition(
        id="comp-1",
        name="National Science Challenge",
        official_rules_url=FORM_URL,
        rules=RuleSet(summary="annual challenge"),
        checklist=[],
    )
    competitions = CompetitionService(generator=None, repository=DictCompetitionRepository())
    competitions._repository.save(competition)

    app = FastAPI()
    app.include_router(m02_router, prefix="/api/v1", dependencies=[Depends(require_tenant)])
    app.dependency_overrides[get_application_flow] = lambda: flow
    app.dependency_overrides[get_service] = lambda: competitions
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(application_routes, "_discovery_service", lambda: _EmptyDiscovery())
    client = TestClient(app)
    rig = type("Rig", (), {
        "client": client, "page": page, "audit": audit, "approvals": approvals,
        "flow": flow, "competitions": competitions, "now": now,
    })()
    yield rig
    monkeypatch.undo()


def create_session(rig, **overrides):
    payload = {"competition_id": "comp-1", "label": "science challenge"}
    payload.update(overrides)
    response = rig.client.post("/api/v1/competition-manager/applications/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def reach_staged(rig):
    """Drive a session to STAGED through the mounted routes."""
    rig.page.url, rig.page.html = FORM_URL, FORM_HTML
    body = create_session(rig)
    sid = body["session_id"]
    assert body["status"] == "ready"
    inspected = rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/inspect")
    assert inspected.status_code == 200, inspected.text
    staged = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/stage",
        json={"fields": {"full name": "Ada Lovelace", "email": "ada@example.org", "essay": "I build things."},
              "submit_selector": "#submit-btn"},
    )
    assert staged.status_code == 200, staged.text
    return sid, staged.json()


def approve(rig, approval_id):
    rig.approvals.decide(approval_id, ApprovalStatus.APPROVED, decided_by="owner")


def test_full_mounted_workflow_with_owner_login_pause(rig):
    # The site opens on a login wall: Atlas pauses for the owner, with instructions.
    body = create_session(rig)
    sid = body["session_id"]
    assert body["status"] == "awaiting_user_login"
    assert any("paired" in step for step in body["instructions"])
    assert any("Never send your password" in step for step in body["instructions"])
    assert rig.page.clicked == []

    # Owner has not actually logged in yet: resume honestly stays paused.
    resumed = rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/resume",
                              json={"login_confirmed": True})
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "awaiting_user_login"

    # Owner completes login in the paired browser; the site now shows the form.
    rig.page.url, rig.page.html = FORM_URL, FORM_HTML
    resumed = rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/resume",
                              json={"login_confirmed": True})
    assert resumed.json()["status"] == "ready"

    inspected = rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/inspect")
    assert inspected.status_code == 200
    fields = {f["selector"]: f for f in inspected.json()["fields"]}
    assert fields["#f-name"]["label"] == "Full name"
    assert fields["#f-pass"]["input_type"] == "password"

    staged = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/stage",
        json={"fields": {"full name": "Ada Lovelace", "email": "ada@example.org", "essay": "I build things."},
              "submit_selector": "#submit-btn"},
    )
    assert staged.status_code == 200, staged.text
    result = staged.json()
    assert result["submitted"] is False
    assert result["preview"]["#f-name"] == {
        "requested": "Ada Lovelace", "on_page": "Ada Lovelace", "matches": True,
    }
    assert result["skipped_password_selectors"] == ["#f-pass"]
    assert "#f-pass" not in rig.page.filled
    assert result["screenshot_digest"] and result["values_digest"]
    assert rig.page.last_mask  # screenshot redacted the filled fields

    requested = rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/submit-approval")
    assert requested.status_code == 201, requested.text
    approval = requested.json()
    assert approval["submitted"] is False
    bound = approval["bound"]
    assert bound["tenant_id"] == "local" and bound["actor_id"] == "local-user"
    assert bound["selector"] == "#submit-btn" and bound["page_url"] == FORM_URL

    approve(rig, approval["approval_id"])
    submitted = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/submit",
        json={"approval_id": approval["approval_id"]},
    )
    assert submitted.status_code == 200, submitted.text
    outcome = submitted.json()
    assert outcome["submitted"] is True
    assert outcome["confirmation"]["final_url"] == DONE_URL
    assert "application was received" in outcome["confirmation"]["page_excerpt"]
    assert rig.page.clicked == ["#submit-btn"]

    # M2 status evidence lands only after the site's own readback.
    competition = rig.competitions.get_competition("comp-1")
    assert competition.status == SubmissionStatus.SUBMITTED
    evidence = competition.status_evidence[-1]
    assert evidence.source == "browser_readback"
    assert sid in evidence.reference

    status = rig.client.get(f"/api/v1/competition-manager/applications/sessions/{sid}")
    assert status.json()["status"] == "submitted"

    actions = [e.action.value for e in rig.audit.events]
    for expected in ("navigate", "login", "extract", "fill", "readback", "screenshot", "submit"):
        assert expected in actions, actions


def test_credentials_are_rejected_at_the_api_boundary(rig):
    sid, _ = reach_staged(rig)
    for bad in ("password", "mfa_code", "cookie", "session_token", "OTP"):
        response = rig.client.post(
            f"/api/v1/competition-manager/applications/sessions/{sid}/stage",
            json={"fields": {"full name": "Ada", bad: "x"}, "submit_selector": "#submit-btn"},
        )
        assert response.status_code == 422, (bad, response.text)
    assert rig.page.clicked == []


def test_cross_tenant_and_cross_actor_are_denied(rig):
    sid, _ = reach_staged(rig)
    base = f"/api/v1/competition-manager/applications/sessions/{sid}"
    other_tenant = {"X-Atlas-Tenant": "other-tenant"}
    assert rig.client.get(base, headers=other_tenant).status_code == 404
    assert rig.client.post(f"{base}/stage", headers=other_tenant,
                           json={"fields": {"full name": "Eve"}, "submit_selector": "#submit-btn"}).status_code == 404

    other_actor = {"X-Atlas-Actor": "mallory"}
    assert rig.client.get(base, headers=other_actor).status_code == 403
    assert rig.client.post(f"{base}/resume", headers=other_actor, json={"login_confirmed": True}).status_code == 403
    assert rig.client.post(f"{base}/stage", headers=other_actor,
                           json={"fields": {"full name": "Eve"}, "submit_selector": "#submit-btn"}).status_code == 403
    requested = rig.client.post(f"{base}/submit-approval")
    approve(rig, requested.json()["approval_id"])
    denied = rig.client.post(f"{base}/submit", headers=other_actor,
                             json={"approval_id": requested.json()["approval_id"]})
    assert denied.status_code == 403
    assert rig.page.clicked == []


def test_unapproved_and_ungrounded_fields_are_never_filled(rig):
    rig.page.url, rig.page.html = FORM_URL, FORM_HTML
    sid = create_session(rig)["session_id"]
    rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/inspect")
    staged = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/stage",
        json={"fields": {"full name": "Ada Lovelace", "phone": "555-0100", "favorite color": "blue"},
              "submit_selector": "#submit-btn"},
    )
    assert staged.status_code == 200, staged.text
    result = staged.json()
    assert result["unmapped_approved_fields"] == ["favorite color", "phone"]
    assert set(rig.page.filled) == {"#f-name"}
    assert list(result["preview"]) == ["#f-name"]


def test_changed_values_url_or_screenshot_invalidate_the_approval(rig):
    sid, _ = reach_staged(rig)
    base = f"/api/v1/competition-manager/applications/sessions/{sid}"

    requested = rig.client.post(f"{base}/submit-approval").json()
    approve(rig, requested["approval_id"])

    rig.page.filled["#f-name"] = "Mallory"  # tampered value
    refused = rig.client.post(f"{base}/submit", json={"approval_id": requested["approval_id"]})
    assert refused.status_code == 409 and rig.page.clicked == []
    rig.page.filled["#f-name"] = "Ada Lovelace"

    rig.page.url = "https://example.com/apply/step-2"  # navigated away
    refused = rig.client.post(f"{base}/submit", json={"approval_id": requested["approval_id"]})
    assert refused.status_code == 409 and rig.page.clicked == []
    rig.page.url = FORM_URL

    rig.page.shot_bytes = b"different-pixels"  # any visual change
    refused = rig.client.post(f"{base}/submit", json={"approval_id": requested["approval_id"]})
    assert refused.status_code == 409 and rig.page.clicked == []
    rig.page.shot_bytes = b"redacted-png-v1"

    # Untampered page still submits against the same approval.
    ok = rig.client.post(f"{base}/submit", json={"approval_id": requested["approval_id"]})
    assert ok.status_code == 200, ok.text


def test_denied_stale_expired_and_replayed_approvals_fail(rig):
    sid, _ = reach_staged(rig)
    base = f"/api/v1/competition-manager/applications/sessions/{sid}"

    # Denied.
    denied = rig.client.post(f"{base}/submit-approval").json()
    rig.approvals.decide(denied["approval_id"], ApprovalStatus.DENIED, decided_by="owner")
    assert rig.client.post(f"{base}/submit", json={"approval_id": denied["approval_id"]}).status_code == 409

    # Stale: bound to a different session.
    other_sid, _ = reach_staged(rig)
    stale = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{other_sid}/submit-approval").json()
    approve(rig, stale["approval_id"])
    refused = rig.client.post(f"{base}/submit", json={"approval_id": stale["approval_id"]})
    assert refused.status_code == 409 and rig.page.clicked == []

    # Expired: decision lands, then the TTL lapses before execution.
    rig.client.post(f"{base}/stage",
                    json={"fields": {"full name": "Ada Lovelace", "email": "ada@example.org", "essay": "I build things."},
                          "submit_selector": "#submit-btn"})
    expiring = rig.client.post(f"{base}/submit-approval").json()
    approve(rig, expiring["approval_id"])
    rig.now[0] = rig.now[0] + timedelta(hours=2)
    refused = rig.client.post(f"{base}/submit", json={"approval_id": expiring["approval_id"]})
    assert refused.status_code == 409 and rig.page.clicked == []
    rig.now[0] = rig.now[0] - timedelta(hours=2)

    # Replayed: one approval, one click, exactly once.
    fresh = rig.client.post(f"{base}/submit-approval").json()
    approve(rig, fresh["approval_id"])
    first = rig.client.post(f"{base}/submit", json={"approval_id": fresh["approval_id"]})
    assert first.status_code == 200, first.text
    replay = rig.client.post(f"{base}/submit", json={"approval_id": fresh["approval_id"]})
    assert replay.status_code == 409
    assert rig.page.clicked == ["#submit-btn"]


def test_captcha_is_an_honest_block_never_a_success(rig):
    rig.page.url, rig.page.html = "https://example.com/apply", CAPTCHA_HTML
    body = create_session(rig)
    assert body["status"] == "blocked"
    assert "CAPTCHA" in body["error"]
    assert rig.page.clicked == []

    # CAPTCHA appearing mid-flow blocks staging honestly.
    sid, _ = reach_staged(rig)
    rig.page.html = CAPTCHA_HTML
    response = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/stage",
        json={"fields": {"full name": "Ada"}, "submit_selector": "#submit-btn"},
    )
    assert response.status_code == 409
    status = rig.client.get(f"/api/v1/competition-manager/applications/sessions/{sid}").json()
    assert status["status"] == "blocked" and "CAPTCHA" in status["error"]


def test_site_redesign_is_an_honest_block(rig):
    rig.page.url, rig.page.html = FORM_URL, FORM_HTML
    sid = create_session(rig)["session_id"]
    rig.client.post(f"/api/v1/competition-manager/applications/sessions/{sid}/inspect")
    rig.page.html = "<html><body><h1>We redesigned our portal</h1></body></html>"
    response = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/stage",
        json={"fields": {"full name": "Ada"}, "submit_selector": "#submit-btn"},
    )
    assert response.status_code == 409
    status = rig.client.get(f"/api/v1/competition-manager/applications/sessions/{sid}").json()
    assert status["status"] == "blocked"
    assert rig.page.clicked == []
    assert rig.competitions.get_competition("comp-1").status != SubmissionStatus.SUBMITTED


def test_failed_click_consumes_approval_and_stays_unsubmitted(rig):
    sid, _ = reach_staged(rig)
    base = f"/api/v1/competition-manager/applications/sessions/{sid}"
    approval = rig.client.post(f"{base}/submit-approval").json()
    approve(rig, approval["approval_id"])

    rig.page.fail_click = True
    failed = rig.client.post(f"{base}/submit", json={"approval_id": approval["approval_id"]})
    assert failed.status_code == 502
    status = rig.client.get(base).json()
    assert status["status"] == "failed" and "click failed" in status["error"]
    # No fake success anywhere: competition and page both show no submission.
    assert rig.competitions.get_competition("comp-1").status != SubmissionStatus.SUBMITTED
    assert rig.page.clicked == []
    # The consumed approval cannot be retried; a fresh stage + approval is required.
    replay = rig.client.post(f"{base}/submit", json={"approval_id": approval["approval_id"]})
    assert replay.status_code == 409

    rig.page.fail_click = False
    assert rig.client.post(f"{base}/submit-approval").status_code == 409  # must re-stage first
    restaged = rig.client.post(
        f"{base}/stage",
        json={"fields": {"full name": "Ada Lovelace", "email": "ada@example.org", "essay": "I build things."},
              "submit_selector": "#submit-btn"},
    )
    assert restaged.status_code == 200
    second = rig.client.post(f"{base}/submit-approval").json()
    approve(rig, second["approval_id"])
    ok = rig.client.post(f"{base}/submit", json={"approval_id": second["approval_id"]})
    assert ok.status_code == 200, ok.text
    assert rig.page.clicked == ["#submit-btn"]


def test_resume_requires_explicit_owner_confirmation(rig):
    body = create_session(rig)
    sid = body["session_id"]
    assert body["status"] == "awaiting_user_login"
    response = rig.client.post(
        f"/api/v1/competition-manager/applications/sessions/{sid}/resume",
        json={"login_confirmed": False},
    )
    assert response.status_code == 422


def test_unknown_competition_and_opportunity_are_404(rig):
    response = rig.client.post("/api/v1/competition-manager/applications/sessions",
                               json={"competition_id": "nope"})
    assert response.status_code == 404
    response = rig.client.post("/api/v1/competition-manager/applications/sessions",
                               json={"opportunity_id": "nope"})
    assert response.status_code == 404
    response = rig.client.post("/api/v1/competition-manager/applications/sessions", json={})
    assert response.status_code == 422


# -- pure-function units ----------------------------------------------------

def test_credential_gate_normalizes_keys():
    for bad in ("Password", "pass-word", "MFA Code", "cookie", "AUTH_TOKEN"):
        with pytest.raises(CredentialRejectedError):
            assert_no_credentials({bad: "x"})
    assert_no_credentials({"full name": "Ada", "essay": "text"})
    with pytest.raises(CredentialRejectedError):
        assert_no_credentials({"nested": {"otp": "123456"}})


def test_probes_report_evidence():
    auth = probe_auth("https://example.com/login", LOGIN_HTML)
    assert auth.required and auth.evidence
    assert not probe_auth(FORM_URL, FORM_HTML).required
    assert probe_captcha(CAPTCHA_HTML)
    assert not probe_captcha(FORM_HTML)


def test_descriptors_are_grounded_in_page_html():
    descriptors = extract_field_descriptors(FORM_HTML)
    by_selector = {d.selector: d for d in descriptors}
    assert by_selector["#f-name"].label == "Full name"
    assert by_selector["#f-name"].required is True
    assert by_selector["#f-essay"].placeholder == "Your essay"
    assert by_selector["#f-pass"].input_type == "password"
