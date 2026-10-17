"""Real multi-process and SIGKILL checks on SQLiteLabStore holds. Scratch sqlite files only,
stub executors, no provider, no production DB."""
import os, subprocess, sys, textwrap, time
from pathlib import Path
import pytest
from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger, InMemorySpendStore
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT / "tests" / "modules")])}


def run_py(code, *args, wait=True):
    p = subprocess.Popen([sys.executable, "-c", textwrap.dedent(code), *args], env=ENV,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not wait:
        return p
    out, err = p.communicate(timeout=60)
    return p.returncode, out, err


RACE = """
import sys, time
from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger, BudgetExceeded
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
db, name, go = sys.argv[1], sys.argv[2], float(sys.argv[3])
st = SQLiteLabStore(db)
led = BudgetLedger(BudgetPolicy(daily_limit_micro=100), store=st)
while time.time() < go: pass
try:
    led.reserve(name, 100); print("ADMIT")
except BudgetExceeded: print("DENY")
"""


def test_cap_for_one_hold_admits_exactly_one_across_processes(tmp_path):
    db = str(tmp_path / "race.db")
    SQLiteLabStore(db).close()
    for rnd in range(3):
        db = str(tmp_path / f"race{rnd}.db")
        SQLiteLabStore(db).close()
        go = time.time() + 1.5
        procs = [run_py(RACE, db, f"p{i}", str(go), wait=False) for i in range(6)]
        outs = [p.communicate(timeout=60)[0].strip() for p in procs]
        assert sorted(outs).count("ADMIT") == 1 and sorted(outs).count("DENY") == 5, outs
        st = SQLiteLabStore(db)
        assert len(st.list_holds()) == 1
        st.close()


def test_non_atomic_check_then_insert_would_admit_more_than_one(tmp_path):
    """Control: shows the race is real for a check-then-put design (guards the harness)."""
    class Racy(SQLiteLabStore):
        reserve_hold = None  # force fallback: separate check, then plain put

    db = str(tmp_path / "ctl.db")
    SQLiteLabStore(db).close()
    code = RACE.replace("from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore",
        """from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore as _S
class SQLiteLabStore(_S):
    def __getattribute__(self, n):
        if n == "reserve_hold": raise AttributeError(n)
        return super().__getattribute__(n)
""").replace('led.reserve(name, 100); print("ADMIT")',
        'led.reserve(name, 100); self_put = st.put_hold(name, 100); print("ADMIT")')
    admits = 0
    for _ in range(4):
        d = str(tmp_path / f"c{_}.db"); SQLiteLabStore(d).close()
        go = time.time() + 1.5
        ps = [run_py(code, d, f"p{i}", str(go), wait=False) for i in range(6)]
        admits = max(admits, [p.communicate(timeout=60)[0].strip() for p in ps].count("ADMIT"))
        if admits > 1: break
    assert admits > 1


CRASH = """
import os, signal, sys
from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_models import BudgetPolicy, usd_to_micro, TaskRequirements
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from app.modules.m12_ai_research_lab.lane_workflows import Workflow, WorkflowStep
from test_m12_lane_unknown_outcome import routed_engine
db, marker, phase = sys.argv[1], sys.argv[2], sys.argv[3]
def send(p, c):
    if phase == "before":
        os.kill(os.getpid(), signal.SIGKILL)
    open(marker, "a").write("effect;")
    c.record_usage(10, 5)
    if phase == "after":
        os.kill(os.getpid(), signal.SIGKILL)
    return {"ok": 1}
st = SQLiteLabStore(db)
led = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(10)), store=st)
eng, _, wf = routed_engine(send, store=st, ledger=led)
wf = Workflow("w", (WorkflowStep("a", "echo"), WorkflowStep("b", "send", depends_on=("a",), max_retries=3,
    route_requirements=TaskRequirements(estimated_input_tokens=1000, estimated_output_tokens=1000))))
eng.run(wf, run_id="k")
"""


@pytest.mark.parametrize("phase", ["before", "after"])
def test_sigkill_leaves_hold_blocks_rerun_and_reconcile_uses_existing_path(tmp_path, phase):
    db, marker = str(tmp_path / "k.db"), tmp_path / "effects.txt"
    rc, _, _ = run_py(CRASH, db, str(marker), phase)
    assert rc == -9                                           # real SIGKILL, not an exception
    effects = marker.read_text().count("effect") if marker.exists() else 0
    assert effects == (0 if phase == "before" else 1)
    st = SQLiteLabStore(db)
    holds = st.list_holds()
    assert list(holds) == ["k:b"] and holds["k:b"] > 0 and st.spend_by_run("k:b") == 0
    st.close()
    # restart: no automatic paid call
    rc, _, _ = run_py(CRASH.replace("os.kill(os.getpid(), signal.SIGKILL)", "pass"), db, str(marker), "x")
    after = marker.read_text().count("effect") if marker.exists() else 0
    assert after == effects                                   # rerun blocked by the pending claim
    st = SQLiteLabStore(db)
    assert list(st.list_holds()) == ["k:b"]
    # the existing explicit mechanism: takeover then retry-with-release (owner acknowledgements)
    led = BudgetLedger(BudgetPolicy(daily_limit_micro=10**9), store=st)
    from test_m12_lane_unknown_outcome import routed_engine
    eng, _, _ = routed_engine(lambda p, c: 1, store=st, ledger=led)
    v = eng.inspect_claim("k", "b")
    eng.take_over_pending_claim("k", "b", expected_generation=v.generation,
                                acknowledge_inflight_effect_may_still_complete=True)
    v = eng.inspect_claim("k", "b")
    eng.authorize_retry_after_reconciliation("k", "b", expected_generation=v.generation,
                                             confirm_effect_did_not_occur=True, release_budget_hold=True)
    assert st.list_holds() == {}
    st.close()


def test_durable_holds_flag_distinguishes_fallback_stores():
    assert BudgetLedger(BudgetPolicy(), store=SQLiteLabStore(":memory:")).durable_holds is True
    assert BudgetLedger(BudgetPolicy()).durable_holds is False
    assert BudgetLedger(BudgetPolicy(), store=InMemorySpendStore()).durable_holds is False
