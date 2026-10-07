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
    assert status["status"] == "outcome_unknown" and "click failed" in status["error"]
    # No fake success anywhere: competition and page both show no submission.
    assert rig.competitions.get_competition("comp-1").status != SubmissionStatus.SUBMITTED
    assert rig.page.clicked == []
    # A click exception is ambiguous. No replay or automatic restage until reconciliation.
    replay = rig.client.post(f"{base}/submit", json={"approval_id": approval["approval_id"]})
    assert replay.status_code == 409

    rig.page.fail_click = False
    assert rig.client.post(f"{base}/submit-approval").status_code == 409
    restaged = rig.client.post(f"{base}/stage",json={"fields":{"full name":"Ada"},"submit_selector":"#submit-btn"})
    assert restaged.status_code == 409


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


def test_unchanged_form_after_click_is_not_positive_receipt(rig):
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 rig.page.after_submit_url=FORM_URL;rig.page.after_submit_html=FORM_HTML
 outcome=rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 assert outcome.status_code==200,outcome.text
 assert outcome.json()['submitted'] is False
 assert outcome.json()['status']=='outcome_unknown'
 assert rig.page.clicked==['#submit-btn']
 assert rig.competitions.get_competition('comp-1').status!=SubmissionStatus.SUBMITTED
 assert rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']}).status_code==409


def test_pre_effect_session_save_failure_prevents_click_and_consumption(rig,monkeypatch):
 from app.modules.m13_browser_agent.application_flow import SessionRevisionConflict
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 def conflict(record):raise SessionRevisionConflict('fixture pre-effect save lost')
 monkeypatch.setattr(rig.flow.store,'save',conflict)
 response=rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 assert response.status_code==409
 assert rig.page.clicked==[]
 assert approval['approval_id'] not in rig.audit.consumed


@pytest.mark.parametrize('html',[
 '<html><body>Application was received. Error processing request.</body></html>',
 '<html><body>Application was received.<form><button>Submit</button></form></body></html>',
 '<html><body>Welcome back</body></html>',
])
def test_ambiguous_or_error_readback_does_not_mark_competition_submitted(rig,html):
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 rig.page.after_submit_html=html
 response=rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 assert response.status_code==200,response.text
 assert response.json()['submitted'] is False and response.json()['status']=='outcome_unknown'
 assert rig.competitions.get_competition('comp-1').status!=SubmissionStatus.SUBMITTED


def test_post_click_save_conflict_retains_durable_claim_and_blocks_replay(rig,monkeypatch):
 from app.modules.m13_browser_agent.application_flow import SessionRevisionConflict
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 original=rig.flow.store.save;calls=[]
 def save(record):
  calls.append(record.status)
  if len(calls)>1:raise SessionRevisionConflict('fixture post-click save lost')
  return original(record)
 monkeypatch.setattr(rig.flow.store,'save',save)
 response=rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 assert response.status_code==409 and rig.page.clicked==['#submit-btn']
 assert rig.client.get(base).json()['status']=='submitting'
 assert approval['approval_id'] in rig.audit.consumed
 assert rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']}).status_code==409
 assert rig.page.clicked==['#submit-btn']
 assert rig.client.post(f'{base}/stage',json={'fields':{'full name':'Ada'},'submit_selector':'#submit-btn'}).status_code==409


def test_consume_crash_after_claim_cannot_replay_even_unconsumed(rig,monkeypatch):
 import asyncio
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 async def crash(*args):raise RuntimeError('fixture consume unavailable')
 original=rig.audit.consume;monkeypatch.setattr(rig.audit,'consume',crash)
 record=next(v for (tenant,session),v in rig.flow.store._rows.items() if session==sid)
 with pytest.raises(RuntimeError,match='consume unavailable'):
  asyncio.run(rig.flow.execute_submit(record.tenant_id,record.actor_id,sid,approval['approval_id']))
 assert rig.client.get(base).json()['status']=='submitting'
 assert approval['approval_id'] not in rig.audit.consumed and rig.page.clicked==[]
 monkeypatch.setattr(rig.audit,'consume',original)
 replay=rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 assert replay.status_code==409 and rig.page.clicked==[]


@pytest.mark.parametrize('case',['readback_failure','captcha'])
def test_postclick_unverifiable_readback_stays_unknown(rig,monkeypatch,case):
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 if case=='captcha':rig.page.after_submit_html=CAPTCHA_HTML
 else:
  async def fail(*args):raise RuntimeError('fixture readback unavailable')
  monkeypatch.setattr(rig.flow.browser,'extract',fail)
 response=rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 assert response.status_code==502
 assert rig.client.get(base).json()['status']=='outcome_unknown'
 assert rig.page.clicked==['#submit-btn'] and approval['approval_id'] in rig.audit.consumed
 assert rig.competitions.get_competition('comp-1').status!=SubmissionStatus.SUBMITTED
 assert rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']}).status_code==409


@pytest.mark.parametrize('kind',['memory','sqlite','postgres'])
def test_simultaneous_real_store_submit_claim_has_one_effect(rig,monkeypatch,tmp_path,kind):
 import asyncio
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 from app.modules.m13_browser_agent.application_flow import SessionRevisionConflict
 if kind!='memory':
  from app.modules.m13_browser_agent.application_store import SQLApplicationSessionStore,ApplicationSessionRow
  if kind=='postgres':
   pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
   url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
  else:url=f'sqlite:///{tmp_path}/submit-race.db'
  engine=create_engine(url);ApplicationSessionRow.__table__.create(engine)
  rig.flow.store=SQLApplicationSessionStore(sessionmaker(bind=engine))
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 original=rig.flow._save;barrier=Barrier(2)
 def save(record):
  if record.status=='submitting':barrier.wait(timeout=5)
  return original(record)
 owner=rig.flow.store.get('local',sid)
 monkeypatch.setattr(rig.flow,'_save',save)
 def execute(_):
  try:return asyncio.run(rig.flow.execute_submit(owner.tenant_id,owner.actor_id,sid,approval['approval_id']))['submitted']
  except SessionRevisionConflict:return False
 with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(execute,[1,2]))==[False,True]
 assert rig.page.clicked==['#submit-btn']
 assert len(rig.audit.consumed)==1


def test_unknown_submit_reconciliation_reads_original_source_without_second_click(rig):
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 rig.page.after_submit_url=FORM_URL;rig.page.after_submit_html=FORM_HTML
 assert rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']}).json()['status']=='outcome_unknown'
 assert not rig.client.post(f'{base}/reconcile-submit').json()['reconciled']
 rig.page.url=DONE_URL;rig.page.html=THANKS_HTML
 result=rig.client.post(f'{base}/reconcile-submit')
 assert result.status_code==200,result.text
 assert not result.json()['reconciled'] and not result.json()['submitted']
 assert result.json()['observation']['positive_text_observed'] and not result.json()['observation']['transaction_bound']
 assert rig.page.clicked==['#submit-btn'] and rig.competitions.get_competition('comp-1').status!=SubmissionStatus.SUBMITTED
 assert rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']}).status_code==409


@pytest.mark.parametrize('case',['unconsumed','other_host','captcha','error','wrong_approval'])
def test_unknown_reconciliation_refuses_unbound_or_negative_source(rig,case):
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 rig.page.after_submit_url=FORM_URL;rig.page.after_submit_html=FORM_HTML
 rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 rig.page.url=DONE_URL;rig.page.html=THANKS_HTML
 if case=='unconsumed':rig.audit.consumed.clear()
 elif case=='other_host':rig.page.url='https://other.example/thanks'
 elif case=='captcha':rig.page.html=CAPTCHA_HTML
 elif case=='error':rig.page.html='<html>Application was received. Error.</html>'
 else:
  rig.approvals.get=lambda aid:{'id':'wrong','payload':{}}
 response=rig.client.post(f'{base}/reconcile-submit',json={'receipt':'approved','retry':True})
 assert response.status_code in [200,403]
 if response.status_code==200:assert not response.json()['reconciled']
 assert rig.page.clicked==['#submit-btn'] and rig.competitions.get_competition('comp-1').status!=SubmissionStatus.SUBMITTED


def test_samehost_different_application_receipt_never_settles_original_unknown(rig):
 sid,_=reach_staged(rig);base=f'/api/v1/competition-manager/applications/sessions/{sid}'
 approval=rig.client.post(f'{base}/submit-approval').json();approve(rig,approval['approval_id'])
 rig.page.after_submit_url=FORM_URL;rig.page.after_submit_html=FORM_HTML
 rig.client.post(f'{base}/submit',json={'approval_id':approval['approval_id']})
 rig.page.url='https://example.com/other-application/thanks'
 rig.page.html='<html><body>Application was received. Applicant: Other person. Reference: OTHER-999.</body></html>'
 observed=rig.client.post(f'{base}/reconcile-submit')
 assert observed.status_code==200 and observed.json()['submitted'] is False and observed.json()['reconciled'] is False
 assert observed.json()['status']=='outcome_unknown' and observed.json()['observation']['transaction_bound'] is False
 assert rig.competitions.get_competition('comp-1').status!=SubmissionStatus.SUBMITTED
 assert rig.page.clicked==['#submit-btn']
