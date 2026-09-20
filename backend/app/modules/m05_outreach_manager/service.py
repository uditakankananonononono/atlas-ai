"""Domain logic for compliant, approval-gated outreach campaigns."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol
from uuid import uuid4

import httpx

from app.core.models import ApprovalRequest
from app.core.providers import generate

from .schemas import (
    CampaignDraftRequest,
    Contact,
    ContactChange,
    ContactCreate,
    DraftEmail,
    FollowUpRequest,
    ProfessorCandidate,
    ProposedAction,
)


class ContactNotFoundError(LookupError):
    """Raised when a requested contact does not exist."""


class UpstreamServiceError(RuntimeError):
    """Raised when an official upstream API cannot satisfy a request."""


class ContactRepository(Protocol):
    """Storage boundary for contacts and their append-only change logs."""

    def save(self, contact: Contact, changes: dict[str, Any]) -> Contact: ...
    def get(self, contact_id: str) -> Contact | None: ...
    def changes(self, contact_id: str) -> list[ContactChange]: ...


class ApprovalSink(Protocol):
    """Shared approval boundary used for all externally visible actions."""

    def put(self, item: ApprovalRequest) -> ApprovalRequest: ...


GenerateFn = Callable[[str, str, str | None], Awaitable[tuple[str, str]]]


class InMemoryContactRepository:
    """Small development repository; production should inject PostgreSQL storage."""

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._changes: dict[str, list[ContactChange]] = {}

    def save(self, contact: Contact, changes: dict[str, Any]) -> Contact:
        stored = contact.model_copy(deep=True)
        self._contacts[stored.id] = stored
        self._changes.setdefault(stored.id, []).append(
            ContactChange(
                contact_id=stored.id,
                version=stored.version,
                changed_at=stored.updated_at,
                changes=deepcopy(changes),
            )
        )
        return stored.model_copy(deep=True)

    def get(self, contact_id: str) -> Contact | None:
        item = self._contacts.get(contact_id)
        return item.model_copy(deep=True) if item else None

    def changes(self, contact_id: str) -> list[ContactChange]:
        return [entry.model_copy(deep=True) for entry in self._changes.get(contact_id, [])]


@dataclass
class SemanticScholarClient:
    """Official Semantic Scholar Graph API client with an injected HTTP client."""

    client: httpx.AsyncClient
    base_url: str = "https://api.semanticscholar.org/graph/v1"

    async def search_authors(self, query: str, limit: int) -> list[ProfessorCandidate]:
        response = await self.client.get(
            f"{self.base_url}/author/search",
            params={
                "query": query,
                "limit": limit,
                "fields": "name,affiliations,homepage,paperCount,citationCount,hIndex",
            },
        )
        if response.is_error:
            raise UpstreamServiceError(
                f"Semantic Scholar request failed ({response.status_code})"
            )
        candidates = []
        for row in response.json().get("data", []):
            citations = int(row.get("citationCount") or 0)
            papers = int(row.get("paperCount") or 0)
            h_index = int(row.get("hIndex") or 0)
            candidates.append(
                ProfessorCandidate(
                    author_id=str(row["authorId"]),
                    name=row["name"],
                    affiliation=(row.get("affiliations") or [None])[0],
                    homepage=row.get("homepage"),
                    paper_count=papers,
                    citation_count=citations,
                    h_index=h_index,
                    score=round(h_index * 3 + math.log1p(citations) + math.log1p(papers), 3),
                )
            )
        return sorted(candidates, key=lambda item: item.score, reverse=True)


class Service:
    """Manage contacts, ranked discovery, drafts, and approval proposals."""

    def __init__(
        self,
        repository: ContactRepository,
        approval_sink: ApprovalSink,
        scholar: SemanticScholarClient,
        llm_generate: GenerateFn = generate,
    ) -> None:
        self.repository = repository
        self.approval_sink = approval_sink
        self.scholar = scholar
        self.llm_generate = llm_generate

    def create_contact(self, data: ContactCreate) -> Contact:
        now = datetime.now(timezone.utc)
        item = Contact(
            id=str(uuid4()),
            created_at=now,
            updated_at=now,
            version=1,
            **data.model_dump(),
        )
        return self.repository.save(item, {"event": "created", **data.model_dump(mode="json")})

    def update_contact(self, contact_id: str, data: ContactCreate) -> Contact:
        existing = self._contact(contact_id)
        updated = Contact(
            id=existing.id,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
            version=existing.version + 1,
            **data.model_dump(),
        )
        changes = {
            field: value
            for field, value in data.model_dump(mode="json").items()
            if value != existing.model_dump(mode="json").get(field)
        }
        return self.repository.save(updated, {"event": "updated", **changes})

    def get_contact(self, contact_id: str) -> Contact:
        return self._contact(contact_id)

    def contact_changes(self, contact_id: str) -> list[ContactChange]:
        self._contact(contact_id)
        return self.repository.changes(contact_id)

    async def search_professors(self, query: str, limit: int) -> list[ProfessorCandidate]:
        return await self.scholar.search_authors(query, limit)

    async def draft_campaign(self, request: CampaignDraftRequest) -> DraftEmail:
        contact = self._contact(request.contact_id)
        prompt = self._campaign_prompt(request, contact)
        model, text = await self.llm_generate(prompt, request.provider, request.model)
        subject, body = self._parse_email(text)
        return DraftEmail(
            id=str(uuid4()),
            contact_id=contact.id,
            subject=subject,
            body=body,
            provider=request.provider,
            model=model,
            created_at=datetime.now(timezone.utc),
        )

    def propose_send(self, draft: DraftEmail) -> ProposedAction:
        contact = self._contact(draft.contact_id)
        if not contact.email:
            raise ValueError("contact has no verified email address")
        payload = {
            "contact_id": contact.id,
            "recipient": str(contact.email),
            "subject": draft.subject,
            "body": draft.body,
            "draft_id": draft.id,
        }
        approval = ApprovalRequest(
            id=str(uuid4()), module_id=5, action_type="send_outreach_email", payload=payload
        )
        self.approval_sink.put(approval)
        return ProposedAction(
            approval_id=approval.id,
            action_type="send_outreach_email",
            payload=payload,
        )

    async def draft_follow_up(self, request: FollowUpRequest) -> DraftEmail:
        contact = self._contact(request.contact_id)
        prompt = (
            "Draft a brief, respectful follow-up email. Do not invent facts. Return exactly "
            "'Subject: ...' followed by the body.\n"
            f"Recipient: {contact.name}\nOriginal subject: {request.original_subject}\n"
            f"Original email: {request.original_body}\n"
            f"Days without a detected reply: {request.days_without_reply}"
        )
        model, text = await self.llm_generate(prompt, request.provider, request.model)
        subject, body = self._parse_email(text)
        return DraftEmail(
            id=str(uuid4()),
            contact_id=contact.id,
            subject=subject,
            body=body,
            provider=request.provider,
            model=model,
            created_at=datetime.now(timezone.utc),
        )

    def propose_follow_up(self, draft: DraftEmail) -> ProposedAction:
        contact = self._contact(draft.contact_id)
        if not contact.email:
            raise ValueError("contact has no verified email address")
        payload = {
            "contact_id": contact.id,
            "recipient": str(contact.email),
            "subject": draft.subject,
            "body": draft.body,
            "draft_id": draft.id,
        }
        approval = ApprovalRequest(
            id=str(uuid4()), module_id=5, action_type="send_follow_up", payload=payload
        )
        self.approval_sink.put(approval)
        return ProposedAction(
            approval_id=approval.id, action_type="send_follow_up", payload=payload
        )

    def _contact(self, contact_id: str) -> Contact:
        contact = self.repository.get(contact_id)
        if contact is None:
            raise ContactNotFoundError(contact_id)
        return contact

    @staticmethod
    def _campaign_prompt(request: CampaignDraftRequest, contact: Contact) -> str:
        works = "\n".join(f"- {item}" for item in request.recent_work) or "- None supplied"
        return (
            "Draft a concise, truthful, personalized research outreach email. Do not claim "
            "familiarity with work beyond the supplied titles. Do not send it. Return exactly "
            "'Subject: ...' followed by the body.\n"
            f"Campaign goal: {request.goal}\nProject: {request.project_id}\n"
            f"Recipient: {contact.name}, {contact.institution or 'institution not supplied'}\n"
            f"Research topics: {', '.join(contact.research_topics)}\nRecent work supplied:\n{works}\n"
            f"Sender context: {request.sender_context}"
        )

    @staticmethod
    def _parse_email(text: str) -> tuple[str, str]:
        cleaned = text.strip()
        first, separator, rest = cleaned.partition("\n")
        if first.lower().startswith("subject:") and separator and rest.strip():
            return first.split(":", 1)[1].strip(), rest.strip()
        raise ValueError("model output must contain a Subject line followed by a body")
