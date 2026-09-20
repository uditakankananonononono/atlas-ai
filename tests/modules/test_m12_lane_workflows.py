"""Tests for the M12 workflow engine."""

import pytest

from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_models import (
    BudgetPolicy, ModelProfile, TaskRequirements, CAP_CHAT, usd_to_micro,
)
from app.modules.m12_ai_research_lab.lane_routing import ModelRouter
from app.modules.m12_ai_research_lab.lane_workflows import (
    InMemoryStepStateStore, Workflow, WorkflowEngine, WorkflowStep,
    WorkflowValidationError,
)


def model(mid="m1", cost_in=1000, cost_out=2000):
    return ModelProfile(
        model_id=mid, provider="t", display_name=mid,
        cost_per_1k_input_micro=cost_in, cost_per_1k_output_micro=cost_out,
        capabilities=frozenset({CAP_CHAT}),
    )


def test_validate_rejects_duplicates_unknown_deps_self_dep_and_cycles():
    s = WorkflowStep("a", "k")
    with pytest.raises(WorkflowValidationError, match="duplicate"):
        Workflow("w", (s, s)).validate()
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        Workflow("w", (WorkflowStep("a", "k", depends_on=("nope",)),)).validate()
    with pytest.raises(WorkflowValidationError, match="itself"):
        Workflow("w", (WorkflowStep("a", "k", depends_on=("a",)),)).validate()
    with pytest.raises(WorkflowValidationError, match="cycle"):
        Workflow("w", (
            WorkflowStep("a", "k", depends_on=("b",)),
            WorkflowStep("b", "k", depends_on=("a",)),
        )).validate()


def test_topological_order_is_deterministic():
    steps = (
        WorkflowStep("c", "k", depends_on=("a", "b")),
        WorkflowStep("b", "k"),
        WorkflowStep("a", "k"),
        WorkflowStep("d", "k", depends_on=("c",)),
    )
    order1 = [s.step_id for s in Workflow("w", steps).validate()]
    order2 = [s.step_id for s in Workflow("w", tuple(reversed(steps))).validate()]
    assert order1 == order2 == ["a", "b", "c", "d"]


def test_engine_executes_in_order_and_threads_dependency_outputs():
    seen = []

    def make(name):
        def fn(params, ctx):
            seen.append((name, dict(ctx.dependency_outputs)))
            return {name: params.get("v", 1)}
        return fn

    wf = Workflow("pipe", (
        WorkflowStep("first", "a", params={"v": 10}),
        WorkflowStep("second", "b", depends_on=("first",)),
    ))
    eng = WorkflowEngine({"a": make("first"), "b": make("second")})
    res = eng.run(wf, run_id="r1")
    assert res.status == "completed"
    assert seen[0] == ("first", {})
    assert seen[1][1]["first"] == {"first": 10}
    assert res.outputs["second"] == {"second": 1}
    assert [e.event for e in res.journal].count("step_completed") == 2


def test_engine_retries_then_succeeds():
    calls = {"n": 0}

    def flaky(params, ctx):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    wf = Workflow("w", (WorkflowStep("s", "flaky", max_retries=2),))
    res = WorkflowEngine({"flaky": flaky}).run(wf)
    assert res.status == "completed"
    assert calls["n"] == 3
    assert res.steps[0].attempts == 3
    assert sum(1 for e in res.journal if e.event == "retry") == 2


def test_engine_fails_after_bounded_retries():
    def always(params, ctx):
        raise RuntimeError("boom")

    wf = Workflow("w", (WorkflowStep("s", "x", max_retries=1),))
    res = WorkflowEngine({"x": always}).run(wf)
    assert res.status == "failed"
    assert res.failed_step_id == "s"
    assert res.steps[0].attempts == 2
    assert "boom" in (res.steps[0].error or "")


def test_missing_executor_fails_cleanly():
    wf = Workflow("w", (WorkflowStep("s", "ghost"),))
    res = WorkflowEngine({"other": lambda p, c: None}).run(wf)
    assert res.status == "failed"
    assert "no executor" in res.journal[-1].detail


def test_routing_and_budget_integration_records_exact_cost():
    router = ModelRouter([model(cost_in=1_000_000, cost_out=2_000_000)])
    ledger = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(10)))

    def llm(params, ctx):
        assert ctx.model is not None and ctx.model.model_id == "m1"
        ctx.record_usage(100, 50)  # $0.10 + $0.10 = 200_000 micro
        return "answer"

    wf = Workflow("w", (
        WorkflowStep("gen", "llm", route_requirements=TaskRequirements()),
    ))
    eng = WorkflowEngine({"llm": llm}, router=router, ledger=ledger)
    res = eng.run(wf, run_id="rb")
    assert res.status == "completed"
    step = res.steps[0]
    assert step.model_id == "m1"
    assert step.cost_micro == 200_000
    assert res.total_cost_micro == 200_000
    st = ledger.status()
    assert st.spent_today_micro == 200_000
    assert st.reserved_micro == 0


def test_budget_exhaustion_fails_run_without_spend():
    router = ModelRouter([model(cost_in=1_000_000_000, cost_out=1_000_000_000)])
    ledger = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(0.001)))

    def llm(params, ctx):
        raise AssertionError("must not execute when reservation fails")

    wf = Workflow("w", (
        WorkflowStep("gen", "llm",
                     route_requirements=TaskRequirements(
                         estimated_input_tokens=1000, estimated_output_tokens=1000)),
    ))
    eng = WorkflowEngine({"llm": llm}, router=router, ledger=ledger)
    res = eng.run(wf, run_id="rb2")
    assert res.status == "failed"
    assert "budget reservation failed" in res.journal[-1].detail
    assert ledger.status().spent_today_micro == 0


def test_resume_skips_completed_steps_without_reexecution():
    state = InMemoryStepStateStore()
    calls = {"a": 0, "b": 0}

    def a(params, ctx):
        calls["a"] += 1
        return "A"

    def b(params, ctx):
        calls["b"] += 1
        if calls["b"] == 1:
            raise RuntimeError("crash")
        return "B"

    wf = Workflow("w", (
        WorkflowStep("a", "a", max_retries=0),
        WorkflowStep("b", "b", depends_on=("a",), max_retries=0),
    ))
    eng = WorkflowEngine({"a": a, "b": b}, state_store=state)
    first = eng.run(wf, run_id="resume-me")
    assert first.status == "failed"
    assert calls == {"a": 1, "b": 1}

    second = eng.run(wf, run_id="resume-me")  # same run_id resumes
    assert second.status == "completed"
    assert calls == {"a": 1, "b": 2}  # step a NOT re-executed
    assert second.steps[0].status == "skipped"
    assert second.outputs["a"] == "A"
    assert second.outputs["b"] == "B"


def test_step_records_carry_hashes():
    wf = Workflow("w", (WorkflowStep("s", "k", params={"x": 1}),))
    res = WorkflowEngine({"k": lambda p, c: {"y": 2}}).run(wf, run_id="rh")
    rec = res.steps[0]
    assert rec.input_hash and len(rec.input_hash) == 64
    assert rec.output_hash and len(rec.output_hash) == 64
