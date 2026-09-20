"""Tests for the Module 14 plan quality gates."""

import pytest

from app.modules.m14_project_builder.quality import (
    criterion_is_measurable,
    dag_stats,
    evaluate_plan,
)
from app.modules.m14_project_builder.schemas import Budget, ProjectPlan, ProjectTask


def task(tid, deps=(), kind="coder", criteria=("tests pass",)):
    return ProjectTask(id=tid, title=f"Task {tid}", objective=f"Do {tid} well",
                       agent_kind=kind, dependencies=list(deps),
                       acceptance_criteria=list(criteria))


def plan(tasks, gates=("human review",), **kw):
    return ProjectPlan(goal="g", tasks=tasks, quality_gates=list(gates), **kw)


class TestCriterionLint:
    @pytest.mark.parametrize("c", [
        "at least 10 sources reviewed", "coverage equals 80%",
        "all sections documented", "tests pass", "no more than 2 failures",
        "results recorded", "setup steps verified",
    ])
    def test_measurable(self, c):
        assert criterion_is_measurable(c)

    @pytest.mark.parametrize("c", [
        "", "   ", "good", "nice and well", "better",
    ])
    def test_unmeasurable(self, c):
        assert not criterion_is_measurable(c)

    def test_vague_word_inside_measurable_text_ok(self):
        assert criterion_is_measurable("code quality reviewed by 2 humans")


class TestDagStats:
    def test_chain(self):
        p = plan([task("a"), task("b", ("a",)), task("c", ("b",))])
        stats = dag_stats(p)
        assert stats.depth == 3
        assert stats.critical_path == ("a", "b", "c")
        assert stats.roots == ("a",)
        assert stats.leaves == ("c",)
        assert stats.edge_count == 2
        assert stats.max_fan_in == 1

    def test_diamond(self):
        p = plan([task("a"), task("b", ("a",)), task("c", ("a",)),
                  task("d", ("b", "c"))])
        stats = dag_stats(p)
        assert stats.depth == 3
        assert stats.max_fan_in == 2
        assert stats.roots == ("a",)
        assert stats.leaves == ("d",)


class TestEvaluatePlan:
    def test_clean_plan_passes(self):
        p = plan([task("a", criteria=("at least 5 sources reviewed",)),
                  task("b", ("a",), kind="writer",
                       criteria=("all sections documented",))])
        report = evaluate_plan(p, budget=Budget())
        assert report.passed
        assert report.score == 1.0
        assert report.findings == ()

    def test_missing_quality_gates_fails(self):
        p = plan([task("a")], gates=())
        report = evaluate_plan(p)
        assert not report.passed
        assert any(f.check == "quality_gates_present" for f in report.findings)

    def test_budget_inconsistency_fails(self):
        tasks = [task(f"t{i}") for i in range(5)]
        report = evaluate_plan(plan(tasks), budget=Budget(max_agent_calls=3))
        assert not report.passed
        assert any("agent calls" in f.message for f in report.findings)

    def test_missing_criteria_warns(self):
        p = plan([task("a", criteria=()), task("b", ("a",))])
        report = evaluate_plan(p)
        assert report.passed
        assert any(f.check == "acceptance_present" and f.task_id == "a"
                   for f in report.findings)

    def test_vague_criteria_warns_with_remediation(self):
        p = plan([task("a", criteria=("make it good",))])
        report = evaluate_plan(p)
        assert any(f.check == "acceptance_measurable" for f in report.findings)
        assert any("verification verb" in r for r in report.remediation)

    def test_fully_parallel_plan_warns(self):
        p = plan([task("a"), task("b"), task("c")])
        report = evaluate_plan(p)
        assert any(f.check == "dag_connected" for f in report.findings)

    def test_single_specialist_concentration_warns(self):
        p = plan([task(f"t{i}", deps=(f"t{i-1}",) if i else ()) for i in range(4)])
        report = evaluate_plan(p)
        assert any(f.check == "specialist_diversity" for f in report.findings)

    def test_specialist_diversity_ok_when_mixed(self):
        kinds = ["literature", "data", "coder", "writer"]
        tasks = [task(f"t{i}", deps=(f"t{i-1}",) if i else (), kind=kinds[i])
                 for i in range(4)]
        report = evaluate_plan(plan(tasks))
        assert not any(f.check == "specialist_diversity" for f in report.findings)

    def test_quality_result_shape(self):
        p = plan([task("a", criteria=())], gates=())
        result = evaluate_plan(p).to_quality_result()
        assert set(result) == {"passed", "score", "findings", "remediation"}
        assert not result["passed"]

    def test_score_drops_with_findings(self):
        clean = evaluate_plan(plan([task("a")]))
        warned = evaluate_plan(plan([task("a", criteria=())]))
        failed = evaluate_plan(plan([task("a")], gates=()))
        assert clean.score == 1.0
        assert warned.score < clean.score
        assert failed.score < warned.score
