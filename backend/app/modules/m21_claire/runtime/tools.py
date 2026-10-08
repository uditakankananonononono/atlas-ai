from __future__ import annotations
import inspect
import re
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, ValidationError
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
    def __init__(self, enforcer: Any = None) -> None:
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
        return (tool.name, tool.risk, type(tool), tag(tool.spends_money), tag(tool.sends_to_person))

    def risk_intact(self, name: str) -> bool:
        """True only if name, risk, class and effect declarations still equal what was registered."""
        tool = self._tools.get(name)
        if tool is None:
            return False
        if any(type(getattr(tool, a)) not in (bool, type(None)) for a in ("spends_money", "sends_to_person")):
            return False
        return self._trusted[name] == self._fingerprint(tool)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    async def execute(self, step: int, name: str, arguments: dict[str, Any], principal: Any = None) -> ToolReceipt:
        if not self.risk_intact(name):
            raise PermissionError("tool no longer matches its registered risk and class")
        tool = self._tools[name]
        if self.enforcer is not None:
            self.enforcer.authorize(tool, arguments, principal)  # raises GateRefused; consumes approvals atomically
        elif tool.risk is not ToolRisk.READ:
            raise PermissionError("non-read tool without enforcer")
        safe_args = redact(arguments)
        try:
            parsed = tool.arguments_model.model_validate(arguments)
            value = tool.run(parsed)
            if inspect.isawaitable(value):
                value = await value
        except (KeyError, TypeError, ValidationError, ValueError, OSError) as exc:
            # Class name only: str(exc) can embed arguments, paths or URLs.
            return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=False, error=f"{type(exc).__name__}")
        return ToolReceipt(step=step, tool=name, arguments=safe_args, ok=True, content=redact(value))
