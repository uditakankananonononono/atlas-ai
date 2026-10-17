"""Durable pre-effect budget hold (real SQLite, simulated process crash; no live provider)."""
import sqlite3
import pytest
from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger, BudgetExceeded
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy, usd_to_micro
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from test_m12_lane_unknown_outcome import routed_engine


def _eng(path, ex, limit=usd_to_micro(10)):
    st = SQLiteLabStore(path)
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=limit), store=st)
    eng, _, wf = routed_engine(ex, store=st, ledger=led)
    return eng, led, wf, st


def _est(wf):
    from dataclasses import replace
    from app.modules.m12_ai_research_lab.lane_models import TaskRequirements
    from app.modules.m12_ai_research_lab.lane_workflows import Workflow, WorkflowStep
    return Workflow("w", (WorkflowStep("a", "echo"),
        WorkflowStep("b", "send", depends_on=("a",), max_retries=3,
                     route_requirements=TaskRequirements(estimated_input_tokens=1000, estimated_output_tokens=1000))))


def test_hold_survives_crash_and_still_counts_against_cap_in_new_process(tmp_path):
    path = str(tmp_path / "h.db"); calls = []

    def send(p, c):
        calls.append(1); c.record_usage(10, 5); raise SystemExit("died mid-effect")

    eng, led, wf, st = _eng(path, send)
    wf = _est(wf)
    try:
        eng.run(wf, run_id="h1")
    except BaseException:
        pass
    held = st.list_holds()
    assert list(held) == ["h1:b"] and held["h1:b"] > 0
    assert st.spend_by_run("h1:b") == 0
    st.close()
    st2 = SQLiteLabStore(path)
    led2 = BudgetLedger(BudgetPolicy(daily_limit_micro=held["h1:b"] + 5), store=st2)
    assert led2.status().reserved_micro == held["h1:b"]
    with pytest.raises(BudgetExceeded):          # cap not freed by the crash
        led2.reserve("other", 10)
    st2.close()


def test_rerun_after_crash_makes_no_new_paid_call(tmp_path):
    path = str(tmp_path / "r.db"); calls = []

    def send(p, c):
        calls.append(1); raise SystemExit("died")

    eng, _, wf, st = _eng(path, send)
    try:
        eng.run(wf, run_id="h2")
    except BaseException:
        pass
    st.close()
    eng2, _, wf2, st2 = _eng(path, send)
    res = eng2.run(wf2, run_id="h2")
    assert res.status == "failed" and len(calls) == 1
    assert list(st2.list_holds()) == ["h2:b"]     # hold kept until explicit reconcile
    st2.close()


def test_explicit_reconcile_release_drops_durable_hold(tmp_path):
    path = str(tmp_path / "x.db")

    def send(p, c):
        raise SystemExit("died")

    eng, _, wf, st = _eng(path, send)
    try:
        eng.run(wf, run_id="h3")
    except BaseException:
        pass
    st.close()
    eng2, led2, wf2, st2 = _eng(path, send)
    view = eng2.inspect_claim("h3", "b")
    eng2.take_over_pending_claim("h3", "b", expected_generation=view.generation, acknowledge_inflight_effect_may_still_complete=True)
    view = eng2.inspect_claim("h3", "b")
    eng2.authorize_retry_after_reconciliation(
        "h3", "b", expected_generation=view.generation,
        confirm_effect_did_not_occur=True, release_budget_hold=True)
    assert st2.list_holds() == {} and led2.status().reserved_micro == 0
    st2.close()


def test_hold_write_failure_fails_closed_executor_never_runs():
    calls = []

    class NoHold(SQLiteLabStore):
        def reserve_hold(self, run_id, amount_micro, check):
            raise RuntimeError("disk")

    st = NoHold(":memory:")
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(10)), store=st)
    eng, _, wf = routed_engine(lambda p, c: calls.append(1), store=st, ledger=led)
    try:
        eng.run(wf, run_id="h4")
    except Exception:
        pass
    assert calls == []


def test_booking_is_atomic_spend_and_hold_removal(tmp_path):
    st = SQLiteLabStore(str(tmp_path / "a.db"))
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=1000), store=st)
    led.reserve("k", 100)
    led.record_incurred("k", 5000)
    assert st.list_holds() == {} and st.spend_by_run("k") == 5000
    led.reserve("m", 1) if False else None
    with pytest.raises(BudgetExceeded):
        led.reserve("n", 1)                       # over cap stays refused after accounting
    st.close()


def test_old_db_without_hold_table_upgrades(tmp_path):
    p = str(tmp_path / "o.db")
    c = sqlite3.connect(p); c.execute("CREATE TABLE spend(entry_id TEXT PRIMARY KEY, run_id TEXT, amount_micro INTEGER, ts_utc TEXT)")
    c.execute("INSERT INTO spend VALUES('e','r',7,'2000-01-01T00:00:00+00:00')"); c.commit(); c.close()
    st = SQLiteLabStore(p)
    assert st.list_holds() == {} and st.spend_by_run("r") == 7
    st.close()


def test_in_memory_store_behaviour_unchanged():
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    led.reserve("a", 60)
    with pytest.raises(BudgetExceeded):
        led.reserve("b", 60)
    led.release("a"); led.reserve("b", 60)
