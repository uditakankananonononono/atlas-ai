"""Reserve-before-invoke effect ledger: real GCWRuntime, real SQLite files,
real SIGKILLs of real subprocesses, real threads. No stubs of the code under test."""
import asyncio, json, os, signal, subprocess, sys, threading
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.modules.m20_general_cognitive_worker.effect_ledger import (
    CURRENT_EFFECT_ID, EffectIdentityConflict, EffectIndeterminate, EffectInProgress,
    EffectLedger, ToolNotExecuted, effect_identity,
)
from app.modules.m20_general_cognitive_worker.safety import SafetyGate
from app.modules.m20_general_cognitive_worker.schemas import Risk, ToolSpec
from app.modules.m20_general_cognitive_worker.tools import ToolDispatcher, ToolRegistry

WORKER = str(Path(__file__).with_name("effect_worker.py"))


def worker(tmp, cmd, *extra, crash="", tenant="t1", hold="0", background=False):
    env = dict(os.environ, EFFECT_CRASH=crash, EFFECT_HOLD=hold)
    args = [sys.executable, WORKER, str(tmp / "atlas.sqlite"), str(tmp / "counter"), tenant, cmd, *extra]
    if background:
        return subprocess.Popen(args, env=env, stdout=subprocess.PIPE, text=True)
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=90)
    return p


def js(p):
    assert p.stdout.strip(), p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def counter(tmp, name="counter"):
    f = tmp / name
    return int(f.read_text() or 0) if f.exists() else 0


def submit(tmp, tenant="t1"):
    return js(worker(tmp, "submit", tenant=tenant))["task_id"]


# --- SIGKILL at every boundary ------------------------------------------------

def test_original_counter_1_to_2_never_increments_again(tmp_path):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash="after_effect").returncode == -signal.SIGKILL
    assert counter(tmp_path) == 1
    for _ in range(3):                               # repeated restarts / retries
        out = js(worker(tmp_path, "run", task))
        assert out["state"] == "blocked"
        assert counter(tmp_path) == 1


def test_kill_before_reserve_runs_exactly_once_on_restart(tmp_path):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash="before_reserve").returncode == -signal.SIGKILL
    assert counter(tmp_path) == 0
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1
    js(worker(tmp_path, "run", task)); assert counter(tmp_path) == 1


def test_kill_after_reserve_before_invoking_is_provably_safe_to_retake(tmp_path):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash="after_reserve").returncode == -signal.SIGKILL
    assert counter(tmp_path) == 0
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1


def test_kill_before_effect_is_indeterminate_not_silently_retried(tmp_path):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash="before_effect").returncode == -signal.SIGKILL
    assert counter(tmp_path) == 0
    out = js(worker(tmp_path, "run", task))
    assert out["state"] == "blocked" and "INDETERMINATE" in out["nodes"][0][1]
    assert counter(tmp_path) == 0                    # conservative: not auto-retried
    info = js(worker(tmp_path, "inspect", task))
    assert info["ledger"] == [["indeterminate", 1]]
    # operator verifies provider shows nothing happened -> exactly one new attempt
    assert js(worker(tmp_path, "reconcile", task, info["node_id"], "not_applied"))["state"] == "running"
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1
    assert js(worker(tmp_path, "inspect", task))["ledger"] == [["succeeded", 2]]


@pytest.mark.parametrize("point", ["after_effect", "before_receipt"])
def test_kill_after_effect_before_receipt_is_indeterminate(tmp_path, point):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash=point).returncode == -signal.SIGKILL
    assert counter(tmp_path) == 1
    out = js(worker(tmp_path, "run", task))
    assert out["state"] == "blocked" and counter(tmp_path) == 1
    info = js(worker(tmp_path, "inspect", task))
    assert info["ledger"] == [["indeterminate", 1]]
    # operator confirms the effect applied -> task completes, still never re-run
    assert js(worker(tmp_path, "reconcile", task, info["node_id"], "applied"))["state"] == "running"
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1


def test_kill_before_final_state_saved_replays_receipt_without_effect(tmp_path):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash="before_final_state").returncode == -signal.SIGKILL
    assert counter(tmp_path) == 1
    out = js(worker(tmp_path, "run", task))
    assert out["state"] == "succeeded" and counter(tmp_path) == 1
    assert js(worker(tmp_path, "inspect", task))["ledger"] == [["succeeded", 1]]


# --- duplicate / concurrent workers --------------------------------------------

def test_duplicate_worker_processes_invoke_once(tmp_path):
    task = submit(tmp_path)
    first = worker(tmp_path, "run", task, hold="2", background=True)
    import time; time.sleep(1.0)                     # first is inside the handler
    second = js(worker(tmp_path, "run", task))
    assert second["state"] in ("running", "pending", "planning")   # held by the live worker, not invoked
    assert second["nodes"][0][0] == "pending"
    first.wait(timeout=60)
    assert counter(tmp_path) == 1
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1


def test_many_threads_race_for_one_reservation(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'race.sqlite'}", connect_args={"timeout": 30})
    results, errors = [], []
    barrier = threading.Barrier(12)

    ledgers = [EffectLedger(engine, "t1") for _ in range(12)]   # schema created up front

    def go(ledger):
        barrier.wait()
        try:
            results.append(ledger.reserve(task_id="T", node_id="N", tool="send", args={"to": "a"}))
        except EffectInProgress as exc:
            errors.append(exc)
    threads = [threading.Thread(target=go, args=(l,)) for l in ledgers]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert len(results) == 1 and len(errors) == 11


# --- dispatcher-level: retry exception, rollback, identity, tenant --------------

def make_dispatcher(tmp_path, handler, *, tenant="t1", name="act", **spec):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'d.sqlite'}", connect_args={"timeout": 30})
    reg = ToolRegistry()
    reg.register(ToolSpec(name=name, description="x", risk=Risk.REVERSIBLE, **spec), handler)
    return ToolDispatcher(reg, SafetyGate(), EffectLedger(engine, tenant)), engine


@pytest.mark.asyncio
async def test_retry_exception_does_not_reinvoke_and_is_indeterminate(tmp_path):
    calls = []

    async def boom(args):
        calls.append(1)
        raise RuntimeError("connection reset after send")

    d, _ = make_dispatcher(tmp_path, boom, max_retries=5)
    with pytest.raises(EffectIndeterminate):
        await d.dispatch("act", {"x": 1}, task_id="T", node_id="N")
    assert len(calls) == 1                           # old dispatcher retried up to 5 times
    with pytest.raises(EffectIndeterminate):
        await d.dispatch("act", {"x": 1}, task_id="T", node_id="N")
    assert len(calls) == 1
    assert d.ledger.list()[0]["state"] == "indeterminate"


@pytest.mark.asyncio
async def test_provably_not_executed_failure_may_retry_same_effect(tmp_path):
    calls = []

    async def flaky(args):
        calls.append(1)
        if len(calls) == 1:
            raise ToolNotExecuted("connection refused before any bytes were sent")
        return {"ok": True}

    d, _ = make_dispatcher(tmp_path, flaky)
    rec = await d.dispatch("act", {}, task_id="T", node_id="N")
    assert rec.succeeded is False
    rec = await d.dispatch("act", {}, task_id="T", node_id="N")
    assert rec.succeeded and len(calls) == 2
    assert [(r["state"], r["attempt"]) for r in d.ledger.list()] == [("succeeded", 2)]


@pytest.mark.asyncio
async def test_provider_idempotency_key_allows_retry_of_indeterminate(tmp_path):
    seen = []

    async def provider(args):
        seen.append(CURRENT_EFFECT_ID.get())
        if len(seen) == 1:
            raise TimeoutError("response lost")
        return {"ok": True}

    d, _ = make_dispatcher(tmp_path, provider, provider_idempotent=True)
    with pytest.raises(EffectIndeterminate):
        await d.dispatch("act", {}, task_id="T", node_id="N")
    rec = await d.dispatch("act", {}, task_id="T", node_id="N")
    assert rec.succeeded and len(seen) == 2 and seen[0] == seen[1] and seen[0]


@pytest.mark.asyncio
async def test_succeeded_effect_is_replayed_from_receipt(tmp_path):
    calls = []

    async def once(args):
        calls.append(1); return {"n": len(calls)}

    d, _ = make_dispatcher(tmp_path, once)
    a = await d.dispatch("act", {}, task_id="T", node_id="N")
    b = await d.dispatch("act", {}, task_id="T", node_id="N")
    assert len(calls) == 1 and a.result_summary == b.result_summary


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger_sql, calls_expected, state_expected", [
    # reserve transaction fails -> rolled back, handler never runs, no row
    ("CREATE TRIGGER t BEFORE INSERT ON m20_effect_ledger BEGIN SELECT RAISE(ABORT,'disk full'); END", 0, None),
    # mark-invoking commit fails -> handler never runs; the dispatcher releases the
    # reservation (state 'failed', retakeable) instead of stranding it 'reserved'
    ("CREATE TRIGGER t BEFORE UPDATE ON m20_effect_ledger WHEN NEW.state='invoking' BEGIN SELECT RAISE(ABORT,'disk full'); END", 0, "failed"),
])
async def test_rollback_before_invocation_never_runs_handler(tmp_path, trigger_sql, calls_expected, state_expected):
    calls = []

    async def act(args):
        calls.append(1); return {}

    d, engine = make_dispatcher(tmp_path, act)
    with engine.begin() as c:
        c.exec_driver_sql(trigger_sql)
    with pytest.raises(Exception, match="disk full"):
        await d.dispatch("act", {}, task_id="T", node_id="N")
    assert len(calls) == calls_expected
    rows = d.ledger.list()
    assert (rows[0]["state"] if rows else None) == state_expected


@pytest.mark.asyncio
async def test_receipt_commit_failure_is_indeterminate_and_not_replayed(tmp_path):
    calls = []

    async def act(args):
        calls.append(1); return {}

    d, engine = make_dispatcher(tmp_path, act)
    with engine.begin() as c:
        c.exec_driver_sql("CREATE TRIGGER t BEFORE UPDATE ON m20_effect_ledger WHEN NEW.state='succeeded' "
                          "BEGIN SELECT RAISE(ABORT,'disk full'); END")
    with pytest.raises(EffectIndeterminate):
        await d.dispatch("act", {}, task_id="T", node_id="N")
    assert d.ledger.list()[0]["state"] == "invoking"      # rolled back, never 'succeeded'
    with engine.begin() as c:
        c.exec_driver_sql("DROP TRIGGER t")
    # same live owner process: held, not re-invoked
    with pytest.raises(EffectInProgress):
        await d.dispatch("act", {}, task_id="T", node_id="N")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_identity_is_immutable_and_ignores_runtime_bookkeeping(tmp_path):
    async def act(args):
        return {}

    d, _ = make_dispatcher(tmp_path, act)
    await d.dispatch("act", {"to": "a", "_expectation_claim_id": "1"}, task_id="T", node_id="N")
    await d.dispatch("act", {"to": "a", "_expectation_claim_id": "2"}, task_id="T", node_id="N")
    assert len(d.ledger.list()) == 1          # both calls are the same effect; one row


def test_identity_conflict_on_same_key_different_args(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'i.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    res = ledger.reserve(task_id="T", node_id="N", tool="act", args={"to": "a"})
    eid, _ = effect_identity("t1", "T", "N", "act", {"to": "a"})
    assert res.effect_id == eid
    with engine.begin() as c:                         # simulate tampered/colliding row
        c.execute(sa.text("UPDATE m20_effect_ledger SET args_hash='other'"))
    with pytest.raises(EffectIdentityConflict):
        ledger.reserve(task_id="T", node_id="N", tool="act", args={"to": "a"})


@pytest.mark.asyncio
async def test_tenant_boundary(tmp_path):
    calls = {"a": 0, "b": 0}
    engine = sa.create_engine(f"sqlite:///{tmp_path/'tn.sqlite'}", connect_args={"timeout": 30})

    def disp(tenant):
        async def act(args):
            calls[tenant] += 1; return {"t": tenant}
        reg = ToolRegistry(); reg.register(ToolSpec(name="act", description="x", risk=Risk.REVERSIBLE), act)
        return ToolDispatcher(reg, SafetyGate(), EffectLedger(engine, tenant))

    a, b = disp("a"), disp("b")
    await a.dispatch("act", {"v": 1}, task_id="T", node_id="N")
    await b.dispatch("act", {"v": 1}, task_id="T", node_id="N")   # identical ids/args, other tenant
    assert calls == {"a": 1, "b": 1}
    assert len(a.ledger.list()) == 1 and len(b.ledger.list()) == 1
    eid_a, _ = effect_identity("a", "T", "N", "act", {"v": 1})
    assert b.ledger.get(eid_a) is None
    # tenant b cannot reconcile or see tenant a's indeterminate effect
    with engine.begin() as c:
        c.execute(sa.text("UPDATE m20_effect_ledger SET state='indeterminate' WHERE tenant_id='a'"))
    with pytest.raises(Exception):
        b.ledger.reconcile(eid_a, outcome="applied", actor="x", note="y")
    assert a.ledger.get(eid_a)["state"] == "indeterminate"
    with pytest.raises(ValueError):
        EffectLedger(engine, "")
