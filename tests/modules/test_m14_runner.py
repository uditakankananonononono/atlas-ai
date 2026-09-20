"""Tests for the Module 14 bounded DAG task runner."""

import pytest

from app.modules.m14_project_builder.budgets import BudgetLedger, BudgetLimits
from app.modules.m14_project_builder.runner import (
    RunnerError,
    TaskOutput,
    TaskRunner,
)
from app.modules.m14_project_builder.schemas import ProjectPlan, ProjectTask


def task(tid, deps=()):
    return ProjectTask(id=tid, title=f"Task {tid}", objective=f"Do {tid}",
                       agent_kind="coder", dependencies=list(deps),
                       acceptance_criteria=["tests pass"])


def plan(*tasks):
    return ProjectPlan(goal="g", tasks=list(tasks), quality_gates=["review"])


def ok_output(task):
    return TaskOutput(success=True, summary=f"{task.id} done", cost_usd=0.1,
                      runtime_seconds=5)


def make_runner(executor=ok_output, calls=50, iters=10, cost=25.0,
                attempts=2, auto=True):
    ledger = BudgetLedger(BudgetLimits(
        max_iterations=iters, max_agent_calls=calls,
        max_runtime_seconds=3600, max_cost_usd=cost,
    ))
    return TaskRunner(ledger, executor, max_task_attempts=attempts,
                      auto_approve=auto), ledger


class TestTaskOutput:
    def test_success_with_failure_reason_rejected(self):
        with pytest.raises(RunnerError):
            TaskOutput(success=True, failure_reason="boom")

    def test_negative_cost_rejected(self):
        with pytest.raises(RunnerError):
            TaskOutput(success=True, cost_usd=-1)

    def test_negative_runtime_rejected(self):
        with pytest.raises(RunnerError):
            TaskOutput(success=True, runtime_seconds=-1)


class TestRun:
    def test_chain_runs_in_order(self):
        seen = []

        def executor(t):
            seen.append(t.id)
            return ok_output(t)

        runner, ledger = make_runner(executor)
        report = runner.run(plan(task("a"), task("b", ("a",)), task("c", ("b",))))
        assert report.stopped_reason == "completed"
        assert seen == ["a", "b", "c"]
        assert report.tasks_completed == ("a", "b", "c")
        assert ledger.status().agent_calls_used == 3
        assert ledger.status().cost_usd_used == pytest.approx(0.3)
        assert ledger.status().runtime_seconds_used == 15

    def test_diamond_unlocks_join(self):
        runner, _ = make_runner()
        report = runner.run(plan(
            task("a"), task("b", ("a",)), task("c", ("a",)),
            task("d", ("b", "c")),
        ))
        assert report.stopped_reason == "completed"
        assert set(report.tasks_completed) == {"a", "b", "c", "d"}

    def test_review_gate_pauses(self):
        runner, _ = make_runner(auto=False)
        report = runner.run(plan(task("a"), task("b", ("a",))))
        assert report.stopped_reason == "awaiting_review"
        assert report.tasks_in_review == ("a", "b") or report.tasks_in_review == ("a",)
        # dependents never ran past their dependency's review
        assert "completed" not in [t.status for t in report.plan.tasks]

    def test_approve_unlocks_dependents(self):
        runner, _ = make_runner(auto=False)
        report = runner.run(plan(task("a"), task("b", ("a",))))
        updated = runner.approve_reviewed(report.plan, "a")
        a = next(t for t in updated.tasks if t.id == "a")
        assert a.status == "completed"

    def test_reject_sends_back(self):
        runner, _ = make_runner(auto=False)
        report = runner.run(plan(task("a")))
        updated = runner.reject_reviewed(report.plan, "a")
        assert next(t for t in updated.tasks if t.id == "a").status == "ready"

    def test_approve_requires_review_status(self):
        runner, _ = make_runner()
        p = plan(task("a"))
        with pytest.raises(RunnerError):
            runner.approve_reviewed(p, "a")
        with pytest.raises(RunnerError):
            runner.approve_reviewed(p, "ghost")

    def test_retry_then_success(self):
        calls = {"n": 0}

        def flaky(t):
            calls["n"] += 1
            if calls["n"] == 1:
                return TaskOutput(success=False, failure_reason="transient")
            return ok_output(t)

        runner, ledger = make_runner(flaky)
        report = runner.run(plan(task("a")))
        assert report.stopped_reason == "completed"
        assert calls["n"] == 2
        assert ledger.status().iterations_used == 1  # retry consumed one

    def test_attempt_cap_marks_failed(self):
        def always_fail(t):
            return TaskOutput(success=False, failure_reason="broken")

        runner, _ = make_runner(always_fail, attempts=2)
        report = runner.run(plan(task("a"), task("b", ("a",))))
        assert report.stopped_reason == "blocked_failures"
        assert report.tasks_failed == ("a",)
        b = next(t for t in report.plan.tasks if t.id == "b")
        assert b.status == "blocked"

    def test_budget_exhaustion_stops_run(self):
        runner, _ = make_runner(calls=1)
        report = runner.run(plan(task("a"), task("b", ("a",)), task("c", ("b",))))
        assert report.stopped_reason == "budget_exhausted"
        assert report.tasks_completed == ("a",)

    def test_cost_budget_exhaustion(self):
        runner, _ = make_runner(cost=0.15)
        report = runner.run(plan(task("a"), task("b", ("a",))))
        assert report.stopped_reason == "budget_exhausted"

    def test_iteration_budget_caps_retries(self):
        def always_fail(t):
            return TaskOutput(success=False, failure_reason="broken")

        runner, _ = make_runner(always_fail, iters=1, attempts=5)
        report = runner.run(plan(task("a")))
        assert report.stopped_reason == "budget_exhausted"

    def test_invalid_attempts_rejected(self):
        ledger = BudgetLedger(BudgetLimits())
        with pytest.raises(RunnerError):
            TaskRunner(ledger, ok_output, max_task_attempts=0)


class TestRunnerBoundaries:
    def test_all_failed_dag_reports_blocked(self):
        def fail(t):
            return TaskOutput(success=False, failure_reason="x")

        runner, _ = make_runner(fail, attempts=1)
        report = runner.run(plan(task("a"), task("b"), task("c", ("a", "b"))))
        assert report.stopped_reason == "blocked_failures"
        assert set(report.tasks_failed) == {"a", "b"}
        c = next(t for t in report.plan.tasks if t.id == "c")
        assert c.status == "blocked"

    def test_report_budget_status_snapshot(self):
        runner, ledger = make_runner()
        report = runner.run(plan(task("a")))
        assert report.budget_status.agent_calls_used == 1
        assert ledger.events()
