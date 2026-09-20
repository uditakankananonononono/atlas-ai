"""Tests for the Module 14 budget ledger."""

import pytest

from app.modules.m14_project_builder.budgets import (
    BudgetError,
    BudgetExceeded,
    BudgetLedger,
    BudgetLimits,
)


@pytest.fixture
def ledger():
    return BudgetLedger(BudgetLimits(
        max_iterations=2, max_agent_calls=3,
        max_runtime_seconds=100, max_cost_usd=1.0,
    ))


class TestLimits:
    def test_invalid_limits_rejected(self):
        with pytest.raises(BudgetError):
            BudgetLimits(max_iterations=0)
        with pytest.raises(BudgetError):
            BudgetLimits(max_agent_calls=0)
        with pytest.raises(BudgetError):
            BudgetLimits(max_runtime_seconds=0)
        with pytest.raises(BudgetError):
            BudgetLimits(max_cost_usd=-1)


class TestIterations:
    def test_up_to_limit_ok(self, ledger):
        ledger.record_iteration("pass 1")
        ledger.record_iteration("pass 2")
        with pytest.raises(BudgetExceeded) as exc:
            ledger.record_iteration("pass 3")
        assert exc.value.dimension == "iterations"
        assert exc.value.limit == 2 and exc.value.attempted == 3

    def test_failed_record_does_not_consume(self, ledger):
        ledger.record_iteration()
        ledger.record_iteration()
        with pytest.raises(BudgetExceeded):
            ledger.record_iteration()
        assert ledger.status().iterations_used == 2


class TestAgentCallsAndCost:
    def test_call_cap(self, ledger):
        for _ in range(3):
            ledger.record_agent_call()
        with pytest.raises(BudgetExceeded) as exc:
            ledger.record_agent_call()
        assert exc.value.dimension == "agent_calls"

    def test_cost_cap_shared_with_calls(self, ledger):
        ledger.record_agent_call(cost_usd=0.6)
        with pytest.raises(BudgetExceeded) as exc:
            ledger.record_agent_call(cost_usd=0.5)
        assert exc.value.dimension == "cost_usd"
        assert ledger.status().cost_usd_used == pytest.approx(0.6)

    def test_negative_cost_rejected(self, ledger):
        with pytest.raises(BudgetError):
            ledger.record_agent_call(cost_usd=-0.1)

    def test_zero_cost_budget_allows_free_calls(self):
        free = BudgetLedger(BudgetLimits(max_cost_usd=0))
        free.record_agent_call(cost_usd=0.0)
        with pytest.raises(BudgetExceeded):
            free.record_agent_call(cost_usd=0.01)


class TestRuntime:
    def test_runtime_cap(self, ledger):
        ledger.record_runtime(60)
        with pytest.raises(BudgetExceeded) as exc:
            ledger.record_runtime(50)
        assert exc.value.dimension == "runtime_seconds"
        assert ledger.status().runtime_seconds_used == 60

    def test_negative_runtime_rejected(self, ledger):
        with pytest.raises(BudgetError):
            ledger.record_runtime(-5)


class TestStatus:
    def test_remaining_counts(self, ledger):
        ledger.record_iteration()
        ledger.record_agent_call(cost_usd=0.25)
        ledger.record_runtime(40)
        status = ledger.status()
        assert status.iterations_remaining == 1
        assert status.agent_calls_remaining == 2
        assert status.runtime_seconds_remaining == 60
        assert status.cost_usd_remaining == pytest.approx(0.75)
        assert not status.exhausted
        assert status.exhausted_dimensions == ()

    def test_exhausted_dimensions_listed(self, ledger):
        ledger.record_iteration()
        ledger.record_iteration()
        status = ledger.status()
        assert status.exhausted
        assert status.exhausted_dimensions == ("iterations",)


class TestPreflightAndEvents:
    def test_can_afford_call(self, ledger):
        assert ledger.can_afford_call(estimated_cost_usd=1.0)
        assert not ledger.can_afford_call(estimated_cost_usd=1.01)
        with pytest.raises(BudgetError):
            ledger.can_afford_call(estimated_cost_usd=-1)

    def test_event_log_records_everything(self, ledger):
        ledger.record_iteration("plan")
        ledger.record_agent_call(cost_usd=0.5, note="literature")
        ledger.record_runtime(10, "task lit")
        events = ledger.events()
        kinds = [e.dimension for e in events]
        assert kinds == ["iterations", "agent_calls", "cost_usd", "runtime_seconds"]
        assert all(e.at for e in events)
        assert events[1].note == "literature"
