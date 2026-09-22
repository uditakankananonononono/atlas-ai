"""Offline tests for module 5, including network and approval safety paths."""

import asyncio
from datetime import datetime, timezone

import httpx

from app.core.models import ApprovalRequest
from app.modules.m05_outreach_manager.schemas import (
    CampaignDraftRequest,
    ContactCreate,
    DraftEmail,
)
from app.modules.m05_outreach_manager.service import (
    InMemoryContactRepository,
    SemanticScholarClient,
    Service,
    UpstreamServiceError,
)


class ApprovalSpy:
    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest, *, user_id=None) -> ApprovalRequest:
        self.items.append(item)
        return item


async def fake_generate(prompt: str, provider: str, model: str | None):
    assert "Do not send it" in prompt
    assert "spatial transcriptomics" in prompt
    return model or "test-model", "Subject: Summer research question\nDear Dr. Rao,\nYour supplied work caught my attention."


def make_service(transport: httpx.BaseTransport | None = None):
    client = httpx.AsyncClient(transport=transport)
    approvals = ApprovalSpy()
    service = Service(
        InMemoryContactRepository(),
        approvals,
        SemanticScholarClient(client, base_url="https://semantic.test"),
        fake_generate,
    )
    return service, approvals, client


def test_campaign_draft_and_send_are_approval_gated():
    service, approvals, client = make_service()
    contact = service.create_contact(
        ContactCreate(
            project_id="atlas",
            name="Dr. Rao",
            email="rao@example.edu",
            institution="Example University",
            research_topics=["spatial transcriptomics"],
        )
    )
    draft = asyncio.run(
        service.draft_campaign(
            CampaignDraftRequest(
                project_id="atlas",
                goal="Find a summer research supervisor in spatial transcriptomics",
                contact_id=contact.id,
                sender_context="Student with single-cell analysis experience",
                recent_work=["A supplied paper title"],
                provider="openai",
            )
        )
    )
    assert draft.subject == "Summer research question"
    assert approvals.items == []

    proposed = service.propose_send(draft)
    assert proposed.status == "pending"
    assert proposed.payload["recipient"] == "rao@example.edu"
    assert len(approvals.items) == 1
    assert approvals.items[0].action_type == "send_outreach_email"
    asyncio.run(client.aclose())


def test_official_api_search_is_mocked_and_ranked():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/author/search"
        assert request.url.params["query"] == "spatial transcriptomics"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"authorId": "a", "name": "A", "paperCount": 10, "citationCount": 100, "hIndex": 8, "affiliations": ["Lab A"]},
                    {"authorId": "b", "name": "B", "paperCount": 20, "citationCount": 1000, "hIndex": 30, "affiliations": ["Lab B"]},
                ]
            },
        )

    service, _, client = make_service(httpx.MockTransport(handler))
    result = asyncio.run(service.search_professors("spatial transcriptomics", 5))
    assert [item.author_id for item in result] == ["b", "a"]
    assert all(item.source == "semantic_scholar" for item in result)
    asyncio.run(client.aclose())


def test_network_failure_is_safe_and_clear():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    service, approvals, client = make_service(httpx.MockTransport(handler))
    try:
        asyncio.run(service.search_professors("genomics", 3))
    except UpstreamServiceError as exc:
        assert "(429)" in str(exc)
    else:
        raise AssertionError("expected UpstreamServiceError")
    assert approvals.items == []
    asyncio.run(client.aclose())


def test_contact_change_log_and_missing_email_safety():
    service, approvals, client = make_service()
    contact = service.create_contact(ContactCreate(project_id="p", name="No Email"))
    updated = service.update_contact(
        contact.id,
        ContactCreate(project_id="p", name="No Email", institution="New Lab"),
    )
    assert updated.version == 2
    assert [row.version for row in service.contact_changes(contact.id)] == [1, 2]

    draft = DraftEmail(
        id="draft-1",
        contact_id=contact.id,
        subject="Hello",
        body="Body",
        provider="openai",
        model="test",
        created_at=datetime.now(timezone.utc),
    )
    try:
        service.propose_send(draft)
    except ValueError as exc:
        assert "verified email" in str(exc)
    else:
        raise AssertionError("expected missing-email safety failure")
    assert approvals.items == []
    asyncio.run(client.aclose())
