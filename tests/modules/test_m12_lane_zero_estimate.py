"""A priced model under a limited budget with a zero cost estimate must be refused
before the step claim and before the executor runs. Free models and unlimited
budgets keep working."""

import pytest

from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_models import (
    BudgetPolicy, ModelProfile, TaskRequirements, CAP_CHAT, usd_to_micro,
)
from app.modules.m12_ai_research_lab.lane_routing import ModelRouter
from app.modules.m12_ai_research_lab.lane_workflows import Workflow, WorkflowEngine, WorkflowStep


def model(cost_in, cost_out, mid="m1"):
    return ModelProfile(model_id=mid, provider="t", display_name=mid,
                        cost_per_1k_input_micro=cost_in, cost_per_1k_output_micro=cost_out,
                        capabilities=frozenset({CAP_CHAT}))


def run(m, policy, req, with_ledger=True):
    calls = []
    reserved_during = []

    def llm(params, ctx):
        calls.append(1)
        if ledger is not None:
            reserved_during.append(ledger.status().reserved_micro)
        ctx.record_usage(10, 10)
        return "ok"

    ledger = BudgetLedger(policy) if with_ledger else None
    eng = WorkflowEngine({"llm": llm}, router=ModelRouter([m]), ledger=ledger)
    wf = Workflow("w", (WorkflowStep("gen", "llm", route_requirements=req),))
    return eng.run(wf, run_id="r1"), calls, ledger, reserved_during


PRICED = dict(cost_in=1_000_000, cost_out=2_000_000)


@pytest.mark.parametrize("policy", [
    BudgetPolicy(daily_limit_micro=usd_to_micro(10)),
    BudgetPolicy(monthly_limit_micro=usd_to_micro(10)),
    BudgetPolicy(per_run_limit_micro=usd_to_micro(10)),
])
def test_priced_model_zero_estimate_limited_budget_refused_before_effect(policy):
    res, calls, ledger, _ = run(model(**PRICED), policy, TaskRequirements())
    assert res.status == "failed"
    assert calls == []
    assert ledger.status().reserved_micro == 0 and ledger.status().spent_today_micro == 0
    assert "estimate" in str(res.journal[-1].detail if hasattr(res.journal[-1], "detail") else res.journal[-1])


def test_free_model_zero_estimate_still_runs():
    res, calls, _, _ = run(model(0, 0), BudgetPolicy(daily_limit_micro=usd_to_micro(10)), TaskRequirements())
    assert res.status == "completed" and calls == [1]


def test_unlimited_budget_zero_estimate_still_runs():
    res, calls, _, _ = run(model(**PRICED), BudgetPolicy(), TaskRequirements())
    assert res.status == "completed" and calls == [1]


def test_no_ledger_zero_estimate_still_runs():
    res, calls, _, _ = run(model(**PRICED), BudgetPolicy(), TaskRequirements(), with_ledger=False)
    assert res.status == "completed" and calls == [1]


def test_real_estimate_limited_budget_runs():
    req = TaskRequirements(estimated_input_tokens=100, estimated_output_tokens=50)
    res, calls, ledger, reserved_during = run(
        model(**PRICED), BudgetPolicy(daily_limit_micro=usd_to_micro(10)), req)
    assert res.status == "completed" and calls == [1]
    # reserve-then-release proven: positive hold observed inside the executor
    # call, zero after the run commits/releases.
    assert reserved_during == [200_000]  # 1M*100/1000 + 2M*50/1000
    assert ledger.status().reserved_micro == 0


def test_asymmetric_output_only_priced_zero_estimate_refused_before_effect():
    # The peer suite prices BOTH sides (cost_in=1M, cost_out=2M), so OR and AND
    # are indistinguishable there. cost_in=0 / cost_out=2M separates them:
    # priced under OR, unpriced under AND. Refused before executor, no hold.
    res, calls, ledger, _ = run(
        model(0, 2_000_000), BudgetPolicy(daily_limit_micro=usd_to_micro(10)), TaskRequirements())
    assert res.status == "failed"
    assert calls == []
    assert ledger.status().reserved_micro == 0 and ledger.status().spent_today_micro == 0
