"""Owning-loop defect: a failing approval store used to be swallowed by
gather(return_exceptions=True). The step stayed PENDING, the run stayed
RUNNING/blocked silently, and nothing was traced. These tests inject a store
that really raises and require the error to be visible on step, run and trace,
and the external sender to never be called."""
import pytest
from app.modules.m20_general_cognitive_worker.legacy_service import *
from test_m20_general_cognitive_worker import Model, Adapter


class BrokenApprovals:
    def put(self, item):
        raise RuntimeError("no such table: m00_approval_events")

    def list(self):
        raise RuntimeError("no such table: m00_approval_events")


async def _service(store):
    service = Service(store, Model())
    reader, sender = Adapter(), Adapter()
    service.tools.register(Tool("reader", "read", Risk.READ, {"read"}, reader))
    service.tools.register(Tool("sender", "send", Risk.EXTERNAL, {"send"}, sender))
    return service, sender


@pytest.mark.asyncio
async def test_approval_store_failure_is_surfaced_not_swallowed():
    service, sender = await _service(BrokenApprovals())
    run = await service.start("research then send", {}, {"seconds": 10, "tokens": 100, "money": 0})
    send = run.plan.steps[1]
    assert sender.calls == 0  # safe direction: no external effect
    assert send.state == State.BLOCKED
    assert "no such table" in send.error and "approval" in send.error.lower()
    assert run.status == State.BLOCKED
    assert any("approval" in t.summary.lower() and "no such table" in t.summary
               for t in run.traces), [t.summary for t in run.traces]


@pytest.mark.asyncio
async def test_unexpected_step_exception_is_traced_and_blocks_run():
    class Weird(BrokenApprovals):
        pass

    service, sender = await _service(Weird())
    original = service.loop._step

    async def boom(run, step):
        if step.tool == "reader":
            raise KeyError("scheduler-level failure")
        return await original(run, step)

    service.loop._step = boom
    run = await service.start("research then send", {}, {"seconds": 10, "tokens": 100, "money": 0})
    read = run.plan.steps[0]
    assert read.state == State.FAILED and "scheduler-level failure" in read.error
    assert run.status == State.BLOCKED
    assert any("scheduler-level failure" in t.summary for t in run.traces)
    assert sender.calls == 0
