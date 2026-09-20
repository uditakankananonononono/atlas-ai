"""Marketing analyses and plans for rows 400-426 of the feature ledger.

Every row produces a typed MarketingArtifact. Three honesty rules are
enforced in code, not by prompt:

1. Nothing publishes. Artifacts are drafts for human review. The engine
   holds no scheduler, adapter, or approval-store reference, so it is
   structurally incapable of causing an external effect. Copy drafts run
   through the module compliance gate before they are stored.
2. No fabricated numbers. Sample size is computed with a closed-form
   two-proportion formula from caller inputs. LLM-suggested keyword
   volumes are stripped unless the caller supplied the metric.
3. No fabricated contacts. Link-building, media-relations, and influencer
   outputs can only name prospects the caller provided; with none, the
   targets section is empty and says why.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import NormalDist
from typing import Any, Awaitable, Callable, Protocol

from app.core.providers import ProviderError

from .compliance import ComplianceIssue, is_blocking, validate_draft
from .models import Platform

GenerateFn = Callable[..., Awaitable[tuple[str, str]]]

HONESTY_PREAMBLE = (
    "Use ONLY the facts provided in the input. Where a fact is missing, write "
    '"TO BE PROVIDED" for that field - never invent metrics, prices, names, '
    "contacts, URLs, statistics, or quotes. This output is a draft for human "
    "review, not for publication."
)


class ArtifactParseError(ValueError):
    """The LLM reply did not contain a usable JSON object."""


@dataclass
class MarketingArtifact:
    """One typed analysis or plan, always a draft for human review."""

    id: str
    row: int
    kind: str
    title: str
    sections: dict[str, Any]
    inputs: dict[str, Any]
    status: str = "draft"  # draft -> approved by a human outside this engine
    provenance: str = "llm-draft"  # "llm-draft" | "computed"
    model: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ArtifactRepository(Protocol):
    def save_artifact(self, artifact: MarketingArtifact) -> MarketingArtifact: ...
    def get_artifact(self, artifact_id: str) -> MarketingArtifact | None: ...
    def list_artifacts(self, kind: str | None = None) -> list[MarketingArtifact]: ...


@dataclass(frozen=True)
class ArtifactSpec:
    """Registry entry for one LLM-backed feature row."""

    row: int
    slug: str
    title: str
    section_keys: tuple[str, ...]
    instructions: str


# Rows 401-426, excluding the deterministic sample-size row (400) and the
# two rows with bespoke request shapes handled below (407 copywriting and
# 409 editorial calendar are still registry-driven; they get extra inputs).
ARTIFACT_SPECS: dict[str, ArtifactSpec] = {spec.slug: spec for spec in [
    ArtifactSpec(401, "segmentation", "Segmentation Analysis",
                 ("segments", "sizing_notes", "data_gaps"),
                 "Divide the described market into 3-6 named segments using the provided audience and "
                 "metrics facts. Each segment needs: name, defining traits, needs, and which PROVIDED "
                 "facts support it. List what data would sharpen the split under data_gaps."),
    ArtifactSpec(402, "targeting", "Targeting Strategy",
                 ("selected_segments", "rationale", "rejected_segments"),
                 "Select the segments to pursue from the provided segmentation input, with rationale "
                 "per selection and per rejection. Reference only segments and facts in the input."),
    ArtifactSpec(403, "positioning", "Positioning Strategy",
                 ("statement", "category", "differentiators", "reasons_to_believe"),
                 "Write a positioning statement (For [audience], [brand] is the [category] that "
                 "[benefit] because [reason]). Ground every differentiator in a provided fact."),
    ArtifactSpec(404, "brand-architecture", "Brand Architecture",
                 ("structure", "entities", "relationships", "migration_notes"),
                 "Organize the provided brand/product list into a branded-house, house-of-brands, or "
                 "hybrid structure with the relationship between each pair of entities."),
    ArtifactSpec(405, "brand-voice", "Brand Voice Development",
                 ("voice_attributes", "tone_by_context", "do_examples", "dont_examples"),
                 "Define 3-5 voice attributes, how tone flexes across contexts (launch, support, "
                 "crisis, social), and one do/don't example pair per attribute."),
    ArtifactSpec(406, "messaging-framework", "Messaging Framework",
                 ("core_message", "pillars", "proof_points", "audience_variants"),
                 "Structure one core message, 3-4 supporting pillars, proof points (only from "
                 "provided facts), and a variant per provided audience segment."),
    ArtifactSpec(407, "copywriting", "Copywriting",
                 ("copy", "headline_options", "call_to_action"),
                 "Write the post copy and 3 headline options for the brief. Respect the platform "
                 "limits in the input and keep any required disclosure hashtags."),
    ArtifactSpec(408, "content-strategy", "Content Strategy",
                 ("pillars", "formats", "cadence", "measurement"),
                 "Define 3-5 content pillars, the format mix per pillar, a weekly cadence, and how "
                 "success will be measured using only metrics the provided analytics can supply."),
    ArtifactSpec(409, "editorial-calendar", "Editorial Calendar",
                 ("entries", "themes"),
                 "Produce dated calendar entries within the requested window. Each entry: date, "
                 "title, theme, platform, format, one-line summary. Entries are DRAFTS; none are "
                 "scheduled or published."),
    ArtifactSpec(410, "seo-optimization", "SEO Optimization",
                 ("on_page", "content_gaps", "priorities"),
                 "Given the provided page content/facts, produce on-page recommendations (title, "
                 "meta, headings, internal links) and a priority order. Analyze only what was "
                 "provided; do not claim to have crawled anything."),
    ArtifactSpec(411, "keyword-research", "Keyword Research",
                 ("keywords", "intent_map", "quick_wins"),
                 "Expand the provided seed keywords into 15-30 terms with search intent "
                 "(informational/commercial/transactional/navigational) per term. Do NOT attach "
                 "search volumes or difficulty scores unless they were provided in the input."),
    ArtifactSpec(412, "link-building", "Link Building",
                 ("targets", "angles", "outreach_drafts"),
                 "For each PROVIDED prospect, propose a value-first pitch angle and a short outreach "
                 "draft. Never invent prospect names, sites, or email addresses; with no prospects "
                 "provided, return empty targets."),
    ArtifactSpec(413, "technical-seo", "Technical SEO",
                 ("findings", "fixes", "checklist"),
                 "From the provided site facts (URLs, statuses, speeds), list findings, the fix per "
                 "finding, and a verification checklist. Flag anything not provided as unverified."),
    ArtifactSpec(414, "local-seo", "Local SEO",
                 ("profile_recommendations", "citations", "review_plan"),
                 "From the provided business name/location/categories, recommend profile "
                 "optimizations, citation categories (not invented listings), and a review-request "
                 "plan. Only use provided locations."),
    ArtifactSpec(415, "content-marketing", "Content Marketing",
                 ("funnel_map", "pieces", "distribution", "measurement"),
                 "Map content to funnel stages, define 5-8 pieces with working titles, a "
                 "distribution plan per piece, and measurement using available analytics."),
    ArtifactSpec(416, "thought-leadership", "Thought Leadership",
                 ("themes", "outlines", "channels"),
                 "From the provided expertise areas, propose 3-5 themes and an outline per theme "
                 "(hook, argument, evidence slot marked TO BE PROVIDED where evidence is missing), "
                 "plus channels."),
    ArtifactSpec(417, "public-relations", "Public Relations",
                 ("narrative", "announcement_plan", "press_release_draft", "risk_notes"),
                 "Build the narrative, an announcement plan, and a DRAFT press release (clearly "
                 "marked draft, review-first). Note reputational risks."),
    ArtifactSpec(418, "media-relations", "Media Relations",
                 ("targets", "pitches", "follow_up_plan"),
                 "For each PROVIDED outlet/journalist, draft a tailored pitch and a follow-up plan. "
                 "Never invent journalists, outlets, or contact details."),
    ArtifactSpec(419, "crisis-communication", "Crisis Communication",
                 ("scenarios", "holding_statements", "escalation_map", "response_templates"),
                 "From the provided risk areas, define scenarios, a holding-statement DRAFT per "
                 "scenario, an internal escalation map (roles, not invented names), and response "
                 "templates. All drafts are review-first."),
    ArtifactSpec(420, "social-media-strategy", "Social Media Strategy",
                 ("platform_roles", "content_mix", "cadence", "kpis"),
                 "Define the role per provided platform, the content mix, posting cadence, and KPIs "
                 "measurable with the platform's official analytics."),
    ArtifactSpec(421, "community-management", "Community Management",
                 ("engagement_playbook", "moderation_guidelines", "response_templates", "escalation"),
                 "Write an engagement playbook, moderation guidelines, response templates for common "
                 "cases, and when to escalate to a human."),
    ArtifactSpec(422, "influencer-marketing", "Influencer Marketing",
                 ("candidates", "briefs", "outreach_drafts", "disclosure_rules"),
                 "For each PROVIDED creator candidate, draft a campaign brief and outreach draft. "
                 "Include FTC/platform disclosure requirements. Never invent creator names, handles, "
                 "rates, or audience sizes."),
    ArtifactSpec(423, "affiliate-marketing", "Affiliate Marketing",
                 ("program_terms", "commission_options", "recruitment_draft", "compliance_notes"),
                 "Define program terms with 2-3 commission structure OPTIONS (clearly labeled as "
                 "options for a human to choose), a partner recruitment draft, and disclosure "
                 "compliance notes."),
    ArtifactSpec(424, "referral-program", "Referral Programs",
                 ("mechanics", "incentive_options", "share_copy", "fraud_guards"),
                 "Design referral mechanics, 2-3 incentive OPTIONS for human choice, share-copy "
                 "drafts, and fraud/self-referral guards."),
    ArtifactSpec(425, "email-marketing", "Email Marketing",
                 ("sequence", "subject_lines", "send_notes"),
                 "Draft the requested email sequence: per email a subject line, preview text, and "
                 "body draft. All emails are DRAFTS for review; nothing is sent."),
    ArtifactSpec(426, "marketing-automation", "Marketing Automation",
                 ("workflows", "triggers", "personalization", "guardrails"),
                 "Define automation workflows as DATA: trigger, conditions, step list per workflow. "
                 "This module stores definitions only and has no execution engine; every workflow "
                 "ships as a draft for human activation elsewhere."),
]}


def sample_size_for_ab_test(
    baseline_rate: float,
    minimum_detectable_effect: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
) -> dict[str, Any]:
    """Per-variant sample size for a two-proportion A/B test (engagement rate).

    Closed-form frequentist calculation: n = (z_1-a/2 + z_power)^2 *
    (p1(1-p1) + p2(1-p2)) / (p2 - p1)^2 with p2 = p1 + MDE. Deterministic;
    the inputs and formula travel with the result so nothing is a black box.
    """
    for name, value, low, high in (
        ("baseline_rate", baseline_rate, 0.0, 1.0),
        ("minimum_detectable_effect", minimum_detectable_effect, 0.0, 1.0),
        ("alpha", alpha, 0.0, 0.5),
        ("power", power, 0.5, 0.9999),
    ):
        if not (low < value < high):
            raise ValueError(f"{name} must be in ({low}, {high}), got {value}")
    p1 = baseline_rate
    p2 = baseline_rate + minimum_detectable_effect
    if p2 >= 1.0:
        raise ValueError(f"baseline_rate + minimum_detectable_effect must stay below 1.0, got {p2}")
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    variance = p1 * (1 - p1) + p2 * (1 - p2)
    per_variant = math.ceil(((z_alpha + z_power) ** 2) * variance / (minimum_detectable_effect ** 2))
    return {
        "per_variant": per_variant,
        "total": per_variant * 2,
        "inputs": {
            "baseline_rate": baseline_rate,
            "minimum_detectable_effect": minimum_detectable_effect,
            "alpha": alpha,
            "power": power,
        },
        "formula": "n = (z_{1-alpha/2} + z_power)^2 * (p1(1-p1) + p2(1-p2)) / (p2-p1)^2, p2 = p1 + MDE",
    }


def _parse_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM reply; tolerant of fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ArtifactParseError("LLM reply contained no JSON object")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise ArtifactParseError(f"LLM reply was not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise ArtifactParseError("LLM reply JSON was not an object")
    return parsed


def _strip_unprovided_keyword_metrics(sections: dict[str, Any], provided_metrics: dict[str, Any]) -> None:
    """Keyword volumes/difficulty exist only if the caller supplied them."""
    keywords = sections.get("keywords")
    if not isinstance(keywords, list):
        return
    for item in keywords:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", ""))
        provided = provided_metrics.get(term) or provided_metrics.get(term.lower())
        for key in ("volume", "difficulty", "cpc"):
            if provided and key in provided:
                item[key] = provided[key]
            elif key in item:
                item[key] = None


def _constrain_targets_to_provided(sections: dict[str, Any], contacts: list[str], key: str = "targets") -> None:
    """Outreach targets may only reference caller-provided prospects."""
    provided = {c.strip() for c in contacts if str(c).strip()}
    targets = sections.get(key)
    if not provided:
        sections[key] = []
        sections["targets_note"] = (
            "No prospects were provided. Supply a prospect list; this module never invents "
            "contacts, outlets, or creators."
        )
        return
    if not isinstance(targets, list):
        sections[key] = []
        return
    kept = []
    for item in targets:
        name = str(item.get("name", "")) if isinstance(item, dict) else str(item)
        if any(token in name for token in provided) or any(token in str(item) for token in provided):
            kept.append(item)
    sections[key] = kept


class MarketingEngine:
    """Produces typed draft analyses/plans; cannot publish or schedule anything."""

    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        generate: GenerateFn,
        provider: str = "openai",
        model: str | None = None,
    ) -> None:
        self._repository = repository
        self._generate = generate
        self._provider = provider
        self._model = model

    def list_artifacts(self, kind: str | None = None) -> list[MarketingArtifact]:
        return self._repository.list_artifacts(kind)

    def sample_size(
        self,
        baseline_rate: float,
        minimum_detectable_effect: float,
        *,
        alpha: float = 0.05,
        power: float = 0.8,
    ) -> MarketingArtifact:
        """Row 400: deterministic power calculation; no LLM, no fabrication."""
        result = sample_size_for_ab_test(
            baseline_rate, minimum_detectable_effect, alpha=alpha, power=power
        )
        artifact = MarketingArtifact(
            id=f"mkt-{uuid.uuid4().hex[:12]}",
            row=400,
            kind="sample-size",
            title="Sample Size Calculation",
            sections=result,
            inputs=result["inputs"],
            provenance="computed",
            model=None,
        )
        return self._repository.save_artifact(artifact)

    async def generate(
        self,
        slug: str,
        *,
        business: str,
        product: str | None = None,
        audience: str | None = None,
        goals: list[str] | None = None,
        facts: dict[str, Any] | None = None,
        contacts: list[str] | None = None,
        provided_metrics: dict[str, Any] | None = None,
        extra_instructions: str = "",
    ) -> MarketingArtifact:
        """Rows 401-426 (except 400): one typed LLM-backed draft artifact."""
        spec = ARTIFACT_SPECS[slug]
        facts = facts or {}
        contacts = contacts or []
        provided_metrics = provided_metrics or {}
        goals = goals or []
        inputs = {
            "business": business,
            "product": product,
            "audience": audience,
            "goals": goals,
            "facts": facts,
            "contacts": contacts,
            "provided_metrics": provided_metrics,
        }
        keys = ", ".join(f'"{key}"' for key in spec.section_keys)
        prompt = (
            f"{HONESTY_PREAMBLE}\n\nYou are producing a {spec.title} (draft). "
            f"{spec.instructions}\n{extra_instructions}\n"
            f"Reply with ONLY a JSON object with keys: {keys}.\n\n"
            f"Input (JSON):\n{json.dumps(inputs, default=str)}"
        )
        model, text = await self._generate(prompt, self._provider, self._model)
        sections = _parse_json_object(text)
        if slug == "keyword-research":
            _strip_unprovided_keyword_metrics(sections, provided_metrics)
        if slug in ("link-building", "media-relations", "influencer-marketing"):
            target_key = {"link-building": "targets", "media-relations": "targets",
                          "influencer-marketing": "candidates"}[slug]
            _constrain_targets_to_provided(sections, contacts, key=target_key)
        artifact = MarketingArtifact(
            id=f"mkt-{uuid.uuid4().hex[:12]}",
            row=spec.row,
            kind=slug,
            title=spec.title,
            sections=sections,
            inputs=inputs,
            model=model,
        )
        return self._repository.save_artifact(artifact)

    async def draft_copy(
        self,
        *,
        brief: str,
        platform: Platform,
        format: str | None = None,
        voice: str | None = None,
        sponsored: bool = False,
        media_count: int = 0,
        alt_texts: int = 0,
    ) -> tuple[MarketingArtifact, list[ComplianceIssue]]:
        """Row 407: persuasive copy through the same compliance gate as plan drafts.

        Blocking findings (over-limit captions, missing sponsored disclosure)
        raise before anything is stored - a non-compliant copy artifact never
        exists in the repository.
        """
        from .compliance import PLATFORM_LIMITS
        from .models import DEFAULT_FORMATS

        fmt = format or DEFAULT_FORMATS[platform]
        limit = PLATFORM_LIMITS[platform.value]["caption_chars"]
        spec = ARTIFACT_SPECS["copywriting"]
        prompt = (
            f"{HONESTY_PREAMBLE}\n\nYou are producing persuasive {platform.value} copy (draft). "
            f"{spec.instructions}\n"
            f"Hard rules: at most {limit} characters for the copy, format {fmt}."
            + (f" Brand voice: {voice}." if voice else "")
            + (" This is sponsored content: the copy MUST include a clear #ad disclosure."
               if sponsored else "")
            + '\nReply with ONLY a JSON object with keys: "copy", "headline_options", "call_to_action".'
            + f"\n\nBrief: {brief}"
        )
        model, text = await self._generate(prompt, self._provider, self._model)
        sections = _parse_json_object(text)
        copy = str(sections.get("copy", ""))
        issues = validate_draft(
            platform.value, fmt, copy,
            sponsored=sponsored, media_count=media_count, alt_texts=alt_texts,
        )
        if is_blocking(issues):
            from .service import DraftComplianceError

            raise DraftComplianceError(issues)
        artifact = MarketingArtifact(
            id=f"mkt-{uuid.uuid4().hex[:12]}",
            row=spec.row,
            kind="copywriting",
            title=spec.title,
            sections=sections,
            inputs={"brief": brief, "platform": platform.value, "format": fmt,
                    "voice": voice, "sponsored": sponsored},
            model=model,
        )
        return self._repository.save_artifact(artifact), issues

    async def editorial_calendar(
        self,
        *,
        business: str,
        themes: list[str],
        start_date: str,
        weeks: int,
        posts_per_week: int,
    ) -> MarketingArtifact:
        """Row 409: a dated draft calendar. Entries are never scheduled here.

        Scheduling remains exclusively on the approval-gated /schedule
        endpoint; this engine holds no scheduler reference by design.
        """
        from datetime import date as _date

        start = _date.fromisoformat(start_date)  # raises on malformed input
        window_days = weeks * 7
        spec = ARTIFACT_SPECS["editorial-calendar"]
        extra = (
            f"Produce exactly {weeks * posts_per_week} entries spread evenly from {start} "
            f"over {window_days} days, about {posts_per_week} per week. Themes: {', '.join(themes)}."
        )
        model, text = await self._generate(
            f"{HONESTY_PREAMBLE}\n\nYou are producing an Editorial Calendar (draft). "
            f"{spec.instructions}\n{extra}\n"
            'Reply with ONLY a JSON object with keys: "entries" (list of objects with "date", '
            '"title", "theme", "platform", "format", "summary") and "themes".\n\n'
            f"Business: {business}",
            self._provider, self._model,
        )
        sections = _parse_json_object(text)
        entries = sections.get("entries")
        if not isinstance(entries, list):
            raise ArtifactParseError("editorial calendar reply had no entries list")
        clean = []
        for item in entries[: weeks * posts_per_week]:
            if not isinstance(item, dict):
                continue
            try:
                day = _date.fromisoformat(str(item.get("date", "")))
            except ValueError:
                continue
            clean.append({**item, "date": day.isoformat(), "status": "draft"})
        sections["entries"] = clean
        sections["scheduling_note"] = (
            "All entries are drafts. Scheduling happens only through the approval-gated "
            "/social-media-manager/plans/{id}/schedule endpoint."
        )
        artifact = MarketingArtifact(
            id=f"mkt-{uuid.uuid4().hex[:12]}",
            row=spec.row,
            kind="editorial-calendar",
            title=spec.title,
            sections=sections,
            inputs={"business": business, "themes": themes, "start_date": start.isoformat(),
                    "weeks": weeks, "posts_per_week": posts_per_week},
            model=model,
        )
        return self._repository.save_artifact(artifact)
