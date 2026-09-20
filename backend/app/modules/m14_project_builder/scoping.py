"""Scoped project generation for Atlas Module 14 (Project Builder).

Stdlib-only. Before the LLM planner decomposes a goal, this engine decides
what kind of project the goal is, whether the constraints (deadline, effort,
budget) can hold it, and writes the scope document: in-scope, out-of-scope,
assumptions, risks, feasibility. Deterministic and auditable; the planner
refines inside these boundaries afterward.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence, Tuple

from .milestones import (
    MILESTONE_TEMPLATES,
    instantiate_template,
    list_template_kinds,
)


class ScopeError(ValueError):
    """Base error for scoping operations."""


# Keyword -> project-kind evidence. First match group wins ties via _PRIORITY.
_KIND_KEYWORDS: Mapping[str, Tuple[str, ...]] = {
    "essay_project": (
        "essay", "personal statement", "application essay", "college essay",
        "sop", "statement of purpose", "writing piece",
    ),
    "competition_application": (
        "competition", "scholarship", "contest", "hackathon", "olympiad",
        "apply", "application", "program application", "summer program",
    ),
    "research_project": (
        "research", "paper", "isef", "experiment", "study", "literature",
        "hypothesis", "science fair", "poster", "investigate",
    ),
    "coding_project": (
        "app", "build", "code", "software", "api", "website",
        "tool", "platform", "cli", "library",
    ),
    "data_analysis": (
        "analyze", "analyse", "analysis", "dataset", "data", "model",
        "predict", "trends", "statistics", "visualize", "visualise",
    ),
}
_PRIORITY = (
    "research_project", "essay_project", "competition_application",
    "coding_project", "data_analysis",
)


@dataclass(frozen=True)
class KindInference:
    kind: str
    confidence: float  # 0.0-1.0
    matched_keywords: Tuple[str, ...]


def infer_project_kind(goal: str, brief_keywords: Sequence[str] = ()) -> KindInference:
    """Score the goal text against kind keyword sets.

    Confidence = matched keywords for the winner / total distinct keywords
    matched across all kinds (1.0 when only one kind matches).
    """
    text = goal.lower()
    for word in brief_keywords:
        text += " " + word.lower()
    scores: dict[str, list[str]] = {}
    for kind, keywords in _KIND_KEYWORDS.items():
        # Word-boundary matching: "app" must not match inside "apply".
        hits = [
            kw
            for kw in keywords
            if re.search(r"\b" + re.escape(kw) + r"\b", text)
        ]
        if hits:
            scores[kind] = hits
    if not scores:
        # Default to the most general kind with zero confidence so callers
        # can route to a human/LLM decision.
        return KindInference(kind="research_project", confidence=0.0,
                             matched_keywords=())
    winner = max(_PRIORITY, key=lambda k: (len(scores.get(k, ())), -_PRIORITY.index(k)))
    total_hits = sum(len(h) for h in scores.values())
    confidence = len(scores[winner]) / total_hits if total_hits else 0.0
    return KindInference(
        kind=winner,
        confidence=round(confidence, 6),
        matched_keywords=tuple(scores[winner]),
    )


@dataclass(frozen=True)
class ScopeConstraints:
    deadline: Optional[datetime] = None
    max_effort_hours: Optional[float] = None
    max_budget_usd: Optional[float] = None
    hours_per_day: float = 8.0
    deliverable_requirements: Tuple[str, ...] = ()
    excluded_activities: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.deadline is not None and (
            self.deadline.tzinfo is None
            or self.deadline.tzinfo.utcoffset(self.deadline) is None
        ):
            raise ValueError("deadline must be timezone-aware")
        if self.max_effort_hours is not None and self.max_effort_hours <= 0:
            raise ValueError("max_effort_hours must be > 0")
        if self.max_budget_usd is not None and self.max_budget_usd < 0:
            raise ValueError("max_budget_usd must be >= 0")
        if self.hours_per_day <= 0:
            raise ValueError("hours_per_day must be > 0")


@dataclass(frozen=True)
class FeasibilityReport:
    feasible: bool
    issues: Tuple[str, ...]
    estimated_effort_hours: float
    estimated_finish: Optional[datetime]
    deadline: Optional[datetime]


@dataclass(frozen=True)
class ScopeDocument:
    project_id: str
    goal: str
    kind: str
    kind_confidence: float
    constraints: ScopeConstraints
    in_scope: Tuple[str, ...]
    out_of_scope: Tuple[str, ...]
    assumptions: Tuple[str, ...]
    risks: Tuple[str, ...]
    feasibility: FeasibilityReport
    created_at: datetime


_DEFAULT_OUT_OF_SCOPE: Mapping[str, Tuple[str, ...]] = {
    "essay_project": (
        "submitting the essay anywhere without human review",
        "fabricating experiences or achievements",
        "exceeding the target word limit",
    ),
    "competition_application": (
        "submitting any application without explicit human approval",
        "paying application fees without budget approval",
        "misrepresenting eligibility or accomplishments",
    ),
    "research_project": (
        "human-subject experiments without ethics approval",
        "paid dataset purchases without budget approval",
        "submission to any competition without human review",
    ),
    "coding_project": (
        "deploying to production without human approval",
        "purchasing domains, hosting, or third-party services",
        "collecting user data beyond the stated requirements",
    ),
    "data_analysis": (
        "scraping sources that prohibit automated access",
        "purchasing datasets without budget approval",
        "publishing results externally without human review",
    ),
}

_DEFAULT_ASSUMPTIONS: Mapping[str, Tuple[str, ...]] = {
    "essay_project": (
        "Source experiences and details come from the user",
        "A target word limit or prompt is known before the final pass",
    ),
    "competition_application": (
        "The user meets the stated eligibility criteria",
        "Required materials (transcripts, essays, recommendations) are obtainable",
    ),
    "research_project": (
        "Suitable public datasets exist and are licensed for research use",
        "Required literature is openly accessible",
    ),
    "coding_project": (
        "Requirements can be finalized before implementation starts",
        "A test environment is available",
    ),
    "data_analysis": (
        "Source data is obtainable and documented",
        "Analysis questions are answerable from available data",
    ),
}

_DEFAULT_RISKS: Mapping[str, Tuple[str, ...]] = {
    "essay_project": (
        "Early drafts may not capture the user's voice",
        "Revision cycles can expand beyond the planned iterations",
    ),
    "competition_application": (
        "External deadlines are fixed and immovable",
        "Recommendation letters may arrive late",
    ),
    "research_project": (
        "Experiment results may not support the hypothesis",
        "Timeline slips if dataset acquisition stalls",
    ),
    "coding_project": (
        "Scope creep beyond agreed requirements",
        "Integration issues discovered late in testing",
    ),
    "data_analysis": (
        "Data quality problems discovered during cleaning",
        "Findings may be inconclusive",
    ),
}


def check_feasibility(
    kind: str,
    constraints: ScopeConstraints,
    start: datetime,
) -> FeasibilityReport:
    """Compare the template's effort and schedule against the constraints."""
    if kind not in MILESTONE_TEMPLATES:
        raise ScopeError(
            f"unknown project kind {kind!r}; available: {', '.join(list_template_kinds())}"
        )
    if start.tzinfo is None or start.tzinfo.utcoffset(start) is None:
        raise ValueError("start must be timezone-aware")
    total_effort = sum(s.effort_hours for s in MILESTONE_TEMPLATES[kind])
    plan = instantiate_template(kind, "feasibility-probe", start,
                                hours_per_day=constraints.hours_per_day)
    finish = max(m.planned_end for m in plan)
    issues = []
    if constraints.max_effort_hours is not None and total_effort > constraints.max_effort_hours:
        issues.append(
            f"template needs {total_effort:.0f}h but only "
            f"{constraints.max_effort_hours:.0f}h are budgeted"
        )
    if constraints.deadline is not None and finish > constraints.deadline:
        issues.append(
            f"estimated finish {finish.date().isoformat()} is after the "
            f"deadline {constraints.deadline.date().isoformat()}"
        )
    required = set(constraints.deliverable_requirements)
    offered = {d for s in MILESTONE_TEMPLATES[kind] for d in s.deliverables}
    missing = required - offered
    if missing:
        issues.append(
            "required deliverables not produced by this project kind: "
            + ", ".join(sorted(missing))
        )
    return FeasibilityReport(
        feasible=not issues,
        issues=tuple(issues),
        estimated_effort_hours=total_effort,
        estimated_finish=finish,
        deadline=constraints.deadline,
    )


def generate_scope(
    project_id: str,
    goal: str,
    constraints: Optional[ScopeConstraints] = None,
    kind: Optional[str] = None,
    brief_keywords: Sequence[str] = (),
    start: Optional[datetime] = None,
    created_at: Optional[datetime] = None,
) -> ScopeDocument:
    """Produce the full scope document for a goal."""
    if not project_id:
        raise ScopeError("project_id must be non-empty")
    if not goal or not goal.strip():
        raise ScopeError("goal must be non-empty")
    constraints = constraints or ScopeConstraints()
    start = start or datetime.now(timezone.utc)
    if kind is None:
        inference = infer_project_kind(goal, brief_keywords)
        kind = inference.kind
        confidence = inference.confidence
    else:
        if kind not in MILESTONE_TEMPLATES:
            raise ScopeError(
                f"unknown project kind {kind!r}; available: "
                + ", ".join(list_template_kinds())
            )
        confidence = 1.0
    feasibility = check_feasibility(kind, constraints, start)
    steps = MILESTONE_TEMPLATES[kind]
    in_scope = tuple(f"{s.title} ({s.phase})" for s in steps)
    out_of_scope = tuple(_DEFAULT_OUT_OF_SCOPE[kind]) + tuple(
        constraints.excluded_activities
    )
    assumptions = tuple(_DEFAULT_ASSUMPTIONS[kind])
    risks = tuple(_DEFAULT_RISKS[kind]) + tuple(feasibility.issues)
    return ScopeDocument(
        project_id=project_id,
        goal=goal,
        kind=kind,
        kind_confidence=confidence,
        constraints=constraints,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        assumptions=assumptions,
        risks=risks,
        feasibility=feasibility,
        created_at=created_at or datetime.now(timezone.utc),
    )


def render_scope_markdown(scope: ScopeDocument) -> str:
    """Human-readable scope document."""
    lines = [
        f"# Scope: {scope.goal}",
        "",
        f"- **Project:** `{scope.project_id}`",
        f"- **Kind:** {scope.kind} (confidence {scope.kind_confidence:.0%})",
        f"- **Feasible:** {'yes' if scope.feasibility.feasible else 'NO - see issues'}",
        f"- **Estimated effort:** {scope.feasibility.estimated_effort_hours:.0f}h",
    ]
    if scope.feasibility.estimated_finish:
        lines.append(
            f"- **Estimated finish:** {scope.feasibility.estimated_finish.date().isoformat()}"
        )
    if scope.constraints.deadline:
        lines.append(
            f"- **Deadline:** {scope.constraints.deadline.date().isoformat()}"
        )
    if scope.constraints.max_budget_usd is not None:
        lines.append(f"- **Budget cap:** ${scope.constraints.max_budget_usd:.2f}")
    lines.append(f"- **Created:** {scope.created_at.isoformat()}")
    for title, values in (
        ("In scope", scope.in_scope),
        ("Out of scope", scope.out_of_scope),
        ("Assumptions", scope.assumptions),
        ("Risks", scope.risks),
    ):
        lines += ["", f"## {title}", ""]
        lines += [f"- {v}" for v in values]
    if scope.feasibility.issues:
        lines += ["", "## Feasibility issues", ""]
        lines += [f"- {i}" for i in scope.feasibility.issues]
    lines.append("")
    return "\n".join(lines)
