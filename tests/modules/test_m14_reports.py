"""Tests for the Module 14 status report renderer."""

from datetime import datetime, timedelta, timezone

from app.modules.m14_project_builder.artifacts import (
    build_manifest,
    validate_manifest_set,
)
from app.modules.m14_project_builder.budgets import BudgetLedger, BudgetLimits
from app.modules.m14_project_builder.milestones import (
    compute_progress,
    detect_slippage,
    instantiate_template,
)
from app.modules.m14_project_builder.reports import (
    StatusReportContext,
    render_status_report,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
PAST = (NOW - timedelta(hours=2)).isoformat()


def full_context():
    milestones = tuple(instantiate_template("research_project", "p1", NOW))
    progress = compute_progress(list(milestones))
    slippage = tuple(detect_slippage(list(milestones), NOW + timedelta(days=3)))
    artifact = build_manifest("p1", "t1", "dataset",
                              "workspace://p1/t1/d.csv", b"x",
                              {"source": "s"})
    validation = validate_manifest_set((artifact,), "p1",
                                       now=NOW + timedelta(days=2))
    ledger = BudgetLedger(BudgetLimits(max_iterations=5, max_agent_calls=10,
                                       max_runtime_seconds=100, max_cost_usd=5))
    ledger.record_agent_call(cost_usd=1.5, note="lit")
    ledger.record_runtime(20)
    return StatusReportContext(
        project_id="p1", goal="Build an ISEF project", status="planned",
        progress=progress, milestones=milestones, slippage=slippage,
        artifact_validation=validation, budget=ledger.status(),
        generated_at=NOW,
    )


class TestStatusReport:
    def test_all_sections_render(self):
        text = render_status_report(full_context())
        assert text.startswith("# Project status: Build an ISEF project")
        for section in ("## Progress", "## Open milestones", "## Slippage",
                        "## Artifact validation", "## Budget"):
            assert section in text
        assert "**Overall:** 0%" in text
        assert "Literature review" in text
        assert "**EXHAUSTED:**" not in text
        assert "$1.50 used" in text

    def test_artifact_errors_listed(self):
        text = render_status_report(full_context())
        assert "missing provenance keys" in text

    def test_exhausted_budget_flagged(self):
        ledger = BudgetLedger(BudgetLimits(max_iterations=1))
        ledger.record_iteration()
        ctx = StatusReportContext(project_id="p1", goal="g", status="running",
                                  budget=ledger.status(), generated_at=NOW)
        assert "**EXHAUSTED:** iterations" in render_status_report(ctx)

    def test_minimal_context(self):
        text = render_status_report(StatusReportContext(
            project_id="p1", goal="g", status="draft", generated_at=NOW))
        assert "## Progress" not in text
        assert "## Budget" not in text
        assert "**Status:** draft" in text
