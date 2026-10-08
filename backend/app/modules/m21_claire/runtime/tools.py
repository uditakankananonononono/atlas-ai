from __future__ import annotations
import asyncio
import inspect
import json
import re
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, ValidationError
from . import bounded
from .gates import GateRefused, require_plain_json
from .redaction import redact
from .types import ToolReceipt, ToolRisk


class Tool(ABC):
    name: str
    description: str = ""
    risk: ToolRisk = ToolRisk.READ
    arguments_model: type[BaseModel]
    # Declared effects of the REGISTERED tool. None = undeclared (fail closed for non-read tools).
    spends_money: bool | None = None
    sends_to_person: bool | None = None
    # Effect journal declarations (trusted Python, frozen at registration). idempotent=True means a re-run with the same
    # idempotency key cannot repeat the effect; it requires accepts_idempotency_key=True (run() then receives the key).
    # A non-read tool must declare idempotent as exactly True or False.
    idempotent: bool | None = None
    accepts_idempotency_key: bool = False
    # Optional: def reconcile(self, key: str) -> "committed" | "absent" | "unknown" - did the effect for this key happen?

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "risk": self.risk.value,
                "parameters": self.arguments_model.model_json_schema()}

    @abstractmethod
    def run(self, arguments: BaseModel) -> Any: ...


class ReadOnlyToolRegistry:
    """Registry. Without an enforcer only tools declared READ can be registered at all (milestone 1).
    With a GateEnforcer, write/execute tools may register but every dispatch is classified and gated.

    TRUST BOUNDARY: tool classes and their declarations are trusted Python code. The registry freezes name, risk, class and
    effect declarations at registration and refuses dispatch if any change; it cannot stop code that replaces the class itself.
    Risk comes from the registered tool, never from the model's call. Names are exact;
    an alias the model invents is an unknown tool, not a lower-risk spelling of a real one.
    """
    def __init__(self, enforcer: Any = None, *, call_timeout: float = 30.0, journal: Any = None) -> None:
        self.journal = journal  # a GoalStore: required to dispatch any non-read tool
        if not (isinstance(call_timeout, (int, float)) and not isinstance(call_timeout, bool) and 0 < call_timeout <= 3600):
            raise ValueError("call_timeout must be a number of seconds in (0, 3600]")
        self.call_timeout = float(call_timeout)
        self._tools: dict[str, Tool] = {}
        self._trusted: dict[str, tuple] = {}  # (name, risk, class, spends_money, sends_to_person) frozen at registration
        self.enforcer = enforcer

    NAME_GRAMMAR = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

    def register(self, tool: Tool) -> None:
        if not isinstance(tool.name, str) or not self.NAME_GRAMMAR.match(tool.name):
            raise ValueError("tool name must match [a-z][a-z0-9_]{0,63} (lowercase words joined by underscores)")
        for attr in ("spends_money", "sends_to_person"):
            if getattr(tool, attr) not in (True, False, None) or type(getattr(tool, attr)) not in (bool, type(None)):
                raise ValueError(f"{attr} must be exactly True, False or None")
        if type(tool.accepts_idempotency_key) is not bool:
            raise ValueError("accepts_idempotency_key must be exactly True or False")
        if type(tool.idempotent) not in (bool, type(None)):
            raise ValueError("idempotent must be exactly True, False or None")
        if tool.risk is not ToolRisk.READ and tool.idempotent is None:
            raise ValueError("a non-read tool must declare idempotent as exactly True or False")
        if tool.idempotent is True and not tool.accepts_idempotency_key:
            raise ValueError("idempotent=True requires accepts_idempotency_key=True")
        if tool.risk is not ToolRisk.READ and self.enforcer is None:
            raise ValueError("a registry without a gate enforcer accepts read-risk tools only")
        if tool.name in self._tools:
            raise ValueError("tool name already registered")
        self._tools[tool.name] = tool
        self._trusted[tool.name] = self._fingerprint(tool)

    @staticmethod
    def _fingerprint(tool: Tool) -> tuple:
        def tag(v: Any) -> tuple:
            return (type(v).__name__, v)  # type-preserving: True != 1, False != 0
        return (tool.name, tool.risk, type(tool), tag(tool.spends_money), tag(tool.sends_to_person), tag(tool.idempotent),
                tag(tool.accepts_idempotency_key), callable(getattr(tool, "reconcile", None)))

    def risk_intact(self, name: str) -> bool:
        """True only if name, risk, class and effect declarations still equal what was registered."""
        tool = self._tools.get(name)
        if tool is None:
            return False
        if any(type(getattr(tool, a)) not in (bool, type(None)) for a in ("spends_money", "sends_to_person", "idempotent")):
            return False
        if type(tool.accepts_idempotency_key) is not bool:
            return False
        return self._trusted[name] == self._fingerprint(tool)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    @staticmethod
    async def _run(tool: Tool, parsed: BaseModel, key: str | None = None) -> Any:
        # Sync bodies run in a worker thread so the timeout can fire; the thread itself cannot be killed.
        value = await asyncio.to_thread(tool.run, parsed) if key is None else await asyncio.to_thread(tool.run, parsed, idempotency_key=key)
        if inspect.isawaitable(value):
            value = await value
        return value

    async def execute(self, step: int, name: str, arguments: dict[str, Any], principal: Any = None) -> ToolReceipt:
        if not self.risk_intact(name):
            raise PermissionError("tool no longer matches its registered risk and class")
        tool = self._tools[name]
        if tool.risk is not ToolRisk.READ:
            return await self._execute_effect(step, name, tool, arguments, principal)
        if self.enforcer is not None:
            self.enforcer.authorize(tool, arguments, principal)  # raises GateRefused; consumes approvals atomically
        safe_args = redact(arguments)
        try:
            parsed = tool.arguments_model.model_validate(arguments)
            value = await bounded.run_bounded(self._run(tool, parsed), self.call_timeout)
        except asyncio.TimeoutError:
            # No retry here. The tool body may still be running or may already have had its effect (effect
            # reconciliation is slice 3b); the receipt says only that the call did not finish in time.
            return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=False, error="timed_out")
        except (KeyError, TypeError, ValidationError, ValueError, OSError) as exc:
            # Class name only: str(exc) can embed arguments, paths or URLs.
            return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=False, error=f"{type(exc).__name__}")
        return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=True, content=redact(value))

    # --- journaled dispatch of non-read tools --------------------------------------------------------
    async def _execute_effect(self, step: int, name: str, tool: Tool, arguments: dict[str, Any], principal: Any) -> ToolReceipt:
        if self.enforcer is None:
            raise PermissionError("non-read tool without enforcer")
        if self.journal is None:
            raise PermissionError("non-read tool without effect journal")
        try:
            require_plain_json(arguments)
        except (ValueError, RecursionError):
            raise GateRefused("invalid_arguments", (), "") from None
        if principal is not None and principal.lease_token is None:
            raise PermissionError("non-read dispatch needs a principal fenced by a lease token")
        safe_args = redact(arguments)
        gates, key = self.enforcer.evaluate(tool, arguments, principal)  # classifies only; consumes nothing
        if principal is None:
            raise PermissionError("non-read dispatch needs a principal fenced by a lease token")
        takeover = tool.idempotent is True
        # Reservation and approval consumption are one transaction inside the journal: replay, pending, lease_lost and a
        # missing approval can never consume an approval or leave an intent row behind.
        status, effect_id, stored = self.journal.begin_effect(principal, name, key, takeover_pending=takeover, gates=gates)
        if status == "approval_required":
            raise GateRefused("approval_required", gates, key)
        if status == "lease_lost":
            raise GateRefused("lease_lost", (), key)
        if status == "replay":
            return self._replay(step, name, safe_args, stored)
        if status == "pending":
            raise GateRefused("effect_unknown", (), key)
        try:
            parsed = tool.arguments_model.model_validate(arguments)
        except ValidationError as exc:
            self.journal.mark_effect(effect_id, "failed")  # never reached the tool body: no effect happened
            return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=False, error=type(exc).__name__)
        try:
            value = await bounded.run_bounded(self._run(tool, parsed, key if tool.accepts_idempotency_key else None), self.call_timeout)
        except asyncio.TimeoutError:
            self.journal.mark_effect(effect_id, "unknown")  # may still be running or may have landed
            return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=False, error="timed_out")
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self.journal.mark_effect(effect_id, "unknown")  # the body ran: an effect may have happened before it raised
            return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=False, error=type(exc).__name__)
        content = redact(value)
        self.journal.mark_effect(effect_id, "committed", {"content": json.loads(json.dumps(content, default=str))})
        return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=True, content=content)

    @staticmethod
    def _replay(step: int, name: str, safe_args: dict[str, Any], stored: str | None) -> ToolReceipt:
        content = json.loads(stored).get("content") if stored else None
        return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=True, content=content, replayed=True)

    def blocking_effects(self, goal_id: str) -> list[dict[str, Any]]:
        """Pending effects that a re-dispatch could not safely resolve by itself."""
        out = []
        for eff in self.journal.pending_effects(goal_id) if self.journal is not None else []:
            tool = self._tools.get(eff["tool"])
            if tool is not None and self.risk_intact(eff["tool"]) and tool.idempotent is True:
                continue  # same key re-dispatch is safe by declaration
            out.append(eff)
        return out

    async def reconcile_pending(self, goal_id: str) -> list[dict[str, Any]]:
        """Ask tools that implement reconcile(key) what happened. Returns the effects that still block the goal."""
        if self.journal is None:
            return []
        for eff in self.journal.pending_effects(goal_id):
            tool = self._tools.get(eff["tool"])
            rec = getattr(tool, "reconcile", None) if tool is not None and self.risk_intact(eff["tool"]) else None
            if tool is None or tool.idempotent is True or not callable(rec):
                continue
            try:
                result = await bounded.run_bounded(self._call(rec, eff["idempotency_key"]), self.call_timeout)
            except (asyncio.TimeoutError, KeyError, TypeError, ValueError, OSError):
                continue
            if result == "committed":
                self.journal.resolve_effect(goal_id, eff["id"], "committed", receipt={"content": {"reconciled": True}})
            elif result == "absent":
                self.journal.resolve_effect(goal_id, eff["id"], "absent")
        return self.blocking_effects(goal_id)

    @staticmethod
    async def _call(fn: Any, key: str) -> Any:
        value = await asyncio.to_thread(fn, key)
        if inspect.isawaitable(value):
            value = await value
        return value
