from __future__ import annotations
import inspect
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

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "risk": self.risk.value,
                "parameters": self.arguments_model.model_json_schema()}

    @abstractmethod
    def run(self, arguments: BaseModel) -> Any: ...


class ReadOnlyToolRegistry:
    """Milestone 1 registry: only tools declared READ can be registered at all.

    Risk comes from the registered tool, never from the model's call. Names are exact;
    an alias the model invents is an unknown tool, not a lower-risk spelling of a real one.
    """
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.risk is not ToolRisk.READ:
            raise ValueError("milestone 1 registry accepts read-risk tools only")
        if tool.name in self._tools:
            raise ValueError("tool name already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    async def execute(self, step: int, name: str, arguments: dict[str, Any]) -> ToolReceipt:
        tool = self._tools[name]
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
