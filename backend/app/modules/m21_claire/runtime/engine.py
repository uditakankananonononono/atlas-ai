from __future__ import annotations
import asyncio, json
from threading import Event
from typing import Any, Callable, Protocol
from pydantic import ValidationError
from . import bounded
from .redaction import redact, scrub_text
from .gates import GateRefused, Principal
from .tools import ReadOnlyToolRegistry
from .types import AgentDecision, Refusal, ReplanRecord, RunReport

SYSTEM = """You are Claire's work engine. Work toward the goal with the available tools. Never claim an action
succeeded unless a tool receipt proves it. Respond only as JSON with exactly one action:
{"thought":"brief reason","tool_call":{"name":"...","arguments":{...}}},
{"thought":"brief reason","replan":{"reason":"why","steps":["new step"]}}, or
{"thought":"brief reason","final":"answer"}. Stop when done or blocked and name the blocker."""


class ModelUnavailable(RuntimeError):
    """Raised by a model adapter when no usable model answered. Carries no provider text."""


class ModelPort(Protocol):
    async def decide(self, messages: list[dict[str, str]]) -> AgentDecision: ...


class ActionPolicy(Protocol):
    def allows(self, tool: str, arguments: dict[str, Any]) -> bool: ...


class NoAdditionalPolicy:
    """Extra per-call hook with no extra rules. NOT a security control: gating is the registry's GateEnforcer."""
    def allows(self, tool: str, arguments: dict[str, Any]) -> bool:
        return True


def _checked_timeout(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.05 <= value <= 3600:  # NaN fails the comparison
        raise ValueError("model_timeout_seconds must be between 0.05 and 3600")
    return float(value)


class Engine:
    """Bounded loop. Produces a RunReport (evidence). Completion is decided elsewhere."""

    def __init__(self, model: ModelPort | None, tools: ReadOnlyToolRegistry, *, max_steps: int = 12,
                 policy: ActionPolicy | None = None, cancel_poll_seconds: float = 0.2,
                 model_timeout_seconds: float | None = None) -> None:
        if not 1 <= max_steps <= 50:
            raise ValueError("max_steps must be between 1 and 50")
        self.model, self.tools, self.max_steps = model, tools, max_steps
        self.policy = policy or NoAdditionalPolicy()
        if not isinstance(cancel_poll_seconds, (int, float)) or isinstance(cancel_poll_seconds, bool) or not 0.01 <= cancel_poll_seconds <= 5:
            raise ValueError("cancel_poll_seconds must be between 0.01 and 5")
        self.cancel_poll = float(cancel_poll_seconds)
        # None = the Worker derives it from the lease (min(60s, lease/2)); standalone use falls back to 60s. There is deliberately
        # NO lease heartbeat: a hung model call would keep a heartbeated lease alive for ever (goal stuck running). Every await
        # is instead bounded below the lease, and the lease is renewed at each step boundary.
        self.model_timeout = None if model_timeout_seconds is None else _checked_timeout(model_timeout_seconds)

    async def _interruptible(self, aw: Any, cancelled: Callable[[], bool], timeout: float | None = None) -> tuple[bool, Any]:
        """Await aw, polling for cancel and enforcing an optional timeout. (False, None) only if the awaitable was actually
        cancelled. Raises asyncio.TimeoutError on timeout. Neither path waits longer than CANCEL_GRACE for the cancelled body's
        cleanup (it is detached), so the wait is bounded below the lease. A call that finished in the same instant keeps its
        result. Sync tool threads cannot be killed: they keep running, which is why an interrupted non-read effect stays unknown."""
        task = asyncio.ensure_future(aw)
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + timeout
        try:
            while True:
                wait = self.cancel_poll if deadline is None else max(0.0, min(self.cancel_poll, deadline - loop.time()))
                done, _ = await asyncio.wait({task}, timeout=wait)
                if done:
                    return True, task.result()
                if cancelled():
                    await bounded.stop(task)
                    if task.done() and not task.cancelled():
                        return True, task.result()
                    return False, None
                if deadline is not None and loop.time() >= deadline:
                    await bounded.stop(task)
                    raise asyncio.TimeoutError
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            bounded.detach(task)  # outer cancellation: do not wait, but never leave an unretrieved late exception
            raise

    async def run(self, goal: str, *, cancel: Event | None = None, principal: Principal | None = None,
                  context: Callable[[], list[dict[str, Any]]] | None = None,
                  lease: Callable[[], bool] | None = None, cancel_check: Callable[[], bool] | None = None,
                  model_timeout: float | None = None) -> RunReport:
        if self.model is None:
            return RunReport(stop_reason="model_unavailable", steps_used=0)
        goal = scrub_text(goal)
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps({"goal": goal, "tools": self.tools.schemas(),
                                                            "context": redact(context()) if context else []}, default=str)}]
        receipts, refusals, replans, replan_log = [], [], 0, []
        decide_timeout = _checked_timeout(model_timeout) if model_timeout is not None else (self.model_timeout or 60.0)

        def cancelled() -> bool:
            return (cancel is not None and cancel.is_set()) or (cancel_check is not None and cancel_check())

        def _rr(**kw: Any) -> RunReport:  # every exit carries the advisory replan evidence
            return RunReport(replans=list(replan_log), **kw)
        for step in range(1, self.max_steps + 1):
            if cancelled():
                return _rr(stop_reason="cancelled", steps_used=step - 1, receipts=receipts, refusals=refusals)
            if lease is not None and not lease():
                return _rr(stop_reason="lease_lost", steps_used=step - 1, receipts=receipts, refusals=refusals)
            try:
                ok, decision = await self._interruptible(self.model.decide(messages), cancelled, decide_timeout)
                if not ok:
                    return _rr(stop_reason="cancelled", steps_used=step - 1, receipts=receipts, refusals=refusals)
            except (ModelUnavailable, asyncio.TimeoutError):  # a hung/slow model is 'unavailable'; no provider text
                return _rr(stop_reason="model_unavailable", steps_used=step - 1, receipts=receipts, refusals=refusals)
            except (ValidationError, json.JSONDecodeError):
                return _rr(stop_reason="model_invalid_output", steps_used=step - 1, receipts=receipts, refusals=refusals)
            messages.append({"role": "assistant", "content": decision.model_dump_json()})
            if decision.final is not None:
                return _rr(final=scrub_text(decision.final), stop_reason="final", steps_used=step,
                                 receipts=receipts, refusals=refusals)
            if decision.replan is not None:
                replans += 1
                if replans > 3:
                    return _rr(stop_reason="replan_limit", steps_used=step, receipts=receipts, refusals=refusals)
                revised = [scrub_text(x)[:500] for x in decision.replan.steps]
                replan_log.append(ReplanRecord(revision=replans, steps=revised))
                messages.append({"role": "tool", "content": json.dumps({"replan": True, "revision": replans, "steps": revised})})
                continue
            call = decision.tool_call
            tool = self.tools.get(call.name)
            if tool is None:
                refusals.append(Refusal(step=step, tool=call.name[:100], risk=None, reason="unknown_tool"))
                messages.append({"role": "tool", "content": json.dumps({"ok": False, "error": "unknown_tool"})})
            elif not self.tools.risk_intact(call.name):
                refusals.append(Refusal(step=step, tool=call.name, risk=tool.risk.value, reason="risk_changed"))
                messages.append({"role": "tool", "content": json.dumps({"ok": False, "error": "risk_changed"})})
            elif not self.policy.allows(call.name, call.arguments):
                refusals.append(Refusal(step=step, tool=call.name, risk=tool.risk.value, reason="policy_denied"))
                messages.append({"role": "tool", "content": json.dumps({"ok": False, "error": "policy_denied"})})
            elif lease is not None and not lease():
                # The model call may have outlived the lease: nothing is dispatched after the lease is lost.
                return _rr(stop_reason="lease_lost", steps_used=step - 1, receipts=receipts, refusals=refusals)
            elif cancelled():
                return _rr(stop_reason="cancelled", steps_used=step - 1, receipts=receipts, refusals=refusals)
            else:
                try:
                    ok, receipt = await self._interruptible(self.tools.execute(step, call.name, call.arguments, principal), cancelled)
                    if not ok:
                        return _rr(stop_reason="cancelled", steps_used=step - 1, receipts=receipts, refusals=refusals)
                except GateRefused as gr:
                    refusals.append(Refusal(step=step, tool=call.name, risk=tool.risk.value, reason=gr.reason,
                                            gates=list(gr.gates), digest=gr.digest, arguments=redact(call.arguments)))
                    messages.append({"role": "tool", "content": json.dumps({"ok": False, "error": gr.reason, "gates": list(gr.gates)})})
                else:
                    receipts.append(receipt)
                    messages.append({"role": "tool", "content": receipt.model_dump_json()})
        return _rr(stop_reason="step_limit", steps_used=self.max_steps, receipts=receipts, refusals=refusals)
