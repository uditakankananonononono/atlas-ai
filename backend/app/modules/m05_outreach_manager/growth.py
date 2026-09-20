"""Typed, evidence-bound business planning artifacts (feature rows 417-450).

PR/media/crisis communication, community/influencer/affiliate/referral/email
marketing, automation/lead scoring/funnel/CRO/landing pages, sales
scripts/objections/negotiation/deals, pricing and monetization, and customer
success/onboarding/support/knowledge-base/community support.

Every builder produces a deterministic, reviewable BusinessArtifact:
- every external effect is listed in gated_effects and stays behind
  exact-review approval (the campaign/delivery runtime owns execution);
- every factual claim is bound to a caller-supplied EvidenceItem;
- builders never fabricate contacts, creators, journalists, prices, or
  market data - supplied inputs are the only source of facts;
- computed rows (lead scoring, price elasticity, CRO, health scoring,
  bundling, dynamic pricing) do transparent arithmetic on supplied numbers
  and embed those numbers as evidence.

Plans never execute. Nothing here sends, publishes, scrapes, or charges.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .campaigns import KIND_TO_ACTION_TYPE
from .planning import OutreachScope, _email_domain, _is_verified
from .schemas import Contact


class GrowthPlanError(ValueError):
    """Raised when a plan request is invalid or unsupported by evidence."""


# --- core artifact models ----------------------------------------------------


class EvidenceItem(BaseModel):
    """One caller-supplied fact with its source."""

    key: str
    source: str
    fact: str


class ArtifactSection(BaseModel):
    """One section of an artifact; evidence_keys must reference supplied evidence."""

    title: str
    body: str
    evidence_keys: list[str] = Field(default_factory=list)


class BusinessArtifact(BaseModel):
    """A deterministic, reviewable planning artifact bound to one ledger row."""

    kind: str
    feature_row: int
    title: str
    summary: str
    sections: list[ArtifactSection]
    evidence: list[EvidenceItem]
    scope_checks: list[str]
    gated_effects: list[str]
    manual_steps: list[str]


# --- typed inputs --------------------------------------------------------------


class MediaContact(BaseModel):
    name: str
    outlet: str
    beat: str | None = None
    relevance_fact: str


class Creator(BaseModel):
    name: str
    platform: str
    handle: str
    relevance_fact: str
    followers: int | None = Field(default=None, ge=0)


class AutomationTrigger(BaseModel):
    event: str
    action: str
    delay_hours: float = Field(default=0, ge=0)


class ScoringCriterion(BaseModel):
    attribute: str
    match: str = "any"  # "any" = attribute present; otherwise exact string match
    points: float = Field(gt=0, le=100)
    rationale: str


class Lead(BaseModel):
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class LeadScore(BaseModel):
    lead: str
    score: float
    reasons: list[str]


class PricePoint(BaseModel):
    price: float = Field(gt=0)
    quantity: float = Field(gt=0)


class ElasticityResult(BaseModel):
    kind: str = "price_elasticity"
    feature_row: int = 436
    elasticities: list[float]
    average_elasticity: float
    classification: str
    interpretation: str
    caveats: list[str]
    evidence: list[EvidenceItem]


class LeadScoringResult(BaseModel):
    kind: str = "lead_scoring"
    feature_row: int = 427
    scores: list[LeadScore]
    scale: str
    evidence: list[EvidenceItem]


class StageMetric(BaseModel):
    stage: str
    visitors: float = Field(ge=0)


class Tier(BaseModel):
    name: str
    price: float = Field(gt=0)
    period: Literal["monthly", "yearly"] = "monthly"
    features: list[str] = Field(default_factory=list)


class DynamicRule(BaseModel):
    condition: str
    adjustment_pct: float = Field(gt=-100, lt=500)


class PriceBounds(BaseModel):
    floor: float = Field(gt=0)
    ceiling: float = Field(gt=0)


class PricedProduct(BaseModel):
    name: str
    price: float = Field(gt=0)


class HealthSignal(BaseModel):
    name: str
    value: float
    target: float = Field(gt=0)
    weight: float = Field(default=1.0, gt=0)
    higher_is_better: bool = True


class AccountHealth(BaseModel):
    account: str
    signals: list[HealthSignal]


class IssueSolution(BaseModel):
    issue: str
    solution: str
    keywords: list[str] = Field(default_factory=list)


# --- shared helpers ---------------------------------------------------------------


def _keys(evidence: list[EvidenceItem]) -> set[str]:
    keys = [e.key for e in evidence]
    if len(set(keys)) != len(keys):
        raise GrowthPlanError(f"evidence keys must be unique: {keys}")
    return set(keys)


def _artifact(
    *,
    kind: str,
    row: int,
    title: str,
    summary: str,
    sections: list[ArtifactSection],
    evidence: list[EvidenceItem],
    scope_checks: list[str] | None = None,
    gated_effects: list[str] | None = None,
    manual_steps: list[str] | None = None,
) -> BusinessArtifact:
    """Assemble an artifact, enforcing the evidence-binding invariant."""
    if not evidence:
        raise GrowthPlanError(f"{kind}: at least one evidence item is required")
    known = _keys(evidence)
    for section in sections:
        missing = [k for k in section.evidence_keys if k not in known]
        if missing:
            raise GrowthPlanError(
                f"{kind}: section '{section.title}' cites unknown evidence keys {missing}"
            )
    checks = [
        "artifact is a reviewable plan only; nothing is sent, published, or charged by this module",
        f"all factual claims trace to {len(evidence)} caller-supplied evidence item(s)",
        *(scope_checks or []),
    ]
    return BusinessArtifact(
        kind=kind,
        feature_row=row,
        title=title,
        summary=summary,
        sections=sections,
        evidence=evidence,
        scope_checks=checks,
        gated_effects=[
            "every external effect below requires a separate exact-review approval",
            *(gated_effects or []),
        ],
        manual_steps=manual_steps or [],
    )


def _facts(prefix: str, facts: list[str], source: str) -> list[EvidenceItem]:
    """Turn caller-supplied fact strings into evidence items."""
    return [EvidenceItem(key=f"{prefix}{i + 1}", source=source, fact=f) for i, f in enumerate(facts)]


def _require(name: str, value: Any) -> Any:
    if value is None or value == "" or value == []:
        raise GrowthPlanError(f"'{name}' is required")
    return value


GATED_SEND = "sending any message runs through the campaign runtime with exact-review approval"
GATED_PUBLISH = "publishing to any external channel is a manual, per-item approved action"


# --- rows 417-419: PR, media, crisis ---------------------------------------------


def plan_public_relations(
    *,
    goal: str,
    brand_facts: list[str],
    reputation_risks: list[str] | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 417 - Public Relations: reputation management plan."""
    _require("brand_facts", brand_facts)
    ev = evidence + _facts("bf", brand_facts, "caller-supplied brand facts")
    sections = [
        ArtifactSection(
            title="Positioning and key messages",
            body="Key messages derived only from supplied brand facts: " + "; ".join(brand_facts),
            evidence_keys=[f"bf{i + 1}" for i in range(len(brand_facts))],
        ),
        ArtifactSection(
            title="Reputation risk watchlist",
            body="Risks to monitor: " + ("; ".join(reputation_risks) if reputation_risks else "none supplied"),
            evidence_keys=[e.key for e in evidence],
        ),
        ArtifactSection(
            title="Review cadence",
            body="Weekly sentiment review against the watchlist; escalate any confirmed negative coverage to the crisis plan (row 419) within one business day.",
        ),
    ]
    return _artifact(
        kind="public_relations",
        row=417,
        title=title or f"Public relations plan: {goal}",
        summary=f"Reputation management plan for goal '{goal}' grounded in {len(brand_facts)} supplied brand facts.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_PUBLISH, GATED_SEND],
        manual_steps=["name an accountable spokesperson before any statement is drafted"],
    )


def plan_media_relations(
    *,
    goal: str,
    journalists: list[MediaContact],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 418 - Media Relations: press relationship plan.

    Journalists must be supplied; this builder never fabricates media contacts.
    """
    jm = [f"{j.name} ({j.outlet}" + (f", {j.beat}" if j.beat else "") + f"): {j.relevance_fact}" for j in journalists]
    ev = evidence + _facts("j", jm, "caller-supplied press list")
    sections = [
        ArtifactSection(
            title="Supplied press list",
            body=(
                f"{len(journalists)} supplied contact(s): " + "; ".join(jm)
                if journalists
                else "No media contacts were supplied. None will be invented."
            ),
            evidence_keys=[f"j{i + 1}" for i in range(len(jm))],
        ),
        ArtifactSection(
            title="Relationship plan",
            body="For each supplied contact: one tailored, fact-grounded introduction referencing their stated beat; one value follow-up after 7 days; log every touch in the CRM.",
        ),
    ]
    scope = ["media contacts come only from the supplied list or the CRM; no fabricated journalists"]
    if not journalists:
        scope.append("no media contacts supplied - import a vetted press list before any outreach step")
    return _artifact(
        kind="media_relations",
        row=418,
        title=title or f"Media relations plan: {goal}",
        summary=f"Press relationship plan over {len(journalists)} supplied contact(s).",
        sections=sections,
        evidence=ev,
        scope_checks=scope,
        gated_effects=[GATED_SEND],
        manual_steps=[] if journalists else ["import a vetted press list into the CRM"],
    )


_SEVERITY_CADENCE_MIN = {"low": 1440, "medium": 240, "high": 60, "critical": 15}


def plan_crisis_communication(
    *,
    scenario: str,
    severity: Literal["low", "medium", "high", "critical"],
    confirmed_facts: list[str],
    stakeholders: list[str],
    update_window: str,
    unconfirmed: list[str] | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 419 - Crisis Communication: grounded holding statement + response plan."""
    _require("confirmed_facts", confirmed_facts)
    _require("stakeholders", stakeholders)
    _require("update_window", update_window)
    ev = evidence + _facts("cf", confirmed_facts, "caller-confirmed crisis facts")
    facts_text = " ".join(confirmed_facts)
    unknown = unconfirmed or []
    holding = (
        f"We are aware of {scenario}. {facts_text} "
        f"We will share our next update {update_window}."
    )
    cadence = _SEVERITY_CADENCE_MIN[severity]
    sections = [
        ArtifactSection(
            title="Severity and response cadence",
            body=f"Severity '{severity}' sets a first-response target of {cadence} minutes and an update every {max(cadence, 60)} minutes until resolution.",
        ),
        ArtifactSection(
            title="Holding statement (draft)",
            body=holding,
            evidence_keys=[f"cf{i + 1}" for i in range(len(confirmed_facts))],
        ),
        ArtifactSection(
            title="Confirmed vs unconfirmed",
            body=(
                "The statement uses only confirmed facts. Not yet confirmed and deliberately excluded: "
                + ("; ".join(unknown) if unknown else "none listed")
            ),
            evidence_keys=[f"cf{i + 1}" for i in range(len(confirmed_facts))],
        ),
        ArtifactSection(
            title="Stakeholder order",
            body="Notify in this order: " + " -> ".join(stakeholders) + ".",
            evidence_keys=[e.key for e in evidence],
        ),
    ]
    return _artifact(
        kind="crisis_communication",
        row=419,
        title=title or f"Crisis communication plan: {scenario}",
        summary=f"Severity-{severity} crisis plan with a fact-grounded holding statement; nothing publishes without approval.",
        sections=sections,
        evidence=ev,
        scope_checks=["the holding statement contains only caller-confirmed facts - no speculation"],
        gated_effects=[GATED_PUBLISH, GATED_SEND],
        manual_steps=["legal/compliance sign-off on the holding statement before release"],
    )


# --- rows 420-426: social, community, influencer, affiliate, referral, email, automation ---


def plan_social_media_strategy(
    *,
    goal: str,
    platforms: list[str],
    brand_facts: list[str],
    posts_per_week: int = 3,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 420 - Social Media Strategy."""
    _require("platforms", platforms)
    _require("brand_facts", brand_facts)
    if not (1 <= posts_per_week <= 14):
        raise GrowthPlanError("posts_per_week must be between 1 and 14")
    plats = [p.strip().lower() for p in platforms if p.strip()]
    ev = evidence + _facts("bf", brand_facts, "caller-supplied brand facts")
    sections = [
        ArtifactSection(
            title="Content pillars",
            body="Pillars derived from supplied brand facts: " + "; ".join(brand_facts),
            evidence_keys=[f"bf{i + 1}" for i in range(len(brand_facts))],
        ),
        ArtifactSection(
            title="Platform cadence",
            body="; ".join(f"{p}: {posts_per_week} posts/week" for p in plats),
        ),
    ]
    return _artifact(
        kind="social_media_strategy",
        row=420,
        title=title or f"Social media strategy: {goal}",
        summary=f"Presence plan across {len(plats)} platform(s) at {posts_per_week} posts/week each.",
        sections=sections,
        evidence=ev,
        scope_checks=["no automated posting, engagement pods, or platform self-bots"],
        gated_effects=[GATED_PUBLISH],
        manual_steps=["each post is drafted, reviewed, and published by a person or an approved scheduler"],
    )


def plan_community_management(
    *,
    community_name: str,
    purpose: str,
    member_facts: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 421 - Community Management."""
    _require("member_facts", member_facts)
    ev = evidence + _facts("mf", member_facts, "caller-supplied community facts")
    sections = [
        ArtifactSection(
            title="Community purpose",
            body=f"{community_name}: {purpose}",
            evidence_keys=[f"mf{i + 1}" for i in range(len(member_facts))],
        ),
        ArtifactSection(
            title="Moderation escalation",
            body="Level 1: moderator warning. Level 2: content removal + DM. Level 3: removal from community, logged with reason. All level 2+ actions are human decisions.",
        ),
        ArtifactSection(
            title="Weekly rituals",
            body="One welcome thread, one member spotlight drawn from supplied member facts, one feedback thread whose results feed the planning loop.",
        ),
    ]
    return _artifact(
        kind="community_management",
        row=421,
        title=title or f"Community management plan: {community_name}",
        summary=f"Nurture plan for '{community_name}' grounded in {len(member_facts)} supplied member facts.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_PUBLISH],
        manual_steps=["appoint at least two human moderators before launch"],
    )


def plan_influencer_marketing(
    *,
    goal: str,
    creators: list[Creator],
    budget: float | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 422 - Influencer Marketing. Creators must be supplied, never invented."""
    rows = [
        f"{c.name} (@{c.handle} on {c.platform}"
        + (f", {c.followers} followers" if c.followers is not None else "")
        + f"): {c.relevance_fact}"
        for c in creators
    ]
    ev = evidence + _facts("cr", rows, "caller-supplied creator list")
    sections = [
        ArtifactSection(
            title="Supplied creators",
            body=(
                f"{len(creators)} supplied creator(s): " + "; ".join(rows)
                if creators
                else "No creators were supplied. None will be invented."
            ),
            evidence_keys=[f"cr{i + 1}" for i in range(len(rows))],
        ),
        ArtifactSection(
            title="Vetting checklist",
            body="Per creator before outreach: confirm audience-topic fit from the supplied relevance fact, check past brand disclosures, agree deliverables and usage rights in writing.",
        ),
        ArtifactSection(
            title="Budget",
            body=(f"Caller-set budget: {budget}." if budget is not None else "No budget supplied; compensation terms are a manual decision per creator."),
        ),
    ]
    scope = [
        "creators come only from the supplied list; no fabricated influencers",
        "all sponsored content must carry platform-required disclosure (#ad or equivalent)",
    ]
    if not creators:
        scope.append("no creators supplied - supply a vetted list before outreach steps apply")
    return _artifact(
        kind="influencer_marketing",
        row=422,
        title=title or f"Influencer marketing plan: {goal}",
        summary=f"Creator partnership plan over {len(creators)} supplied creator(s).",
        sections=sections,
        evidence=ev,
        scope_checks=scope,
        gated_effects=[GATED_SEND, GATED_PUBLISH],
        manual_steps=[] if creators else ["supply a vetted creator list"],
    )


def plan_affiliate_marketing(
    *,
    program_name: str,
    commission_pct: float,
    cookie_days: int,
    avg_order_value: float | None = None,
    payout_threshold: float | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 423 - Affiliate Marketing: program structure from supplied terms."""
    if not (0 < commission_pct <= 100):
        raise GrowthPlanError("commission_pct must be in (0, 100]")
    if not (1 <= cookie_days <= 365):
        raise GrowthPlanError("cookie_days must be between 1 and 365")
    terms = [f"commission {commission_pct}%", f"attribution window {cookie_days} days"]
    if payout_threshold is not None:
        terms.append(f"payout threshold {payout_threshold}")
    ev = evidence + _facts("t", terms, "caller-supplied program terms")
    example = ""
    if avg_order_value is not None:
        if avg_order_value <= 0:
            raise GrowthPlanError("avg_order_value must be positive")
        example = f" At the supplied average order value of {avg_order_value}, one referral pays {round(avg_order_value * commission_pct / 100, 2)}."
    sections = [
        ArtifactSection(
            title="Program terms",
            body="; ".join(terms) + "." + example,
            evidence_keys=[f"t{i + 1}" for i in range(len(terms))],
        ),
        ArtifactSection(
            title="Recruitment and tracking",
            body="Recruit partners whose audience matches the supplied evidence; track via unique links or codes; pay only on confirmed, non-refunded orders.",
        ),
    ]
    return _artifact(
        kind="affiliate_marketing",
        row=423,
        title=title or f"Affiliate program: {program_name}",
        summary=f"Affiliate structure at {commission_pct}% commission over a {cookie_days}-day window.",
        sections=sections,
        evidence=ev,
        scope_checks=["no self-referral, cookie-stuffing, or incentivized-click schemes; violations void payout"],
        gated_effects=[GATED_SEND],
        manual_steps=["publish written program terms before recruiting partners"],
    )


def plan_referral_program(
    *,
    program_name: str,
    referrer_reward: str,
    referee_reward: str,
    mechanics: str = "unique link",
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 424 - Referral Programs."""
    _require("referrer_reward", referrer_reward)
    _require("referee_reward", referee_reward)
    terms = [f"referrer reward: {referrer_reward}", f"referee reward: {referee_reward}", f"mechanics: {mechanics}"]
    ev = evidence + _facts("r", terms, "caller-supplied referral terms")
    sections = [
        ArtifactSection(
            title="Double-sided incentive",
            body=f"Referrer gets {referrer_reward}; referee gets {referee_reward}. Distributed via {mechanics}.",
            evidence_keys=["r1", "r2", "r3"],
        ),
        ArtifactSection(
            title="Fraud guards",
            body="One reward per new customer; rewards vest only after the referee's first confirmed transaction; self-referrals and disposable-email signups are excluded.",
        ),
    ]
    return _artifact(
        kind="referral_program",
        row=424,
        title=title or f"Referral program: {program_name}",
        summary=f"Double-sided referral program via {mechanics}.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=["cap total reward liability before launch"],
    )


def plan_email_marketing(
    *,
    goal: str,
    contacts: list[Contact],
    sequence_steps: list[str] | None = None,
    scope: OutreachScope | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 425 - Email Marketing: nurture sequence bound to the M05 runtime.

    Uses the same verified-email and per-domain-cap scope rules as campaign
    planning, and every send step maps to a real approval action type.
    """
    scope = scope or OutreachScope()
    _require("contacts", contacts)
    if len(contacts) > scope.max_contacts:
        raise GrowthPlanError(
            f"email marketing scope allows at most {scope.max_contacts} contacts per plan, got {len(contacts)}"
        )
    per_domain: dict[str, int] = {}
    unverified: list[str] = []
    for contact in contacts:
        domain = _email_domain(contact)
        if domain:
            per_domain[domain] = per_domain.get(domain, 0) + 1
            if per_domain[domain] > scope.per_domain_cap:
                raise GrowthPlanError(
                    f"per-domain cap of {scope.per_domain_cap} exceeded for {domain}"
                )
        if scope.require_verified_email and not _is_verified(contact):
            unverified.append(contact.name)
    if unverified:
        raise GrowthPlanError(
            "scope requires provider-verified emails; unverified contacts: " + ", ".join(unverified)
        )
    steps = sequence_steps or ["welcome and value", "proof and education", "direct ask"]
    ev = evidence + _facts(
        "c", [f"{c.name} <{c.email}>" for c in contacts], "CRM contacts supplied by caller"
    )
    sections = [
        ArtifactSection(
            title="Audience",
            body=f"{len(contacts)} verified, scope-checked contact(s): " + "; ".join(c.name for c in contacts),
            evidence_keys=[f"c{i + 1}" for i in range(len(contacts))],
        ),
        ArtifactSection(
            title="Nurture sequence",
            body=" -> ".join(f"{i + 1}. {s}" for i, s in enumerate(steps)),
        ),
        ArtifactSection(
            title="Runtime binding",
            body=(
                "Each step executes as a campaign message requiring exact-review approval "
                f"(action type '{KIND_TO_ACTION_TYPE['initial']}'), with replies cancelling follow-ups "
                "and bounces marking contacts bounced - the same machinery as outreach campaigns."
            ),
        ),
    ]
    return _artifact(
        kind="email_marketing",
        row=425,
        title=title or f"Email marketing sequence: {goal}",
        summary=f"{len(steps)}-step nurture sequence over {len(contacts)} scope-checked contacts.",
        sections=sections,
        evidence=ev,
        scope_checks=[
            f"max {scope.max_contacts} contacts, {scope.per_domain_cap} per domain, verified email required = {scope.require_verified_email}"
        ],
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_marketing_automation(
    *,
    goal: str,
    triggers: list[AutomationTrigger],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 426 - Marketing Automation: rules as proposals, never autonomous."""
    _require("triggers", triggers)
    ev = evidence + _facts(
        "tr",
        [f"on '{t.event}' -> {t.action} after {t.delay_hours}h" for t in triggers],
        "caller-supplied automation rules",
    )
    sections = [
        ArtifactSection(
            title="Proposed rules",
            body="; ".join(
                f"when '{t.event}' occurs, {t.action} after {t.delay_hours} hour(s)" for t in triggers
            ),
            evidence_keys=[f"tr{i + 1}" for i in range(len(triggers))],
        ),
        ArtifactSection(
            title="Activation policy",
            body="Each rule is inert until a person approves it; every message the rules produce still passes exact-review approval before sending.",
        ),
    ]
    return _artifact(
        kind="marketing_automation",
        row=426,
        title=title or f"Marketing automation plan: {goal}",
        summary=f"{len(triggers)} proposed automation rule(s); none activate autonomously.",
        sections=sections,
        evidence=ev,
        scope_checks=["no autonomous sends: every rule activation and every produced message is approval-gated"],
        gated_effects=["activating any automation rule", GATED_SEND],
        manual_steps=[],
    )


# --- rows 427-434: lead scoring, funnel, CRO, landing page, sales -----------------


def score_leads(
    *,
    leads: list[Lead],
    criteria: list[ScoringCriterion],
    evidence: list[EvidenceItem],
) -> LeadScoringResult:
    """Row 427 - Lead Scoring: transparent, rule-based prioritization.

    The score is a capped sum of matched criterion points; every point is
    explained in the returned reasons. No opaque model, no hidden features.
    """
    _require("leads", leads)
    _require("criteria", criteria)
    total_possible = sum(c.points for c in criteria)
    if total_possible <= 0:
        raise GrowthPlanError("criteria must carry positive total points")
    scores: list[LeadScore] = []
    for lead in leads:
        raw = 0.0
        reasons: list[str] = []
        for criterion in criteria:
            value = lead.attributes.get(criterion.attribute)
            matched = value is not None and (
                criterion.match == "any" or str(value) == criterion.match
            )
            if matched:
                raw += criterion.points
                reasons.append(
                    f"+{criterion.points} {criterion.attribute}"
                    + ("" if criterion.match == "any" else f"={criterion.match}")
                    + f" ({criterion.rationale})"
                )
        scores.append(
            LeadScore(
                lead=lead.name,
                score=round(min(100.0, raw / total_possible * 100), 1),
                reasons=reasons or ["no criteria matched"],
            )
        )
    scores.sort(key=lambda s: s.score, reverse=True)
    ev = evidence + _facts(
        "lc",
        [f"{c.attribute}={c.match} worth {c.points}: {c.rationale}" for c in criteria],
        "caller-supplied scoring criteria",
    ) + _facts("ld", [f"{l.name}: {l.attributes}" for l in leads], "caller-supplied lead attributes")
    return LeadScoringResult(
        scores=scores,
        scale="0-100, normalized against the total possible criterion points",
        evidence=ev,
    )


def design_sales_funnel(
    *,
    goal: str,
    stages: list[StageMetric] | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 428 - Sales Funnel Design. Conversion math only on supplied metrics."""
    if stages:
        names = [s.stage for s in stages]
        conv = []
        for prev, cur in zip(stages, stages[1:]):
            rate = round(cur.visitors / prev.visitors * 100, 1) if prev.visitors else 0.0
            conv.append(f"{prev.stage} -> {cur.stage}: {rate}%")
        metric_lines = [f"{s.stage}: {s.visitors}" for s in stages]
        ev = evidence + _facts("fm", metric_lines, "caller-supplied funnel metrics")
        sections = [
            ArtifactSection(
                title="Supplied funnel",
                body="Stages: " + " -> ".join(names),
                evidence_keys=[f"fm{i + 1}" for i in range(len(metric_lines))],
            ),
            ArtifactSection(
                title="Stage conversion (computed from supplied numbers)",
                body="; ".join(conv) if conv else "single stage supplied; no conversion to compute",
                evidence_keys=[f"fm{i + 1}" for i in range(len(metric_lines))],
            ),
        ]
        summary = f"Buyer journey of {len(stages)} stage(s) with computed conversion rates."
    else:
        names = ["awareness", "interest", "consideration", "decision", "retention"]
        ev = evidence
        sections = [
            ArtifactSection(
                title="Default journey template",
                body="Stages: " + " -> ".join(names) + ". No metrics were supplied, so no conversion claims are made.",
            ),
        ]
        summary = "Buyer journey template; instrument it before drawing conclusions."
    return _artifact(
        kind="sales_funnel",
        row=428,
        title=title or f"Sales funnel: {goal}",
        summary=summary,
        sections=sections,
        evidence=ev,
        scope_checks=["conversion figures appear only when stage metrics were supplied"],
        gated_effects=[],
        manual_steps=["instrument each stage before optimizing"],
    )


def plan_conversion_optimization(
    *,
    goal: str,
    funnel: list[StageMetric],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 429 - Conversion Rate Optimization: find the biggest drop, propose tests."""
    _require("funnel", funnel)
    if len(funnel) < 2:
        raise GrowthPlanError("at least two funnel stages are required to find a drop-off")
    drops: list[tuple[str, float]] = []
    for prev, cur in zip(funnel, funnel[1:]):
        rate = cur.visitors / prev.visitors if prev.visitors else 0.0
        drops.append((f"{prev.stage} -> {cur.stage}", rate))
    worst, worst_rate = min(drops, key=lambda d: d[1])
    metric_lines = [f"{s.stage}: {s.visitors}" for s in funnel]
    ev = evidence + _facts("fm", metric_lines, "caller-supplied funnel metrics")
    sections = [
        ArtifactSection(
            title="Measured funnel",
            body="; ".join(f"{name}: {round(rate * 100, 1)}%" for name, rate in drops),
            evidence_keys=[f"fm{i + 1}" for i in range(len(metric_lines))],
        ),
        ArtifactSection(
            title="Priority: largest drop-off",
            body=f"'{worst}' converts at {round(worst_rate * 100, 1)}%, the weakest step. First experiment targets this transition.",
            evidence_keys=[f"fm{i + 1}" for i in range(len(metric_lines))],
        ),
        ArtifactSection(
            title="Experiment plan",
            body="One hypothesis per test, single variable per variant, run to a pre-committed sample size, log outcomes as new evidence before iterating.",
        ),
    ]
    return _artifact(
        kind="conversion_optimization",
        row=429,
        title=title or f"CRO plan: {goal}",
        summary=f"Prioritized the weakest transition '{worst}' from supplied funnel metrics.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=["confirm tracking integrity before trusting the measured rates"],
    )


def plan_landing_page(
    *,
    page_url: str,
    current_headline: str,
    cta_text: str,
    value_facts: list[str],
    load_time_ms: int | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 430 - Landing Page Optimization: deterministic audit + grounded variant."""
    _require("value_facts", value_facts)
    findings: list[str] = []
    headline_words = len(current_headline.split())
    findings.append(
        f"headline is {headline_words} word(s) - "
        + ("within the 12-word scan budget" if headline_words <= 12 else "over the 12-word scan budget; tighten it")
    )
    findings.append(
        f"CTA text '{cta_text}' is "
        + ("action-oriented" if cta_text.split()[0].lower() in {"get", "start", "try", "book", "join", "claim", "see", "download", "request"} else "not obviously action-oriented; lead with a verb")
    )
    if load_time_ms is not None:
        if load_time_ms < 0:
            raise GrowthPlanError("load_time_ms cannot be negative")
        findings.append(
            f"measured load time {load_time_ms}ms - "
            + ("within the 2500ms budget" if load_time_ms <= 2500 else "over the 2500ms budget; performance work comes before copy work")
        )
    ev = evidence + _facts("vf", value_facts, "caller-supplied value facts")
    variant = f"{value_facts[0].rstrip('.')} - {cta_text}"
    sections = [
        ArtifactSection(title="Audit findings", body=" ".join(findings), evidence_keys=[e.key for e in evidence]),
        ArtifactSection(
            title="Variant draft (grounded)",
            body=f"Candidate headline built from the first supplied value fact: '{variant}'.",
            evidence_keys=["vf1"],
        ),
    ]
    return _artifact(
        kind="landing_page_optimization",
        row=430,
        title=title or f"Landing page plan: {page_url}",
        summary="Deterministic audit plus one evidence-grounded variant; nothing deploys automatically.",
        sections=sections,
        evidence=ev,
        gated_effects=["deploying any page variant is a manual, reviewed action"],
        manual_steps=[],
    )


def develop_sales_script(
    *,
    persona: str,
    product_facts: list[str],
    call_to_action: str,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 431 - Sales Script Development: every claim cites a supplied fact."""
    _require("product_facts", product_facts)
    _require("call_to_action", call_to_action)
    ev = evidence + _facts("pf", product_facts, "caller-supplied product facts")
    sections = [
        ArtifactSection(
            title="Opener",
            body=f"Honest opener for {persona}: state who you are, why you are reaching out, and ask for a short conversation. No false familiarity, no implied prior relationship.",
        ),
        ArtifactSection(
            title="Discovery questions",
            body="Ask before pitching: current workflow, biggest friction, what they have tried, decision process, timeline.",
        ),
        ArtifactSection(
            title="Value mapping",
            body=" ".join(f"Because {fact.rstrip('.')}, you get a concrete benefit." for fact in product_facts),
            evidence_keys=[f"pf{i + 1}" for i in range(len(product_facts))],
        ),
        ArtifactSection(title="Close", body=f"Single, specific ask: {call_to_action}."),
    ]
    return _artifact(
        kind="sales_script",
        row=431,
        title=title or f"Sales script for {persona}",
        summary=f"Script for {persona} whose product claims all cite supplied facts.",
        sections=sections,
        evidence=ev,
        scope_checks=["every product claim in the value mapping cites a supplied fact"],
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_objection_handling(
    *,
    objections: list[str],
    product_facts: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 432 - Objection Handling: responses grounded in supplied facts."""
    _require("objections", objections)
    _require("product_facts", product_facts)
    ev = evidence + _facts("pf", product_facts, "caller-supplied product facts")
    per_objection = [
        ArtifactSection(
            title=f"Objection: {obj}",
            body=(
                "Listen without interrupting; acknowledge the concern; explore the specifics; "
                "respond only with supplied facts: " + "; ".join(product_facts)
            ),
            evidence_keys=[f"pf{i + 1}" for i in range(len(product_facts))],
        )
        for obj in objections
    ]
    per_objection.append(
        ArtifactSection(
            title="Never say",
            body="Do not invent numbers, comparisons, or customer names. If the answer is not in the supplied facts, promise a follow-up and log the gap as new evidence needed.",
        )
    )
    return _artifact(
        kind="objection_handling",
        row=432,
        title=title or "Objection handling playbook",
        summary=f"Playbook for {len(objections)} objection(s), responses bound to supplied facts.",
        sections=per_objection,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_negotiation(
    *,
    target_outcome: str,
    walk_away: str,
    constraints: list[str],
    counterpart_facts: list[str],
    opening_offer: float | None = None,
    walk_away_price: float | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 433 - Negotiation Strategy: explicit walk-away, computed concession ladder."""
    _require("target_outcome", target_outcome)
    _require("walk_away", walk_away)
    _require("constraints", constraints)
    _require("counterpart_facts", counterpart_facts)
    ev = evidence + _facts("cf", counterpart_facts, "caller-supplied counterpart facts")
    sections = [
        ArtifactSection(
            title="Position",
            body=f"Target: {target_outcome}. Walk-away: {walk_away}. Constraints: " + "; ".join(constraints),
            evidence_keys=[e.key for e in evidence],
        ),
        ArtifactSection(
            title="Counterpart grounding",
            body="Known about the counterpart (supplied): " + "; ".join(counterpart_facts),
            evidence_keys=[f"cf{i + 1}" for i in range(len(counterpart_facts))],
        ),
    ]
    if opening_offer is not None and walk_away_price is not None:
        if opening_offer <= 0 or walk_away_price <= 0:
            raise GrowthPlanError("prices must be positive")
        step = (opening_offer - walk_away_price) / 3
        ladder = [round(opening_offer - step * i, 2) for i in range(4)]
        sections.append(
            ArtifactSection(
                title="Concession ladder (computed)",
                body="Four evenly spaced positions from opening to walk-away: " + " -> ".join(str(p) for p in ladder) + ". Never move past the final rung.",
            )
        )
    return _artifact(
        kind="negotiation_strategy",
        row=433,
        title=title or f"Negotiation plan: {target_outcome}",
        summary="Position, counterpart grounding, and walk-away discipline; any agreement is a human decision.",
        sections=sections,
        evidence=ev,
        gated_effects=["agreeing to any term is a human decision, never automated"],
        manual_steps=[],
    )


def structure_deal(
    *,
    parties: list[str],
    terms: dict[str, Any],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 434 - Deal Structuring: term sheet artifact with open-term tracking."""
    _require("parties", parties)
    _require("terms", terms)
    fixed = {k: v for k, v in terms.items() if v not in (None, "", "TBD")}
    open_terms = [k for k, v in terms.items() if k not in fixed]
    ev = evidence + _facts(
        "dt", [f"{k}: {v}" for k, v in fixed.items()], "caller-supplied deal terms"
    )
    sections = [
        ArtifactSection(
            title="Parties",
            body=" and ".join(parties),
            evidence_keys=[e.key for e in evidence],
        ),
        ArtifactSection(
            title="Fixed terms",
            body="; ".join(f"{k}: {v}" for k, v in fixed.items()),
            evidence_keys=[f"dt{i + 1}" for i in range(len(fixed))],
        ),
        ArtifactSection(
            title="Open terms",
            body=("Unresolved: " + ", ".join(open_terms)) if open_terms else "All supplied terms are fixed.",
        ),
    ]
    return _artifact(
        kind="deal_structuring",
        row=434,
        title=title or "Deal structure: " + " and ".join(parties),
        summary=f"Term sheet artifact: {len(fixed)} fixed term(s), {len(open_terms)} open.",
        sections=sections,
        evidence=ev,
        scope_checks=["this is a structuring aid, not legal advice; counsel reviews before signature"],
        gated_effects=["sending any term sheet or signature request is approval-gated"],
        manual_steps=["legal review of the final terms before any party signs"],
    )


# --- rows 435-445: pricing and monetization ---------------------------------------


def plan_pricing_strategy(
    *,
    product: str,
    unit_cost: float,
    target_margin_pct: float,
    competitor_prices: list[float] | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 435 - Pricing Strategy: every number derives from supplied inputs."""
    if unit_cost <= 0:
        raise GrowthPlanError("unit_cost must be positive")
    if not (0 <= target_margin_pct < 100):
        raise GrowthPlanError("target_margin_pct must be in [0, 100)")
    floor = round(unit_cost / (1 - target_margin_pct / 100), 2) if target_margin_pct else unit_cost
    facts = [f"unit cost {unit_cost}", f"target margin {target_margin_pct}%"]
    body = f"Cost floor at the supplied unit cost and target margin: price at or above {floor}."
    keys_count = 2
    if competitor_prices:
        if any(p <= 0 for p in competitor_prices):
            raise GrowthPlanError("competitor prices must be positive")
        lo, hi = min(competitor_prices), max(competitor_prices)
        facts.append(f"supplied competitor prices: {competitor_prices}")
        body += f" Supplied competitor range {lo}-{hi}; position inside it only with evidence, never below the cost floor."
        keys_count = 3
    else:
        body += " No competitor prices were supplied, so no market positioning is claimed."
    ev = evidence + _facts("pc", facts, "caller-supplied pricing inputs")
    sections = [
        ArtifactSection(
            title="Price floor (computed)",
            body=body,
            evidence_keys=[f"pc{i + 1}" for i in range(keys_count)],
        ),
        ArtifactSection(
            title="Guardrails",
            body="Never price below the computed floor without an explicit, time-boxed experiment approved by a person. Review the floor whenever unit cost changes.",
        ),
    ]
    return _artifact(
        kind="pricing_strategy",
        row=435,
        title=title or f"Pricing strategy: {product}",
        summary=f"Computed cost floor {floor} from supplied cost and margin; no unsupported market claims.",
        sections=sections,
        evidence=ev,
        scope_checks=["every price figure derives from supplied inputs; no market data is invented"],
        gated_effects=["changing any published price is an approved, reviewed action"],
        manual_steps=[],
    )


def analyze_price_elasticity(
    *,
    points: list[PricePoint],
    evidence: list[EvidenceItem],
) -> ElasticityResult:
    """Row 436 - Price Elasticity Analysis: midpoint method on supplied observations."""
    _require("points", points)
    if len(points) < 2:
        raise GrowthPlanError("at least two price/quantity observations are required")
    elasticities: list[float] = []
    for a, b in zip(points, points[1:]):
        dq = (b.quantity - a.quantity) / ((a.quantity + b.quantity) / 2)
        dp = (b.price - a.price) / ((a.price + b.price) / 2)
        if dp == 0:
            raise GrowthPlanError("two consecutive observations share a price; elasticity is undefined")
        elasticities.append(round(abs(dq / dp), 3))
    avg = round(sum(elasticities) / len(elasticities), 3)
    classification = "elastic" if avg > 1 else ("inelastic" if avg < 1 else "unitary")
    interpretation = {
        "elastic": "quantity responds more than proportionally to price; increases likely reduce revenue",
        "inelastic": "quantity responds less than proportionally; moderate increases may raise revenue",
        "unitary": "quantity responds proportionally; revenue is roughly price-neutral",
    }[classification]
    caveats = ["elasticity from few observations is a weak signal; treat it as directional only"]
    if len(points) < 4:
        caveats.append(f"only {len(points)} observations supplied; gather more before acting")
    ev = evidence + _facts(
        "pp",
        [f"price {p.price} -> quantity {p.quantity}" for p in points],
        "caller-supplied price/quantity observations",
    )
    return ElasticityResult(
        elasticities=elasticities,
        average_elasticity=avg,
        classification=classification,
        interpretation=interpretation,
        caveats=caveats,
        evidence=ev,
    )


def design_revenue_model(
    *,
    value_proposition: str,
    streams: list[dict[str, str]],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 437 - Revenue Model Design."""
    _require("value_proposition", value_proposition)
    _require("streams", streams)
    known = {"subscription", "usage", "transaction", "licensing", "advertising", "services", "marketplace"}
    lines = []
    for stream in streams:
        name = _require("stream name", stream.get("name", ""))
        stype = stream.get("type", "other")
        stype = stype if stype in known else "other"
        lines.append(f"{name} ({stype}): {stream.get('description', 'no description supplied')}")
    ev = evidence + _facts("rs", lines, "caller-supplied revenue streams")
    sections = [
        ArtifactSection(
            title="Value proposition",
            body=value_proposition,
            evidence_keys=[e.key for e in evidence],
        ),
        ArtifactSection(
            title="Revenue streams",
            body="; ".join(lines),
            evidence_keys=[f"rs{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Coherence check",
            body="Each stream must be explainable to a customer in one sentence and trace to the value proposition; any stream that cannot is flagged for removal in review.",
        ),
    ]
    return _artifact(
        kind="revenue_model",
        row=437,
        title=title or "Revenue model",
        summary=f"{len(streams)} revenue stream(s) mapped to the supplied value proposition.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def design_subscription(
    *,
    tiers: list[Tier],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 438 - Subscription Design: validated tiers with computed equivalents."""
    _require("tiers", tiers)
    names = [t.name for t in tiers]
    if len(set(names)) != len(names):
        raise GrowthPlanError("tier names must be unique")
    lines = []
    for t in tiers:
        monthly = round(t.price / 12, 2) if t.period == "yearly" else t.price
        lines.append(
            f"{t.name}: {t.price}/{t.period} (monthly equivalent {monthly})"
            + (f" - {len(t.features)} feature(s): " + ", ".join(t.features) if t.features else "")
        )
    ev = evidence + _facts("st", lines, "caller-supplied subscription tiers")
    sections = [
        ArtifactSection(
            title="Tiers",
            body="; ".join(lines),
            evidence_keys=[f"st{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Retention levers",
            body="Annual-billing discount, pause-instead-of-cancel, and downgrade paths reduce churn; each is a billing change requiring review before it ships.",
        ),
    ]
    return _artifact(
        kind="subscription_design",
        row=438,
        title=title or "Subscription design",
        summary=f"{len(tiers)} validated tier(s) with computed monthly equivalents.",
        sections=sections,
        evidence=ev,
        gated_effects=["changing subscription prices for existing customers is an approved, communicated action"],
        manual_steps=[],
    )


def plan_freemium(
    *,
    free_features: list[str],
    paid_features: list[str],
    free_unit_cost: float,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 439 - Freemium Strategy: free tier must be sustainable and gated by value."""
    _require("free_features", free_features)
    _require("paid_features", paid_features)
    if free_unit_cost < 0:
        raise GrowthPlanError("free_unit_cost cannot be negative")
    overlap = set(free_features) & set(paid_features)
    if overlap:
        raise GrowthPlanError(f"features cannot be both free and paid: {sorted(overlap)}")
    facts = [
        f"free tier: {', '.join(free_features)}",
        f"paid tier: {', '.join(paid_features)}",
        f"free-user unit cost {free_unit_cost}",
    ]
    ev = evidence + _facts("ff", facts, "caller-supplied freemium inputs")
    sections = [
        ArtifactSection(
            title="Tier split",
            body="Free: " + ", ".join(free_features) + ". Paid: " + ", ".join(paid_features) + ".",
            evidence_keys=["ff1", "ff2"],
        ),
        ArtifactSection(
            title="Sustainability",
            body=f"Each free user costs {free_unit_cost}; the plan is viable only while conversion covers total free-tier cost - track this as a standing metric.",
            evidence_keys=["ff3"],
        ),
        ArtifactSection(
            title="Upgrade triggers",
            body="Prompt upgrade exactly where a user reaches for a paid feature: " + ", ".join(paid_features) + ".",
            evidence_keys=["ff2"],
        ),
    ]
    return _artifact(
        kind="freemium_strategy",
        row=439,
        title=title or "Freemium strategy",
        summary=f"{len(free_features)} free vs {len(paid_features)} paid features, with a stated free-user cost.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=["add free-tier unit cost to the standing metrics review"],
    )


def plan_usage_based_pricing(
    *,
    meter: str,
    unit_price: float,
    free_allowance: float = 0,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 440 - Usage-Based Pricing: worked bills computed from supplied numbers."""
    _require("meter", meter)
    if unit_price <= 0:
        raise GrowthPlanError("unit_price must be positive")
    if free_allowance < 0:
        raise GrowthPlanError("free_allowance cannot be negative")

    def bill(units: float) -> float:
        return round(max(0.0, units - free_allowance) * unit_price, 2)

    examples = [free_allowance, free_allowance * 2 + 1, free_allowance * 10 + 10]
    example_text = "; ".join(f"{u} {meter} -> bill {bill(u)}" for u in examples)
    facts = [f"meter: {meter}", f"unit price {unit_price}", f"free allowance {free_allowance}"]
    ev = evidence + _facts("ub", facts, "caller-supplied usage pricing inputs")
    sections = [
        ArtifactSection(
            title="Meter and price",
            body=f"Bill per {meter} at {unit_price} after a free allowance of {free_allowance}.",
            evidence_keys=["ub1", "ub2", "ub3"],
        ),
        ArtifactSection(
            title="Worked examples (computed)",
            body=example_text,
            evidence_keys=["ub1", "ub2", "ub3"],
        ),
        ArtifactSection(
            title="Bill shock guard",
            body="Usage dashboards, spend alerts at 50%/80%/100% of a caller-set budget, and a hard cap option are required before launch.",
        ),
    ]
    return _artifact(
        kind="usage_based_pricing",
        row=440,
        title=title or f"Usage-based pricing: {meter}",
        summary=f"Per-{meter} pricing at {unit_price} with computed example bills.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=["ship usage dashboards and spend alerts with the meter, not after"],
    )


def plan_tiered_pricing(
    *,
    tiers: list[Tier],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 441 - Tiered Pricing: spacing analysis computed from supplied prices."""
    _require("tiers", tiers)
    if len(tiers) < 2:
        raise GrowthPlanError("tiered pricing needs at least two tiers")
    ordered = sorted(tiers, key=lambda t: t.price)
    gaps: list[str] = []
    warnings: list[str] = []
    for low, high in zip(ordered, ordered[1:]):
        pct = round((high.price - low.price) / low.price * 100, 1)
        gaps.append(f"{low.name} -> {high.name}: +{pct}%")
        if pct < 20:
            warnings.append(f"{low.name}/{high.name} are only {pct}% apart; buyers cannot tell them apart")
        if pct > 300:
            warnings.append(f"{low.name}/{high.name} are {pct}% apart; the jump may strand upgraders")
    lines = [f"{t.name}: {t.price}/{t.period}" for t in ordered]
    ev = evidence + _facts("tp", lines, "caller-supplied tiers")
    sections = [
        ArtifactSection(
            title="Tier ladder",
            body="; ".join(lines),
            evidence_keys=[f"tp{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Spacing analysis (computed)",
            body="; ".join(gaps) + ("." if not warnings else " Warnings: " + " ".join(warnings)),
            evidence_keys=[f"tp{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="tiered_pricing",
        row=441,
        title=title or "Tiered pricing",
        summary=f"{len(tiers)} tiers with computed price-spacing analysis.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def plan_dynamic_pricing(
    *,
    base_price: float,
    rules: list[DynamicRule],
    bounds: PriceBounds,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 442 - Dynamic Pricing: hard bounds are mandatory; stacking is checked."""
    _require("rules", rules)
    if base_price <= 0:
        raise GrowthPlanError("base_price must be positive")
    if bounds.floor >= bounds.ceiling:
        raise GrowthPlanError("bounds.floor must be below bounds.ceiling")
    if not (bounds.floor <= base_price <= bounds.ceiling):
        raise GrowthPlanError("base_price must sit inside the supplied bounds")
    worst = base_price
    for rule in rules:
        worst *= 1 + rule.adjustment_pct / 100
    worst = round(worst, 2)
    if not (bounds.floor <= worst <= bounds.ceiling):
        raise GrowthPlanError(
            f"stacking every rule pushes the price to {worst}, outside the bounds "
            f"[{bounds.floor}, {bounds.ceiling}]; narrow the rules or widen the bounds"
        )
    facts = [f"base price {base_price}", f"bounds [{bounds.floor}, {bounds.ceiling}]"] + [
        f"when {r.condition}: {r.adjustment_pct:+}%" for r in rules
    ]
    ev = evidence + _facts("dp", facts, "caller-supplied dynamic pricing inputs")
    sections = [
        ArtifactSection(
            title="Rules within bounds",
            body="; ".join(f"when {r.condition}: {r.adjustment_pct:+}%" for r in rules)
            + f". Worst-case stacked price {worst} stays inside [{bounds.floor}, {bounds.ceiling}].",
            evidence_keys=[f"dp{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Fairness guardrails",
            body="No personalized prices per individual without disclosure; surge conditions are shown to the buyer; a person can always override to the base price.",
        ),
    ]
    return _artifact(
        kind="dynamic_pricing",
        row=442,
        title=title or "Dynamic pricing",
        summary=f"{len(rules)} bounded rule(s); worst case {worst} verified inside [{bounds.floor}, {bounds.ceiling}].",
        sections=sections,
        evidence=ev,
        scope_checks=["rules that could breach the supplied bounds are rejected outright"],
        gated_effects=["activating dynamic pricing on a live checkout is an approved action"],
        manual_steps=[],
    )


def plan_bundling(
    *,
    products: list[PricedProduct],
    bundle_price: float,
    bundle_name: str,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 443 - Bundling Strategy: the bundle must be cheaper than its parts."""
    _require("products", products)
    if len(products) < 2:
        raise GrowthPlanError("a bundle needs at least two products")
    total = round(sum(p.price for p in products), 2)
    if bundle_price <= 0:
        raise GrowthPlanError("bundle_price must be positive")
    if bundle_price >= total:
        raise GrowthPlanError(
            f"bundle price {bundle_price} is not below the {total} sum of parts; the bundle offers no value"
        )
    discount = round((total - bundle_price) / total * 100, 1)
    facts = [f"{p.name}: {p.price}" for p in products] + [f"bundle price {bundle_price}"]
    ev = evidence + _facts("bp", facts, "caller-supplied product prices")
    sections = [
        ArtifactSection(
            title="Bundle economics (computed)",
            body=f"Parts sum to {total}; '{bundle_name}' at {bundle_price} is a {discount}% saving.",
            evidence_keys=[f"bp{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Cannibalization check",
            body="Track whether the bundle shifts existing full-price buyers versus attracting new ones; review after one billing cycle with real numbers.",
        ),
    ]
    return _artifact(
        kind="bundling_strategy",
        row=443,
        title=title or f"Bundle: {bundle_name}",
        summary=f"'{bundle_name}' at {bundle_price} vs {total} sum of parts ({discount}% saving).",
        sections=sections,
        evidence=ev,
        scope_checks=["a bundle that is not cheaper than its parts is rejected as dishonest"],
        gated_effects=[],
        manual_steps=[],
    )


def plan_upselling(
    *,
    current: PricedProduct,
    upgrades: list[PricedProduct],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 444 - Upselling: upgrade path with computed uplifts from supplied prices."""
    _require("upgrades", upgrades)
    lines = []
    for up in upgrades:
        uplift = round((up.price - current.price) / current.price * 100, 1)
        if uplift <= 0:
            raise GrowthPlanError(f"upgrade '{up.name}' at {up.price} is not above the current {current.price}")
        lines.append(f"{current.name} -> {up.name}: +{uplift}%")
    facts = [f"current: {current.name} at {current.price}"] + [f"{u.name}: {u.price}" for u in upgrades]
    ev = evidence + _facts("up", facts, "caller-supplied product prices")
    sections = [
        ArtifactSection(
            title="Upgrade path (computed)",
            body="; ".join(lines),
            evidence_keys=[f"up{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Timing",
            body="Offer the upgrade only after the customer has reached a success milestone on the current plan; never mid-onboarding or during a support issue.",
        ),
    ]
    return _artifact(
        kind="upselling",
        row=444,
        title=title or f"Upsell path from {current.name}",
        summary=f"{len(upgrades)} upgrade(s) with computed price uplifts.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_cross_selling(
    *,
    anchor: PricedProduct,
    complements: list[PricedProduct],
    pairing_facts: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 445 - Cross-Selling: pairings must cite a supplied relevance fact."""
    _require("complements", complements)
    _require("pairing_facts", pairing_facts)
    ev = evidence + _facts("pf", pairing_facts, "caller-supplied pairing facts")
    lines = [f"{anchor.name} + {c.name} ({c.price})" for c in complements]
    sections = [
        ArtifactSection(
            title="Pairings",
            body="; ".join(lines),
            evidence_keys=[e.key for e in evidence],
        ),
        ArtifactSection(
            title="Why these pairings",
            body="Supplied relevance facts: " + "; ".join(pairing_facts),
            evidence_keys=[f"pf{i + 1}" for i in range(len(pairing_facts))],
        ),
    ]
    return _artifact(
        kind="cross_selling",
        row=445,
        title=title or f"Cross-sell from {anchor.name}",
        summary=f"{len(complements)} complement pairing(s), each justified by a supplied fact.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


# --- rows 446-450: customer success -----------------------------------------------


def _health_score(signals: list[HealthSignal]) -> tuple[float, list[str]]:
    total_weight = sum(s.weight for s in signals)
    score = 0.0
    details: list[str] = []
    for s in signals:
        attainment = min(s.value / s.target, 1.0)
        if not s.higher_is_better:
            attainment = min(s.target / s.value, 1.0) if s.value else 1.0
        score += (s.weight / total_weight) * attainment * 100
        details.append(f"{s.name}: {s.value} vs target {s.target}")
    return round(score, 1), details


def _health_band(score: float) -> str:
    if score >= 70:
        return "healthy"
    if score >= 40:
        return "at-risk"
    return "critical"


def plan_customer_success(
    *,
    accounts: list[AccountHealth],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 446 - Customer Success: computed health scores with per-band playbooks."""
    _require("accounts", accounts)
    lines: list[str] = []
    details_all: list[str] = []
    for account in accounts:
        if not account.signals:
            raise GrowthPlanError(f"account '{account.account}' has no health signals")
        score, details = _health_score(account.signals)
        lines.append(f"{account.account}: {score} ({_health_band(score)})")
        details_all.append(f"{account.account} - " + "; ".join(details))
    ev = evidence + _facts("hs", details_all, "caller-supplied health signals")
    sections = [
        ArtifactSection(
            title="Health scores (computed)",
            body="; ".join(lines),
            evidence_keys=[f"hs{i + 1}" for i in range(len(details_all))],
        ),
        ArtifactSection(
            title="Playbooks by band",
            body=(
                "healthy: quarterly value review, ask for a referral. "
                "at-risk: success call within one week, agree a recovery plan. "
                "critical: same-week executive outreach and a named owner until the score recovers."
            ),
        ),
    ]
    return _artifact(
        kind="customer_success",
        row=446,
        title=title or "Customer success plan",
        summary=f"Computed health for {len(accounts)} account(s) with band playbooks.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=["assign a named owner to every critical account"],
    )


def plan_onboarding(
    *,
    product: str,
    steps: list[str],
    target_time_to_value_minutes: int,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 447 - Onboarding Optimization: first-value path with instrumentation."""
    _require("steps", steps)
    if target_time_to_value_minutes <= 0:
        raise GrowthPlanError("target_time_to_value_minutes must be positive")
    facts = [f"step {i + 1}: {s}" for i, s in enumerate(steps)]
    ev = evidence + _facts("ob", facts, "caller-supplied onboarding steps")
    sections = [
        ArtifactSection(
            title="First-value path",
            body=" -> ".join(steps) + f". Target: first value within {target_time_to_value_minutes} minutes.",
            evidence_keys=[f"ob{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Instrumentation",
            body="Log completion and time per step; the step with the worst completion-to-time ratio is the first optimization target. No step is removed without data.",
        ),
        ArtifactSection(
            title="Stall recovery",
            body="If a user stalls past twice the target time, trigger a human-reviewed help message through the approval-gated campaign runtime.",
        ),
    ]
    return _artifact(
        kind="onboarding_optimization",
        row=447,
        title=title or f"Onboarding: {product}",
        summary=f"{len(steps)}-step first-value path targeting {target_time_to_value_minutes} minutes.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def design_support_system(
    *,
    channels: list[str],
    coverage_hours: str,
    first_response_sla_minutes: int,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 448 - Support System Design."""
    _require("channels", channels)
    _require("coverage_hours", coverage_hours)
    if first_response_sla_minutes <= 0:
        raise GrowthPlanError("first_response_sla_minutes must be positive")
    facts = [f"channel: {c}" for c in channels] + [
        f"coverage: {coverage_hours}",
        f"first response SLA: {first_response_sla_minutes} minutes",
    ]
    ev = evidence + _facts("ss", facts, "caller-supplied support parameters")
    sections = [
        ArtifactSection(
            title="Channel matrix",
            body="Channels: " + ", ".join(channels) + f". Coverage: {coverage_hours}. First response within {first_response_sla_minutes} minutes.",
            evidence_keys=[f"ss{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Escalation path",
            body="Tier 1: known answers from the knowledge base. Tier 2: product specialist. Tier 3: engineering with a repro. Every escalation carries the full conversation context.",
        ),
    ]
    return _artifact(
        kind="support_system",
        row=448,
        title=title or "Support system",
        summary=f"{len(channels)} channel(s), {coverage_hours} coverage, {first_response_sla_minutes}-minute first-response SLA.",
        sections=sections,
        evidence=ev,
        scope_checks=["no unsupervised auto-replies to customers; automated drafts are human-reviewed"],
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_knowledge_base(
    *,
    product: str,
    articles: list[IssueSolution],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 449 - Knowledge Base Creation: articles strictly from supplied solutions."""
    _require("articles", articles)
    for a in articles:
        _require(f"solution for '{a.issue}'", a.solution)
    ev = evidence + _facts(
        "kb", [f"{a.issue} -> {a.solution}" for a in articles], "caller-supplied issue/solution pairs"
    )
    sections = [
        ArtifactSection(
            title=f"Article: {a.issue}",
            body=(
                f"Title: How to resolve: {a.issue}. Symptom: {a.issue}. "
                f"Resolution: {a.solution}."
                + (f" Search keywords: {', '.join(a.keywords)}." if a.keywords else "")
            ),
            evidence_keys=[f"kb{i + 1}"],
        )
        for i, a in enumerate(articles)
    ]
    sections.append(
        ArtifactSection(
            title="Coverage policy",
            body="Every article traces to a supplied, verified solution. Unanswered questions found in support logs are queued as gaps for a human to answer - never auto-filled.",
        )
    )
    return _artifact(
        kind="knowledge_base",
        row=449,
        title=title or f"Knowledge base: {product}",
        summary=f"{len(articles)} article outline(s) built strictly from supplied solutions.",
        sections=sections,
        evidence=ev,
        scope_checks=["no invented solutions: an issue without a supplied resolution is rejected"],
        gated_effects=[GATED_PUBLISH],
        manual_steps=[],
    )


def plan_community_support(
    *,
    community_name: str,
    guidelines: list[str],
    moderators: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 450 - Community Support: peer help with a path to official support."""
    _require("guidelines", guidelines)
    _require("moderators", moderators)
    ev = evidence + _facts("cg", guidelines, "caller-supplied community guidelines")
    sections = [
        ArtifactSection(
            title="Peer-help program",
            body=f"{community_name}: members answer members under {len(guidelines)} supplied guideline(s). Moderators: {', '.join(moderators)}.",
            evidence_keys=[f"cg{i + 1}" for i in range(len(guidelines))],
        ),
        ArtifactSection(
            title="Escalation to official support",
            body="A peer answer unresolved after 24 hours, or any safety/legal/account issue, moves to the official support system (row 448) with full context.",
        ),
        ArtifactSection(
            title="Recognition",
            body="Highlight helpful members monthly; recognition is reputational (badges, thanks), never undisclosed compensation.",
        ),
    ]
    return _artifact(
        kind="community_support",
        row=450,
        title=title or f"Community support: {community_name}",
        summary=f"Peer-help program for '{community_name}' with {len(moderators)} moderator(s) and a formal escalation path.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_PUBLISH],
        manual_steps=[],
    )
