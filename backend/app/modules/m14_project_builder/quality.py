"""Plan quality gates for Atlas Module 14 (Project Builder).

Static checks over a ProjectPlan before it is proposed for execution:
measurable acceptance criteria, quality-gate presence, budget consistency,
DAG health (depth, critical path, orphans, specialist concentration).
Produces reports shaped for the module's QualityResult contract. These are
deterministic lints; judgment calls still belong to the human review that
every plan requires.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from .schemas import Budget, ProjectPlan, ProjectTask

# Words that make an acceptance criterion unmeasurable on their own.
_VAGUE_WORDS = frozenset({
    "good", "nice", "well", "better", "best", "fine", "ok", "okay",
    "reasonable", "appropriate", "quality", "properly", "correctly",
})
# A criterion looks measurable when it contains a number, a percent, an
# equality, or an explicit verification verb.
_MEASURABLE_HINT = re.compile(
    r"(\d|%|equals?|at least|at most|no more than|every|all|none|"
    r"pass(?:es|ed)?|fail(?:s|ed)?|match(?:es)?|exists?|present|absent|"
    r"complete[ds]?|documented|reviewed|verified|recorded|defined|stated|"
    r"written|listed|included?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QualityFinding:
    check: str
    severity: str  # "error" | "warning"
    task_id: str  # empty for plan-level findings
    message: str
    remediation: str


@dataclass(frozen=True)
class DagStats:
    task_count: int
    edge_count: int
    depth: int  # longest dependency chain, in tasks
    critical_path: Tuple[str, ...]
    max_fan_in: int
    roots: Tuple[str, ...]
    leaves: Tuple[str, ...]


@dataclass(frozen=True)
class PlanQualityReport:
    passed: bool
    score: float
    findings: Tuple[QualityFinding, ...]
    remediation: Tuple[str, ...]
    stats: DagStats

    def to_quality_result(self) -> Dict[str, object]:
        """Shape for the module's QualityResult pydantic contract."""
        return {
            "passed": self.passed,
            "score": self.score,
            "findings": [f.message for f in self.findings],
            "remediation": list(self.remediation),
        }


def dag_stats(plan: ProjectPlan) -> DagStats:
    """Depth, critical path, fan-in, roots and leaves of the plan DAG."""
    tasks = {t.id: t for t in plan.tasks}
    memo: Dict[str, List[str]] = {}

    def longest_from(task_id: str) -> List[str]:
        if task_id in memo:
            return memo[task_id]
        task = tasks[task_id]
        if not task.dependencies:
            memo[task_id] = [task_id]
        else:
            best = max(
                (longest_from(dep) for dep in task.dependencies), key=len
            )
            memo[task_id] = best + [task_id]
        return memo[task_id]

    critical = max((longest_from(tid) for tid in tasks), key=len)
    depended_on = {dep for t in plan.tasks for dep in t.dependencies}
    roots = tuple(sorted(tid for tid in tasks if not tasks[tid].dependencies))
    leaves = tuple(sorted(tid for tid in tasks if tid not in depended_on))
    return DagStats(
        task_count=len(plan.tasks),
        edge_count=sum(len(t.dependencies) for t in plan.tasks),
        depth=len(critical),
        critical_path=tuple(critical),
        max_fan_in=max(len(t.dependencies) for t in plan.tasks),
        roots=roots,
        leaves=leaves,
    )


def criterion_is_measurable(criterion: str) -> bool:
    """Heuristic: measurable criteria carry a number or verification verb,
    and are not built only from vague adjectives."""
    text = criterion.strip()
    if not text:
        return False
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words and words <= _VAGUE_WORDS:
        return False
    return bool(_MEASURABLE_HINT.search(text))


def evaluate_plan(
    plan: ProjectPlan, budget: Budget | None = None
) -> PlanQualityReport:
    """Run all plan-level and per-task quality checks."""
    findings: List[QualityFinding] = []
    stats = dag_stats(plan)

    if not plan.quality_gates:
        findings.append(QualityFinding(
            check="quality_gates_present", severity="error", task_id="",
            message="plan declares no quality gates",
            remediation="add at least one human or automated review gate",
        ))
    if budget is not None and stats.task_count > budget.max_agent_calls:
        findings.append(QualityFinding(
            check="budget_consistency", severity="error", task_id="",
            message=(
                f"plan has {stats.task_count} tasks but the budget allows "
                f"only {budget.max_agent_calls} agent calls"
            ),
            remediation="raise max_agent_calls or reduce task count",
        ))
    if stats.task_count > 1:
        depended_on = {d for t in plan.tasks for d in t.dependencies}
        orphans = [
            t.id for t in plan.tasks
            if not t.dependencies and t.id not in depended_on
        ]
        if len(orphans) == stats.task_count:
            findings.append(QualityFinding(
                check="dag_connected", severity="warning", task_id="",
                message="no task depends on any other; plan is fully parallel",
                remediation="confirm tasks really are independent",
            ))
    for task in plan.tasks:
        if not task.acceptance_criteria:
            findings.append(QualityFinding(
                check="acceptance_present", severity="warning", task_id=task.id,
                message=f"task {task.id!r} has no acceptance criteria",
                remediation="add at least one measurable acceptance criterion",
            ))
        for criterion in task.acceptance_criteria:
            if not criterion_is_measurable(criterion):
                findings.append(QualityFinding(
                    check="acceptance_measurable", severity="warning",
                    task_id=task.id,
                    message=(
                        f"task {task.id!r} criterion is not measurable: "
                        f"{criterion!r}"
                    ),
                    remediation=(
                        "rewrite with a number, threshold, or explicit "
                        "verification verb"
                    ),
                ))
    kinds: Dict[str, int] = {}
    for task in plan.tasks:
        kinds[task.agent_kind] = kinds.get(task.agent_kind, 0) + 1
    if stats.task_count >= 4 and len(kinds) == 1:
        only = next(iter(kinds))
        findings.append(QualityFinding(
            check="specialist_diversity", severity="warning", task_id="",
            message=(
                f"all {stats.task_count} tasks use the {only!r} specialist"
            ),
            remediation="check whether some tasks belong to other specialists",
        ))

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    score = max(0.0, 1.0 - 0.34 * errors - 0.05 * warnings)
    return PlanQualityReport(
        passed=errors == 0,
        score=round(score, 6),
        findings=tuple(findings),
        remediation=tuple(dict.fromkeys(f.remediation for f in findings)),
        stats=stats,
    )
