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

    def __init__(self, registry: ToolRegistry, safety: SafetyGate) -> None:
        self.registry = registry
        self.safety = safety
        self.records: list[ActionRecord] = []

    async def dispatch(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        task_id: str | None = None,
        granted_approval_id: str | None = None,
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
