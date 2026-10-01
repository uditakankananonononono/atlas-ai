"""Audit regressions, round 3.

F1: legacy "|"-joined id lookup must verify the row is the same effect.
L2: a RESERVED row whose mark_invoking failed must be released, not left
    EffectInProgress behind a live owner.
L3: owner token includes boot/PID-namespace identity; a zombie leader with
    live threads is alive.
"""
import os
import socket
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from app.modules.m20_general_cognitive_worker.effect_ledger import (
    EffectInProgress, EffectLedger, _environment_token, _owner_process_alive,
    _proc_state_and_start, current_owner_token, effect_identity, legacy_effect_identity,
)
from test_effect_ledger import make_dispatcher

NOW = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


def _insert_row(engine, *, effect_id, task, node, tool="act", args_hash, state="succeeded",
                summary="old receipt", tenant="t1"):
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO m20_effect_ledger (tenant_id, effect_id, task_id, node_id, tool,"
                    " args_hash, state, attempt, owner, owner_host, owner_pid, owner_pid_start,"
                    " lease_expires_at, result_summary, error, note, created_at, updated_at)"
                    " VALUES (:tenant, :eid, :task, :node, :tool, :h, :state, 1, 'old-worker',"
                    " 'old-host', 1, '', :now, :summary, '', '', :now, :now)"),
            {"tenant": tenant, "eid": effect_id, "task": task, "node": node, "tool": tool,
             "h": args_hash, "state": state, "summary": summary, "now": NOW()})


# --- F1 --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migrated_row_collision_does_not_replay_for_distinct_effect(tmp_path):
    """Pre-fix row (task='T|N', node='X') shares its legacy id with the distinct
    effect (task='T', node='N|X'). The distinct effect must run, not replay."""
    calls = []

    async def act(args):
        calls.append(1)
        return {"real": len(calls)}

    dispatcher, engine = make_dispatcher(tmp_path, act)
    legacy_id = legacy_effect_identity("t1", "T|N", "X", "act", {})
    _, args_hash = effect_identity("t1", "T|N", "X", "act", {})
    _insert_row(engine, effect_id=legacy_id, task="T|N", node="X", args_hash=args_hash)

    rec = await dispatcher.dispatch("act", {}, task_id="T", node_id="N|X")
    assert calls == [1], "distinct effect was silently replayed from another effect's receipt"
    assert rec.result_summary != "old receipt"
    rows = {r["effect_id"]: r for r in dispatcher.ledger.list()}
    assert rows[legacy_id]["result_summary"] == "old receipt"        # legacy row untouched
    new_id, _ = effect_identity("t1", "T", "N|X", "act", {})
    assert rows[new_id]["state"] == "succeeded"

    # The legacy row's own effect still replays its receipt.
    again = await dispatcher.dispatch("act", {}, task_id="T|N", node_id="X")
    assert again.result_summary == "old receipt" and calls == [1]


def test_legacy_row_with_mismatched_tool_or_args_is_ignored(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    legacy_id = legacy_effect_identity("t1", "T", "N", "act", {"a": 1})
    _, args_hash = effect_identity("t1", "T", "N", "act", {"a": 1})
    _insert_row(engine, effect_id=legacy_id, task="T", node="N", tool="other_tool", args_hash=args_hash)
    assert ledger.get_legacy("T", "N", "act", args_hash) is None
    _insert_row(engine, effect_id=legacy_effect_identity("t1", "T", "N2", "act", {}),
                task="T", node="N2", args_hash="0" * 64)
    _, h2 = effect_identity("t1", "T", "N2", "act", {})
    assert ledger.get_legacy("T", "N2", "act", h2) is None
    # Matching row is accepted.
    _insert_row(engine, effect_id=legacy_effect_identity("t1", "T", "N3", "act", {}),
                task="T", node="N3", args_hash=effect_identity("t1", "T", "N3", "act", {})[1])
    assert ledger.get_legacy("T", "N3", "act", effect_identity("t1", "T", "N3", "act", {})[1]) is not None


def test_reconcile_resolution_ignores_colliding_legacy_row(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'r.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    legacy_id = legacy_effect_identity("t1", "T|N", "X", "act", {})
    _, args_hash = effect_identity("t1", "T|N", "X", "act", {})
    _insert_row(engine, effect_id=legacy_id, task="T|N", node="X", args_hash=args_hash,
                state="indeterminate")
    # Colliding distinct effect resolves to its own (new) id, so reconcile cannot touch the other row.
    new_id, _ = effect_identity("t1", "T", "N|X", "act", {})
    assert ledger.resolve_effect_id("T", "N|X", "act", {}) == new_id
    from app.modules.m20_general_cognitive_worker.effect_ledger import EffectError
    with pytest.raises(EffectError):
        ledger.reconcile(new_id, outcome="applied", actor="op", note="n")
    assert ledger.get(legacy_id)["state"] == "indeterminate"
    # The row's real owner still resolves to the legacy id.
    assert ledger.resolve_effect_id("T|N", "X", "act", {}) == legacy_id


# --- L2 --------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("commit_landed", [False, True])
async def test_mark_invoking_failure_releases_reservation(tmp_path, commit_landed):
    """mark_invoking raising (before the commit, or after it with the ack lost)
    must not leave a live-owner row stuck. The handler never ran."""
    calls = []

    async def act(args):
        calls.append(1)
        return "ok"

    dispatcher, _ = make_dispatcher(tmp_path, act)
    ledger = dispatcher.ledger
    real = ledger.mark_invoking
    armed = {"on": True}

    def flaky(res):
        if armed["on"]:
            if commit_landed:
                real(res)
            raise OperationalError("UPDATE", {}, Exception("connection lost"))
        return real(res)

    ledger.mark_invoking = flaky
    with pytest.raises(OperationalError):
        await dispatcher.dispatch("act", {}, task_id="T", node_id="N")
    assert calls == []
    row = ledger.list()[0]
    assert row["state"] == "failed" and row["error"].startswith("not executed")

    armed["on"] = False            # same live process retries: no EffectInProgress
    rec = await dispatcher.dispatch("act", {}, task_id="T", node_id="N")
    assert rec.succeeded and calls == [1]


def test_release_does_not_touch_a_reservation_taken_by_another_worker(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'o.sqlite'}")
    a, b = EffectLedger(engine, "t1"), EffectLedger(engine, "t1")
    res = a.reserve(task_id="T", node_id="N", tool="act", args={})
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE m20_effect_ledger SET owner='someone-else'"))
    assert b.release(res, "x") is False
    assert a.list()[0]["state"] == "reserved"


# --- L3 --------------------------------------------------------------------

pytestmark_proc = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="Linux /proc only")


@pytestmark_proc
def test_owner_token_has_boot_and_namespace_and_rejects_foreign_boot(tmp_path):
    token = current_owner_token()
    env, _, start = token.rpartition(":")
    assert env == _environment_token() and start == _proc_state_and_start(os.getpid())[1]
    assert len(token) <= 64
    assert _owner_process_alive(os.getpid(), token) is True
    boot, ns = env.split(".")
    other_boot = ("000000" if boot != "000000" else "111111") + "." + ns
    # Reboot: same PID, same start ticks, different boot id -> dead.
    assert _owner_process_alive(os.getpid(), f"{other_boot}:{start}") is False
    # Different PID namespace on the same boot: unverifiable, caller uses the lease.
    assert _owner_process_alive(os.getpid(), f"{boot}.1:{start}") is None
    engine = sa.create_engine(f"sqlite:///{tmp_path / 't.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    base = {"owner_host": socket.gethostname(), "owner_pid": os.getpid(), "lease_expires_at": past}
    assert ledger._owner_dead({**base, "owner_pid_start": f"{other_boot}:{start}"}) is True
    assert ledger._owner_dead({**base, "owner_pid_start": f"{boot}.1:{start}"}) is True            # lease expired
    assert ledger._owner_dead({**base, "owner_pid_start": f"{boot}.1:{start}",
                               "lease_expires_at": future}) is False                              # lease live
    assert ledger._owner_dead({**base, "owner_pid_start": token}) is False
    assert ledger._owner_dead({**base, "owner_pid_start": start}) is False                        # legacy bare token
    assert ledger._owner_dead({**base, "owner_pid_start": f"{boot}.{ns}:1"}) is True              # PID reuse


@pytestmark_proc
def test_reserve_stores_boot_aware_token(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 's.sqlite'}")
    ledger = EffectLedger(engine, "t1")
    ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    assert ledger.list()[0]["owner_pid_start"] == current_owner_token()


@pytestmark_proc
def test_zombie_leader_with_live_threads_is_alive(tmp_path):
    """After the main thread calls pthread_exit the leader shows state Z while
    other threads keep running. That process is alive; a plain zombie is not."""
    ready = tmp_path / "ready"
    code = textwrap.dedent(f"""
        import ctypes, threading, time, pathlib
        t = threading.Thread(target=lambda: time.sleep(30), daemon=True); t.start()
        pathlib.Path({str(ready)!r}).write_text('1')
        ctypes.CDLL(None).pthread_exit(None)
    """)
    proc = subprocess.Popen([sys.executable, "-c", code])
    try:
        end = time.monotonic() + 15
        while time.monotonic() < end and _proc_state_and_start(proc.pid)[0] != "Z":
            time.sleep(0.05)
        assert _proc_state_and_start(proc.pid)[0] == "Z", "leader never became a zombie"
        assert _owner_process_alive(proc.pid, "") is True
        assert _owner_process_alive(proc.pid, current_owner_token(proc.pid)) is True
    finally:
        proc.kill()
        proc.wait()
    # Plain zombie (no threads) is still dead.
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    try:
        end = time.monotonic() + 5
        while time.monotonic() < end and _proc_state_and_start(pid)[0] != "Z":
            time.sleep(0.01)
        assert _owner_process_alive(pid, "") is False
    finally:
        os.waitpid(pid, 0)


def test_runtime_reconcile_does_not_hit_colliding_legacy_row(tmp_path):
    """GCWRuntime.reconcile_effect for (task='T', node='N|X') must not reconcile
    the pre-fix indeterminate row that belongs to (task='T|N', node='X')."""
    from app.modules.m20_general_cognitive_worker.effect_ledger import EffectError
    from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
    from app.modules.m20_general_cognitive_worker.schemas import PlanNode, Risk, TaskContext, TaskState
    from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'rt.sqlite'}")
    repo = GCWRepository(engine, tenant_id="t1")
    repo.create_schema()
    runtime = GCWRuntime(repo)
    node = PlanNode(id="N|X", title="deliver", tool="act", risk=Risk.REVERSIBLE, arguments={})
    context = TaskContext(id="T", goal="g", plan=[node], state=TaskState.RUNNING)
    repo.save_task(context)
    legacy_id = legacy_effect_identity("t1", "T|N", "X", "act", {})
    _insert_row(engine, effect_id=legacy_id, task="T|N", node="X", state="indeterminate",
                args_hash=effect_identity("t1", "T|N", "X", "act", {})[1])
    with pytest.raises(EffectError):
        runtime.reconcile_effect("T", "N|X", outcome="applied", actor="op", note="n")
    assert runtime.ledger.get(legacy_id)["state"] == "indeterminate"
