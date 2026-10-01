"""Audit regressions: file-backed external writes and real killed workers, offline."""
import os
import signal

import pytest

from app.modules.m20_general_cognitive_worker.effect_ledger import (
    EffectError, EffectIndeterminate, EffectInProgress,
)
from app.modules.m20_general_cognitive_worker.tools import ApprovalPending, ToolError
from test_effect_ledger import counter, js, make_dispatcher, submit, worker


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ToolError("provider response lost after write"),
                                  ApprovalPending("act", "late-handler-approval")])
async def test_handler_toolerror_after_external_write_never_reinvokes(tmp_path, error):
    async def write_then_error(args):
        path = tmp_path / "counter"
        with path.open("a+") as f:
            f.seek(0)
            value = int(f.read() or 0) + 1
            f.seek(0)
            f.truncate()
            f.write(str(value))
            f.flush()
            os.fsync(f.fileno())
        raise error

    dispatcher, _ = make_dispatcher(tmp_path, write_then_error, max_retries=5)
    errors = []
    for _ in range(2):
        try:
            await dispatcher.dispatch("act", {}, task_id="T", node_id="N")
        except Exception as exc:
            errors.append(exc)
    assert counter(tmp_path) == 1, f"external writes performed: {counter(tmp_path)}"
    assert len(errors) == 2 and all(isinstance(e, EffectIndeterminate) for e in errors)
    assert [(r["state"], r["attempt"]) for r in dispatcher.ledger.list()] == [("indeterminate", 1)]


@pytest.mark.asyncio
async def test_underscore_destination_is_real_identity_not_bookkeeping(tmp_path):
    async def deliver(args):
        with (tmp_path / "deliveries").open("a") as f:
            f.write(args["_destination"] + "\n")
            f.flush()
            os.fsync(f.fileno())
        return {"delivered_to": args["_destination"]}

    dispatcher, _ = make_dispatcher(tmp_path, deliver)
    a = await dispatcher.dispatch("act", {"_destination": "alice", "_expectation_claim_id": "1"},
                                  task_id="T", node_id="N")
    b = await dispatcher.dispatch("act", {"_destination": "bob", "_expectation_claim_id": "2"},
                                  task_id="T", node_id="N")
    replay = await dispatcher.dispatch("act", {"_destination": "bob", "_expectation_claim_id": "3"},
                                       task_id="T", node_id="N")
    assert (tmp_path / "deliveries").read_text().splitlines() == ["alice", "bob"]
    assert a.result_summary != b.result_summary == replay.result_summary
    assert len(dispatcher.ledger.list()) == 2


@pytest.mark.parametrize("point,outcome", [("after_effect", "applied"), ("before_effect", "not_applied")])
def test_reconcile_immediately_after_crash_without_restart_run(tmp_path, point, outcome):
    task = submit(tmp_path)
    assert worker(tmp_path, "run", task, crash=point).returncode == -signal.SIGKILL
    info = js(worker(tmp_path, "inspect", task))
    assert info["ledger"] == [["invoking", 1]]
    result = worker(tmp_path, "reconcile", task, info["node_id"], outcome)
    assert result.returncode == 0, result.stderr
    assert js(result)["state"] == "running"
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1
    assert js(worker(tmp_path, "run", task))["state"] == "succeeded"
    assert counter(tmp_path) == 1


def test_reconcile_refuses_live_invocation_and_reserved_effect(tmp_path):
    async def act(args):
        return {}

    dispatcher, _ = make_dispatcher(tmp_path, act)
    ledger = dispatcher.ledger
    res = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    with pytest.raises(EffectError):
        ledger.reconcile(res.effect_id, outcome="applied", actor="op", note="verified")
    ledger.mark_invoking(res)
    with pytest.raises(EffectInProgress):
        ledger.reconcile(res.effect_id, outcome="applied", actor="op", note="verified")
    assert ledger.get(res.effect_id)["state"] == "invoking"


def test_reconcile_hash_matches_dispatch_with_persisted_claim(tmp_path):
    from sqlalchemy import create_engine
    from app.modules.m20_general_cognitive_worker.effect_ledger import effect_identity
    from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
    from app.modules.m20_general_cognitive_worker.schemas import PlanNode, Risk, TaskContext, TaskState
    from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository

    repo = GCWRepository(create_engine(f"sqlite:///{tmp_path / 'runtime.sqlite'}"), tenant_id="t1")
    repo.create_schema()
    runtime = GCWRuntime(repo)
    node = PlanNode(title="deliver", tool="act", risk=Risk.REVERSIBLE,
                    arguments={"_destination": "alice", "_expectation_claim_id": "persisted-claim"})
    context = TaskContext(goal="deliver once", plan=[node], state=TaskState.RUNNING)
    repo.save_task(context)
    res = runtime.ledger.reserve(task_id=context.id, node_id=node.id, tool="act",
                                 args={"_destination": "alice", "_expectation_claim_id": "dispatch-claim"})
    runtime.ledger.mark_invoking(res)
    runtime.ledger.mark_indeterminate(res, "response lost")
    result = runtime.reconcile_effect(context.id, node.id, outcome="applied", actor="op", note="verified alice")
    assert result.plan[0].state == TaskState.SUCCEEDED
    assert runtime.ledger.get(res.effect_id)["state"] == "reconciled_applied"
    assert res.effect_id == effect_identity("t1", context.id, node.id, "act", node.arguments)[0]
    assert res.effect_id != effect_identity("t1", context.id, node.id, "act", {"_destination": "bob"})[0]


def test_reconcile_cannot_override_receipt_or_other_tenant(tmp_path):
    from app.modules.m20_general_cognitive_worker.effect_ledger import EffectLedger

    async def act(args):
        return {}

    dispatcher, engine = make_dispatcher(tmp_path, act)
    ledger = dispatcher.ledger
    res = ledger.reserve(task_id="T", node_id="N", tool="act", args={})
    ledger.mark_invoking(res)
    ledger.complete(res, "provider receipt")
    with pytest.raises(EffectError):
        ledger.reconcile(res.effect_id, outcome="not_applied", actor="op", note="wrong")
    assert ledger.get(res.effect_id)["state"] == "succeeded"
    other = EffectLedger(engine, "t2")
    with pytest.raises(EffectError):
        other.reconcile(res.effect_id, outcome="applied", actor="op", note="wrong tenant")
    assert ledger.get(res.effect_id)["result_summary"] == "provider receipt"
