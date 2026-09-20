"""API and domain models for the Competition Manager."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SubmissionStatus(str, Enum):
    """Lifecycle states supported by trustworthy evidence."""

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    SUBMISSION_PROPOSED = "submission_proposed"
    SUBMITTED = "submitted"
    JUDGING = "judging"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RuleSet(BaseModel):
    """Structured facts extracted from official competition rules."""

    summary: str
    eligibility_criteria: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)


class ChecklistItem(BaseModel):
    """One reviewable task derived from a required material."""

    title: str
    due_hint: str | None = None
    completed: bool = False


class CompetitionCreate(BaseModel):
    """Official rule content supplied by an upstream licensed connector or user."""

    name: str = Field(min_length=1, max_length=300)
    official_rules_url: HttpUrl
    official_rules_text: str = Field(min_length=20, max_length=200_000)
    provider: str = "openai"
    model: str | None = None


class Competition(BaseModel):
    """Competition state maintained by this bounded module."""

    id: str
    name: str
    official_rules_url: HttpUrl
    rules: RuleSet
    checklist: list[ChecklistItem]
    drafts: dict[str, str] = Field(default_factory=dict)
    status: SubmissionStatus = SubmissionStatus.DRAFT
    status_evidence: list["StatusEvidence"] = Field(default_factory=list)


class DraftRequest(BaseModel):
    """Inputs for drafting one required application field."""

    field_name: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=10_000)
    project_context: str = Field(min_length=1, max_length=40_000)
    approved_examples: list[str] = Field(default_factory=list, max_length=10)
    provider: str = "openai"
    model: str | None = None


class DraftResult(BaseModel):
    """A draft that remains subject to user review."""

    competition_id: str
    field_name: str
    text: str
    requires_user_review: bool = True
    model: str


class FormFillProposalRequest(BaseModel):
    """Approved text to stage for a browser form without submitting it."""

    form_url: HttpUrl
    fields: dict[str, str] = Field(min_length=1)


class ProposedAction(BaseModel):
    """An irreversible effect description for the Human Approval Center."""

    action_type: str
    payload: dict[str, Any]
    requires_approval: bool = True
    execution_performed: bool = False


class StatusEvidence(BaseModel):
    """Evidence obtained from a compliant upstream source."""

    source: str = Field(pattern="^(official_api|email|manual)$")
    reference: str = Field(min_length=1, max_length=1000)
    observed_at: datetime
    status: SubmissionStatus


class StatusUpdate(BaseModel):
    """A status transition backed by explicit evidence."""

    evidence: StatusEvidence


class ApplicationAnswersIn(BaseModel):
    answers:dict[str,str]=Field(min_length=1,max_length=100)
    provider:str="openai"
