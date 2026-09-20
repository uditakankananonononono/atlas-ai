"""Scoped outreach planning: audiences, PR, micro-surveys, proposals.

Ledger rows CRM-135 (PR outreach planning), CRM-136 (business proposals
from AI-created projects), CRM-137 (micro-survey), CRM-138
(professor/researcher/professional/student outreach), and CRM-140
(non-email channels are planned as manual handoffs with per-send Module 0
approval - never automated login DMs).

A plan is deterministic and reviewable: it names every stage, every
approval gate, and every scope rule it enforced, before anything is
drafted or sent. Plans never execute; execution is the campaign,
delivery, and approval layers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .campaigns import KIND_TO_ACTION_TYPE, MessageKind
from .schemas import Contact

AudienceType = Literal["professor", "researcher", "professional", "student", "press"]

AUDIENCE_PROFILES: dict[str, dict[str, str]] = {
    "professor": {
        "tone": "formal and concise",
        "guidance": "Reference the recipient's supplied recent work by title; state the ask in one sentence; no flattery beyond supplied facts.",
    },
    "researcher": {
        "tone": "collegial and technical",
        "guidance": "Lead with the shared research interest; offer the specific collaboration or data in supplied facts.",
    },
    "professional": {
        "tone": "direct and businesslike",
        "guidance": "Lead with the concrete value proposition; keep to three short paragraphs; one clear call to action.",
    },
    "student": {
        "tone": "friendly and encouraging",
        "guidance": "Peer-to-peer voice; be explicit about time commitment and what is in it for them.",
    },
    "press": {
        "tone": "newsworthy and crisp",
        "guidance": "Lead with the story in one sentence; supply the embargo and the unique angle; offer assets and a contact.",
    },
}

DEFAULT_SURVEY_QUESTION = "What tool do you wish you had?"
MAX_SCOPE_CONTACTS = 500


class ScopeViolationError(ValueError):
    """Raised when requested outreach exceeds its approved scope."""


class OutreachScope(BaseModel):
    """Hard limits every plan must enforce."""

    max_contacts: int = Field(default=25, ge=1, le=MAX_SCOPE_CONTACTS)
    per_domain_cap: int = Field(default=3, ge=1, le=50)
    require_verified_email: bool = True
    follow_up_window_days: int = Field(default=5, ge=1, le=90)
    max_follow_ups: int = Field(default=2, ge=0, le=10)


class PlanStep(BaseModel):
    """One stage of a plan, in execution order."""

    order: int
    stage: str
    description: str
    requires_approval: bool = False
    approval_action_type: str | None = None


class ContactAssignment(BaseModel):
    """One contact's place in a plan."""

    contact_id: str
    position: int
    kind: MessageKind = "initial"


class OutreachPlan(BaseModel):
    """A complete, reviewable outreach plan. Planning output only."""

    id: str
    goal: str
    audience: str
    kind: MessageKind = "initial"
    steps: list[PlanStep]
    assignments: list[ContactAssignment]
    scope: OutreachScope
    scope_checks: list[str]
    manual_channels: list[str] = Field(default_factory=list)
    created_at: datetime


class PRTarget(BaseModel):
    """One press target supplied by the user or a verified source."""

    outlet: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    beat: str | None = Field(default=None, max_length=200)


class ProjectSummary(BaseModel):
    """Grounding facts about an AI-created project for a business proposal."""

    name: str = Field(min_length=1, max_length=200)
    problem: str = Field(min_length=3, max_length=4000)
    solution: str = Field(min_length=3, max_length=4000)
    evidence: list[str] = Field(default_factory=list, max_length=25)
    ask: str = Field(min_length=3, max_length=1000)


class ProposalDraft(BaseModel):
    """A drafted business proposal awaiting exact human review."""

    id: str
    project_name: str
    recipient_context: str
    subject: str
    body: str
    provider: str
    model: str
    created_at: datetime


GenerateFn = Callable[[str, str, str | None], Awaitable[tuple[str, str]]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _email_domain(contact: Contact) -> str | None:
    if not contact.email or "@" not in contact.email:
        return None
    return contact.email.rsplit("@", 1)[1].lower()


def _is_verified(contact: Contact) -> bool:
    enrichment = (contact.metadata or {}).get("enrichment") or {}
    return enrichment.get("email_verified") is True


def _pipeline_steps(kind: MessageKind) -> list[PlanStep]:
    """The stage list every plan shares; external effects name their gate."""
    action_type = KIND_TO_ACTION_TYPE[kind]
    return [
        PlanStep(order=1, stage="discover", description="Resolve recipients from verified sources (registry, official APIs, user-supplied lists)."),
        PlanStep(order=2, stage="enrich", description="Fill and verify contact fields via keyed provider adapters; provenance recorded per field."),
        PlanStep(order=3, stage="draft", description="Draft personalized messages grounded only in supplied facts and audience profile."),
        PlanStep(order=4, stage="review", description="Human reviews every exact recipient, subject, and body in the Approval Center.", requires_approval=True, approval_action_type=action_type),
        PlanStep(order=5, stage="send", description="Delivery layer sends only payload-identical approved content and audits the result.", requires_approval=True, approval_action_type=action_type),
        PlanStep(order=6, stage="follow_up", description="If no reply lands inside the window, a follow-up is drafted and queued for its own approval.", requires_approval=True, approval_action_type="send_follow_up"),
    ]


def plan_campaign(
    *,
    goal: str,
    audience: AudienceType,
    contacts: list[Contact],
    scope: OutreachScope | None = None,
    kind: MessageKind = "initial",
    manual_channels: list[str] | None = None,
) -> OutreachPlan:
    """Plan a scoped campaign. Raises ScopeViolationError on any breach."""
    scope = scope or OutreachScope()
    if audience not in AUDIENCE_PROFILES:
        raise ValueError(f"unknown audience: {audience}")
    checks: list[str] = []

    if len(contacts) > scope.max_contacts:
        raise ScopeViolationError(
            f"{len(contacts)} contacts exceeds the scope cap of {scope.max_contacts}"
        )
    checks.append(f"contact count {len(contacts)} within cap {scope.max_contacts}")

    domains: dict[str, int] = {}
    for contact in contacts:
        domain = _email_domain(contact)
        if domain:
            domains[domain] = domains.get(domain, 0) + 1
    over = {domain: count for domain, count in domains.items() if count > scope.per_domain_cap}
    if over:
        raise ScopeViolationError(
            f"per-domain cap {scope.per_domain_cap} exceeded: {sorted(over)}"
        )
    checks.append(f"per-domain counts within cap {scope.per_domain_cap}")

    if scope.require_verified_email:
        unverified = [contact.id for contact in contacts if not _is_verified(contact)]
        if unverified:
            raise ScopeViolationError(
                f"{len(unverified)} contacts lack a provider-verified email: {unverified[:5]}"
            )
        checks.append("every contact email is provider-verified")
    else:
        missing = [contact.id for contact in contacts if not contact.email]
        if missing:
            raise ScopeViolationError(f"contacts without any email: {missing[:5]}")
        checks.append("every contact has an email (verification not required)")

    channels = [channel for channel in (manual_channels or []) if channel != "email"]
    if channels:
        checks.append(
            "non-email channels are manual handoffs with per-send Module 0 approval: "
            + ", ".join(sorted(channels))
        )

    return OutreachPlan(
        id=str(uuid4()),
        goal=goal,
        audience=audience,
        kind=kind,
        steps=_pipeline_steps(kind),
        assignments=[
            ContactAssignment(contact_id=contact.id, position=index + 1, kind=kind)
            for index, contact in enumerate(contacts)
        ],
        scope=scope,
        scope_checks=checks,
        manual_channels=sorted(channels),
        created_at=_utcnow(),
    )


def plan_pr_outreach(
    *,
    goal: str,
    targets: list[PRTarget],
    embargo: datetime | None = None,
    scope: OutreachScope | None = None,
) -> OutreachPlan:
    """Plan PR outreach: press targets, one angle each, embargo honored.

    Targets become assignments on synthetic contact ids (``pr:<outlet>``)
    because press targets are supplied directly rather than stored
    contacts; drafting imports them through the contacts API first.
    """
    scope = scope or OutreachScope(require_verified_email=False)
    if not targets:
        raise ValueError("PR planning requires at least one supplied target")
    if len(targets) > scope.max_contacts:
        raise ScopeViolationError(
            f"{len(targets)} press targets exceeds the scope cap of {scope.max_contacts}"
        )
    checks = [
        f"{len(targets)} supplied press targets within cap {scope.max_contacts}",
        "targets are user/verified-source supplied, not scraped",
    ]
    steps = _pipeline_steps("pr_pitch")
    if embargo is not None:
        steps.insert(
            4,
            PlanStep(
                order=5,
                stage="embargo",
                description=f"No send before embargo lifts at {embargo.isoformat()}.",
            ),
        )
        steps = [step.model_copy(update={"order": index + 1}) for index, step in enumerate(steps)]
        checks.append(f"embargo gate at {embargo.isoformat()}")
    return OutreachPlan(
        id=str(uuid4()),
        goal=goal,
        audience="press",
        kind="pr_pitch",
        steps=steps,
        assignments=[
            ContactAssignment(contact_id=f"pr:{target.outlet}", position=index + 1, kind="pr_pitch")
            for index, target in enumerate(targets)
        ],
        scope=scope,
        scope_checks=checks,
        created_at=_utcnow(),
    )


def build_micro_survey(
    *,
    goal: str,
    contacts: list[Contact],
    question: str = DEFAULT_SURVEY_QUESTION,
    scope: OutreachScope | None = None,
) -> OutreachPlan:
    """The micro-survey workflow: one question, approved sends, reply tracking.

    Defaults to the ledger's exact question, "What tool do you wish you
    had?" Responses come back through the reply seam; aggregation reads
    replied survey messages.
    """
    if not question.strip():
        raise ValueError("survey question must not be empty")
    plan = plan_campaign(
        goal=goal,
        audience="professional",
        contacts=contacts,
        scope=scope or OutreachScope(),
        kind="survey",
    )
    plan.scope_checks.append(f"single survey question: {question!r}")
    return plan


async def draft_proposal(
    *,
    project: ProjectSummary,
    recipient_context: str,
    llm_generate: GenerateFn,
    provider: str = "openai",
    model: str | None = None,
) -> ProposalDraft:
    """Draft a business proposal grounded ONLY in the supplied project facts.

    The prompt forbids inventing traction, metrics, or commitments; the
    draft then goes through the campaign pipeline as a ``proposal``
    message, which needs exact human review (share_proposal approval)
    before it can reach anyone.
    """
    if not recipient_context.strip():
        raise ValueError("recipient context is required for a grounded proposal")
    evidence = "\n".join(f"- {item}" for item in project.evidence) or "- None supplied"
    prompt = (
        "Draft a concise business proposal email. Use ONLY the supplied project facts; "
        "do not invent traction, metrics, customers, or commitments. Return exactly "
        "'Subject: ...' followed by the body.\n"
        f"Project: {project.name}\nProblem: {project.problem}\nSolution: {project.solution}\n"
        f"Supplied evidence:\n{evidence}\nAsk: {project.ask}\n"
        f"Recipient context: {recipient_context}"
    )
    used_model, text = await llm_generate(prompt, provider, model)
    subject, body = _parse_email(text)
    return ProposalDraft(
        id=str(uuid4()),
        project_name=project.name,
        recipient_context=recipient_context,
        subject=subject,
        body=body,
        provider=provider,
        model=used_model,
        created_at=_utcnow(),
    )


def audience_prompt_profile(audience: AudienceType) -> dict[str, str]:
    """The drafting guidance for one audience (used by campaign drafting)."""
    if audience not in AUDIENCE_PROFILES:
        raise ValueError(f"unknown audience: {audience}")
    return AUDIENCE_PROFILES[audience]


def _parse_email(text: str) -> tuple[str, str]:
    cleaned = text.strip()
    first, separator, rest = cleaned.partition("\n")
    if first.lower().startswith("subject:") and separator and rest.strip():
        return first.split(":", 1)[1].strip(), rest.strip()
    raise ValueError("model output must contain a Subject line followed by a body")
