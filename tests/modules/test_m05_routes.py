"""Offline HTTP tests for the Outreach Manager router (fake container, no network)."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models import ApprovalRequest
from app.modules.m05_outreach_manager import routes as m05_routes
from app.modules.m05_outreach_manager.campaigns import CampaignService, InMemoryCampaignRepository
from app.modules.m05_outreach_manager.delivery import (
    ApprovalView,
    DeliveryReceipt,
    DeliveryService,
)
from app.modules.m05_outreach_manager.discovery import (
    LabDiscoveryService,
    LabPageCollector,
    LabRegistry,
)
from app.modules.m05_outreach_manager.enrichment import EnrichmentService, HunterIoClient
from app.modules.m05_outreach_manager.service import (
    InMemoryContactRepository,
    SemanticScholarClient,
    Service,
)

LAB_HTML = (
    "<html><head><title>Rao Lab</title></head><body><h1>Rao Lab</h1>"
    '<a href="mailto:rao@example.edu">Contact</a></body></html>'
)


class ApprovalSpy:
    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items.append(item)
        return item


class SpyGate:
    """Answers approved for any approval the spy recorded."""

    def __init__(self, spy: ApprovalSpy) -> None:
        self.spy = spy

    def get(self, approval_id: str) -> ApprovalView | None:
        for item in self.spy.items:
            if item.id == approval_id:
                return ApprovalView(
                    id=item.id, status="approved", action_type=item.action_type, payload=item.payload
                )
        return None


class FakeSender:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, *, to, subject, body, from_account=None) -> DeliveryReceipt:
        self.calls.append({"to": to, "subject": subject})
        return DeliveryReceipt(provider_message_id="pm-1", thread_id="thread-1")


def http_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v2/email-verifier":
        return httpx.Response(200, json={"data": {"status": "valid", "result": "deliverable", "score": 95}})
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    if request.url.host == "example.edu":
        return httpx.Response(200, text=LAB_HTML, headers={"content-type": "text/html"})
    return httpx.Response(404, json={})


def make_client(delivery_configured=True):
    transport = httpx.MockTransport(http_handler)
    http = httpx.AsyncClient(transport=transport)
    contacts = InMemoryContactRepository()
    campaigns_repo = InMemoryCampaignRepository()
    spy = ApprovalSpy()
    container = m05_routes.Container.__new__(m05_routes.Container)
    container.contacts = contacts
    container.outreach = Service(contacts, spy, SemanticScholarClient(http, base_url="https://s2.test"))
    container.enrichment = EnrichmentService(
        contacts, HunterIoClient(http, api_key="k", base_url="https://hunter.test/v2")
    )
    container.discovery = LabDiscoveryService(LabRegistry.load(), LabPageCollector(http))
    container.campaigns = CampaignService(campaigns_repo, contacts, spy)
    container.delivery = (
        DeliveryService(container.campaigns, SpyGate(spy), FakeSender()) if delivery_configured else None
    )

    app = FastAPI()
    app.include_router(m05_routes.router, prefix="/api/v1")
    app.dependency_overrides[m05_routes.get_container] = lambda: container
    return TestClient(app), container, spy


def test_full_pipeline_over_http():
    client, container, spy = make_client()
    contact = client.post(
        "/api/v1/outreach-manager/contacts",
        json={"project_id": "atlas", "name": "Dr. Rao", "email": "rao@example.edu"},
    ).json()
    campaign = client.post(
        "/api/v1/outreach-manager/campaigns",
        json={"project_id": "atlas", "name": "Summer", "goal": "Find supervisors"},
    ).json()
    message = client.post(
        f"/api/v1/outreach-manager/campaigns/{campaign['id']}/messages",
        json={"contact_id": contact["id"], "subject": "Hello", "body": "Body text"},
    ).json()
    assert message["status"] == "draft"

    submitted = client.post(f"/api/v1/outreach-manager/messages/{message['id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_approval"
    assert spy.items[0].payload["recipient"] == "rao@example.edu"

    decided = client.post(
        f"/api/v1/outreach-manager/messages/{message['id']}/decision", json={"approved": True}
    )
    assert decided.json()["status"] == "approved"

    sent = client.post(f"/api/v1/outreach-manager/messages/{message['id']}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["thread_id"] == "thread-1"

    events = client.get(f"/api/v1/outreach-manager/messages/{message['id']}/events").json()
    assert [row["event"] for row in events] == [
        "drafted", "submitted_for_approval", "approved", "sent",
    ]
    audit = client.get(f"/api/v1/outreach-manager/messages/{message['id']}/delivery-audit").json()
    assert [row["event"] for row in audit] == ["sent"]
    report = client.get(f"/api/v1/outreach-manager/campaigns/{campaign['id']}/delivery-report").json()
    assert report["counts"] == {"sent": 1}


def test_send_without_approval_is_409_and_sends_nothing():
    client, container, spy = make_client()
    contact = client.post(
        "/api/v1/outreach-manager/contacts",
        json={"project_id": "p", "name": "Dr. Rao", "email": "rao@example.edu"},
    ).json()
    campaign = client.post(
        "/api/v1/outreach-manager/campaigns",
        json={"project_id": "p", "name": "C", "goal": "Goal here"},
    ).json()
    message = client.post(
        f"/api/v1/outreach-manager/campaigns/{campaign['id']}/messages",
        json={"contact_id": contact["id"], "subject": "Hi", "body": "Body"},
    ).json()
    response = client.post(f"/api/v1/outreach-manager/messages/{message['id']}/send")
    assert response.status_code == 409
    assert container.delivery.sender.calls == []


def test_unconfigured_delivery_is_a_clear_503():
    client, _, _ = make_client(delivery_configured=False)
    response = client.post("/api/v1/outreach-manager/messages/anything/send")
    assert response.status_code == 503
    assert "ATLAS_SMTP_HOST" in response.json()["detail"]


def test_verify_email_then_scoped_plan():
    client, container, spy = make_client()
    contact = client.post(
        "/api/v1/outreach-manager/contacts",
        json={"project_id": "p", "name": "Dr. Rao", "email": "rao@example.edu"},
    ).json()

    verdict = client.post(f"/api/v1/outreach-manager/contacts/{contact['id']}/verify-email")
    assert verdict.status_code == 200
    assert verdict.json()["status"] == "valid"

    plan = client.post(
        "/api/v1/outreach-manager/plans/campaign",
        json={"goal": "Find supervisors", "audience": "professor", "contact_ids": [contact["id"]]},
    )
    assert plan.status_code == 200
    assert any("provider-verified" in check for check in plan.json()["scope_checks"])


def test_unverified_contact_fails_scoped_plan_with_422():
    client, _, _ = make_client()
    contact = client.post(
        "/api/v1/outreach-manager/contacts",
        json={"project_id": "p", "name": "Dr. Rao", "email": "rao@example.edu"},
    ).json()
    plan = client.post(
        "/api/v1/outreach-manager/plans/campaign",
        json={"goal": "Find supervisors", "audience": "professor", "contact_ids": [contact["id"]]},
    )
    assert plan.status_code == 422
    assert "provider-verified" in plan.json()["detail"]


def test_lab_search_and_collect_over_http():
    client, _, _ = make_client()
    hits = client.post(
        "/api/v1/outreach-manager/labs/search", json={"topics": ["spatial transcriptomics"]}
    )
    assert hits.status_code == 200
    assert any("Broad" in hit["university"] or "Sanger" in hit["university"] for hit in hits.json())

    page = client.post("/api/v1/outreach-manager/labs/collect", json={"url": "https://example.edu/lab"})
    assert page.status_code == 200
    assert page.json()["emails"] == ["rao@example.edu"]

    surface = client.post(
        "/api/v1/outreach-manager/labs/discover-contacts", json={"url": "https://example.edu/lab"}
    )
    assert surface.json()["emails"][0]["source_url"] == "https://example.edu/lab"


def test_micro_survey_plan_uses_default_question():
    client, _, _ = make_client()
    contact = client.post(
        "/api/v1/outreach-manager/contacts",
        json={
            "project_id": "p",
            "name": "Founder",
            "email": "f@x.io",
            "metadata": {"enrichment": {"email_verified": True}},
        },
    ).json()
    plan = client.post(
        "/api/v1/outreach-manager/plans/micro-survey",
        json={"goal": "Tool wishes", "contact_ids": [contact["id"]]},
    )
    assert plan.status_code == 200
    assert any("What tool do you wish you had?" in check for check in plan.json()["scope_checks"])
    assert plan.json()["kind"] == "survey"


def test_proposal_draft_over_http(monkeypatch):
    async def fake_generate(prompt, provider, model):
        return model or "test-model", "Subject: Atlas proposal\nGrounded body."

    monkeypatch.setattr("app.core.providers.generate", fake_generate)
    client, _, _ = make_client()
    response = client.post(
        "/api/v1/outreach-manager/proposals/draft",
        json={
            "project": {
                "name": "Atlas",
                "problem": "Students miss deadlines",
                "solution": "Approval-gated planning agent",
                "evidence": ["200 beta users"],
                "ask": "Pilot partnerships",
            },
            "recipient_context": "Innovation director",
        },
    )
    assert response.status_code == 200
    assert response.json()["subject"] == "Atlas proposal"


def test_missing_campaign_and_message_are_404():
    client, _, _ = make_client()
    assert client.get("/api/v1/outreach-manager/campaigns/nope").status_code == 404
    assert client.get("/api/v1/outreach-manager/messages/nope").status_code == 404
