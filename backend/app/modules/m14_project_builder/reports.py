"""Project status reports for Atlas Module 14 (Project Builder).

Stdlib-only rendering of the full project state - milestone progress,
slippage, artifact validation, and budget consumption - into one markdown
report for the dashboard, exports, or the human review gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from .artifacts import SetValidationReport
from .budgets import BudgetStatus
from .milestones import Milestone, ProgressReport, Slippage


@dataclass(frozen=True)
class StatusReportContext:
    project_id: str
    goal: str
    status: str
    progress: Optional[ProgressReport] = None
    milestones: Tuple[Milestone, ...] = ()
    slippage: Tuple[Slippage, ...] = ()
    artifact_validation: Optional[SetValidationReport] = None
    budget: Optional[BudgetStatus] = None
    generated_at: Optional[datetime] = None


def render_status_report(context: StatusReportContext) -> str:
    """Render the one-page project status report as markdown."""
    stamp = (context.generated_at or datetime.now(timezone.utc)).isoformat()
    lines = [
        f"# Project status: {context.goal}",
        "",
        f"- **Project:** `{context.project_id}`",
        f"- **Status:** {context.status}",
        f"- **Generated:** {stamp}",
    ]
    if context.progress is not None:
        p = context.progress
        lines += [
            "",
            "## Progress",
            "",
            f"- **Overall:** {p.overall_progress:.0%} "
            f"({p.completed_effort_hours:.0f}h of {p.total_effort_hours:.0f}h)",
        ]
        if p.per_phase:
            lines.append("- **By phase:**")
            for phase in sorted(p.per_phase):
                lines.append(f"  - {phase}: {p.per_phase[phase]:.0%}")
        if p.counts_by_status:
            counts = ", ".join(
                f"{k}: {v}" for k, v in sorted(p.counts_by_status.items())
            )
            lines.append(f"- **Milestones:** {counts}")
    open_milestones = [
        m for m in context.milestones
        if m.status.value not in {"completed", "failed", "skipped"}
    ]
    if open_milestones:
        lines += ["", "## Open milestones", ""]
        for m in open_milestones:
            end = m.planned_end.date().isoformat() if m.planned_end else "-"
            lines.append(
                f"- {m.title} ({m.phase}) - {m.status.value}, "
                f"{m.progress:.0%}, due {end}"
            )
    if context.slippage:
        lines += ["", "## Slippage", ""]
        for s in context.slippage:
            lines.append(f"- **{s.kind}** `{s.milestone_id}`: {s.detail}")
    if context.artifact_validation is not None:
        v = context.artifact_validation
        lines += [
            "",
            "## Artifact validation",
            "",
            f"- **Passed:** {'yes' if v.passed else 'NO'} "
            f"(score {v.score:.2f}, {len(v.artifact_reports)} artifacts)",
        ]
        problems = [
            f.message
            for r in v.artifact_reports
            for f in r.findings
            if f.severity == "error"
        ]
        problems += [f.message for f in v.findings if f.severity == "error"]
        if problems:
            lines.append("- **Errors:**")
            lines += [f"  - {m}" for m in problems]
    if context.budget is not None:
        b = context.budget
        lines += [
            "",
            "## Budget",
            "",
            f"- **Iterations:** {b.iterations_used} used, "
            f"{b.iterations_remaining} remaining",
            f"- **Agent calls:** {b.agent_calls_used} used, "
            f"{b.agent_calls_remaining} remaining",
            f"- **Runtime:** {b.runtime_seconds_used:.0f}s used, "
            f"{b.runtime_seconds_remaining:.0f}s remaining",
            f"- **Cost:** ${b.cost_usd_used:.2f} used, "
            f"${b.cost_usd_remaining:.2f} remaining",
        ]
        if b.exhausted:
            lines.append(
                "- **EXHAUSTED:** " + ", ".join(b.exhausted_dimensions)
            )
    lines.append("")
    return "\n".join(lines)
