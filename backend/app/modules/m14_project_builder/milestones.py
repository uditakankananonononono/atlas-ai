"""Milestone engine for Atlas Module 14 (Project Builder).

Stdlib-only domain logic: per-project-kind milestone templates, dependency-aware
scheduling with cycle detection, effort-weighted progress roll-up, slippage
detection, replanning, and acceptance-criteria gating.

No I/O, no framework imports: the router/service layer adapts these types to
tenant-scoped persistence and approval gates. All datetimes must be
timezone-aware; naive datetimes are rejected so schedules are unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


class MilestoneError(ValueError):
    """Base error for milestone operations."""


class DependencyError(MilestoneError):
    """Unknown, duplicate, or self dependency references."""


class CycleError(MilestoneError):
    """Dependency graph contains a cycle."""

    def __init__(self, remaining_ids: Sequence[str]):
        self.remaining_ids = tuple(sorted(remaining_ids))
        super().__init__(
            "dependency cycle detected among milestones: " + ", ".join(self.remaining_ids)
        )


class TransitionError(MilestoneError):
    """Illegal status transition."""


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


TERMINAL_STATUSES = frozenset(
    {MilestoneStatus.COMPLETED, MilestoneStatus.FAILED, MilestoneStatus.SKIPPED}
)

# Legal forward transitions. FAILED -> PENDING is the retry path; BLOCKED can
# release back to PENDING or straight to IN_PROGRESS.
_LEGAL_TRANSITIONS: Dict[MilestoneStatus, frozenset] = {
    MilestoneStatus.PENDING: frozenset(
        {MilestoneStatus.IN_PROGRESS, MilestoneStatus.BLOCKED, MilestoneStatus.SKIPPED}
    ),
    MilestoneStatus.IN_PROGRESS: frozenset(
        {MilestoneStatus.COMPLETED, MilestoneStatus.FAILED, MilestoneStatus.BLOCKED}
    ),
    MilestoneStatus.BLOCKED: frozenset(
        {MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS, MilestoneStatus.SKIPPED}
    ),
    MilestoneStatus.COMPLETED: frozenset(),
    MilestoneStatus.FAILED: frozenset({MilestoneStatus.PENDING}),
    MilestoneStatus.SKIPPED: frozenset(),
}


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(frozen=True)
class Milestone:
    milestone_id: str
    project_id: str
    title: str
    phase: str
    description: str = ""
    depends_on: Tuple[str, ...] = ()
    estimated_effort_hours: float = 0.0
    deliverables: Tuple[str, ...] = ()
    acceptance_criteria: Tuple[str, ...] = ()
    status: MilestoneStatus = MilestoneStatus.PENDING
    progress: float = 0.0
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.milestone_id:
            raise ValueError("milestone_id must be non-empty")
        if not self.project_id:
            raise ValueError("project_id must be non-empty")
        if not self.title.strip():
            raise ValueError("title must be non-empty")
        if not self.phase.strip():
            raise ValueError("phase must be non-empty")
        if self.estimated_effort_hours < 0:
            raise ValueError("estimated_effort_hours must be >= 0")
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be within [0.0, 1.0]")
        if self.milestone_id in self.depends_on:
            raise DependencyError(
                f"milestone {self.milestone_id!r} cannot depend on itself"
            )
        if len(set(self.depends_on)) != len(self.depends_on):
            raise DependencyError(
                f"milestone {self.milestone_id!r} has duplicate dependencies"
            )
        for name, value in (
            ("planned_start", self.planned_start),
            ("planned_end", self.planned_end),
            ("actual_start", self.actual_start),
            ("actual_end", self.actual_end),
        ):
            if value is not None:
                _require_aware(value, name)
        if (
            self.planned_start is not None
            and self.planned_end is not None
            and self.planned_end < self.planned_start
        ):
            raise ValueError("planned_end must be >= planned_start")


def validate_dependencies(milestones: Sequence[Milestone]) -> None:
    """Every depends_on reference must point at a milestone in the set."""
    ids = {m.milestone_id for m in milestones}
    if len(ids) != len(milestones):
        raise DependencyError("duplicate milestone_id in set")
    for m in milestones:
        for dep in m.depends_on:
            if dep not in ids:
                raise DependencyError(
                    f"milestone {m.milestone_id!r} depends on unknown {dep!r}"
                )


def topological_order(milestones: Sequence[Milestone]) -> List[str]:
    """Kahn's algorithm. Returns ids in a valid dependency order."""
    validate_dependencies(milestones)
    indegree: Dict[str, int] = {m.milestone_id: 0 for m in milestones}
    dependents: Dict[str, List[str]] = {m.milestone_id: [] for m in milestones}
    for m in milestones:
        for dep in m.depends_on:
            indegree[m.milestone_id] += 1
            dependents[dep].append(m.milestone_id)
    ready = sorted(mid for mid, deg in indegree.items() if deg == 0)
    order: List[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for nxt in dependents[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
        ready.sort()
    if len(order) != len(milestones):
        remaining = [mid for mid, deg in indegree.items() if deg > 0]
        raise CycleError(remaining)
    return order


def advance_status(
    milestone: Milestone, new_status: MilestoneStatus, at: datetime
) -> Milestone:
    """Move a milestone to a new status, stamping actual start/end times."""
    _require_aware(at, "at")
    if new_status not in _LEGAL_TRANSITIONS[milestone.status]:
        raise TransitionError(
            f"cannot move {milestone.milestone_id!r} from "
            f"{milestone.status.value} to {new_status.value}"
        )
    updates: Dict[str, object] = {"status": new_status}
    if new_status == MilestoneStatus.IN_PROGRESS and milestone.actual_start is None:
        updates["actual_start"] = at
    if new_status == MilestoneStatus.COMPLETED:
        updates["actual_end"] = at
        updates["progress"] = 1.0
    if new_status == MilestoneStatus.FAILED:
        updates["actual_end"] = at
    if new_status == MilestoneStatus.PENDING:  # retry after failure/block
        updates["actual_end"] = None
        updates["progress"] = 0.0 if milestone.status == MilestoneStatus.FAILED else milestone.progress
    return replace(milestone, **updates)


def schedule_milestones(
    milestones: Sequence[Milestone],
    start: datetime,
    hours_per_day: float = 8.0,
) -> List[Milestone]:
    """Assign planned_start/planned_end in dependency order.

    Each milestone starts at the later of `start` and the latest planned_end
    of its dependencies. Zero-effort milestones are gates: end == start.
    Returns new Milestone objects in topological order; inputs are unchanged.
    """
    _require_aware(start, "start")
    if hours_per_day <= 0:
        raise ValueError("hours_per_day must be > 0")
    order = topological_order(milestones)
    by_id = {m.milestone_id: m for m in milestones}
    scheduled: Dict[str, Milestone] = {}
    for mid in order:
        m = by_id[mid]
        dep_ends = [scheduled[d].planned_end for d in m.depends_on]
        planned_start = max([start, *(d for d in dep_ends if d is not None)])
        duration = timedelta(hours=m.estimated_effort_hours / hours_per_day * 24.0)
        planned_end = planned_start + duration
        scheduled[mid] = replace(
            m, planned_start=planned_start, planned_end=planned_end
        )
    return [scheduled[mid] for mid in order]


@dataclass(frozen=True)
class ProgressReport:
    project_id: str
    overall_progress: float  # 0.0-1.0, effort-weighted
    total_effort_hours: float
    completed_effort_hours: float
    per_phase: Mapping[str, float]
    counts_by_status: Mapping[str, int]


def compute_progress(milestones: Sequence[Milestone]) -> ProgressReport:
    if not milestones:
        raise ValueError("cannot compute progress over an empty milestone set")
    project_ids = {m.project_id for m in milestones}
    if len(project_ids) != 1:
        raise ValueError("milestones span multiple projects")
    total_effort = sum(m.estimated_effort_hours for m in milestones)
    counts: Dict[str, int] = {}
    for m in milestones:
        counts[m.status.value] = counts.get(m.status.value, 0) + 1

    def effective_progress(m: Milestone) -> float:
        if m.status == MilestoneStatus.COMPLETED:
            return 1.0
        if m.status == MilestoneStatus.SKIPPED:
            return 1.0  # skipped work is done-work for roll-up purposes
        if m.status == MilestoneStatus.FAILED:
            return 0.0
        return m.progress

    if total_effort > 0:
        overall = (
            sum(m.estimated_effort_hours * effective_progress(m) for m in milestones)
            / total_effort
        )
    else:
        overall = sum(effective_progress(m) for m in milestones) / len(milestones)
    completed_effort = sum(
        m.estimated_effort_hours
        for m in milestones
        if m.status in (MilestoneStatus.COMPLETED, MilestoneStatus.SKIPPED)
    )
    phases: Dict[str, List[Milestone]] = {}
    for m in milestones:
        phases.setdefault(m.phase, []).append(m)
    per_phase: Dict[str, float] = {}
    for phase, members in phases.items():
        phase_effort = sum(m.estimated_effort_hours for m in members)
        if phase_effort > 0:
            per_phase[phase] = (
                sum(m.estimated_effort_hours * effective_progress(m) for m in members)
                / phase_effort
            )
        else:
            per_phase[phase] = sum(effective_progress(m) for m in members) / len(members)
    return ProgressReport(
        project_id=project_ids.pop(),
        overall_progress=round(overall, 6),
        total_effort_hours=total_effort,
        completed_effort_hours=completed_effort,
        per_phase=per_phase,
        counts_by_status=counts,
    )


@dataclass(frozen=True)
class Slippage:
    milestone_id: str
    kind: str  # "overdue" | "behind_schedule"
    detail: str
    overdue_by: Optional[timedelta] = None
    progress_gap: Optional[float] = None


def detect_slippage(
    milestones: Sequence[Milestone],
    as_of: datetime,
    progress_tolerance: float = 0.10,
) -> List[Slippage]:
    """Flag overdue milestones and in-progress milestones trailing the plan.

    Expected progress is linear between planned_start and planned_end. A
    milestone is behind schedule when actual progress trails expected progress
    by more than `progress_tolerance`.
    """
    _require_aware(as_of, "as_of")
    if not 0.0 <= progress_tolerance <= 1.0:
        raise ValueError("progress_tolerance must be within [0.0, 1.0]")
    findings: List[Slippage] = []
    for m in sorted(milestones, key=lambda x: x.milestone_id):
        if m.status in TERMINAL_STATUSES:
            continue
        if m.planned_end is not None and as_of > m.planned_end:
            findings.append(
                Slippage(
                    milestone_id=m.milestone_id,
                    kind="overdue",
                    detail=(
                        f"{m.title!r} planned to end {m.planned_end.isoformat()} "
                        f"but is still {m.status.value}"
                    ),
                    overdue_by=as_of - m.planned_end,
                )
            )
            continue
        if (
            m.status == MilestoneStatus.IN_PROGRESS
            and m.planned_start is not None
            and m.planned_end is not None
            and m.planned_end > m.planned_start
            and as_of > m.planned_start
        ):
            span = (m.planned_end - m.planned_start).total_seconds()
            elapsed = min((as_of - m.planned_start).total_seconds(), span)
            expected = elapsed / span
            gap = expected - m.progress
            if gap > progress_tolerance:
                findings.append(
                    Slippage(
                        milestone_id=m.milestone_id,
                        kind="behind_schedule",
                        detail=(
                            f"{m.title!r} expected {expected:.0%} complete, "
                            f"actual {m.progress:.0%}"
                        ),
                        progress_gap=round(gap, 6),
                    )
                )
    return findings


@dataclass(frozen=True)
class ReplanResult:
    milestones: Tuple[Milestone, ...]
    shifts: Mapping[str, timedelta]  # milestone_id -> planned_end movement


def replan(
    milestones: Sequence[Milestone],
    as_of: datetime,
    hours_per_day: float = 8.0,
) -> ReplanResult:
    """Reschedule non-terminal milestones from `as_of`.

    Terminal milestones keep their dates and anchor their dependents at
    actual_end (falling back to planned_end). Non-terminal milestones are
    re-sequenced in topological order starting no earlier than `as_of`.
    """
    _require_aware(as_of, "as_of")
    if hours_per_day <= 0:
        raise ValueError("hours_per_day must be > 0")
    order = topological_order(milestones)
    by_id = {m.milestone_id: m for m in milestones}
    result: Dict[str, Milestone] = {}
    for mid in order:
        m = by_id[mid]
        if m.status in TERMINAL_STATUSES:
            result[mid] = m
            continue
        anchor = as_of
        for dep in m.depends_on:
            d = result[dep]
            dep_end = d.actual_end or d.planned_end
            if dep_end is not None and dep_end > anchor:
                anchor = dep_end
        duration = timedelta(hours=m.estimated_effort_hours / hours_per_day * 24.0)
        if m.status == MilestoneStatus.IN_PROGRESS:
            # Keep the real start; remaining work runs from the replan anchor.
            remaining = m.estimated_effort_hours * (1.0 - m.progress)
            remaining_duration = timedelta(hours=remaining / hours_per_day * 24.0)
            result[mid] = replace(
                m,
                planned_start=m.actual_start or as_of,
                planned_end=anchor + max(remaining_duration, timedelta(0)),
            )
        else:
            result[mid] = replace(
                m, planned_start=anchor, planned_end=anchor + duration
            )
    shifts = {
        mid: (result[mid].planned_end - by_id[mid].planned_end)
        for mid in order
        if by_id[mid].planned_end is not None and result[mid].planned_end is not None
    }
    return ReplanResult(milestones=tuple(result[mid] for mid in order), shifts=shifts)


@dataclass(frozen=True)
class AcceptanceReport:
    milestone_id: str
    passed: bool
    satisfied: Tuple[str, ...]
    missing: Tuple[str, ...]


def evaluate_acceptance(
    milestone: Milestone, evidence: Mapping[str, str]
) -> AcceptanceReport:
    """Check every acceptance criterion has non-empty recorded evidence.

    The engine does not judge evidence quality; it enforces that each named
    criterion was addressed before a milestone may be completed.
    """
    satisfied = tuple(
        c for c in milestone.acceptance_criteria if evidence.get(c, "").strip()
    )
    missing = tuple(
        c for c in milestone.acceptance_criteria if not evidence.get(c, "").strip()
    )
    return AcceptanceReport(
        milestone_id=milestone.milestone_id,
        passed=not missing,
        satisfied=satisfied,
        missing=missing,
    )


def can_complete(
    milestone: Milestone,
    all_milestones: Sequence[Milestone],
    evidence: Mapping[str, str],
) -> Tuple[bool, str]:
    """Completion gate: dependencies done, acceptance criteria evidenced."""
    by_id = {m.milestone_id: m for m in all_milestones}
    for dep in milestone.depends_on:
        d = by_id.get(dep)
        if d is None:
            return False, f"unknown dependency {dep!r}"
        if d.status not in (MilestoneStatus.COMPLETED, MilestoneStatus.SKIPPED):
            return False, f"dependency {dep!r} is {d.status.value}"
    report = evaluate_acceptance(milestone, evidence)
    if not report.passed:
        return False, "missing acceptance evidence: " + ", ".join(report.missing)
    return True, "ready to complete"


# --- Template library -------------------------------------------------------


@dataclass(frozen=True)
class TemplateStep:
    key: str
    title: str
    phase: str
    depends_on: Tuple[str, ...] = ()
    effort_hours: float = 0.0
    deliverables: Tuple[str, ...] = ()
    acceptance_criteria: Tuple[str, ...] = ()


MILESTONE_TEMPLATES: Dict[str, Tuple[TemplateStep, ...]] = {
    "research_project": (
        TemplateStep(
            key="literature_review",
            title="Literature review",
            phase="research",
            effort_hours=16.0,
            deliverables=("annotated_bibliography", "related_work_notes"),
            acceptance_criteria=("sources_reviewed", "gaps_identified"),
        ),
        TemplateStep(
            key="dataset_acquisition",
            title="Dataset acquisition",
            phase="data",
            depends_on=("literature_review",),
            effort_hours=12.0,
            deliverables=("dataset_manifest",),
            acceptance_criteria=("sources_documented", "license_verified"),
        ),
        TemplateStep(
            key="experiment_design",
            title="Experiment design",
            phase="design",
            depends_on=("literature_review",),
            effort_hours=10.0,
            deliverables=("experiment_plan",),
            acceptance_criteria=("hypotheses_stated", "controls_defined"),
        ),
        TemplateStep(
            key="implementation",
            title="Implementation and experiments",
            phase="execution",
            depends_on=("experiment_design", "dataset_acquisition"),
            effort_hours=30.0,
            deliverables=("experiment_code", "run_logs"),
            acceptance_criteria=("runs_reproducible", "results_recorded"),
        ),
        TemplateStep(
            key="analysis",
            title="Analysis",
            phase="execution",
            depends_on=("implementation",),
            effort_hours=20.0,
            deliverables=("analysis_notebook", "figures"),
            acceptance_criteria=("statistics_reported", "limitations_noted"),
        ),
        TemplateStep(
            key="paper_draft",
            title="Paper draft",
            phase="writing",
            depends_on=("analysis",),
            effort_hours=24.0,
            deliverables=("paper_pdf",),
            acceptance_criteria=("all_sections_drafted", "citations_complete"),
        ),
        TemplateStep(
            key="poster",
            title="Poster",
            phase="writing",
            depends_on=("analysis",),
            effort_hours=8.0,
            deliverables=("poster_pdf",),
            acceptance_criteria=("fits_template",),
        ),
        TemplateStep(
            key="submission_package",
            title="Submission package",
            phase="delivery",
            depends_on=("paper_draft", "poster"),
            effort_hours=6.0,
            deliverables=("submission_checklist",),
            acceptance_criteria=("rules_compliance_checked",),
        ),
    ),
    "coding_project": (
        TemplateStep(
            key="requirements",
            title="Requirements",
            phase="planning",
            effort_hours=8.0,
            deliverables=("requirements_doc",),
            acceptance_criteria=("scope_agreed",),
        ),
        TemplateStep(
            key="architecture",
            title="Architecture",
            phase="design",
            depends_on=("requirements",),
            effort_hours=10.0,
            deliverables=("architecture_doc",),
            acceptance_criteria=("components_defined", "interfaces_defined"),
        ),
        TemplateStep(
            key="implementation",
            title="Implementation",
            phase="execution",
            depends_on=("architecture",),
            effort_hours=40.0,
            deliverables=("source_tree",),
            acceptance_criteria=("features_complete",),
        ),
        TemplateStep(
            key="testing",
            title="Testing",
            phase="verification",
            depends_on=("implementation",),
            effort_hours=16.0,
            deliverables=("test_report",),
            acceptance_criteria=("suite_green", "coverage_recorded"),
        ),
        TemplateStep(
            key="documentation",
            title="Documentation",
            phase="delivery",
            depends_on=("implementation",),
            effort_hours=8.0,
            deliverables=("readme", "api_docs"),
            acceptance_criteria=("setup_steps_verified",),
        ),
        TemplateStep(
            key="release",
            title="Release",
            phase="delivery",
            depends_on=("testing", "documentation"),
            effort_hours=4.0,
            deliverables=("release_artifact",),
            acceptance_criteria=("changelog_written",),
        ),
    ),
    "essay_project": (
        TemplateStep(
            key="brainstorm",
            title="Brainstorm and concept selection",
            phase="planning",
            effort_hours=4.0,
            deliverables=("concept_list",),
            acceptance_criteria=("concepts_recorded", "theme_chosen"),
        ),
        TemplateStep(
            key="outline",
            title="Outline",
            phase="planning",
            depends_on=("brainstorm",),
            effort_hours=4.0,
            deliverables=("outline",),
            acceptance_criteria=("structure_defined",),
        ),
        TemplateStep(
            key="draft",
            title="First draft",
            phase="writing",
            depends_on=("outline",),
            effort_hours=10.0,
            deliverables=("draft_doc",),
            acceptance_criteria=("draft_complete",),
        ),
        TemplateStep(
            key="critique",
            title="Critique",
            phase="review",
            depends_on=("draft",),
            effort_hours=4.0,
            deliverables=("critique_notes",),
            acceptance_criteria=("feedback_recorded",),
        ),
        TemplateStep(
            key="revision",
            title="Revision",
            phase="writing",
            depends_on=("critique",),
            effort_hours=8.0,
            deliverables=("revised_draft",),
            acceptance_criteria=("feedback_addressed",),
        ),
        TemplateStep(
            key="final_proof",
            title="Final proofread",
            phase="delivery",
            depends_on=("revision",),
            effort_hours=2.0,
            deliverables=("final_essay",),
            acceptance_criteria=("word_limit_verified", "proofread_done"),
        ),
    ),
    "competition_application": (
        TemplateStep(
            key="opportunity_screen",
            title="Opportunity screening",
            phase="planning",
            effort_hours=3.0,
            deliverables=("shortlist",),
            acceptance_criteria=("eligibility_verified",),
        ),
        TemplateStep(
            key="requirements_audit",
            title="Requirements audit",
            phase="planning",
            depends_on=("opportunity_screen",),
            effort_hours=3.0,
            deliverables=("requirements_checklist",),
            acceptance_criteria=("deadlines_recorded", "materials_listed"),
        ),
        TemplateStep(
            key="material_gathering",
            title="Material gathering",
            phase="preparation",
            depends_on=("requirements_audit",),
            effort_hours=6.0,
            deliverables=("materials_folder",),
            acceptance_criteria=("all_materials_collected",),
        ),
        TemplateStep(
            key="application_draft",
            title="Application draft",
            phase="writing",
            depends_on=("requirements_audit",),
            effort_hours=8.0,
            deliverables=("application_draft",),
            acceptance_criteria=("all_prompts_answered",),
        ),
        TemplateStep(
            key="review",
            title="Review",
            phase="review",
            depends_on=("application_draft", "material_gathering"),
            effort_hours=4.0,
            deliverables=("review_notes",),
            acceptance_criteria=("review_completed",),
        ),
        TemplateStep(
            key="submission",
            title="Submission",
            phase="delivery",
            depends_on=("review",),
            effort_hours=2.0,
            deliverables=("submission_receipt",),
            acceptance_criteria=("human_approval_recorded", "receipt_saved"),
        ),
    ),
    "data_analysis": (
        TemplateStep(
            key="question_definition",
            title="Question definition",
            phase="planning",
            effort_hours=4.0,
            deliverables=("question_brief",),
            acceptance_criteria=("question_measurable",),
        ),
        TemplateStep(
            key="data_collection",
            title="Data collection",
            phase="data",
            depends_on=("question_definition",),
            effort_hours=12.0,
            deliverables=("raw_dataset", "collection_log"),
            acceptance_criteria=("sources_documented",),
        ),
        TemplateStep(
            key="cleaning",
            title="Cleaning",
            phase="data",
            depends_on=("data_collection",),
            effort_hours=10.0,
            deliverables=("clean_dataset",),
            acceptance_criteria=("missingness_handled", "schema_documented"),
        ),
        TemplateStep(
            key="exploration",
            title="Exploration",
            phase="analysis",
            depends_on=("cleaning",),
            effort_hours=8.0,
            deliverables=("eda_notebook",),
            acceptance_criteria=("distributions_reviewed",),
        ),
        TemplateStep(
            key="modeling",
            title="Modeling",
            phase="analysis",
            depends_on=("exploration",),
            effort_hours=16.0,
            deliverables=("model_artifacts", "metrics"),
            acceptance_criteria=("baseline_beaten", "evaluation_documented"),
        ),
        TemplateStep(
            key="report",
            title="Report",
            phase="delivery",
            depends_on=("modeling",),
            effort_hours=10.0,
            deliverables=("final_report",),
            acceptance_criteria=("claims_match_evidence",),
        ),
    ),
}


def list_template_kinds() -> Tuple[str, ...]:
    return tuple(sorted(MILESTONE_TEMPLATES))


def instantiate_template(
    kind: str,
    project_id: str,
    start: datetime,
    hours_per_day: float = 8.0,
) -> List[Milestone]:
    """Build and schedule a milestone plan for a project kind."""
    if kind not in MILESTONE_TEMPLATES:
        raise KeyError(
            f"unknown project kind {kind!r}; available: {', '.join(list_template_kinds())}"
        )
    milestones = [
        Milestone(
            milestone_id=f"{project_id}:{step.key}",
            project_id=project_id,
            title=step.title,
            phase=step.phase,
            depends_on=tuple(f"{project_id}:{d}" for d in step.depends_on),
            estimated_effort_hours=step.effort_hours,
            deliverables=step.deliverables,
            acceptance_criteria=step.acceptance_criteria,
        )
        for step in MILESTONE_TEMPLATES[kind]
    ]
    return schedule_milestones(milestones, start, hours_per_day=hours_per_day)
