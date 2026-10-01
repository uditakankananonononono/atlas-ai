"""Tool integration (spec 4.2.5): unified function-calling interface.

The registry holds every tool the GCW may use - other Atlas modules, the
Python sandbox, shell, internet search, workspace files, third-party REST
APIs - each with description, parameters (JSON schema) and preconditions.
The registry exports the OpenAI function-calling format so any LLM can
select tools natively. The dispatcher enforces safety preflight, timeouts
and bounded retries, and records every call as an ActionRecord.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .effect_ledger import (
    CURRENT_EFFECT_ID, EffectError, EffectIndeterminate, EffectInProgress, EffectLedger, ToolNotExecuted,
)
from .safety import SafetyGate
from .schemas import ActionRecord, ApprovalGateDecision, Risk, ToolSpec

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ToolError(Exception):
    pass


class ToolBlockedError(ToolError):
    def __init__(self, name: str, reasons: list[str]) -> None:
        super().__init__(f"tool {name!r} blocked: {'; '.join(reasons)}")
        self.reasons = reasons


class ApprovalPending(ToolError):
    def __init__(self, name: str, approval_id: str) -> None:
        super().__init__(f"tool {name!r} waiting on approval {approval_id}")
        self.approval_id = approval_id


class RegisteredTool:
    def __init__(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self.spec = spec
        self.handler = handler

    def check_preconditions(self, context: dict[str, Any]) -> list[str]:
        """Each precondition is a context key that must be truthy."""
        missing = [
            key for key in self.spec.preconditions if not context.get(key)
        ]
        return missing

    def to_function_schema(self) -> dict[str, Any]:
        """OpenAI function-calling format (spec 4.2.5)."""
        return {
            "type": "function",
            "function": {
                "name": self.spec.name,
                "description": self.spec.description,
                "parameters": self.spec.parameters or {"type": "object", "properties": {}},
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> RegisteredTool:
        if spec.name in self._tools:
            raise ToolError(f"tool {spec.name!r} already registered")
        tool = RegisteredTool(spec, handler)
        self._tools[spec.name] = tool
        return tool

    def get(self, name: str) -> RegisteredTool:
        if name not in self._tools:
            raise ToolError(f"unknown tool: {name!r}")
        return self._tools[name]

    def find_by_capability(self, capability: str) -> list[RegisteredTool]:
        return [
            t for t in self._tools.values() if capability in t.spec.capabilities
        ]

    def function_schemas(self) -> list[dict[str, Any]]:
        return [t.to_function_schema() for t in self._tools.values()]

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.spec.name,
                "description": t.spec.description,
                "risk": t.spec.risk.value,
                "capabilities": t.spec.capabilities,
                "preconditions": t.spec.preconditions,
            }
            for t in self._tools.values()
        ]

    def __len__(self) -> int:
        return len(self._tools)


class ToolDispatcher:
    """Executes tools through the safety gate with timeouts and retries."""

    def __init__(self, registry: ToolRegistry, safety: SafetyGate,
                 ledger: EffectLedger | None = None) -> None:
        self.registry = registry
        self.safety = safety
        self.records: list[ActionRecord] = []
        # Non-idempotent tools are reserved here before invocation. Runtimes
        # bind a durable ledger; a bare dispatcher gets a process-local one
        # (same protocol, but lost on restart - bind a durable ledger in prod).
        if ledger is None:
            import sqlalchemy as sa
            from sqlalchemy.pool import StaticPool
            ledger = EffectLedger(
                sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                                 poolclass=StaticPool), "ephemeral")
        self.ledger = ledger

    async def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
        granted_approval_id: str | None = None,
        node_id: str | None = None,
    ) -> ActionRecord:
        tool = self.registry.get(name)
        context = context or {}
        missing = tool.check_preconditions(context)
        if missing:
            raise ToolBlockedError(name, [f"missing precondition: {m}" for m in missing])
        may_proceed, approval_id, violations = self.safety.preflight(
            name, tool.spec.risk, arguments, task_id=task_id,
            summary=tool.spec.description,
            granted_approval_id=granted_approval_id,
        )
        if violations:
            raise ToolBlockedError(name, [f"{v.rule_id}: {v.reason}" for v in violations])
        if not may_proceed and approval_id is not None:
            raise ApprovalPending(name, approval_id)
        record = ActionRecord(tool=name, arguments=arguments, started_at=datetime.now(timezone.utc))
        if tool.spec.risk != Risk.READ:
            return await self._dispatch_reserved(tool, name, arguments, record,
                                                 task_id=task_id, node_id=node_id)
        attempts = max(1, tool.spec.max_retries)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                result = await asyncio.wait_for(
                    tool.handler(arguments), timeout=tool.spec.timeout_seconds,
                )
                record.succeeded = True
                record.result_summary = str(result)[:500]
                record.finished_at = datetime.now(timezone.utc)
                self.records.append(record)
                return record
            except (ToolError, ApprovalPending):
                raise
            except Exception as exc:  # handler failure: retry within bound
                last_error = exc
        record.succeeded = False
        record.result_summary = f"failed after {attempts} attempt(s): {last_error}"
        record.finished_at = datetime.now(timezone.utc)
        self.records.append(record)
        return record

    async def _dispatch_reserved(self, tool: RegisteredTool, name: str, arguments: dict[str, Any],
                                 record: ActionRecord, *, task_id: str | None,
                                 node_id: str | None) -> ActionRecord:
        """Reserve durably, mark invoking, THEN call the handler exactly once."""
        ledger = self.ledger
        res = ledger.reserve(
            task_id=task_id or "-", node_id=node_id or "-", tool=name,
            # runtime bookkeeping keys ("_expectation_claim_id") are random per run
            # and are not part of the effect's identity
            args={k: v for k, v in arguments.items() if not str(k).startswith("_")},
            lease_seconds=tool.spec.timeout_seconds + 30,
            provider_idempotent=tool.spec.provider_idempotent)
        if res.replayed:  # recorded receipt: never invoke again
            record.succeeded = True
            record.result_summary = res.result_summary
            record.finished_at = datetime.now(timezone.utc)
            self.records.append(record)
            return record
        ledger.mark_invoking(res)  # committed before the handler runs
        token = CURRENT_EFFECT_ID.set(res.effect_id)
        try:
            result = await asyncio.wait_for(tool.handler(arguments), timeout=tool.spec.timeout_seconds)
        except ToolNotExecuted as exc:
            ledger.fail_safe(res, f"not executed: {exc}")
            record.succeeded = False
            record.result_summary = f"not executed: {exc}"
        except (ToolError, ApprovalPending) as exc:
            ledger.fail_safe(res, f"tool layer refused: {exc}")
            raise
        except BaseException as exc:  # handler may or may not have had its effect
            ledger.mark_indeterminate(res, f"{type(exc).__name__}: {exc}")
            if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                raise
            raise EffectIndeterminate(res.effect_id, f"{type(exc).__name__}: {exc}") from exc
        else:
            record.succeeded = True
            record.result_summary = str(result)[:500]
            try:
                ledger.complete(res, record.result_summary)
            except EffectError:
                raise
            except Exception as exc:  # receipt not durable: state stays 'invoking'
                raise EffectIndeterminate(res.effect_id, f"receipt not saved: {exc}") from exc
        finally:
            CURRENT_EFFECT_ID.reset(token)
        record.finished_at = datetime.now(timezone.utc)
        self.records.append(record)
        return record


def builtin_python_sandbox_spec() -> ToolSpec:
    return ToolSpec(
        name="python_sandbox",
        description="Run Python in an ephemeral, network-restricted container for data analysis.",
        parameters={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
        preconditions=[],
        risk=Risk.REVERSIBLE,
        capabilities=["code_execution", "data_analysis"],
    )


def builtin_web_search_spec() -> ToolSpec:
    return ToolSpec(
        name="web_search",
        description="Search the public web (Brave/Google programmable search).",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        preconditions=["network"],
        risk=Risk.READ,
        capabilities=["search", "research"],
    )
