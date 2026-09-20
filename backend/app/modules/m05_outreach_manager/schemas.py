"""API schemas for the Outreach Manager module."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ContactCreate(BaseModel):
    """Create or update a project-linked outreach contact."""

    project_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    institution: str | None = Field(default=None, max_length=300)
    research_topics: list[str] = Field(default_factory=list, max_length=50)
    profile_url: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        """Apply a conservative syntax check without adding a shared dependency."""

        if value is None:
            return None
        local, separator, domain = value.strip().partition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("invalid email address")
        return value.strip()


class Contact(ContactCreate):
    """A contact with audit metadata."""

    id: str
    created_at: datetime
    updated_at: datetime
    version: int


class ContactChange(BaseModel):
    """One immutable contact change-log entry."""

    contact_id: str
    version: int
    changed_at: datetime
    changes: dict[str, Any]


class ProfessorSearchRequest(BaseModel):
    """Search Semantic Scholar for authors who match a campaign topic."""

    query: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class ProfessorCandidate(BaseModel):
    """A professor candidate ranked with transparent publication signals."""

    author_id: str
    name: str
    affiliation: str | None = None
    homepage: HttpUrl | None = None
    paper_count: int = 0
    citation_count: int = 0
    h_index: int = 0
    score: float
    source: Literal["semantic_scholar"] = "semantic_scholar"


class CampaignDraftRequest(BaseModel):
    """Inputs needed to draft a personalized outreach message."""

    project_id: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=3, max_length=2000)
    contact_id: str
    sender_context: str = Field(min_length=3, max_length=8000)
    recent_work: list[str] = Field(default_factory=list, max_length=10)
    provider: str = "openai"
    model: str | None = None


class DraftEmail(BaseModel):
    """An unsent outreach email draft."""

    id: str
    contact_id: str
    subject: str
    body: str
    provider: str
    model: str
    created_at: datetime


class ProposedAction(BaseModel):
    """An external action that can only proceed through shared approval."""

    approval_id: str
    action_type: Literal["send_outreach_email", "send_follow_up"]
    status: Literal["pending"] = "pending"
    payload: dict[str, Any]


class FollowUpRequest(BaseModel):
    """Request a follow-up draft after a reply-check window elapsed."""

    contact_id: str
    original_subject: str = Field(min_length=1, max_length=500)
    original_body: str = Field(min_length=1, max_length=20_000)
    days_without_reply: int = Field(ge=1, le=365)
    provider: str = "openai"
    model: str | None = None
