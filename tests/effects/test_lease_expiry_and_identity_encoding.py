"""Audit regressions, round 2:

F1: _owner_dead treated an expired lease as a dead owner without checking the
    owner PID. A handler that blocks the event loop past timeout+30s (its
    lease) could be reconciled/retaken while alive -> double external write.
F2: effect_identity joined components with "|", so (task='T|N', node='X')
    collided with (task='T', node='N|X') and the second effect silently
    replayed the first receipt.
"""
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.modules.m20_general_cognitive_worker.effect_ledger import (
    EffectInProgress, EffectLedger, effect_identity,
)
from test_effect_ledger import counter, make_dispatcher

LIVE_WORKER = str(Path(__file__).with_name("live_owner_worker.py"))


def _wait_for(path: Path, timeout: float = 15.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists():
            return
        time.sleep(0.01)
    pytest.fail(f"worker did not reach {path.name}")


def test_live_owner_past_lease_is_never_retaken_or_reconciled(tmp_path):
    """The auditor's sleep-past-lease case: the handler blocks the loop past
    its lease while the owner process is alive. Reconcile and retake must both
    be refused, and the external effect must happen exactly once."""
    env = dict(os.environ, EFFECT_LEASE="0.3", EFFECT_HOLD="2.5")
    proc = subprocess.Popen(
        [sys.executable, LIVE_WORKER, str(tmp_path / "live.sqlite"), str(tmp_path / "counter"),
         "t1", str(tmp_path / "entered")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _wait_for(tmp_path / "entered")            # owner is inside the handler, loop blocked
        time.sleep(0.6)                            # lease (0.3s) expired; owner still alive
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'live.sqlite'}",
                                  connect_args={"timeout": 30})
        other = EffectLedger(engine, "t1")
        effect_id, _ = effect_identity("t1", "T", "N", "act", {})
        row = other.get(effect_id)
        assert row is not None and row["state"] == "invoking"
        assert datetime.fromisoformat(row["lease_expires_at"]) <= datetime.now(timezone.utc)
        with pytest.raises(EffectInProgress):
            other.reconcile(effect_id, outcome="not_applied", actor="op", note="looks stuck")
        with pytest.raises(EffectInProgress):
            other.reserve(task_id="T", node_id="N", tool="act", args={})
        assert other.get(effect_id)["state"] == "invoking"
    finally:
        out, err = proc.communicate(timeout=30)
    assert proc.returncode == 0, (out, err)
    assert counter(tmp_path) == 1                  # exactly one external write
    assert other.get(effect_id)["state"] == "succeeded"


def test_owner_liveness_rules(tmp_path):
    """Same-host liveness = live PID + process start-time identity (PID-reuse
    guard); the lease alone never kills a live same-host owner. Cross-host
    owners remain bounded by the lease only."""
    from app.modules.m20_general_cognitive_worker.effect_ledger import _proc_state_and_start

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'l.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    _, my_start = _proc_state_and_start(os.getpid())
    base = {"owner_host": socket.gethostname(), "owner_pid": os.getpid(),
            "owner_pid_start": my_start, "lease_expires_at": past}

    assert ledger._owner_dead(base) is False                 # live owner, expired lease
    assert ledger._owner_dead({**base, "owner_pid_start": "1"}) is True   # PID reused
    assert ledger._owner_dead({**base, "owner_pid": 2 ** 22}) is True     # no such process
    assert ledger._owner_dead({**base, "owner_pid_start": ""}) is False   # legacy row: live PID
    # Cross-host: the lease decides, PID checks do not apply.
    assert ledger._owner_dead({**base, "owner_host": "other-host"}) is True
    assert ledger._owner_dead({**base, "owner_host": "other-host",
                               "lease_expires_at": future}) is False


@pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="Linux /proc only")
def test_zombie_owner_is_dead(tmp_path):
    """A SIGKILLed but unreaped owner is a zombie: kill(pid, 0) succeeds on it,
    but it must count as dead."""
    from app.modules.m20_general_cognitive_worker.effect_ledger import (
        _owner_process_alive, _proc_state_and_start)

    pid = os.fork()
    if pid == 0:
        os._exit(0)
    try:
        end = time.monotonic() + 5
        while time.monotonic() < end and _proc_state_and_start(pid)[0] != "Z":
            time.sleep(0.01)
        assert _proc_state_and_start(pid)[0] == "Z"
        assert _owner_process_alive(pid, "") is False
    finally:
        os.waitpid(pid, 0)


def test_prerelease_pipe_joined_rows_remain_authoritative(tmp_path):
    """Compat: a row written before the identity-encoding fix keeps its old
    "|"-joined id. Dispatch replays its receipt instead of re-invoking, and
    no duplicate row is created under the new id."""
    from app.modules.m20_general_cognitive_worker.effect_ledger import legacy_effect_identity

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    legacy_id = legacy_effect_identity("t1", "T", "N", "act", {"to": "a"})
    new_id, args_hash = effect_identity("t1", "T", "N", "act", {"to": "a"})
    assert legacy_id != new_id
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO m20_effect_ledger (tenant_id, effect_id, task_id, node_id, tool,"
                    " args_hash, state, attempt, owner, owner_host, owner_pid, owner_pid_start,"
                    " lease_expires_at, result_summary, error, note, created_at, updated_at)"
                    " VALUES ('t1', :eid, 'T', 'N', 'act', :h, 'succeeded', 1, 'old-worker',"
                    " 'old-host', 1, '', :now, 'old receipt', '', '', :now, :now)"),
            {"eid": legacy_id, "h": args_hash, "now": now})
    res = ledger.reserve(task_id="T", node_id="N", tool="act", args={"to": "a"})
    assert res.replayed and res.result_summary == "old receipt"
    assert res.effect_id == legacy_id
    assert [r["effect_id"] for r in ledger.list()] == [legacy_id]   # no duplicate new-id row


@pytest.mark.asyncio
async def test_prerelease_indeterminate_row_reconcilable_via_runtime(tmp_path):
    """Compat: GCWRuntime.reconcile_effect reaches a pre-upgrade indeterminate
    row through the legacy identity fallback."""
    from app.modules.m20_general_cognitive_worker.effect_ledger import legacy_effect_identity
    from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
    from app.modules.m20_general_cognitive_worker.schemas import PlanNode, Risk, TaskContext, TaskState
    from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'rt.sqlite'}")
    repo = GCWRepository(engine, tenant_id="t1")
    repo.create_schema()
    runtime = GCWRuntime(repo)
    node = PlanNode(title="deliver", tool="act", risk=Risk.REVERSIBLE, arguments={"to": "a"})
    context = TaskContext(goal="deliver once", plan=[node], state=TaskState.RUNNING)
    repo.save_task(context)
    legacy_id = legacy_effect_identity("t1", context.id, node.id, "act", node.arguments)
    _, args_hash = effect_identity("t1", context.id, node.id, "act", node.arguments)
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO m20_effect_ledger (tenant_id, effect_id, task_id, node_id, tool,"
                    " args_hash, state, attempt, owner, owner_host, owner_pid, owner_pid_start,"
                    " lease_expires_at, result_summary, error, note, created_at, updated_at)"
                    " VALUES ('t1', :eid, :task, :node, 'act', :h, 'indeterminate', 1, 'old-worker',"
                    " 'old-host', 1, '', :now, '', 'response lost', '', :now, :now)"),
            {"eid": legacy_id, "h": args_hash, "task": context.id, "node": node.id, "now": now})
    result = runtime.reconcile_effect(context.id, node.id, outcome="applied", actor="op", note="verified")
    assert result.plan[0].state == TaskState.SUCCEEDED
    assert runtime.ledger.get(legacy_id)["state"] == "reconciled_applied"


def test_effect_identity_separator_in_components_never_collides():
    a, _ = effect_identity("t1", "T|N", "X", "act", {})
    b, _ = effect_identity("t1", "T", "N|X", "act", {})
    assert a != b


@pytest.mark.asyncio
async def test_separator_in_task_or_node_does_not_false_replay(tmp_path):
    """(task='T|N', node='X') and (task='T', node='N|X') are different effects:
    the second dispatch must invoke its handler, not replay the first receipt."""
    calls = []

    async def act(args):
        calls.append(1)
        return {"n": len(calls)}

    dispatcher, _ = make_dispatcher(tmp_path, act)
    first = await dispatcher.dispatch("act", {}, task_id="T|N", node_id="X")
    second = await dispatcher.dispatch("act", {}, task_id="T", node_id="N|X")
    assert len(calls) == 2
    assert first.result_summary != second.result_summary
    assert len(dispatcher.ledger.list()) == 2
