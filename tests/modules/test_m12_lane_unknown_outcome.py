"""Lane engine: indeterminate external effects are never retried or re-run automatically.
Stub executors only; no live provider. Evidence is simulation, not real delivery."""
import pytest

from app.modules.m12_ai_research_lab.lane_budgets import BudgetLedger
from app.modules.m12_ai_research_lab.lane_models import (
    BudgetPolicy, ModelProfile, TaskRequirements, CAP_CHAT, usd_to_micro,
)
from app.modules.m12_ai_research_lab.lane_routing import ModelRouter
from app.modules.m12_ai_research_lab.lane_store import SQLiteLabStore
from app.modules.m12_ai_research_lab import lane_store as ls_mod
from app.modules.m12_ai_research_lab.lane_workflows import (
    InMemoryStepStateStore, Workflow, WorkflowEngine, WorkflowStep,
)


class Unknown(RuntimeError):
    outcome = "unknown"


def model():
    return ModelProfile(model_id="m1", provider="t", display_name="m1",
                        cost_per_1k_input_micro=1000, cost_per_1k_output_micro=2000,
                        capabilities=frozenset({CAP_CHAT}))


def routed_engine(executor, store=None, ledger=None):
    router = ModelRouter([model()])
    ledger = ledger or BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(10)))
    eng = WorkflowEngine({"send": executor, "echo": lambda p, c: p}, router=router,
                         ledger=ledger, state_store=store)
    wf = Workflow("w", (WorkflowStep("a", "echo"),
                        WorkflowStep("b", "send", depends_on=("a",), max_retries=3,
                                     route_requirements=TaskRequirements())))
    return eng, ledger, wf


def test_unknown_outcome_is_not_retried_and_is_neither_success_nor_plain_failure():
    calls = []

    def send(p, c):
        calls.append(1)
        c.record_usage(10, 5)
        raise Unknown("timeout after dispatch")

    eng, ledger, wf = routed_engine(send)
    res = eng.run(wf, run_id="r1")
    assert len(calls) == 1                       # max_retries=3 not used
    assert res.status == "failed" and res.failed_step_id == "b"
    rec = {s.step_id: s for s in res.steps}
    assert rec["b"].status == "unknown_outcome" and rec["b"].attempts == 1
    assert rec["b"].cost_micro == 0 and "b" not in res.outputs
    assert any(j.event == "step_outcome_unknown" for j in res.journal)
    assert not any(j.event == "retry" for j in res.journal)
    with pytest.raises(ValueError):             # hold kept (open reservation): spend not assumed zero
        ledger.reserve("r1:b", 0)


def test_ordinary_error_before_unknown_still_retries_then_stops_on_unknown():
    seq = ["boom", "unknown"]
    calls = []

    def send(p, c):
        calls.append(1)
        if seq[len(calls) - 1] == "boom":
            raise RuntimeError("transient")
        raise Unknown("x")

    eng, _, wf = routed_engine(send)
    res = eng.run(wf, run_id="r2")
    assert len(calls) == 2
    assert {s.step_id: s for s in res.steps}["b"].attempts == 2


def test_ordinary_failures_unchanged_all_retries_used():
    calls = []

    def send(p, c):
        calls.append(1)
        raise RuntimeError("plain")

    eng, ledger, wf = routed_engine(send)
    res = eng.run(wf, run_id="r3")
    assert len(calls) == 4
    assert {s.step_id: s for s in res.steps}["b"].status == "failed"
    assert ledger.status().reserved_micro == 0


def test_rerun_does_not_reexecute_unknown_step_until_resolved():
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("x")

    eng, _, wf = routed_engine(send)
    eng.run(wf, run_id="r4")
    res2 = eng.run(wf, run_id="r4")
    assert len(calls) == 1
    assert res2.status == "failed" and "outcome unknown" in res2.journal[-1].detail
    assert {s.step_id: s for s in res2.steps}["b"].status == "unknown_outcome"


def test_resolve_with_output_checkpoints_and_resume_skips():
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("x")

    eng, ledger, wf = routed_engine(send)
    eng.run(wf, run_id="r5")
    eng.resolve_unknown_as_completed("r5", "b", expected_generation=_g(eng, "r5", "b"), output={"sent": True}, release_budget_hold=True)
    res = eng.run(wf, run_id="r5")
    assert len(calls) == 1 and res.status == "completed"
    assert res.outputs["b"] == {"sent": True}
    assert ledger.status().reserved_micro == 0


def test_retry_after_reconciliation_is_deliberate_and_explicit():
    calls = []

    def send(p, c):
        calls.append(1)
        if len(calls) == 1:
            raise Unknown("x")
        return "ok"

    eng, ledger, wf = routed_engine(send)
    eng.run(wf, run_id="r6")
    for kw in ({}, {"confirm_effect_did_not_occur": True},
               {"confirm_effect_did_not_occur": True, "release_budget_hold": False},
               {"confirm_effect_did_not_occur": 1, "release_budget_hold": True}):
        with pytest.raises((ValueError, TypeError)):
            eng.authorize_retry_after_reconciliation("r6", "b", expected_generation=_g(eng, "r6", "b"), **kw)
    assert eng.run(wf, run_id="r6").status == "failed" and len(calls) == 1   # still blocked
    eng.authorize_retry_after_reconciliation(
        "r6", "b", expected_generation=_g(eng, "r6", "b"), confirm_effect_did_not_occur=True, release_budget_hold=True)
    res = eng.run(wf, run_id="r6")
    assert res.status == "completed" and len(calls) == 2


def test_none_is_a_legitimate_resolved_output_and_output_is_required():
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("x")

    eng, _, wf = routed_engine(send)
    eng.run(wf, run_id="r6b")
    with pytest.raises(TypeError):
        eng.resolve_unknown_as_completed("r6b", "b", expected_generation=_g(eng, "r6b", "b"))           # no silent default
    eng.resolve_unknown_as_completed("r6b", "b", expected_generation=_g(eng, "r6b", "b"), output=None, release_budget_hold=True)
    res = eng.run(wf, run_id="r6b")
    assert res.status == "completed" and res.outputs["b"] is None and len(calls) == 1


def test_resolve_unknown_validation():
    eng, _, wf = routed_engine(lambda p, c: "x")
    with pytest.raises(ValueError):
        eng.resolve_unknown_as_completed("none", "b", expected_generation=_g(eng, "none", "b"), output=1)
    with pytest.raises(ValueError):
        eng.authorize_retry_after_reconciliation(
            "none", "b", expected_generation=_g(eng, "none", "b"), confirm_effect_did_not_occur=True, release_budget_hold=True)


def test_resume_false_does_not_override_unknown_marker():
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("x")

    eng, ledger, wf = routed_engine(send)
    eng.run(wf, run_id="r7")
    ledger.release("r7:b")                       # even with the hold gone
    res = eng.run(wf, run_id="r7", resume=False)
    assert len(calls) == 1 and res.status == "failed"
    assert {s.step_id: s for s in res.steps}["b"].status == "unknown_outcome"


def test_sqlite_store_marker_survives_new_engine(tmp_path):
    path = str(tmp_path / "lab.db")
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("x")

    eng, _, wf = routed_engine(send, store=SQLiteLabStore(path))
    eng.run(wf, run_id="r8")
    eng_b, _, wf_b = routed_engine(send, store=SQLiteLabStore(path))   # fresh process-like engine + ledger
    res = eng_b.run(wf_b, run_id="r8")
    assert len(calls) == 1 and "outcome unknown" in res.journal[-1].detail
    eng_b.resolve_unknown_as_completed("r8", "b", expected_generation=_g(eng_b, "r8", "b"), output="done", release_budget_hold=True)
    assert eng_b.run(wf_b, run_id="r8").status == "completed"
    assert len(calls) == 1


class Bare:
    def __init__(self): self.d = {}
    def load_completed(self, r): return dict(self.d.get(r, {}))
    def save_completed(self, r, s, o): self.d.setdefault(r, {})[s] = o
    def clear_run(self, r): self.d.pop(r, None)


def test_store_without_claim_support_fails_closed_for_every_step_kind():
    calls = []

    def ext(p, c):
        calls.append(1)
        raise Unknown("x")

    # unrouted external step on a marker-less store (reviewer P4): never executed
    eng = WorkflowEngine({"ext": ext, "echo": lambda p, c: p}, state_store=Bare())
    wf = Workflow("w", (WorkflowStep("u", "ext"),))
    for _ in range(2):
        res = eng.run(wf, run_id="P4")
        assert res.status == "failed" and res.failed_step_id == "u"
        assert "lacks durable step-claim support" in res.journal[-1].detail
    assert calls == []
    # routed step: refused before reservation as well
    eng2, ledger, wf2 = routed_engine(ext, store=Bare())
    res = eng2.run(wf2, run_id="r9")
    assert calls == [] and res.status == "failed"
    ledger.reserve("r9:b", 0)                    # no reservation was taken
    with pytest.raises(ValueError):
        eng2.resolve_unknown_as_completed("r9", "b", expected_generation=_g(eng2, "r9", "b"), output=1)


class MarkWriteFails(InMemoryStepStateStore):
    def mark_unknown(self, run_id, step_id, token, detail):
        raise OSError("disk full")


def test_unrouted_mark_unknown_failure_still_blocks_rerun_via_pending_claim():
    calls = []

    def ext(p, c):
        calls.append(1)
        raise Unknown("x")

    eng = WorkflowEngine({"ext": ext}, state_store=MarkWriteFails())
    wf = Workflow("w", (WorkflowStep("u", "ext"),))
    r1 = eng.run(wf, run_id="P5u")
    r2 = eng.run(wf, run_id="P5u")
    assert len(calls) == 1
    assert r1.status == "failed" and r2.status == "failed"
    assert {s.step_id: s for s in r2.steps}["u"].status == "unknown_outcome"


class ClaimWriteFails(InMemoryStepStateStore):
    def claim_step(self, run_id, step_id):
        if step_id == "b":                       # let the unrouted prep step through
            raise OSError("disk full")
        return super().claim_step(run_id, step_id)


def test_claim_persist_failure_means_executor_never_runs_and_hold_is_released():
    calls = []

    def send(p, c):
        calls.append(1)
        return "x"

    eng, ledger, wf = routed_engine(send, store=ClaimWriteFails())
    res = eng.run(wf, run_id="c1")
    assert calls == [] and res.status == "failed" and res.failed_step_id == "b"
    assert "claim could not be persisted" in res.journal[-1].detail
    ledger.reserve("c1:b", 0)                    # reservation was released: effect never started


def test_interrupted_execution_leaves_pending_claim_and_rerun_is_blocked():
    calls = []

    class Crash(BaseException):
        pass

    def send(p, c):
        calls.append(1)
        raise Crash()

    store = InMemoryStepStateStore()
    eng, _, wf = routed_engine(send, store=store)
    with pytest.raises(Crash):
        eng.run(wf, run_id="k1")
    assert store.load_claims("k1")["b"][0] == "pending"
    res = eng.run(wf, run_id="k1")
    assert len(calls) == 1 and res.status == "failed"
    assert {s.step_id: s for s in res.steps}["b"].status == "unknown_outcome"
    with pytest.raises(ValueError, match="pending claim"):      # may be live: ordinary reconcile refused
        eng.resolve_unknown_as_completed("k1", "b", expected_generation=_g(eng, "k1", "b"), output="x", release_budget_hold=True)
    with pytest.raises(ValueError):
        eng.take_over_pending_claim("k1", "b", expected_generation=_g(eng, "k1", "b"), acknowledge_inflight_effect_may_still_complete=False)
    eng.take_over_pending_claim("k1", "b", expected_generation=_g(eng, "k1", "b"), acknowledge_inflight_effect_may_still_complete=True)
    eng.resolve_unknown_as_completed("k1", "b", expected_generation=_g(eng, "k1", "b"), output="verified-externally", release_budget_hold=True)
    assert eng.run(wf, run_id="k1").status == "completed" and len(calls) == 1


def test_success_and_ordinary_failure_leave_no_claim():
    store = InMemoryStepStateStore()
    eng, _, wf = routed_engine(lambda p, c: "ok", store=store)
    assert eng.run(wf, run_id="s1").status == "completed"
    assert store.load_claims("s1") == {}
    store2 = InMemoryStepStateStore()
    n = []

    def bad(p, c):
        n.append(1)
        raise RuntimeError("plain")

    eng2, _, wf2 = routed_engine(bad, store=store2)
    assert eng2.run(wf2, run_id="s2").status == "failed"
    assert store2.load_claims("s2") == {}
    eng2.run(wf2, run_id="s2")                   # determinate failure: retry allowed
    assert len(n) == 8


def test_budget_commit_failure_after_effect_blocks_rerun():
    calls = []

    class BadCommit(BudgetLedger):
        def commit(self, run_id, actual_micro):
            raise ValueError("ledger write failed")

    def send(p, c):
        calls.append(1)
        c.record_usage(1, 1)
        return "sent"

    eng, _, wf = routed_engine(send, ledger=BadCommit(BudgetPolicy(daily_limit_micro=usd_to_micro(10))))
    r1 = eng.run(wf, run_id="b1")
    assert r1.status == "failed" and "budget commit failed" in r1.journal[-1].detail
    r2 = eng.run(wf, run_id="b1")
    assert len(calls) == 1 and r2.status == "failed"


def test_two_engines_shared_sqlite_same_run_only_one_executes(tmp_path):
    import threading, time
    path = str(tmp_path / "lab.db")
    calls = []
    gate = threading.Barrier(2)

    def send(p, c):
        calls.append(1)
        try:
            gate.wait(timeout=1.0)               # the second engine must never get here
        except threading.BrokenBarrierError:
            pass
        time.sleep(0.05)
        raise Unknown("transport dropped after dispatch")

    results = []

    def run_one():
        eng, _, wf = routed_engine(send, store=SQLiteLabStore(path))
        results.append(eng.run(wf, run_id="P6"))

    ts = [threading.Thread(target=run_one) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(calls) == 1
    assert sorted(r.status for r in results) == ["failed", "failed"]
    assert all(any(j.event == "step_outcome_unknown" for j in r.journal) for r in results)


def test_claim_lost_to_other_engine_releases_own_hold_and_does_not_execute():
    calls = []

    class Lost(InMemoryStepStateStore):
        def claim_step(self, run_id, step_id):
            return None if step_id == "b" else super().claim_step(run_id, step_id)

    eng, ledger, wf = routed_engine(lambda p, c: calls.append(1), store=Lost())
    res = eng.run(wf, run_id="L1")
    assert calls == [] and res.status == "failed" and res.failed_step_id == "b"
    assert any(j.event == "step_outcome_unknown" for j in res.journal)
    ledger.reserve("L1:b", 0)


def test_http_resume_false_cannot_reexecute_unknown_step(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m12_ai_research_lab.lane_http import build_router
    from app.modules.m12_ai_research_lab.lane_service import AIResearchLabService
    store = SQLiteLabStore(str(tmp_path / "lab.db"))
    router = ModelRouter([model()])
    ledger = BudgetLedger(BudgetPolicy(daily_limit_micro=usd_to_micro(10)), store=store)
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("transport dropped after dispatch")

    engine = WorkflowEngine({"send": send}, router=router, ledger=ledger, state_store=store)
    svc = AIResearchLabService(router=router, ledger=ledger, engine=engine, store=store)
    app = FastAPI(); app.include_router(build_router(svc), prefix="/lab")
    c = TestClient(app)
    body = {"name": "w", "run_id": "h1", "steps": [
        {"step_id": "s", "kind": "send", "max_retries": 3,
         "route_requirements": {"required_capabilities": ["chat"]}}]}
    r1 = c.post("/lab/workflows/run", json=body)
    assert r1.status_code == 200 and r1.json()["status"] == "failed"
    assert r1.json()["steps"][0]["status"] == "unknown_outcome"
    for resume in (True, False):
        r = c.post("/lab/workflows/run", json={**body, "resume": resume})
        assert r.status_code == 200 and r.json()["status"] == "failed"
    assert len(calls) == 1


def test_sqlite_claim_step_is_atomic_across_connections(tmp_path):
    import threading
    path = str(tmp_path / "lab.db")
    stores = [SQLiteLabStore(path) for _ in range(8)]
    wins = []
    go = threading.Barrier(8)

    def race(st):
        go.wait()
        tok = st.claim_step("rr", "s")
        if tok:
            wins.append((st, tok))

    ts = [threading.Thread(target=race, args=(st,)) for st in stores]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(wins) == 1
    st, tok = wins[0]
    assert st.release_claim("rr", "s", tok) is True
    assert stores[1].claim_step("rr", "s")


def test_claims_loaded_even_when_resume_false_without_relying_on_atomic_claim():
    calls = []

    class NoAtomic(InMemoryStepStateStore):
        def claim_step(self, run_id, step_id):   # pretend the atomic backstop is absent
            tok = super().claim_step(run_id, step_id)
            return tok if tok is not None or step_id != "b" else "dup-token"

    def send(p, c):
        calls.append(1)
        raise Unknown("x")

    store = NoAtomic()
    eng, ledger, wf = routed_engine(send, store=store)
    eng.run(wf, run_id="rf")
    ledger.release("rf:b")
    res = eng.run(wf, run_id="rf", resume=False)
    assert len(calls) == 1 and res.status == "failed"


import threading


def _g(eng, run_id, step_id):
    view = eng.inspect_claim(run_id, step_id)
    return view.generation if view is not None else "no-claim"


def _stores(tmp_path, kind):
    if kind == "memory":
        m = InMemoryStepStateStore()
        return m, m
    p = str(tmp_path / "f.db")
    return SQLiteLabStore(p), SQLiteLabStore(p)


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_store_fencing_semantics(tmp_path, kind):
    a, b = _stores(tmp_path, kind)
    t1 = a.claim_step("r", "s")
    assert t1 and b.claim_step("r", "s") is None
    assert b.mark_unknown("r", "s", "wrong-token", "d") is False
    assert b.release_claim("r", "s", "wrong-token") is False
    assert b.complete_step("r", "s", "wrong-token", "out") is False
    assert "s" not in a.load_completed("r") and a.load_claims("r")["s"][0] == "pending"
    g1 = a.inspect_claim("r", "s")[2]
    assert a.resolve_claim_completed("r", "s", "unknown", g1, "x") is False     # state-checked
    assert a.clear_claim_for_retry("r", "s", "unknown", g1) is False
    assert b.takeover_pending("r", "s", "stale-gen") is False                   # generation-checked
    assert a.load_claims("r")["s"][0] == "pending"
    assert b.takeover_pending("r", "s", g1) is True
    g2 = a.inspect_claim("r", "s")[2]
    assert g2 != g1
    assert a.load_claims("r")["s"][0] == "unknown"
    assert a.takeover_pending("r", "s", g2) is False                            # only pending
    assert a.mark_unknown("r", "s", t1, "late") is False                    # revoked owner
    assert a.release_claim("r", "s", t1) is False
    assert a.complete_step("r", "s", t1, "late-out") is False
    assert "s" not in a.load_completed("r") and "s" in a.load_claims("r")
    assert b.resolve_claim_completed("r", "s", "unknown", g1, "recon") is False    # stale generation
    assert b.clear_claim_for_retry("r", "s", "unknown", g1) is False
    assert "s" in a.load_claims("r") and "s" not in a.load_completed("r")
    assert b.resolve_claim_completed("r", "s", "unknown", g2, "recon") is True
    assert a.load_completed("r")["s"] == "recon" and a.load_claims("r") == {}
    t2 = a.claim_step("r2", "s")
    assert a.complete_step("r2", "s", t2, None) is True                     # None is a real output
    assert a.load_completed("r2") == {"s": None}


def _blocking_engine(path, executor_factory):
    eng, ledger, wf = routed_engine(executor_factory, store=SQLiteLabStore(path))
    return eng, ledger, wf


def test_live_owner_reconcile_refused_takeover_revokes_late_checkpoint(tmp_path):
    path = str(tmp_path / "lab.db")
    entered, go = threading.Event(), threading.Event()
    calls = []

    def send_a(p, c):
        calls.append("A")
        entered.set()
        go.wait(timeout=10)
        return "A-output"

    eng_a, _, wf_a = routed_engine(send_a, store=SQLiteLabStore(path))
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("a", eng_a.run(wf_a, run_id="F")))
    t.start()
    assert entered.wait(timeout=10)
    eng_b, _, _ = routed_engine(lambda p, c: calls.append("B"), store=SQLiteLabStore(path))
    with pytest.raises(ValueError, match="pending claim"):
        eng_b.authorize_retry_after_reconciliation(
            "F", "b", expected_generation=_g(eng_b, "F", "b"), confirm_effect_did_not_occur=True, release_budget_hold=True)
    with pytest.raises(ValueError, match="pending claim"):
        eng_b.resolve_unknown_as_completed("F", "b", expected_generation=_g(eng_b, "F", "b"), output="x")
    assert SQLiteLabStore(path).load_claims("F")["b"][0] == "pending"        # live claim intact
    with pytest.raises(ValueError):
        eng_b.take_over_pending_claim("F", "b", expected_generation=_g(eng_b, "F", "b"), acknowledge_inflight_effect_may_still_complete=1)
    eng_b.take_over_pending_claim("F", "b", expected_generation=_g(eng_b, "F", "b"), acknowledge_inflight_effect_may_still_complete=True)
    go.set(); t.join()
    res = out["a"]
    assert res.status == "failed" and {s.step_id: s for s in res.steps}["b"].status == "unknown_outcome"
    assert "b" not in res.outputs and "b" not in SQLiteLabStore(path).load_completed("F")
    assert SQLiteLabStore(path).load_claims("F")["b"][0] == "unknown"
    eng_b.resolve_unknown_as_completed("F", "b", expected_generation=_g(eng_b, "F", "b"), output="reconciled", release_budget_hold=True)
    done = eng_b.run(wf_a, run_id="F")
    assert done.status == "completed" and done.outputs["b"] == "reconciled" and calls == ["A"]


@pytest.mark.parametrize("late", ["success", "ordinary_error", "unknown"])
def test_old_owner_late_outcome_cannot_touch_new_claim(tmp_path, late):
    path = str(tmp_path / "lab.db")
    a_in, a_go, c_in, c_go = (threading.Event() for _ in range(4))

    def send_a(p, c):
        a_in.set(); a_go.wait(timeout=10)
        if late == "ordinary_error":
            raise RuntimeError("late plain failure")
        if late == "unknown":
            raise Unknown("late unknown")
        return "A-output"

    def send_c(p, c):
        c_in.set(); c_go.wait(timeout=10)
        return "C-output"

    eng_a, _, wf = routed_engine(send_a, store=SQLiteLabStore(path))
    ra = {}
    ta = threading.Thread(target=lambda: ra.setdefault("r", eng_a.run(wf, run_id="G", )))
    ta.start(); assert a_in.wait(timeout=10)
    op, _, _ = routed_engine(send_c, store=SQLiteLabStore(path))
    op.take_over_pending_claim("G", "b", expected_generation=_g(op, "G", "b"), acknowledge_inflight_effect_may_still_complete=True)
    op.authorize_retry_after_reconciliation(
        "G", "b", expected_generation=_g(op, "G", "b"), confirm_effect_did_not_occur=True, release_budget_hold=True)
    eng_c, _, wf_c = routed_engine(send_c, store=SQLiteLabStore(path))
    rc = {}
    tc = threading.Thread(target=lambda: rc.setdefault("r", eng_c.run(wf_c, run_id="G")))
    tc.start(); assert c_in.wait(timeout=10)                                 # C owns a new claim
    a_go.set(); ta.join()                                                    # A finishes late
    view = SQLiteLabStore(path)
    assert view.load_claims("G")["b"][0] == "pending"                        # C's claim untouched
    assert "b" not in view.load_completed("G")                               # A recorded nothing
    c_go.set(); tc.join()
    assert rc["r"].status == "completed" and rc["r"].outputs["b"] == "C-output"
    assert view.load_completed("G")["b"] == "C-output" and view.load_claims("G") == {}
    assert ra["r"].status == "failed"


class CompleteFails(InMemoryStepStateStore):
    def complete_step(self, run_id, step_id, token, output):
        if step_id == "b":
            raise OSError("checkpoint write failed")
        return super().complete_step(run_id, step_id, token, output)


def test_checkpoint_write_failure_is_loud_spend_once_and_blocks_rerun():
    calls = []

    def send(p, c):
        calls.append(1)
        c.record_usage(10, 5)
        return "done"

    store = CompleteFails()
    eng, ledger, wf = routed_engine(send, store=store)
    with pytest.raises(OSError):
        eng.run(wf, run_id="cw")
    assert store.load_claims("cw")["b"][0] == "pending"
    r = eng.run(wf, run_id="cw")
    assert len(calls) == 1 and r.status == "failed"
    assert ledger.status().spent_today_micro == 20            # 10 in + 5 out, booked once
    assert ledger.status().reserved_micro == 0
    store.__class__ = InMemoryStepStateStore                                 # healthy store
    eng.take_over_pending_claim("cw", "b", expected_generation=_g(eng, "cw", "b"), acknowledge_inflight_effect_may_still_complete=True)
    eng.resolve_unknown_as_completed("cw", "b", expected_generation=_g(eng, "cw", "b"), output="done", release_budget_hold=True)
    assert eng.run(wf, run_id="cw").status == "completed" and len(calls) == 1


# ---- generation compare-and-set (ABA) -------------------------------------

def _two_unknowns(store):
    calls = []

    def send(p, c):
        calls.append(1)
        raise Unknown("attempt %d" % len(calls))

    eng, ledger, wf = routed_engine(send, store=store)
    eng.run(wf, run_id="ABA")
    g1 = eng.inspect_claim("ABA", "b").generation
    eng.authorize_retry_after_reconciliation(
        "ABA", "b", expected_generation=g1, confirm_effect_did_not_occur=True, release_budget_hold=True)
    eng.run(wf, run_id="ABA")
    g2 = eng.inspect_claim("ABA", "b").generation
    return eng, ledger, wf, calls, g1, g2


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_stale_generation_cannot_reconcile_newer_unknown_claim(tmp_path, kind):
    store = InMemoryStepStateStore() if kind == "memory" else SQLiteLabStore(str(tmp_path / "a.db"))
    eng, ledger, wf, calls, g1, g2 = _two_unknowns(store)
    assert g1 != g2 and len(calls) == 2
    before = (dict(store.load_claims("ABA")), dict(store.load_completed("ABA")), dict(ledger._reservations))
    with pytest.raises(ValueError, match="generation"):
        eng.resolve_unknown_as_completed("ABA", "b", expected_generation=g1, output="stale", release_budget_hold=True)
    with pytest.raises(ValueError, match="generation"):
        eng.authorize_retry_after_reconciliation(
            "ABA", "b", expected_generation=g1, confirm_effect_did_not_occur=True, release_budget_hold=True)
    with pytest.raises(ValueError):
        eng.take_over_pending_claim("ABA", "b", expected_generation=g1,
                                    acknowledge_inflight_effect_may_still_complete=True)
    after = (dict(store.load_claims("ABA")), dict(store.load_completed("ABA")), dict(ledger._reservations))
    assert before == after and "b" not in after[1]                 # no checkpoint, claim, or hold change
    eng.resolve_unknown_as_completed("ABA", "b", expected_generation=g2, output="ok", release_budget_hold=True)
    assert store.load_completed("ABA")["b"] == "ok" and len(calls) == 2


@pytest.mark.parametrize("bad", [None, "", 5])
def test_generation_is_required_for_every_reconcile_call(bad):
    eng, _, wf, calls, g1, g2 = _two_unknowns(InMemoryStepStateStore())
    with pytest.raises(ValueError, match="expected_generation"):
        eng.resolve_unknown_as_completed("ABA", "b", expected_generation=bad, output=1)
    with pytest.raises(ValueError, match="expected_generation"):
        eng.authorize_retry_after_reconciliation(
            "ABA", "b", expected_generation=bad, confirm_effect_did_not_occur=True, release_budget_hold=True)
    with pytest.raises(ValueError, match="expected_generation"):
        eng.take_over_pending_claim("ABA", "b", expected_generation=bad,
                                    acknowledge_inflight_effect_may_still_complete=True)
    assert eng.inspect_claim("ABA", "b").generation == g2


def test_blocked_run_reports_generation_for_caller():
    eng, _, wf, calls, g1, g2 = _two_unknowns(InMemoryStepStateStore())
    res = eng.run(wf, run_id="ABA")
    rec = {r.step_id: r for r in res.steps}["b"]
    assert "claim_generation=%s" % g2 in rec.error and len(calls) == 2


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_mark_unknown_changes_generation(tmp_path, kind):
    st = InMemoryStepStateStore() if kind == "memory" else SQLiteLabStore(str(tmp_path / "m.db"))
    tok = st.claim_step("r", "s")
    g0 = st.inspect_claim("r", "s")[2]
    assert st.mark_unknown("r", "s", tok, "d") is True
    g1 = st.inspect_claim("r", "s")[2]
    assert g1 != g0
    assert st.resolve_claim_completed("r", "s", "unknown", g0, "x") is False
    assert st.resolve_claim_completed("r", "s", "unknown", g1, "x") is True


# ---- old-schema migration --------------------------------------------------

_OLD_NO_TOKEN = (
    "CREATE TABLE step_claim (run_id TEXT NOT NULL, step_id TEXT NOT NULL,"
    " state TEXT NOT NULL CHECK (state IN ('pending','unknown')),"
    " detail TEXT NOT NULL, saved_utc TEXT NOT NULL, PRIMARY KEY (run_id, step_id))")
_OLD_TOKEN_NO_GEN = _OLD_NO_TOKEN.replace("detail TEXT", "token TEXT NOT NULL, detail TEXT")


def _make_old(path, ddl, token_col):
    import sqlite3
    c = sqlite3.connect(path)
    c.execute(ddl)
    for run, state in (("OLDU", "unknown"), ("OLDP", "pending")):
        if token_col:
            c.execute("INSERT INTO step_claim VALUES (?,?,?,?,?,?)", (run, "b", state, "oldtok", "old " + state, "t"))
        else:
            c.execute("INSERT INTO step_claim VALUES (?,?,?,?,?)", (run, "b", state, "old " + state, "t"))
    c.commit(); c.close()


@pytest.mark.parametrize("ddl,token_col", [(_OLD_NO_TOKEN, False), (_OLD_TOKEN_NO_GEN, True)])
def test_old_schema_upgrades_preserving_markers_and_allows_new_claims(tmp_path, ddl, token_col):
    path = str(tmp_path / "old.db")
    _make_old(path, ddl, token_col)
    st = SQLiteLabStore(path)
    assert st.load_claims("OLDU") == {"b": ("unknown", "old unknown")}
    assert st.load_claims("OLDP") == {"b": ("pending", "old pending")}      # not wiped, not retried
    calls = []
    eng, _, wf = routed_engine(lambda p, c: (calls.append(1), "done")[1], store=st)
    assert eng.run(wf, run_id="NEW").status == "completed" and len(calls) == 1   # new claims work
    for run in ("OLDU", "OLDP"):
        assert eng.run(wf, run_id=run).status == "failed"                  # old markers still block
    assert len(calls) == 1
    with pytest.raises(ValueError, match="pending claim"):
        eng.resolve_unknown_as_completed("OLDP", "b", expected_generation=_g(eng, "OLDP", "b"), output=1)
    eng.take_over_pending_claim("OLDP", "b", expected_generation=_g(eng, "OLDP", "b"),
                                acknowledge_inflight_effect_may_still_complete=True)
    eng.resolve_unknown_as_completed("OLDU", "b", expected_generation=_g(eng, "OLDU", "b"), output="x")
    assert st.load_completed("OLDU")["b"] == "x"
    if token_col:                                                           # an old owner token is never honored
        assert st.release_claim("OLDP", "b", "oldtok") is False


def test_migration_is_idempotent_and_fresh_db_untouched(tmp_path):
    path = str(tmp_path / "old.db")
    _make_old(path, _OLD_NO_TOKEN, False)
    s1 = SQLiteLabStore(path)
    g = s1.inspect_claim("OLDU", "b")[2]
    s2 = SQLiteLabStore(path)                                               # repeated init
    s3 = SQLiteLabStore(path)
    assert s3.inspect_claim("OLDU", "b")[2] == g and s2.load_claims("OLDP")["b"][0] == "pending"
    fresh = SQLiteLabStore(str(tmp_path / "fresh.db"))
    assert fresh.claim_step("r", "s") and fresh.load_claims("r")["s"][0] == "pending"


def test_concurrent_migration_init_is_safe(tmp_path):
    path = str(tmp_path / "old.db")
    _make_old(path, _OLD_NO_TOKEN, False)
    go, errs, stores = threading.Barrier(6), [], []

    def init():
        try:
            go.wait(timeout=10)
            stores.append(SQLiteLabStore(path))
        except Exception as exc:
            errs.append(repr(exc))

    ts = [threading.Thread(target=init) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert errs == []
    gens = {s.inspect_claim("OLDU", "b")[2] for s in stores}
    assert len(gens) == 1 and "" not in gens                                # one consistent assigned generation
    assert len({r for r in SQLiteLabStore(path).load_claims("OLDU")}) == 1


def test_migration_failure_rolls_back_and_keeps_markers(tmp_path, monkeypatch):
    import sqlite3
    path = str(tmp_path / "old.db")
    _make_old(path, _OLD_NO_TOKEN, False)

    real = ls_mod.uuid.uuid4
    n = {"c": 0}

    def boom():
        n["c"] += 1
        if n["c"] >= 2:
            raise RuntimeError("injected mid-migration failure")
        return real()
    monkeypatch.setattr(ls_mod.uuid, "uuid4", boom)
    with pytest.raises(RuntimeError):
        SQLiteLabStore(path)
    monkeypatch.undo()
    c = sqlite3.connect(path)
    cols = [r[1] for r in c.execute("PRAGMA table_info(step_claim)")]
    rows = c.execute("SELECT run_id, state, detail FROM step_claim ORDER BY run_id").fetchall()
    c.close()
    assert "token" not in cols and "gen" not in cols                        # DDL rolled back too
    assert rows == [("OLDP", "pending", "old pending"), ("OLDU", "unknown", "old unknown")]
    st = SQLiteLabStore(path)                                               # retry now succeeds
    assert st.load_claims("OLDU")["b"][0] == "unknown" and st.claim_step("n", "s")
