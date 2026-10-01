"""Real database and handler regressions for audit limits L1-L4. No stubs."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa

from app.modules.m20_general_cognitive_worker.effect_ledger import (
    EffectIndeterminate, EffectInProgress, EffectLedger, effects, worker_identity,
)
from app.modules.m20_general_cognitive_worker.schemas import Risk, ToolSpec
from app.modules.m20_general_cognitive_worker.safety import SafetyGate
from app.modules.m20_general_cognitive_worker.tools import ToolBlockedError, ToolDispatcher, ToolRegistry


def test_worker_id_fits_existing_owner_column(tmp_path):
    # Linux permits a 64-byte hostname. No socket stub needed on this host:
    # enforce the bound of the encoding itself as well as the generated id.
    import socket
    ledger = EffectLedger(sa.create_engine(f"sqlite:///{tmp_path / 'owner.db'}"), "t")
    assert len(worker_identity("h" * 255, 2147483647)) <= 64
    assert len(ledger.worker_id) <= 64
    assert socket.gethostname() not in ledger.worker_id
    res = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    assert ledger.get(res.effect_id)["owner_host"] == socket.gethostname()


def test_concurrent_first_boot(tmp_path):
    """Synchronize real CREATE statements after checkfirst has found no table."""
    barrier = Barrier(2)
    url = f"sqlite:///{tmp_path / 'boot.db'}"

    def boot():
        engine = sa.create_engine(url, connect_args={"timeout": 30})
        @sa.event.listens_for(engine, "before_cursor_execute")
        def synchronize(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().startswith("CREATE TABLE m20_effect_ledger"):
                barrier.wait(timeout=10)
        try:
            ledger = EffectLedger(engine, "t")
            return ledger.list()
        finally:
            engine.dispose()

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(boot) for _ in range(2)]
        assert [future.result(timeout=20) for future in futures] == [[], []]


@pytest.mark.parametrize("action", ["release", "complete", "fail_safe", "mark_indeterminate", "mark_invoking"])
def test_stale_same_owner_attempt_cannot_change_live_row(tmp_path, action):
    ledger = EffectLedger(sa.create_engine(f"sqlite:///{tmp_path / 'cas.db'}"), "t")
    old = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    assert ledger.release(old, "provably never executed")
    live = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    assert live.owner == old.owner and live.attempt > old.attempt
    if action != "mark_invoking":
        ledger.mark_invoking(live)
    before = ledger.get(live.effect_id)
    if action == "mark_invoking":
        with pytest.raises(EffectInProgress):
            ledger.mark_invoking(old)
    elif action == "complete":
        with pytest.raises(EffectIndeterminate):
            ledger.complete(old, "stale receipt")
    elif action == "release":
        assert ledger.release(old, "stale release") is False
    else:
        getattr(ledger, action)(old, "stale error")
    assert ledger.get(live.effect_id) == before


def test_reserved_retake_increments_fence_even_with_same_owner(tmp_path):
    ledger = EffectLedger(sa.create_engine(f"sqlite:///{tmp_path / 'retake.db'}"), "t")
    old = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    # Actual persisted dead-process state, not a mocked liveness check.
    with ledger.engine.begin() as conn:
        conn.execute(sa.update(effects).values(owner_pid=0))
    live = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    assert live.attempt > old.attempt
    assert ledger.release(old, "stale") is False
    ledger.mark_invoking(live)
    ledger.complete(live, "new receipt")


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [{}, {"task_id": "T"}, {"node_id": "N"},
                                 {"task_id": "", "node_id": "N"},
                                 {"task_id": "T", "node_id": " "}])
async def test_non_read_requires_stable_ids_before_handler_or_reserve(tmp_path, ids):
    calls = []
    async def act(args):
        calls.append(args)
        return "ok"
    registry = ToolRegistry()
    registry.register(ToolSpec(name="act", description="x", risk=Risk.REVERSIBLE), act)
    ledger = EffectLedger(sa.create_engine(f"sqlite:///{tmp_path / 'dispatch.db'}"), "t")
    dispatcher = ToolDispatcher(registry, SafetyGate(), ledger)
    with pytest.raises(ToolBlockedError, match="task_id and node_id"):
        await dispatcher.dispatch("act", {}, **ids)
    assert calls == [] and ledger.list() == []


@pytest.mark.asyncio
async def test_read_still_runs_each_time_without_ids(tmp_path):
    calls = []
    async def read(args):
        calls.append(1)
        return "ok"
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read", description="x", risk=Risk.READ), read)
    ledger = EffectLedger(sa.create_engine(f"sqlite:///{tmp_path / 'read.db'}"), "t")
    dispatcher = ToolDispatcher(registry, SafetyGate(), ledger)
    for _ in range(2):
        assert (await dispatcher.dispatch("read", {})).succeeded
    assert calls == [1, 1] and ledger.list() == []


def test_unrelated_startup_database_error_is_not_swallowed(tmp_path):
    path = tmp_path / "read-only.db"
    seed = sa.create_engine(f"sqlite:///{path}")
    with seed.begin() as conn:
        conn.execute(sa.text("CREATE TABLE unrelated (id INTEGER)"))
    seed.dispose()
    engine = sa.create_engine(f"sqlite:///file:{path}?mode=ro&uri=true")
    try:
        with pytest.raises(sa.exc.OperationalError, match="readonly"):
            EffectLedger(engine, "t")
    finally:
        engine.dispose()
