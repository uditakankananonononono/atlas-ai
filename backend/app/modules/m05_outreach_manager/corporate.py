"""Evidence-bound corporate review artifacts (feature rows 476-509).

Stakeholders, communication, training, org design, culture, mission/vision,
strategy frameworks (SWOT/PESTLE/scenarios), OKRs/KPIs/scorecards, performance,
compensation/equity/cap table, fundraising/pitch/financial model/valuation,
due diligence, term sheets, investor/board, exit/M&A/IPO.

Same invariants as growth.py: artifacts are reviewable plans only; every claim
cites caller-supplied evidence; computed rows do transparent arithmetic on
supplied numbers. Finance- and legal-adjacent rows carry explicit
not-advice scope checks, and no builder contacts investors or sends anything.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .growth import (
    ArtifactSection,
    BusinessArtifact,
    EvidenceItem,
    GATED_PUBLISH,
    GATED_SEND,
    GrowthPlanError,
    _artifact,
    _facts,
    _require,
)

NOT_FINANCIAL_ADVICE = "planning aid only - not financial, legal, tax, or investment advice"
NO_FUNDRAISING_OUTREACH = "no investor contact, solicitation, or send is performed by this module"


# --- typed inputs ---------------------------------------------------------------


class Stakeholder(BaseModel):
    name: str
    interest: str
    influence: Literal["low", "medium", "high"]
    stance: Literal["support", "neutral", "oppose"] = "neutral"


class AudienceComm(BaseModel):
    audience: str
    message_facts: list[str]
    channel: str
    frequency: str


class SkillGap(BaseModel):
    skill: str
    audience: str
    current_level: int = Field(ge=1, le=5)
    target_level: int = Field(ge=1, le=5)


class TeamSpec(BaseModel):
    name: str
    mission: str
    size: int = Field(ge=1)


class ManagerSpan(BaseModel):
    manager: str
    reports: int = Field(ge=0)


class TopologyTeam(BaseModel):
    name: str
    type: Literal["stream-aligned", "platform", "enabling", "complicated-subsystem"]
    interacts_with: list[str] = Field(default_factory=list)


class ValueSpec(BaseModel):
    name: str
    description: str
    behaviors: list[str] = Field(default_factory=list)


class PESTLEFactor(BaseModel):
    category: Literal["political", "economic", "social", "technological", "environmental", "legal"]
    fact: str
    impact: Literal["positive", "negative", "unclear"] = "unclear"


class StrategicDriver(BaseModel):
    name: str
    states: list[str] = Field(min_length=2)


class StrategicGoal(BaseModel):
    objective: str
    horizon: Literal["quarter", "year", "three_year"]
    owner: str
    measures: list[str] = Field(min_length=1)


class KeyResult(BaseModel):
    description: str
    baseline: float
    target: float
    current: float | None = None
    unit: str = ""


class Objective(BaseModel):
    objective: str
    key_results: list[KeyResult] = Field(min_length=1)


class KPICandidate(BaseModel):
    name: str
    formula: str
    data_source: str
    frequency: Literal["daily", "weekly", "monthly", "quarterly"]
    kind: Literal["leading", "lagging"]


class CompComponent(BaseModel):
    name: str
    type: Literal["base", "bonus", "equity", "benefit"]
    annual_value: float = Field(ge=0)


class EquityGrant(BaseModel):
    holder: str
    shares: int = Field(ge=0)
    share_class: str = "common"


class DeckFacts(BaseModel):
    problem: str | None = None
    solution: str | None = None
    traction: str | None = None
    market: str | None = None
    team: str | None = None
    ask: str | None = None


class DiligenceArea(BaseModel):
    category: str
    documents: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)


class TermPosition(BaseModel):
    term: str
    our_position: str
    their_position: str
    priority: Literal["must", "want", "give"] = "want"


class ExitOption(BaseModel):
    type: Literal["acquisition", "ipo", "secondary", "wind_down"]
    readiness_facts: list[str] = Field(default_factory=list)


class ReadinessArea(BaseModel):
    area: str
    status: Literal["ready", "gap"]


# --- rows 476-486: stakeholders, communication, training, org, culture, mission/vision ---


def analyze_stakeholders(
    *,
    initiative: str,
    stakeholders: list[Stakeholder],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 476 - Stakeholder Analysis: computed power/interest mapping."""
    _require("stakeholders", stakeholders)
    lines = []
    for s in stakeholders:
        quadrant = (
            "manage closely" if s.influence == "high" and s.stance != "support"
            else "keep satisfied" if s.influence == "high"
            else "keep informed" if s.stance == "support"
            else "monitor"
        )
        lines.append(f"{s.name} ({s.influence} influence, {s.stance}): {s.interest} -> {quadrant}")
    ev = evidence + _facts("sh", lines, "caller-supplied stakeholder map")
    sections = [
        ArtifactSection(
            title="Stakeholder map (computed)",
            body="; ".join(lines),
            evidence_keys=[f"sh{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Engagement order",
            body="Brief high-influence non-supporters first with facts only; never route around a declared opponent.",
        ),
    ]
    return _artifact(
        kind="stakeholder_analysis",
        row=476,
        title=title or f"Stakeholder analysis: {initiative}",
        summary=f"{len(stakeholders)} stakeholder(s) mapped into engagement quadrants.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_communication(
    *,
    initiative: str,
    audiences: list[AudienceComm],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 477 - Communication Planning: messages strictly from supplied facts."""
    _require("audiences", audiences)
    for a in audiences:
        _require(f"message_facts for '{a.audience}'", a.message_facts)
    lines = [
        f"{a.audience} via {a.channel} ({a.frequency}): " + "; ".join(a.message_facts)
        for a in audiences
    ]
    ev = evidence + _facts("cm", lines, "caller-supplied communication matrix")
    sections = [
        ArtifactSection(
            title="Communication matrix",
            body=" | ".join(lines),
            evidence_keys=[f"cm{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Feedback loop",
            body="Each audience gets a named feedback channel; unanswered questions become new evidence, not new invented messaging.",
        ),
    ]
    return _artifact(
        kind="communication_planning",
        row=477,
        title=title or f"Communication plan: {initiative}",
        summary=f"Messaging matrix for {len(audiences)} audience(s), all content from supplied facts.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_SEND, GATED_PUBLISH],
        manual_steps=[],
    )


def design_training(
    *,
    program: str,
    gaps: list[SkillGap],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 478 - Training Design: objectives sized to the measured gap."""
    _require("gaps", gaps)
    for g in gaps:
        if g.target_level <= g.current_level:
            raise GrowthPlanError(
                f"'{g.skill}': target level {g.target_level} must exceed current {g.current_level}"
            )
    lines = [
        f"{g.skill} for {g.audience}: level {g.current_level} -> {g.target_level} "
        f"({'coaching' if g.target_level - g.current_level == 1 else 'structured course + practice'})"
        for g in gaps
    ]
    ev = evidence + _facts("tg", lines, "caller-supplied capability assessment")
    sections = [
        ArtifactSection(
            title="Learning objectives (gap-sized)",
            body="; ".join(lines),
            evidence_keys=[f"tg{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Assessment",
            body="Re-measure each skill 30 days after training with the same rubric; the delta is the training's only success metric.",
        ),
    ]
    return _artifact(
        kind="training_design",
        row=478,
        title=title or f"Training program: {program}",
        summary=f"{len(gaps)} capability gap(s) with level-sized interventions.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=["confirm the level assessment with each team lead before scheduling"],
    )


def design_organization(
    *,
    teams: list[TeamSpec],
    design_drivers: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 479 - Organizational Design from supplied teams and drivers."""
    _require("teams", teams)
    _require("design_drivers", design_drivers)
    total = sum(t.size for t in teams)
    lines = [f"{t.name} ({t.size} people, {round(t.size / total * 100, 1)}% of org): {t.mission}" for t in teams]
    ev = evidence + _facts("od", lines, "caller-supplied team roster")
    sections = [
        ArtifactSection(
            title="Team structure",
            body="; ".join(lines),
            evidence_keys=[f"od{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Design drivers",
            body="Supplied drivers: " + "; ".join(design_drivers),
            evidence_keys=[e.key for e in evidence],
        ),
        ArtifactSection(
            title="Change policy",
            body="Structure changes are announced with rationale, a transition date, and a named owner for each affected team.",
        ),
    ]
    return _artifact(
        kind="organizational_design",
        row=479,
        title=title or "Organizational design",
        summary=f"{len(teams)} team(s), {total} people, mapped to supplied drivers.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def analyze_span_of_control(
    *,
    managers: list[ManagerSpan],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 480 - Span of Control: computed ratios with context flags."""
    _require("managers", managers)
    lines = []
    warnings = []
    for m in managers:
        lines.append(f"{m.manager}: {m.reports} direct report(s)")
        if m.reports > 10:
            warnings.append(f"{m.manager} has {m.reports} reports - above the common 10-report ceiling; check support load")
        if 0 < m.reports < 2:
            warnings.append(f"{m.manager} has {m.reports} report - possibly a redundant management layer")
    avg = round(sum(m.reports for m in managers) / len(managers), 1)
    ev = evidence + _facts("sc", lines, "caller-supplied org roster")
    sections = [
        ArtifactSection(
            title="Spans (computed)",
            body=f"Average span {avg}. " + "; ".join(lines) + (". Flags: " + " ".join(warnings) if warnings else ". No outliers flagged."),
            evidence_keys=[f"sc{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Caveat",
            body="The right span depends on work type and seniority; flags are prompts for review, not verdicts.",
        ),
    ]
    return _artifact(
        kind="span_of_control",
        row=480,
        title=title or "Span of control analysis",
        summary=f"Average span {avg} across {len(managers)} manager(s), {len(warnings)} flag(s).",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def design_matrix_organization(
    *,
    functions: list[str],
    products: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 481 - Matrix Organization: axes plus conflict-resolution rules."""
    _require("functions", functions)
    _require("products", products)
    cells = [f"{p} x {f}" for p in products for f in functions]
    ev = evidence + _facts("mx", cells, "caller-supplied matrix axes")
    sections = [
        ArtifactSection(
            title="Matrix map",
            body=f"{len(products)} product axis x {len(functions)} function axis = {len(cells)} cells: " + "; ".join(cells),
            evidence_keys=[f"mx{i + 1}" for i in range(len(cells))],
        ),
        ArtifactSection(
            title="Dual-reporting rules",
            body="Function leads own craft standards and career growth; product leads own priorities and delivery. Conflicts escalate once to the shared manager, then to the executive sponsor - never resolved by silence.",
        ),
    ]
    return _artifact(
        kind="matrix_organization",
        row=481,
        title=title or "Matrix organization",
        summary=f"{len(products)}x{len(functions)} matrix with explicit dual-reporting rules.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=["name the escalation sponsor before launching the matrix"],
    )


def design_team_topology(
    *,
    teams: list[TopologyTeam],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 482 - Team Topology Design: validated types and interactions."""
    _require("teams", teams)
    names = {t.name for t in teams}
    if len(names) != len(teams):
        raise GrowthPlanError("team names must be unique")
    for t in teams:
        unknown = [x for x in t.interacts_with if x not in names]
        if unknown:
            raise GrowthPlanError(f"team '{t.name}' interacts with unknown team(s): {unknown}")
    if not any(t.type == "stream-aligned" for t in teams):
        raise GrowthPlanError("a topology needs at least one stream-aligned team")
    lines = [f"{t.name} [{t.type}]" + (f" <-> {', '.join(t.interacts_with)}" if t.interacts_with else "") for t in teams]
    ev = evidence + _facts("tt", lines, "caller-supplied team topology")
    sections = [
        ArtifactSection(
            title="Topology map",
            body="; ".join(lines),
            evidence_keys=[f"tt{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Flow rules",
            body="Stream-aligned teams own end-to-end delivery; platform teams serve them as internal customers; enabling teams have a stated exit date for their engagement.",
        ),
    ]
    return _artifact(
        kind="team_topology",
        row=482,
        title=title or "Team topology",
        summary=f"{len(teams)} team(s) with validated types and interactions.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def design_culture(
    *,
    values: list[ValueSpec],
    rituals: list[str] | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 483 - Culture Design: values tied to observable behaviors."""
    _require("values", values)
    for v in values:
        _require(f"behaviors for value '{v.name}'", v.behaviors)
    lines = [f"{v.name}: {v.description} - observable as: " + "; ".join(v.behaviors) for v in values]
    ev = evidence + _facts("cv", lines, "caller-supplied values and behaviors")
    sections = [
        ArtifactSection(
            title="Values with behaviors",
            body=" | ".join(lines),
            evidence_keys=[f"cv{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Reinforcement",
            body=("Rituals: " + "; ".join(rituals) + ". " if rituals else "")
            + "Hiring, feedback, and promotion cite the observable behaviors, not the value labels.",
        ),
    ]
    return _artifact(
        kind="culture_design",
        row=483,
        title=title or "Culture design",
        summary=f"{len(values)} value(s), each bound to observable behaviors.",
        sections=sections,
        evidence=ev,
        scope_checks=["a value without observable behaviors is rejected"],
        gated_effects=[],
        manual_steps=[],
    )


def define_values(
    *,
    values: list[ValueSpec],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 484 - Values Definition: principles with decision tests."""
    _require("values", values)
    for v in values:
        _require(f"behaviors for value '{v.name}'", v.behaviors)
    lines = [f"{v.name}: {v.description}" for v in values]
    ev = evidence + _facts("vd", lines, "caller-supplied value drafts")
    sections = [
        ArtifactSection(
            title="Principles",
            body=" | ".join(lines),
            evidence_keys=[f"vd{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Decision tests",
            body=" ".join(
                f"When torn, ask: does this choice show {v.behaviors[0]} ({v.name})?" for v in values
            ),
            evidence_keys=[f"vd{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="values_definition",
        row=484,
        title=title or "Values definition",
        summary=f"{len(values)} principle(s) with concrete decision tests.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_PUBLISH],
        manual_steps=[],
    )


def create_mission_statement(
    *,
    purpose_facts: list[str],
    audience: str,
    differentiator: str,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 485 - Mission Statement: composed only from supplied facts."""
    _require("purpose_facts", purpose_facts)
    _require("differentiator", differentiator)
    statement = f"We exist to {purpose_facts[0].rstrip('.')} for {audience}, by {differentiator.rstrip('.')}."
    words = len(statement.split())
    ev = evidence + _facts("ms", purpose_facts + [f"audience: {audience}", f"differentiator: {differentiator}"], "caller-supplied mission inputs")
    sections = [
        ArtifactSection(
            title="Draft mission",
            body=f"'{statement}' ({words} words; aim for under 25).",
            evidence_keys=["ms1", f"ms{len(purpose_facts) + 1}", f"ms{len(purpose_facts) + 2}"],
        ),
        ArtifactSection(
            title="Grounding",
            body="Every phrase traces to a supplied fact: " + "; ".join(purpose_facts),
            evidence_keys=[f"ms{i + 1}" for i in range(len(purpose_facts))],
        ),
    ]
    return _artifact(
        kind="mission_statement",
        row=485,
        title=title or "Mission statement",
        summary=f"Draft mission of {words} words, fully grounded in supplied facts.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_PUBLISH],
        manual_steps=["ratify the final wording with the founders before publishing"],
    )


def create_vision_statement(
    *,
    aspiration_facts: list[str],
    horizon_years: int,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 486 - Vision Statement: future picture with an explicit horizon."""
    _require("aspiration_facts", aspiration_facts)
    if not (1 <= horizon_years <= 30):
        raise GrowthPlanError("horizon_years must be between 1 and 30")
    statement = f"In {horizon_years} years, {aspiration_facts[0].rstrip('.')}."
    ev = evidence + _facts("vs", aspiration_facts, "caller-supplied aspirations")
    sections = [
        ArtifactSection(
            title="Draft vision",
            body=f"'{statement}'",
            evidence_keys=["vs1"],
        ),
        ArtifactSection(
            title="Grounding and horizon",
            body=f"Horizon {horizon_years} years. Aspirations used verbatim: " + "; ".join(aspiration_facts),
            evidence_keys=[f"vs{i + 1}" for i in range(len(aspiration_facts))],
        ),
    ]
    return _artifact(
        kind="vision_statement",
        row=486,
        title=title or "Vision statement",
        summary=f"Draft vision over a {horizon_years}-year horizon from supplied aspirations.",
        sections=sections,
        evidence=ev,
        gated_effects=[GATED_PUBLISH],
        manual_steps=[],
    )


# --- rows 487-495: strategy frameworks, OKRs, KPIs, scorecard, performance ---------


def develop_strategy(
    *,
    winning_aspiration: str,
    where_to_play: list[str],
    differentiators: list[str],
    capabilities: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 487 - Strategy Development: choice cascade from supplied inputs."""
    _require("winning_aspiration", winning_aspiration)
    _require("where_to_play", where_to_play)
    _require("differentiators", differentiators)
    _require("capabilities", capabilities)
    facts = [
        f"aspiration: {winning_aspiration}",
        "where to play: " + "; ".join(where_to_play),
        "how to win: " + "; ".join(differentiators),
        "capabilities: " + "; ".join(capabilities),
    ]
    ev = evidence + _facts("st", facts, "caller-supplied strategy choices")
    sections = [
        ArtifactSection(
            title="Strategy choice cascade",
            body=(
                f"Aspiration: {winning_aspiration}. Where to play: " + "; ".join(where_to_play)
                + ". How to win: " + "; ".join(differentiators)
                + ". Required capabilities: " + "; ".join(capabilities) + "."
            ),
            evidence_keys=["st1", "st2", "st3", "st4"],
        ),
        ArtifactSection(
            title="Consistency check",
            body="Each differentiator must map to at least one listed capability; an unmatched differentiator is a gap to close, not a claim to make.",
        ),
    ]
    unmatched = [d for d in differentiators if not any(d.lower().split()[0] in c.lower() for c in capabilities)]
    if unmatched:
        sections[1].body += f" Unmatched differentiator(s) flagged: {', '.join(unmatched)}."
    return _artifact(
        kind="strategy_development",
        row=487,
        title=title or "Strategy",
        summary="Choice cascade from supplied inputs with a differentiator-capability consistency check.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def analyze_swot(
    *,
    subject: str,
    strengths: list[str],
    weaknesses: list[str],
    opportunities: list[str],
    threats: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 488 - SWOT Analysis: typed matrix with computed pairings."""
    for name, items in (("strengths", strengths), ("weaknesses", weaknesses), ("opportunities", opportunities), ("threats", threats)):
        _require(name, items)
    facts = (
        [f"S: {s}" for s in strengths] + [f"W: {w}" for w in weaknesses]
        + [f"O: {o}" for o in opportunities] + [f"T: {t}" for t in threats]
    )
    ev = evidence + _facts("sw", facts, "caller-supplied SWOT items")
    pairings = [
        f"SO: use '{strengths[0]}' to capture '{opportunities[0]}'",
        f"WO: fix '{weaknesses[0]}' because it blocks '{opportunities[0]}'",
        f"ST: lean on '{strengths[0]}' against '{threats[0]}'",
        f"WT: mitigate '{weaknesses[0]}' before '{threats[0]}' compounds it",
    ]
    sections = [
        ArtifactSection(
            title="SWOT matrix",
            body=(
                f"Strengths ({len(strengths)}): " + "; ".join(strengths)
                + f". Weaknesses ({len(weaknesses)}): " + "; ".join(weaknesses)
                + f". Opportunities ({len(opportunities)}): " + "; ".join(opportunities)
                + f". Threats ({len(threats)}): " + "; ".join(threats)
            ),
            evidence_keys=[f"sw{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Pairings (computed)",
            body=" | ".join(pairings),
            evidence_keys=["sw1", f"sw{len(strengths) + 1}", f"sw{len(strengths) + len(weaknesses) + 1}", f"sw{len(strengths) + len(weaknesses) + len(opportunities) + 1}"],
        ),
    ]
    return _artifact(
        kind="swot_analysis",
        row=488,
        title=title or f"SWOT: {subject}",
        summary=f"{len(strengths)}S/{len(weaknesses)}W/{len(opportunities)}O/{len(threats)}T with computed SO/WO/ST/WT pairings.",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=[],
    )


def analyze_pestle(
    *,
    subject: str,
    factors: list[PESTLEFactor],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 489 - PESTLE Analysis: grouped environment scan, negatives highlighted."""
    _require("factors", factors)
    categories = ["political", "economic", "social", "technological", "environmental", "legal"]
    grouped = {c: [f for f in factors if f.category == c] for c in categories}
    missing = [c for c in categories if not grouped[c]]
    negatives = [f for f in factors if f.impact == "negative"]
    lines = [f"{f.category} [{f.impact}]: {f.fact}" for f in factors]
    ev = evidence + _facts("pe", lines, "caller-supplied PESTLE factors")
    sections = [
        ArtifactSection(
            title="Environment scan",
            body=" | ".join(
                f"{c.upper()}: " + ("; ".join(x.fact for x in grouped[c]) if grouped[c] else "none supplied")
                for c in categories
            ),
            evidence_keys=[f"pe{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Attention list (computed)",
            body=(
                f"{len(negatives)} negative factor(s) need a response plan: " + "; ".join(f.fact for f in negatives)
                if negatives else "No negative factors supplied."
            ) + (f" Categories with no supplied factors: {', '.join(missing)}." if missing else ""),
            evidence_keys=[f"pe{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="pestle_analysis",
        row=489,
        title=title or f"PESTLE: {subject}",
        summary=f"{len(factors)} factor(s) across {len(categories) - len(missing)} of 6 categories.",
        sections=sections,
        evidence=ev,
        scope_checks=["unscanned categories are declared, not silently skipped"],
        gated_effects=[],
        manual_steps=[],
    )


def plan_scenarios(
    *,
    subject: str,
    drivers: list[StrategicDriver],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 490 - Scenario Planning: scenario grid from supplied driver states."""
    _require("drivers", drivers)
    if len(drivers) > 2:
        raise GrowthPlanError("supply the two most uncertain drivers; more than two makes an unreadable grid")
    facts = [f"{d.name}: {' / '.join(d.states)}" for d in drivers]
    ev = evidence + _facts("sd", facts, "caller-supplied uncertainty drivers")
    if len(drivers) == 2:
        a, b = drivers
        scenarios = [f"{sa} x {sb}" for sa in a.states for sb in b.states]
    else:
        scenarios = list(drivers[0].states)
    sections = [
        ArtifactSection(
            title="Scenario grid (computed)",
            body=f"{len(scenarios)} scenario(s): " + "; ".join(scenarios),
            evidence_keys=[f"sd{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Per-scenario plan",
            body="For each scenario: leading indicator to watch, trigger threshold, pre-agreed first move. Indicators come from supplied evidence only.",
        ),
    ]
    return _artifact(
        kind="scenario_planning",
        row=490,
        title=title or f"Scenarios: {subject}",
        summary=f"{len(scenarios)} scenario(s) from {len(drivers)} supplied driver(s).",
        sections=sections,
        evidence=ev,
        gated_effects=[],
        manual_steps=["assign a named owner to each scenario's leading indicator"],
    )


def plan_strategy(
    *,
    goals: list[StrategicGoal],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 491 - Strategic Planning: goals with horizons, owners, and measures."""
    _require("goals", goals)
    lines = [f"[{g.horizon}] {g.objective} - owner {g.owner}, measured by: " + "; ".join(g.measures) for g in goals]
    horizons = {h: sum(1 for g in goals if g.horizon == h) for h in ("quarter", "year", "three_year")}
    ev = evidence + _facts("sg", lines, "caller-supplied strategic goals")
    sections = [
        ArtifactSection(
            title="Goal portfolio",
            body=" | ".join(lines),
            evidence_keys=[f"sg{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Horizon balance (computed)",
            body=f"quarter: {horizons['quarter']}, year: {horizons['year']}, three_year: {horizons['three_year']}. A portfolio with no three_year goal is a todo list, not a strategy.",
            evidence_keys=[f"sg{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="strategic_planning",
        row=491,
        title=title or "Strategic plan",
        summary=f"{len(goals)} goal(s) with computed horizon balance.",
        sections=sections,
        evidence=ev,
        scope_checks=["a goal without at least one measure is rejected at input validation"],
        gated_effects=[],
        manual_steps=[],
    )


def set_okrs(
    *,
    period: str,
    objectives: list[Objective],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 492 - OKR Setting: numeric key results with computed scoring."""
    _require("objectives", objectives)
    lines = []
    for o in objectives:
        if len(o.key_results) > 5:
            raise GrowthPlanError(f"objective '{o.objective}' has {len(o.key_results)} key results; cap is 5")
        kr_lines = []
        for kr in o.key_results:
            if kr.baseline == kr.target:
                raise GrowthPlanError(f"key result '{kr.description}' has baseline == target; nothing to move")
            kr_lines.append(f"{kr.description}: {kr.baseline} -> {kr.target} {kr.unit}".rstrip())
        lines.append(f"{o.objective} [{'; '.join(kr_lines)}]")
    ev = evidence + _facts("ok", lines, "caller-supplied OKRs")
    sections = [
        ArtifactSection(
            title="Objectives and key results",
            body=" | ".join(lines),
            evidence_keys=[f"ok{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Scoring formula",
            body="Score each KR at period end as (current - baseline) / (target - baseline), clamped to [0, 1]; 0.7 is the healthy bar. Grading is a human review with this arithmetic shown.",
        ),
    ]
    return _artifact(
        kind="okr_setting",
        row=492,
        title=title or f"OKRs: {period}",
        summary=f"{len(objectives)} objective(s) with numeric, scorable key results.",
        sections=sections,
        evidence=ev,
        scope_checks=["key results must carry numeric baseline and target - vague KRs are rejected"],
        gated_effects=[],
        manual_steps=[],
    )


def score_okr(key_result: KeyResult) -> float:
    """Compute one key result score; exposed for period-end review."""
    current = key_result.current if key_result.current is not None else key_result.baseline
    span = key_result.target - key_result.baseline
    if span == 0:
        raise GrowthPlanError("baseline == target")
    return round(min(max((current - key_result.baseline) / span, 0.0), 1.0), 3)


def select_kpis(
    *,
    candidates: list[KPICandidate],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 493 - KPI Selection: measurable metrics only, with leading/lagging balance."""
    _require("candidates", candidates)
    leading = [k for k in candidates if k.kind == "leading"]
    lagging = [k for k in candidates if k.kind == "lagging"]
    lines = [f"{k.name} [{k.kind}, {k.frequency}]: {k.formula} (source: {k.data_source})" for k in candidates]
    ev = evidence + _facts("kp", lines, "caller-supplied KPI candidates")
    sections = [
        ArtifactSection(
            title="Selected KPIs",
            body=" | ".join(lines),
            evidence_keys=[f"kp{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Balance (computed)",
            body=f"{len(leading)} leading vs {len(lagging)} lagging. "
            + ("No leading indicator supplied - you will see problems only after they land." if not leading else "")
            + ("No lagging indicator supplied - nothing confirms outcomes." if not lagging else ""),
            evidence_keys=[f"kp{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="kpi_selection",
        row=493,
        title=title or "KPI selection",
        summary=f"{len(candidates)} KPI(s), {len(leading)} leading / {len(lagging)} lagging.",
        sections=sections,
        evidence=ev,
        scope_checks=["a KPI without a formula and data source is rejected at input validation"],
        gated_effects=[],
        manual_steps=[],
    )


def build_balanced_scorecard(
    *,
    financial: list[str],
    customer: list[str],
    internal_process: list[str],
    learning_growth: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 494 - Balanced Scorecard: all four perspectives populated and linked."""
    for name, items in (("financial", financial), ("customer", customer), ("internal_process", internal_process), ("learning_growth", learning_growth)):
        _require(name, items)
    facts = (
        [f"F: {x}" for x in financial] + [f"C: {x}" for x in customer]
        + [f"P: {x}" for x in internal_process] + [f"L: {x}" for x in learning_growth]
    )
    ev = evidence + _facts("bs", facts, "caller-supplied scorecard measures")
    sections = [
        ArtifactSection(
            title="Four perspectives",
            body=(
                "Financial: " + "; ".join(financial) + ". Customer: " + "; ".join(customer)
                + ". Internal process: " + "; ".join(internal_process)
                + ". Learning & growth: " + "; ".join(learning_growth)
            ),
            evidence_keys=[f"bs{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Cause-and-effect chain",
            body="Review order each period: learning & growth -> internal process -> customer -> financial. A financial miss is diagnosed down the chain, not treated in isolation.",
        ),
    ]
    return _artifact(
        kind="balanced_scorecard",
        row=494,
        title=title or "Balanced scorecard",
        summary=f"{len(facts)} measure(s) across all four perspectives.",
        sections=sections,
        evidence=ev,
        scope_checks=["all four perspectives must be populated - empty ones are rejected"],
        gated_effects=[],
        manual_steps=[],
    )


def plan_performance_management(
    *,
    roles: list[str],
    cadence: Literal["monthly", "quarterly", "biannual"],
    expectations: list[str],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 495 - Performance Management: review cycle grounded in expectations."""
    _require("roles", roles)
    _require("expectations", expectations)
    facts = [f"{r}" for r in roles] + [f"expectation: {e}" for e in expectations]
    ev = evidence + _facts("pm", facts, "caller-supplied roles and expectations")
    sections = [
        ArtifactSection(
            title="Review cycle",
            body=f"{cadence.capitalize()} reviews for: " + ", ".join(roles) + ". Assessed against supplied expectations: " + "; ".join(expectations),
            evidence_keys=[f"pm{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Fairness rules",
            body="Ratings cite observable evidence from the period; calibration across managers is a human meeting; improvement plans name support, not just gaps.",
        ),
    ]
    return _artifact(
        kind="performance_management",
        row=495,
        title=title or "Performance management",
        summary=f"{cadence.capitalize()} cycle for {len(roles)} role(s) against {len(expectations)} expectation(s).",
        sections=sections,
        evidence=ev,
        scope_checks=["no automated ratings of people; assessments are human decisions with shown evidence"],
        gated_effects=[],
        manual_steps=[],
    )


# --- rows 496-509: comp, equity, cap table, fundraising, finance, governance --------


def design_compensation(
    *,
    role: str,
    components: list[CompComponent],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 496 - Compensation Design: computed pay mix from supplied components."""
    _require("components", components)
    total = sum(c.annual_value for c in components)
    if total <= 0:
        raise GrowthPlanError("total annual value must be positive")
    lines = [f"{c.name} [{c.type}]: {c.annual_value} ({round(c.annual_value / total * 100, 1)}%)" for c in components]
    ev = evidence + _facts("cc", lines, "caller-supplied compensation components")
    sections = [
        ArtifactSection(
            title="Pay mix (computed)",
            body=f"Total {round(total, 2)}. " + "; ".join(lines),
            evidence_keys=[f"cc{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Review rules",
            body="Band positions are reviewed against supplied market data only; adjustments are human decisions with rationale recorded.",
        ),
    ]
    return _artifact(
        kind="compensation_design",
        row=496,
        title=title or f"Compensation: {role}",
        summary=f"Pay mix over {len(components)} component(s), total {round(total, 2)}.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE],
        gated_effects=[],
        manual_steps=[],
    )


def plan_equity_distribution(
    *,
    grants: list[EquityGrant],
    total_shares: int,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 497 - Equity Distribution: computed ownership percentages."""
    _require("grants", grants)
    if total_shares <= 0:
        raise GrowthPlanError("total_shares must be positive")
    issued = sum(g.shares for g in grants)
    if issued > total_shares:
        raise GrowthPlanError(f"grants total {issued} shares, exceeding the {total_shares} authorized")
    lines = [f"{g.holder} [{g.share_class}]: {g.shares} shares ({round(g.shares / total_shares * 100, 2)}%)" for g in grants]
    ev = evidence + _facts("eg", lines, "caller-supplied equity grants")
    sections = [
        ArtifactSection(
            title="Allocation (computed)",
            body="; ".join(lines) + f". Unallocated: {total_shares - issued} shares ({round((total_shares - issued) / total_shares * 100, 2)}%).",
            evidence_keys=[f"eg{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Grant policy",
            body="Every grant states vesting and cliff in writing; nothing vests without a signed agreement.",
        ),
    ]
    return _artifact(
        kind="equity_distribution",
        row=497,
        title=title or "Equity distribution",
        summary=f"{issued} of {total_shares} shares allocated across {len(grants)} grant(s).",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE],
        gated_effects=["executing any grant agreement is a signed, human-approved action"],
        manual_steps=["legal counsel reviews grant documents before signature"],
    )


def manage_cap_table(
    *,
    entries: list[EquityGrant],
    authorized_shares: int,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 498 - Cap Table Management: computed fully-diluted view with reconciliation."""
    _require("entries", entries)
    if authorized_shares <= 0:
        raise GrowthPlanError("authorized_shares must be positive")
    issued = sum(e.shares for e in entries)
    if issued > authorized_shares:
        raise GrowthPlanError(f"issued {issued} shares exceeds {authorized_shares} authorized")
    by_class: dict[str, int] = {}
    for e in entries:
        by_class[e.share_class] = by_class.get(e.share_class, 0) + e.shares
    lines = [f"{e.holder}: {e.shares} {e.share_class} ({round(e.shares / authorized_shares * 100, 2)}%)" for e in entries]
    ev = evidence + _facts("ct", lines, "caller-supplied cap table entries")
    sections = [
        ArtifactSection(
            title="Fully-diluted view (computed)",
            body="; ".join(lines) + f". Total issued {issued} of {authorized_shares} authorized ({round(issued / authorized_shares * 100, 2)}%).",
            evidence_keys=[f"ct{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="By class (computed)",
            body="; ".join(f"{k}: {v}" for k, v in sorted(by_class.items())),
            evidence_keys=[f"ct{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="cap_table",
        row=498,
        title=title or "Cap table",
        summary=f"{len(entries)} holder(s), {issued}/{authorized_shares} shares issued, reconciled by class.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE, "entries that exceed authorized shares are rejected"],
        gated_effects=[],
        manual_steps=["reconcile against signed agreements after every financing event"],
    )


def plan_fundraising(
    *,
    target_amount: float,
    runway_months: int,
    milestones: list[str],
    current_monthly_burn: float,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 499 - Fundraising Strategy: amount justified by computed runway math."""
    _require("milestones", milestones)
    if target_amount <= 0 or current_monthly_burn < 0 or runway_months <= 0:
        raise GrowthPlanError("target_amount > 0, runway_months > 0, burn >= 0 required")
    needed = round(current_monthly_burn * runway_months, 2)
    buffer = round(target_amount - needed, 2)
    facts = [
        f"target {target_amount}",
        f"monthly burn {current_monthly_burn}",
        f"runway goal {runway_months} months -> need {needed}",
        f"buffer over need: {buffer}",
    ]
    ev = evidence + _facts("fr", facts, "caller-supplied fundraising inputs")
    sections = [
        ArtifactSection(
            title="Amount logic (computed)",
            body=f"Target {target_amount} covers {runway_months} months at burn {current_monthly_burn} (need {needed}) with buffer {buffer}.",
            evidence_keys=["fr1", "fr2", "fr3", "fr4"],
        ),
        ArtifactSection(
            title="Milestones to fund",
            body="Raise narrative ties the amount to supplied milestones: " + "; ".join(milestones),
            evidence_keys=[e.key for e in evidence],
        ),
    ]
    return _artifact(
        kind="fundraising_strategy",
        row=499,
        title=title or "Fundraising strategy",
        summary=f"Target {target_amount} = {runway_months} months runway (need {needed}) + buffer {buffer}.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE, NO_FUNDRAISING_OUTREACH],
        gated_effects=[GATED_SEND],
        manual_steps=["any investor conversation is initiated and approved by a founder"],
    )


def create_pitch_deck(
    *,
    company: str,
    facts: DeckFacts,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 500 - Pitch Deck Creation: outline strictly from supplied facts; gaps flagged."""
    supplied = {k: v for k, v in facts.model_dump().items() if v}
    missing = [k for k in ("problem", "solution", "traction", "market", "team", "ask") if k not in supplied]
    ev = evidence + _facts("pd", [f"{k}: {v}" for k, v in supplied.items()], "caller-supplied deck facts")
    sections = [
        ArtifactSection(
            title=f"Slide: {k}",
            body=str(v),
            evidence_keys=[f"pd{i + 1}"],
        )
        for i, (k, v) in enumerate(supplied.items())
    ]
    sections.append(
        ArtifactSection(
            title="Gaps",
            body=("Missing sections to fill with real facts before showing investors: " + ", ".join(missing)) if missing else "All core sections supplied.",
        )
    )
    return _artifact(
        kind="pitch_deck",
        row=500,
        title=title or f"Pitch deck: {company}",
        summary=f"{len(supplied)} slide(s) from supplied facts; {len(missing)} gap(s) flagged.",
        sections=sections,
        evidence=ev,
        scope_checks=[NO_FUNDRAISING_OUTREACH, "no traction or market number appears without a supplied source"],
        gated_effects=[],
        manual_steps=["a founder owns every number on every slide"],
    )


def build_financial_model(
    *,
    starting_revenue: float,
    monthly_growth_pct: float,
    monthly_costs: float,
    months: int = 12,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 501 - Financial Modeling: transparent projection arithmetic from supplied assumptions."""
    if starting_revenue < 0 or monthly_costs < 0 or not (1 <= months <= 60):
        raise GrowthPlanError("starting_revenue >= 0, monthly_costs >= 0, months in 1..60 required")
    revenue = starting_revenue
    rows = []
    for month in range(1, months + 1):
        net = round(revenue - monthly_costs, 2)
        rows.append(f"M{month}: rev {round(revenue, 2)}, costs {monthly_costs}, net {net}")
        revenue = round(revenue * (1 + monthly_growth_pct / 100), 2)
    facts = [
        f"starting revenue {starting_revenue}",
        f"growth {monthly_growth_pct}%/month",
        f"costs {monthly_costs}/month",
        f"horizon {months} months",
    ]
    ev = evidence + _facts("fm", facts, "caller-supplied model assumptions")
    sections = [
        ArtifactSection(
            title="Projection (computed)",
            body="; ".join(rows),
            evidence_keys=["fm1", "fm2", "fm3", "fm4"],
        ),
        ArtifactSection(
            title="Sensitivity note",
            body="Rerun with growth and cost assumptions +/-20% before quoting any month; the model is arithmetic on assumptions, not a forecast of reality.",
        ),
    ]
    return _artifact(
        kind="financial_model",
        row=501,
        title=title or "Financial model",
        summary=f"{months}-month projection computed from supplied growth and cost assumptions.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE, "every projected number derives from the four supplied assumptions"],
        gated_effects=[],
        manual_steps=[],
    )


def analyze_valuation(
    *,
    method: Literal["revenue_multiple", "earnings_multiple"],
    base_amount: float,
    multiple: float,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 502 - Valuation Analysis: arithmetic on a supplied base and multiple only."""
    if base_amount <= 0 or multiple <= 0:
        raise GrowthPlanError("base_amount and multiple must be positive")
    value = round(base_amount * multiple, 2)
    facts = [f"method {method}", f"base {base_amount}", f"multiple {multiple}", f"value {value}"]
    ev = evidence + _facts("va", facts, "caller-supplied valuation inputs")
    sections = [
        ArtifactSection(
            title="Estimate (computed)",
            body=f"{method}: {base_amount} x {multiple} = {value}.",
            evidence_keys=["va1", "va2", "va3", "va4"],
        ),
        ArtifactSection(
            title="Caveats",
            body="Single-multiple estimates are a conversation anchor, not a valuation opinion; the multiple's source must be supplied evidence.",
        ),
    ]
    return _artifact(
        kind="valuation_analysis",
        row=502,
        title=title or "Valuation analysis",
        summary=f"{method} estimate {value} from supplied base and multiple.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE, "no valuation range is stated beyond what the supplied inputs compute"],
        gated_effects=[],
        manual_steps=["commission an independent valuation before relying on the number"],
    )


def prepare_due_diligence(
    *,
    company: str,
    areas: list[DiligenceArea],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 503 - Due Diligence Preparation: data-room checklist with computed coverage."""
    _require("areas", areas)
    lines = []
    total_required = 0
    total_have = 0
    for area in areas:
        missing = [r for r in area.required if r not in area.documents]
        total_required += len(area.required)
        total_have += len(area.required) - len(missing)
        lines.append(
            f"{area.category}: {len(area.documents)} document(s)"
            + (f", missing required: {', '.join(missing)}" if missing else ", all required present")
        )
    coverage = round(total_have / total_required * 100, 1) if total_required else 0.0
    ev = evidence + _facts("dd", lines, "caller-supplied data room inventory")
    sections = [
        ArtifactSection(
            title="Data room coverage (computed)",
            body=f"Required-document coverage {coverage}%. " + " | ".join(lines),
            evidence_keys=[f"dd{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Access policy",
            body="Data room access is granted per reviewer with an NDA on file and an access log; nothing is shared broadly.",
        ),
    ]
    return _artifact(
        kind="due_diligence",
        row=503,
        title=title or f"Due diligence: {company}",
        summary=f"{coverage}% required-document coverage across {len(areas)} area(s).",
        sections=sections,
        evidence=ev,
        scope_checks=["documents are inventoried, never summarized into claims they do not contain"],
        gated_effects=["granting any data-room access is an approved action"],
        manual_steps=[],
    )


def negotiate_term_sheet(
    *,
    parties: list[str],
    terms: list[TermPosition],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 504 - Term Sheet Negotiation: position comparison and trade plan."""
    _require("parties", parties)
    _require("terms", terms)
    aligned = [t for t in terms if t.our_position == t.their_position]
    contested = [t for t in terms if t.our_position != t.their_position]
    lines = [
        f"{t.term} [{t.priority}]: ours '{t.our_position}' vs theirs '{t.their_position}'"
        + (" (aligned)" if t in aligned else " (open)")
        for t in terms
    ]
    gives = [t for t in contested if t.priority == "give"]
    musts = [t for t in contested if t.priority == "must"]
    ev = evidence + _facts("ts", lines, "caller-supplied term positions")
    sections = [
        ArtifactSection(
            title="Position map",
            body=f"{len(aligned)} aligned, {len(contested)} open. " + " | ".join(lines),
            evidence_keys=[f"ts{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Trade plan (computed)",
            body=(
                (f"Offer on 'give' terms ({', '.join(t.term for t in gives)}) in exchange for movement on 'must' terms ({', '.join(t.term for t in musts)})."
                 if gives and musts else "No clean give-for-must trade available; escalate priorities to the principals.")
            ),
            evidence_keys=[f"ts{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="term_sheet_negotiation",
        row=504,
        title=title or "Term sheet: " + " and ".join(parties),
        summary=f"{len(contested)} open term(s) with a computed give-for-must trade plan.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE, "counsel reviews every counter before it is communicated"],
        gated_effects=[GATED_SEND],
        manual_steps=["legal review of the final sheet before signature"],
    )


def plan_investor_relations(
    *,
    investors: list[dict[str, str]],
    update_cadence: Literal["monthly", "quarterly"],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 505 - Investor Relations: update calendar for supplied investors only."""
    _require("investors", investors)
    lines = []
    for inv in investors:
        name = _require("investor name", inv.get("name", ""))
        firm = inv.get("firm", "")
        lines.append(f"{name}" + (f" ({firm})" if firm else ""))
    ev = evidence + _facts("ir", lines, "caller-supplied investor list")
    sections = [
        ArtifactSection(
            title="Update calendar",
            body=f"{update_cadence.capitalize()} updates to {len(investors)} supplied investor(s): " + ", ".join(lines),
            evidence_keys=[f"ir{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Update content rules",
            body="Updates state supplied metrics with their period, one win, one honest miss, and one ask; nothing is sent without founder review.",
        ),
    ]
    return _artifact(
        kind="investor_relations",
        row=505,
        title=title or "Investor relations",
        summary=f"{update_cadence.capitalize()} update calendar for {len(investors)} supplied investor(s).",
        sections=sections,
        evidence=ev,
        scope_checks=["investors come only from the supplied list; no new investor outreach", NO_FUNDRAISING_OUTREACH],
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def manage_board(
    *,
    directors: list[dict[str, str]],
    meeting_cadence: Literal["monthly", "quarterly"],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 506 - Board Management: calendar, pack process, consent tracking."""
    _require("directors", directors)
    lines = []
    for d in directors:
        name = _require("director name", d.get("name", ""))
        lines.append(f"{name}" + (f" ({d.get('role')})" if d.get("role") else ""))
    ev = evidence + _facts("bm", lines, "caller-supplied board roster")
    sections = [
        ArtifactSection(
            title="Board calendar",
            body=f"{meeting_cadence.capitalize()} meetings with: " + ", ".join(lines) + ". Pack circulated 5 business days ahead; minutes within 3 days after.",
            evidence_keys=[f"bm{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Consent tracking",
            body="Reserved matters are listed with their vote outcome and date; no consent is recorded without an explicit vote in the minutes.",
        ),
    ]
    return _artifact(
        kind="board_management",
        row=506,
        title=title or "Board management",
        summary=f"{meeting_cadence.capitalize()} cadence for {len(directors)} director(s).",
        sections=sections,
        evidence=ev,
        scope_checks=["board decisions are human votes recorded in minutes; this module only organizes"],
        gated_effects=[GATED_SEND],
        manual_steps=[],
    )


def plan_exit(
    *,
    options: list[ExitOption],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 507 - Exit Planning: readiness per supplied option from supplied facts."""
    _require("options", options)
    lines = [
        f"{o.type}: readiness facts - " + ("; ".join(o.readiness_facts) if o.readiness_facts else "none supplied")
        for o in options
    ]
    gaps = [o.type for o in options if not o.readiness_facts]
    ev = evidence + _facts("ex", lines, "caller-supplied exit options")
    sections = [
        ArtifactSection(
            title="Options and readiness",
            body=" | ".join(lines),
            evidence_keys=[f"ex{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Gaps",
            body=(f"Options with no readiness evidence: {', '.join(gaps)}. Build the evidence before pursuing them." if gaps else "Every option carries readiness facts."),
            evidence_keys=[f"ex{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="exit_planning",
        row=507,
        title=title or "Exit planning",
        summary=f"{len(options)} exit option(s) assessed against supplied readiness facts.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE],
        gated_effects=[],
        manual_steps=["engage advisors before entering any process"],
    )


def analyze_acquisition(
    *,
    target_name: str,
    rationale_facts: list[str],
    target_revenue: float | None = None,
    asking_price: float | None = None,
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 508 - M&A Analysis: rationale from supplied facts; price cross-check when numbers supplied."""
    _require("rationale_facts", rationale_facts)
    facts = list(rationale_facts)
    price_section_body = "No target financials supplied; no price commentary is made."
    if target_revenue is not None and asking_price is not None:
        if target_revenue <= 0 or asking_price <= 0:
            raise GrowthPlanError("target_revenue and asking_price must be positive")
        implied = round(asking_price / target_revenue, 2)
        facts.append(f"target revenue {target_revenue}")
        facts.append(f"asking price {asking_price} (implied {implied}x revenue)")
        price_section_body = f"Asking {asking_price} against revenue {target_revenue} implies {implied}x revenue; sanity-check this multiple against supplied comparables."
    ev = evidence + _facts("ma", facts, "caller-supplied acquisition inputs")
    sections = [
        ArtifactSection(
            title=f"Target: {target_name}",
            body="Rationale grounded in supplied facts: " + "; ".join(rationale_facts),
            evidence_keys=[f"ma{i + 1}" for i in range(len(rationale_facts))],
        ),
        ArtifactSection(
            title="Price cross-check (computed)",
            body=price_section_body,
            evidence_keys=[f"ma{i + 1}" for i in range(len(facts))],
        ),
        ArtifactSection(
            title="Process",
            body="Letter of intent, diligence, and definitive agreement are sequenced human decisions with counsel at each step; synergies are claimed only from supplied facts.",
        ),
    ]
    return _artifact(
        kind="mna_analysis",
        row=508,
        title=title or f"M&A analysis: {target_name}",
        summary=f"Acquisition assessment of {target_name} from {len(rationale_facts)} supplied rationale fact(s).",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE],
        gated_effects=[],
        manual_steps=["commission independent diligence before signing anything"],
    )


def prepare_ipo(
    *,
    company: str,
    areas: list[ReadinessArea],
    title: str | None = None,
    evidence: list[EvidenceItem],
) -> BusinessArtifact:
    """Row 509 - IPO Preparation: readiness scorecard with computed gap ratio."""
    _require("areas", areas)
    ready = [a for a in areas if a.status == "ready"]
    gaps = [a for a in areas if a.status == "gap"]
    pct = round(len(ready) / len(areas) * 100, 1)
    lines = [f"{a.area}: {a.status}" for a in areas]
    ev = evidence + _facts("ip", lines, "caller-supplied readiness assessment")
    sections = [
        ArtifactSection(
            title="Readiness scorecard (computed)",
            body=f"{len(ready)} of {len(areas)} areas ready ({pct}%). Ready: " + (", ".join(a.area for a in ready) or "none"),
            evidence_keys=[f"ip{i + 1}" for i in range(len(lines))],
        ),
        ArtifactSection(
            title="Gap list",
            body=("Close before any timeline is discussed: " + ", ".join(a.area for a in gaps)) if gaps else "No gaps declared.",
            evidence_keys=[f"ip{i + 1}" for i in range(len(lines))],
        ),
    ]
    return _artifact(
        kind="ipo_preparation",
        row=509,
        title=title or f"IPO readiness: {company}",
        summary=f"{pct}% readiness across {len(areas)} area(s); {len(gaps)} gap(s) to close.",
        sections=sections,
        evidence=ev,
        scope_checks=[NOT_FINANCIAL_ADVICE, "readiness comes from the supplied assessment; no filing or listing step is taken here"],
        gated_effects=[],
        manual_steps=["engage underwriters and counsel only after gaps are closed"],
    )
