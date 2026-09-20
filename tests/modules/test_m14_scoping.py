"""Tests for the Module 14 scoped project generation engine."""

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m14_project_builder.scoping import (
    ScopeConstraints,
    ScopeError,
    check_feasibility,
    generate_scope,
    infer_project_kind,
    render_scope_markdown,
)

UTC = timezone.utc
START = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)


class TestKindInference:
    def test_research_goal(self):
        result = infer_project_kind("Build an ISEF research paper on algae biofuels")
        assert result.kind == "research_project"
        assert result.confidence > 0
        assert "isef" in result.matched_keywords

    def test_coding_goal(self):
        result = infer_project_kind("Build a CLI tool that renames photos")
        assert result.kind == "coding_project"

    def test_data_goal(self):
        result = infer_project_kind("Analyze this dataset and visualize trends")
        assert result.kind == "data_analysis"

    def test_no_match_defaults_with_zero_confidence(self):
        result = infer_project_kind("zyx wvut")
        assert result.kind == "research_project"
        assert result.confidence == 0.0
        assert result.matched_keywords == ()

    def test_brief_keywords_count(self):
        result = infer_project_kind("Do the thing", brief_keywords=["dataset", "analysis"])
        assert result.kind == "data_analysis"

    def test_tie_breaks_by_priority(self):
        result = infer_project_kind("build an app to analyze data")
        # coding (build, app) ties data_analysis (analyze, data); priority wins
        assert result.kind == "coding_project"


class TestConstraints:
    def test_naive_deadline_rejected(self):
        with pytest.raises(ValueError):
            ScopeConstraints(deadline=datetime(2026, 10, 1))

    def test_nonpositive_effort_rejected(self):
        with pytest.raises(ValueError):
            ScopeConstraints(max_effort_hours=0)

    def test_negative_budget_rejected(self):
        with pytest.raises(ValueError):
            ScopeConstraints(max_budget_usd=-5)

    def test_nonpositive_hours_per_day_rejected(self):
        with pytest.raises(ValueError):
            ScopeConstraints(hours_per_day=0)


class TestFeasibility:
    def test_generous_constraints_feasible(self):
        report = check_feasibility(
            "research_project",
            ScopeConstraints(deadline=START + timedelta(days=90)),
            START,
        )
        assert report.feasible
        assert report.issues == ()
        assert report.estimated_effort_hours == 126.0  # sum of template efforts
        assert report.estimated_finish > START

    def test_tight_deadline_flagged(self):
        report = check_feasibility(
            "research_project",
            ScopeConstraints(deadline=START + timedelta(days=2)),
            START,
        )
        assert not report.feasible
        assert any("deadline" in issue for issue in report.issues)

    def test_effort_cap_flagged(self):
        report = check_feasibility(
            "coding_project", ScopeConstraints(max_effort_hours=10), START,
        )
        assert not report.feasible
        assert any("budgeted" in issue for issue in report.issues)

    def test_missing_deliverable_flagged(self):
        report = check_feasibility(
            "coding_project",
            ScopeConstraints(deliverable_requirements=("mobile_app",)),
            START,
        )
        assert not report.feasible
        assert any("mobile_app" in issue for issue in report.issues)

    def test_unknown_kind_rejected(self):
        with pytest.raises(ScopeError):
            check_feasibility("nope", ScopeConstraints(), START)

    def test_naive_start_rejected(self):
        with pytest.raises(ValueError):
            check_feasibility("coding_project", ScopeConstraints(),
                              datetime(2026, 9, 21))


class TestScopeDocument:
    def test_full_document(self):
        scope = generate_scope(
            "p1", "Build an ISEF research paper on algae biofuels",
            constraints=ScopeConstraints(
                deadline=START + timedelta(days=60),
                max_budget_usd=100,
                excluded_activities=("live vertebrate studies",),
            ),
            start=START, created_at=START,
        )
        assert scope.kind == "research_project"
        assert scope.feasibility.feasible
        assert len(scope.in_scope) == 8  # all template steps
        assert "live vertebrate studies" in scope.out_of_scope
        assert any("ethics approval" in item for item in scope.out_of_scope)
        assert scope.assumptions
        assert scope.risks
        assert scope.created_at == START

    def test_explicit_kind_full_confidence(self):
        scope = generate_scope("p1", "Something ambiguous", kind="coding_project",
                               start=START, created_at=START)
        assert scope.kind == "coding_project"
        assert scope.kind_confidence == 1.0

    def test_infeasible_issues_become_risks(self):
        scope = generate_scope(
            "p1", "Build an ISEF research paper",
            constraints=ScopeConstraints(deadline=START + timedelta(days=1)),
            start=START, created_at=START,
        )
        assert not scope.feasibility.feasible
        assert any("deadline" in risk for risk in scope.risks)

    def test_empty_goal_rejected(self):
        with pytest.raises(ScopeError):
            generate_scope("p1", "   ")

    def test_empty_project_id_rejected(self):
        with pytest.raises(ScopeError):
            generate_scope("", "goal")


class TestScopeMarkdown:
    def test_renders_sections(self):
        scope = generate_scope(
            "p1", "Analyze this dataset and visualize trends",
            constraints=ScopeConstraints(deadline=START + timedelta(days=30),
                                         max_budget_usd=50),
            start=START, created_at=START,
        )
        text = render_scope_markdown(scope)
        assert text.startswith("# Scope: Analyze this dataset")
        assert "**Kind:** data_analysis" in text
        assert "**Feasible:** yes" in text
        assert "**Budget cap:** $50.00" in text
        for section in ("## In scope", "## Out of scope", "## Assumptions", "## Risks"):
            assert section in text

    def test_infeasible_shows_issues_section(self):
        scope = generate_scope(
            "p1", "Analyze this dataset",
            constraints=ScopeConstraints(deadline=START + timedelta(hours=1)),
            start=START, created_at=START,
        )
        text = render_scope_markdown(scope)
        assert "**Feasible:** NO" in text
        assert "## Feasibility issues" in text


class TestNewKinds:
    def test_essay_goal(self):
        result = infer_project_kind("Write my college essay about my grandmother")
        assert result.kind == "essay_project"

    def test_competition_goal(self):
        result = infer_project_kind("Apply to the national science olympiad")
        assert result.kind == "competition_application"
        assert "olympiad" in result.matched_keywords

    @pytest.mark.parametrize("kind", ["essay_project", "competition_application"])
    def test_new_kinds_scope_cleanly(self, kind):
        scope = generate_scope("p1", "placeholder", kind=kind,
                               start=START, created_at=START)
        assert scope.feasibility.feasible
        assert scope.out_of_scope and scope.assumptions and scope.risks
        assert len(scope.in_scope) == 6

    def test_competition_out_of_scope_gates_submission(self):
        scope = generate_scope("p1", "Apply to the hackathon", start=START,
                               created_at=START)
        assert any("human approval" in item for item in scope.out_of_scope)
