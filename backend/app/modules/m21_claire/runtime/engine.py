from __future__ import annotations
import json
from threading import Event
from typing import Any, Callable, Protocol
from pydantic import ValidationError
from .redaction import redact, scrub_text
from .gates import GateRefused, Principal
from .tools import ReadOnlyToolRegistry
from .types import AgentDecision, Refusal, RunReport

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


class Engine:
    """Bounded loop. Produces a RunReport (evidence). Completion is decided elsewhere."""

    def __init__(self, model: ModelPort | None, tools: ReadOnlyToolRegistry, *, max_steps: int = 12,
                 policy: ActionPolicy | None = None) -> None:
        if not 1 <= max_steps <= 50:
            raise ValueError("max_steps must be between 1 and 50")
        self.model, self.tools, self.max_steps = model, tools, max_steps
        self.policy = policy or NoAdditionalPolicy()

    async def run(self, goal: str, *, cancel: Event | None = None, principal: Principal | None = None,
                  context: Callable[[], list[dict[str, Any]]] | None = None) -> RunReport:
        if self.model is None:
            return RunReport(stop_reason="model_unavailable", steps_used=0)
        goal = scrub_text(goal)
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps({"goal": goal, "tools": self.tools.schemas(),
                                                            "context": redact(context()) if context else []}, default=str)}]
        receipts, refusals, replans = [], [], 0
        for step in range(1, self.max_steps + 1):
            if cancel is not None and cancel.is_set():
                return RunReport(stop_reason="cancelled", steps_used=step - 1, receipts=receipts, refusals=refusals)
            try:
                decision = await self.model.decide(messages)
            except ModelUnavailable:
                return RunReport(stop_reason="model_unavailable", steps_used=step - 1, receipts=receipts, refusals=refusals)
            except (ValidationError, json.JSONDecodeError):
                return RunReport(stop_reason="model_invalid_output", steps_used=step - 1, receipts=receipts, refusals=refusals)
            messages.append({"role": "assistant", "content": decision.model_dump_json()})
            if decision.final is not None:
                return RunReport(final=scrub_text(decision.final), stop_reason="final", steps_used=step,
                                 receipts=receipts, refusals=refusals)
            if decision.replan is not None:
                replans += 1
                if replans > 3:
                    return RunReport(stop_reason="replan_limit", steps_used=step, receipts=receipts, refusals=refusals)
                revised = [scrub_text(x)[:500] for x in decision.replan.steps]
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
            else:
                try:
                    receipt = await self.tools.execute(step, call.name, call.arguments, principal)
                except GateRefused as gr:
                    refusals.append(Refusal(step=step, tool=call.name, risk=tool.risk.value, reason=gr.reason,
                                            gates=list(gr.gates), digest=gr.digest, arguments=redact(call.arguments)))
                    messages.append({"role": "tool", "content": json.dumps({"ok": False, "error": gr.reason, "gates": list(gr.gates)})})
                else:
                    receipts.append(receipt)
                    messages.append({"role": "tool", "content": receipt.model_dump_json()})
        return RunReport(stop_reason="step_limit", steps_used=self.max_steps, receipts=receipts, refusals=refusals)
