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


class EnrichEmailRequest(BaseModel):
    """Find a verified-candidate email for a contact at one domain."""

    domain: str = Field(min_length=3, max_length=253)


class LabSearchRequest(BaseModel):
    """Search the curated lab registry."""

    query: str = Field(default="", max_length=500)
    topics: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=10, ge=1, le=50)


class LabCollectRequest(BaseModel):
    """Collect one public lab page (robots-respecting)."""

    url: str = Field(min_length=10, max_length=2000)


class CampaignCreateRequest(BaseModel):
    """Create a scoped outreach campaign."""

    project_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=3, max_length=2000)
    audience: str = Field(default="professor", max_length=40)
    max_follow_ups: int = Field(default=2, ge=0, le=10)
    follow_up_window_days: int = Field(default=5, ge=1, le=90)


class CampaignStatusUpdate(BaseModel):
    """Pause, resume, or complete a campaign."""

    status: Literal["active", "paused", "completed"]


class MessageDraftRequest(BaseModel):
    """Add a message draft to a campaign."""

    contact_id: str
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    kind: Literal["initial", "follow_up", "survey", "proposal", "pr_pitch"] = "initial"
    provider: str | None = None
    model: str | None = None



class ReplyRecordRequest(BaseModel):
    """Record a reply detected via provider thread metadata."""

    thread_id: str | None = Field(default=None, max_length=200)
    snippet: str | None = Field(default=None, max_length=1000)


class FailureRecordRequest(BaseModel):
    """Record a delivery failure or bounce notice."""

    reason: str = Field(min_length=1, max_length=1000)
    bounced: bool = False


class FollowUpDraftRequest(BaseModel):
    """Draft the next follow-up for a due message."""

    provider: str = "openai"
    model: str | None = None


class CampaignPlanRequest(BaseModel):
    """Plan a scoped campaign over stored contacts."""

    goal: str = Field(min_length=3, max_length=2000)
    audience: Literal["professor", "researcher", "professional", "student", "press"]
    contact_ids: list[str] = Field(min_length=1, max_length=500)
    scope: dict[str, Any] | None = None
    manual_channels: list[str] = Field(default_factory=list, max_length=10)


class SurveyPlanRequest(BaseModel):
    """Plan a micro-survey over stored contacts."""

    goal: str = Field(min_length=3, max_length=2000)
    contact_ids: list[str] = Field(min_length=1, max_length=500)
    question: str | None = Field(default=None, max_length=500)
    scope: dict[str, Any] | None = None


class PRPlanRequest(BaseModel):
    """Plan PR outreach over supplied press targets."""

    goal: str = Field(min_length=3, max_length=2000)
    targets: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    embargo: datetime | None = None
    scope: dict[str, Any] | None = None


class ProposalDraftRequest(BaseModel):
    """Draft a business proposal grounded in supplied project facts."""

    project: dict[str, Any]
    recipient_context: str = Field(min_length=1, max_length=2000)
    provider: str = "openai"
    model: str | None = None


# --- growth planning (feature rows 417-450) -------------------------------------


class EvidenceInput(BaseModel):
    """One caller-supplied fact with its source; key auto-assigned when omitted."""

    key: str | None = None
    source: str = "caller"
    fact: str


class GrowthPlanRequest(BaseModel):
    """Generic request for the growth planning endpoints.

    `inputs` carries the builder-specific fields (validated and typed by the
    builder); `evidence` carries the facts the artifact may cite;
    `contact_ids` binds CRM contacts for the email-marketing endpoint.
    """

    title: str | None = None
    goal: str = "growth"
    tenant_id: str = Field(default="local", min_length=1, max_length=120)
    actor_id: str = Field(default="caller", min_length=1, max_length=120)
    inputs: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceInput] = Field(default_factory=list)
    contact_ids: list[str] = Field(default_factory=list)
