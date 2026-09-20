"""Tests for M12 budget ledger and policy."""

from datetime import datetime, timezone

import pytest

from app.modules.m12_ai_research_lab.lane_budgets import (
    BudgetExceeded, BudgetLedger, InMemorySpendStore,
)
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy, usd_to_micro

CLOCK = datetime(2026, 9, 20, 15, 30, tzinfo=timezone.utc)


def make(**policy_kwargs):
    return BudgetLedger(BudgetPolicy(**policy_kwargs), clock=lambda: CLOCK)


def test_reserve_commit_flow_counts_spend_once():
    led = make(daily_limit_micro=usd_to_micro(10))
    led.reserve("run-1", usd_to_micro(1))
    led.commit("run-1", usd_to_micro(0.8))
    st = led.status()
    assert st.spent_today_micro == usd_to_micro(0.8)
    assert st.reserved_micro == 0
    assert st.daily_remaining_micro == usd_to_micro(10) - usd_to_micro(0.8)


def test_reservation_blocks_overspend_by_other_runs():
    led = make(daily_limit_micro=usd_to_micro(1))
    led.reserve("run-1", usd_to_micro(0.7))
    with pytest.raises(BudgetExceeded) as exc:
        led.reserve("run-2", usd_to_micro(0.5))
    assert exc.value.scope == "daily"
    # The reserving run itself can still commit up to policy limits.
    led.commit("run-1", usd_to_micro(0.7))


def test_release_frees_capacity():
    led = make(daily_limit_micro=usd_to_micro(1))
    led.reserve("run-1", usd_to_micro(0.9))
    led.release("run-1")
    led.reserve("run-2", usd_to_micro(0.9))  # would have raised without release
    led.release("run-2")  # idempotent
    led.release("run-2")


def test_per_run_limit_enforced():
    led = make(per_run_limit_micro=usd_to_micro(0.5))
    with pytest.raises(BudgetExceeded) as exc:
        led.reserve("run-1", usd_to_micro(0.6))
    assert exc.value.scope == "per_run"
    led.reserve("run-1", usd_to_micro(0.5))


def test_monthly_limit_enforced_across_days():
    store = InMemorySpendStore()
    clock = lambda: CLOCK
    led = BudgetLedger(
        BudgetPolicy(monthly_limit_micro=usd_to_micro(1)), store=store, clock=clock
    )
    # Simulate earlier spend this month (different day).
    store.add_spend("e0", "old-run", usd_to_micro(0.9), "2026-09-01T00:00:00+00:00")
    with pytest.raises(BudgetExceeded) as exc:
        led.reserve("run-1", usd_to_micro(0.2))
    assert exc.value.scope == "monthly"


def test_day_window_isolated_from_month_window():
    store = InMemorySpendStore()
    led = BudgetLedger(
        BudgetPolicy(daily_limit_micro=usd_to_micro(1),
                     monthly_limit_micro=usd_to_micro(100)),
        store=store, clock=lambda: CLOCK,
    )
    store.add_spend("e0", "old", usd_to_micro(50), "2026-09-01T00:00:00+00:00")
    led.reserve("run-1", usd_to_micro(0.9))  # daily fresh, monthly fine
    led.commit("run-1", usd_to_micro(0.9))


def test_double_reserve_rejected():
    led = make()
    led.reserve("run-1", 100)
    with pytest.raises(ValueError):
        led.reserve("run-1", 100)


def test_commit_rechecks_limits_against_actual():
    led = make(daily_limit_micro=usd_to_micro(1))
    led.reserve("run-1", usd_to_micro(0.4))
    with pytest.raises(BudgetExceeded):
        led.commit("run-1", usd_to_micro(2))


def test_warnings_fire_near_threshold():
    led = make(daily_limit_micro=usd_to_micro(1), warn_fraction=0.8)
    led.reserve("run-1", usd_to_micro(0.85))
    st = led.status()
    assert "daily spend at or above warn threshold" in st.warnings
    led.release("run-1")
    assert led.status().warnings == ()


def test_spend_outside_window_not_counted():
    store = InMemorySpendStore()
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(1)),
                       store=store, clock=lambda: CLOCK)
    store.add_spend("old", "r", usd_to_micro(5), "2026-08-31T23:59:59+00:00")
    led.reserve("run-1", usd_to_micro(0.9))  # yesterday's spend irrelevant to daily


def test_policy_validation():
    with pytest.raises(ValueError):
        BudgetPolicy(daily_limit_micro=0)
    with pytest.raises(ValueError):
        BudgetPolicy(warn_fraction=1.5)


def test_negative_amounts_rejected():
    led = make()
    with pytest.raises(ValueError):
        led.reserve("run-1", -1)
    led.reserve("run-1", 10)
    with pytest.raises(ValueError):
        led.commit("run-1", -1)
