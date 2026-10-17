"""Hold ownership, partial-capability stores, hold validation, exhaustion booking failure,
concurrent first open. Real sqlite scratch files, stub executors, no provider."""
import sqlite3, sys
import pytest
from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger, BudgetExceeded
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy, usd_to_micro
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from test_m12_lane_unknown_outcome import routed_engine
from test_m12_lane_multiprocess_hold import run_py


def two(tmp_path, cap=100):
    p = str(tmp_path / "o.db")
    sa, sb = SQLiteLabStore(p), SQLiteLabStore(p)
    return (BudgetLedger(BudgetPolicy(daily_limit_micro=cap), store=sa),
            BudgetLedger(BudgetPolicy(daily_limit_micro=cap), store=sb), sa, sb)


def test_foreign_release_does_not_drop_live_hold(tmp_path):
    a, b, sa, sb = two(tmp_path)
    a.reserve("r", 60)
    b.release("r")
    assert sa.list_holds() == {"r": 60}
    with pytest.raises(BudgetExceeded):
        b.reserve("x", 60)


def test_foreign_commit_and_incurred_book_spend_but_keep_foreign_hold(tmp_path):
    a, b, sa, sb = two(tmp_path, cap=10**6)
    a.reserve("r", 60)
    b.record_incurred("r", 5)
    assert sa.list_holds() == {"r": 60} and sa.spend_by_run("r") == 5
    b.commit("r", 7)
    assert sa.list_holds() == {"r": 60} and sa.spend_by_run("r") == 12
    a.commit("r", 1)                                   # owner commit drops its own hold
    assert sa.list_holds() == {}


def test_explicit_takeover_release_may_drop_foreign_hold(tmp_path):
    a, b, sa, sb = two(tmp_path)
    a.reserve("r", 60)
    b.release("r", takeover=True)
    assert sa.list_holds() == {}


def test_owner_release_and_own_commit_still_work(tmp_path):
    a, b, sa, sb = two(tmp_path)
    a.reserve("r", 60); a.release("r"); assert sa.list_holds() == {}
    a.reserve("q", 60); a.commit("q", 10); assert sa.list_holds() == {} and sa.spend_by_run("q") == 10


def test_partial_capability_store_is_not_treated_as_durable_no_double_count(tmp_path):
    class Mixed(SQLiteLabStore):
        book_and_drop_hold = None
        def add_spend(self, *a):
            super().add_spend(*a); raise SystemExit("crash after spend insert")
    p = str(tmp_path / "m.db")
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=100), store=Mixed(p))
    assert led.durable_holds is False
    led.reserve("k", 40)
    try:
        led.commit("k", 40)
    except BaseException:
        pass
    st = BudgetLedger(BudgetPolicy(daily_limit_micro=100), store=Mixed(p)).status()
    assert st.spent_today_micro == 40 and st.reserved_micro == 0      # no hold persisted, no double count


def test_hold_validation_python_and_sql(tmp_path):
    st = SQLiteLabStore(str(tmp_path / "v.db"))
    for bad in (-1, 1.5, True, "3", None):
        with pytest.raises(ValueError):
            st.put_hold("h", bad)
        with pytest.raises(ValueError):
            st.reserve_hold("h", bad, lambda: None, "o")
    with pytest.raises(ValueError):
        st.put_hold("", 1)
    with pytest.raises(sqlite3.IntegrityError):         # DB-level CHECK, bypassing python
        st._conn.execute("INSERT INTO budget_hold(run_id, owner, amount_micro) VALUES('e','o',-5)")
    assert st.list_holds() == {}
    st.close()


def test_exhausted_failure_with_unbookable_incurred_keeps_claim_and_blocks_rerun(tmp_path):
    calls = []

    class NoBook(BudgetLedger):
        def record_incurred(self, run_id, actual_micro):
            raise RuntimeError("store down")

    def send(p, c):
        calls.append(1); c.record_usage(10, 5); raise RuntimeError("plain")

    path = str(tmp_path / "x.db")
    st = SQLiteLabStore(path)
    led = NoBook(BudgetPolicy(daily_limit_micro=usd_to_micro(10)), store=st)
    eng, _, wf = routed_engine(send, store=st, ledger=led)
    res = eng.run(wf, run_id="x1")                     # must not raise
    assert res.status == "failed" and "NOT booked" in str(res) and len(calls) == 4
    assert "b" in st.load_claims("x1")                  # claim kept
    res2 = eng.run(wf, run_id="x1")
    assert len(calls) == 4 and res2.status == "failed"  # no second paid attempt
    st.close()


def test_concurrent_first_open_of_one_new_db_succeeds(tmp_path):
    import time
    code = ("import sys,time\nfrom app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore\n"
            "go=float(sys.argv[2])\nwhile time.time()<go: pass\nSQLiteLabStore(sys.argv[1]).close();print('OK')")
    for rnd in range(4):
        db = str(tmp_path / f"n{rnd}.db"); go = time.time() + 1.5
        ps = [run_py(code, db, str(go), wait=False) for _ in range(8)]
        outs = [(p.communicate(timeout=60)[0].strip(), p.returncode) for p in ps]
        assert all(o == ("OK", 0) for o in outs), outs
