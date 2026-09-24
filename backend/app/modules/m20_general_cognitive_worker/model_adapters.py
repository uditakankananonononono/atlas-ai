"""Bind M20's injected model protocols to the free-first model layer.

PlannerModel.decompose and ExecutiveModel.complete are synchronous protocols;
these adapters call app.core.model_catalog.generate_free_first (local Ollama /
OpenAI-compatible server first, HF free tier next, paid only with
ATLAS_ALLOW_PAID) and parse strict JSON back. A model can only raise a step's
risk tier, never lower it below the registered tool's risk; the dispatcher's
approval gate still keys off the tool's own spec.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
from typing import Any

from app.core import model_catalog
from app.core.providers import ProviderError

from .htn_planner import PlanError
from .schemas import Risk

_ORDER = [Risk.READ, Risk.REVERSIBLE, Risk.EXTERNAL, Risk.IRREVERSIBLE]


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def extract_json(text: str) -> Any:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = fenced.group(1) if fenced else text
    starts = [i for i in (body.find("["), body.find("{")) if i >= 0]
    if not starts:
        raise ValueError("no JSON in model output")
    return json.JSONDecoder().raw_decode(body[min(starts):])[0]


def _model_name() -> str | None:
    return os.getenv("ATLAS_GCW_MODEL") or None


class FreeFirstPlannerModel:
    def __init__(self, tool_risks: dict[str, Risk] | None = None, model_name: str | None = None) -> None:
        self._static_risks = dict(tool_risks or {})
        self._registry = None
        self.model_name = model_name if model_name is not None else _model_name()
        self.last_route: tuple[str, str] | None = None

    def bind_registry(self, registry) -> None:
        """Read tool names and registered risk tiers from the live ToolRegistry."""
        self._registry = registry

    @property
    def tool_risks(self) -> dict[str, Risk]:
        risks = dict(self._static_risks)
        if self._registry is not None:
            for t in self._registry.describe():
                risks[t["name"]] = Risk(t["risk"])
        return risks

    def _prompt(self, goal: str, context: str) -> str:
        tools = ", ".join(f"{n} ({r.value})" for n, r in sorted(self.tool_risks.items())) or "none registered"
        return (
            "Break the goal into 2-8 concrete steps. Reply with ONLY a JSON array. Each item: "
            '{"id": "s1", "title": "...", "tool": "<one of the tools or null>", "arguments": {}, '
            '"depends_on": ["s0"], "risk": "read|reversible|external|irreversible"}. '
            "Mark anything that sends, publishes, pays or deletes as external or irreversible.\n"
            f"Tools: {tools}\nContext: {context[:4000]}\nGoal: {goal[:2000]}"
        )

    def decompose(self, goal: str, *, context: str = "") -> list[dict[str, Any]]:
        try:
            provider, model, text = _run(model_catalog.generate_free_first(self._prompt(goal, context), self.model_name))
        except ProviderError as exc:
            raise PlanError(f"planner model unavailable: {exc}") from exc
        self.last_route = (provider, model)
        try:
            data = extract_json(text)
        except ValueError as exc:
            raise PlanError(f"planner model returned no parseable JSON ({provider}/{model})") from exc
        steps = data.get("steps") if isinstance(data, dict) else data
        if not isinstance(steps, list):
            raise PlanError("planner model JSON was not a list of steps")
        risks = self.tool_risks
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("tool") in (None, "null", ""):
                step.pop("tool", None)
            floor = risks.get(step.get("tool") or "")
            raw = step.get("risk", Risk.READ.value)
            if floor is not None and raw in {r.value for r in Risk} and _ORDER.index(Risk(raw)) < _ORDER.index(floor):
                step["risk"] = floor.value
        return steps


class FreeFirstExecutiveModel:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name if model_name is not None else _model_name()

    def complete(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"Task: {purpose}. Reply with ONLY a JSON object. For 'reflect' use "
            '{"cause": "...", "fix": "...", "retry": true|false}.\n'
            f"Input: {json.dumps(payload, default=str)[:6000]}"
        )
        try:
            provider, model, text = _run(model_catalog.generate_free_first(prompt, self.model_name))
        except ProviderError as exc:
            return {"available": False, "error": str(exc)}
        try:
            data = extract_json(text)
        except ValueError:
            data = {"text": text.strip()[:4000]}
        if not isinstance(data, dict):
            data = {"value": data}
        data.setdefault("route", f"{provider}/{model}")
        return data


def bound_models(tool_risks: dict[str, Risk] | None = None) -> dict[str, Any]:
    """Models for GCWRuntime; empty when ATLAS_GCW_MODEL_ROUTING=off."""
    if os.getenv("ATLAS_GCW_MODEL_ROUTING", "free_first").lower() == "off":
        return {}
    return {"planner_model": FreeFirstPlannerModel(tool_risks), "executive_model": FreeFirstExecutiveModel()}
