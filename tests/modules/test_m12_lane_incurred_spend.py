"""Spend already consumed is booked as incurred, even when a limit or the ledger refuses commit.
Stub executors only; simulation, not a live provider."""
import pytest

from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy, usd_to_micro
from test_m12_lane_unknown_outcome import routed_engine


def test_record_incurred_books_past_limit_and_clears_reservation():
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    led.reserve("r", 50)
    led.record_incurred("r", 500)
    st = led.status()
    assert st.spent_today_micro == 500 and st.reserved_micro == 0
    assert st.daily_remaining_micro == -400


@pytest.mark.parametrize("bad", [-1, 1.5, True, "3", None])
def test_record_incurred_validates(bad):
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    with pytest.raises(ValueError):
        led.record_incurred("r", bad)


def test_exhausted_failure_after_usage_books_spend_not_zero():
    def send(p, c):
        c.record_usage(10, 5)
        raise RuntimeError("plain")

    eng, ledger, wf = routed_engine(send)
    res = eng.run(wf, run_id="i1")
    rec = {s.step_id: s for s in res.steps}["b"]
    assert rec.status == "failed" and rec.attempts == 4
    assert ledger.status().reserved_micro == 0
    assert ledger.status().spent_today_micro > 0
    assert rec.cost_micro == ledger.status().spent_today_micro


def test_exhausted_failure_without_usage_books_nothing():
    def send(p, c):
        raise RuntimeError("plain")

    eng, ledger, wf = routed_engine(send)
    res = eng.run(wf, run_id="i2")
    assert {s.step_id: s for s in res.steps}["b"].cost_micro == 0
    st = ledger.status()
    assert st.spent_today_micro == 0 and st.reserved_micro == 0


def test_commit_refusal_books_incurred_and_still_blocks_rerun():
    calls = []

    class RefusingLedger(BudgetLedger):
        def commit(self, run_id, actual_micro):
            raise RuntimeError("limit exceeded")

    def send(p, c):
        calls.append(1)
        c.record_usage(10, 5)
        return {"ok": True}

    ledger = RefusingLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(10)))
    eng, _, wf = routed_engine(send, ledger=ledger)
    res = eng.run(wf, run_id="i3")
    assert res.status == "failed" and "micro booked)" in str(res) and "NOT booked" not in str(res)
    assert ledger.status().spent_today_micro > 0 and ledger.status().reserved_micro == 0
    eng.run(wf, run_id="i3")
    assert len(calls) == 1   # not silently repeated (and not paid for twice)


def test_commit_refusal_and_booking_failure_is_reported_not_hidden():
    class Broken(BudgetLedger):
        def commit(self, run_id, actual_micro):
            raise RuntimeError("x")

        def record_incurred(self, run_id, actual_micro):
            raise RuntimeError("y")

    def send(p, c):
        c.record_usage(10, 5)
        return 1

    eng, ledger, wf = routed_engine(send, ledger=Broken(BudgetPolicy(daily_limit_micro=usd_to_micro(10))))
    res = eng.run(wf, run_id="i4")
    assert res.status == "failed"
    assert "NOT booked" in str(res)


# ---- real SQLite store: crash windows and caller boundary ----
import inspect, re
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from app.modules.m12_ai_research_lab import lane_workflows as lw


def _engine_on(path, executor, ledger_cls=BudgetLedger):
    store = SQLiteLabStore(path)
    led = ledger_cls(BudgetPolicy(daily_limit_micro=usd_to_micro(10)), store=store)
    eng, _, wf = routed_engine(executor, store=store, ledger=led)
    return eng, led, wf, store


def test_sqlite_commit_refusal_spend_persists_once_and_rerun_blocked_in_new_process(tmp_path):
    path = str(tmp_path / "s.db")
    calls = []

    class Refuse(BudgetLedger):
        def commit(self, run_id, actual_micro):
            raise RuntimeError("refused")

    def send(p, c):
        calls.append(1)
        c.record_usage(10, 5)
        return 1

    eng, led, wf, st = _engine_on(path, send, Refuse)
    eng.run(wf, run_id="q1")
    spent = st.spend_by_run("q1:b")
    assert spent > 0 and len(calls) == 1
    st.close()
    eng2, led2, wf2, st2 = _engine_on(path, send)
    res = eng2.run(wf2, run_id="q1")
    assert len(calls) == 1 and res.status == "failed"
    assert st2.spend_by_run("q1:b") == spent          # not double booked
    st2.close()


def test_sqlite_crash_after_booking_before_checkpoint_keeps_claim_and_spend(tmp_path):
    path = str(tmp_path / "c.db")
    calls = []

    class Crash(BudgetLedger):
        def commit(self, run_id, actual_micro):
            raise RuntimeError("refused")

        def record_incurred(self, run_id, actual_micro):
            super().record_incurred(run_id, actual_micro)
            raise SystemExit("crash after booking")

    def send(p, c):
        calls.append(1)
        c.record_usage(10, 5)
        return 1

    eng, led, wf, st = _engine_on(path, send, Crash)
    try:
        eng.run(wf, run_id="q2")
    except BaseException:
        pass
    spent = st.spend_by_run("q2:b")
    st.close()
    eng2, _, wf2, st2 = _engine_on(path, send)
    eng2.run(wf2, run_id="q2")
    assert spent > 0 and len(calls) == 1               # pending claim blocked a second provider attempt
    assert st2.spend_by_run("q2:b") == spent
    st2.close()


def test_crash_before_booking_leaves_spend_unbooked_but_rerun_blocked(tmp_path):
    """Documented limit: usage consumed but the process died before any booking."""
    path = str(tmp_path / "d.db")
    calls = []

    def send(p, c):
        calls.append(1)
        c.record_usage(10, 5)
        raise SystemExit("process died mid-step")

    eng, led, wf, st = _engine_on(path, send)
    try:
        eng.run(wf, run_id="q3")
    except BaseException:
        pass
    assert st.spend_by_run("q3:b") == 0               # unbooked: known accounting gap
    st.close()
    eng2, _, wf2, st2 = _engine_on(path, send)
    eng2.run(wf2, run_id="q3")
    assert len(calls) == 1
    st2.close()


def test_record_incurred_only_called_after_executor_in_engine_source():
    src = inspect.getsource(lw)
    ex = src.index("output = executor(")
    for m in re.finditer(r"record_incurred\(", src):
        assert m.start() > ex
    import app.modules.m12_ai_research_lab as pkg, pathlib
    callers = [p.name for p in pathlib.Path(pkg.__file__).parent.glob("*.py")
               if "record_incurred(" in p.read_text() and p.name != "lane_budgets.py"]
    assert callers == ["lane_workflows.py"]


def test_record_incurred_never_reserves_or_authorizes_new_spend():
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=100))
    led.record_incurred("r", 500)                     # over limit, accounted
    with pytest.raises(Exception):                    # but new pre-effect authorization still refused
        led.reserve("r2", 1)
