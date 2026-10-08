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
import math
import os
import re
from typing import Any

from app.core import model_catalog
from app.core.providers import ProviderError, ProviderOutcomeUnknown

from .htn_planner import PlanError
from .schemas import Risk

class PlannerOutcomeUnknown(PlanError):
    outcome = "unknown"
    retry_allowed = False


_ORDER = [Risk.READ, Risk.REVERSIBLE, Risk.EXTERNAL, Risk.IRREVERSIBLE]


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def extract_json(text: str) -> Any:
    if not isinstance(text,str) or len(text)>100000:
        raise ValueError("model output must be bounded text")
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = (fenced.group(1) if fenced else text).strip()
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError("duplicate JSON key")
            result[key]=value
        return result
    def invalid(value):raise ValueError("nonfinite JSON constant: "+value)
    def finite_number(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON numeric exponent exceeds finite range")
        return number
    try:
        result = json.loads(body,object_pairs_hook=unique,parse_constant=invalid,parse_float=finite_number)
    except RecursionError as exc:
        raise ValueError("model JSON nesting exceeds decoder boundary") from exc
    stack = [(result, 0)]
    count = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        if depth > 64 or count > 20000:
            raise ValueError("model JSON exceeds depth64/node20000 boundary")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
    return result


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
        from app.platform.integrations import LangChainPipeline
        pipeline = LangChainPipeline([
            self._prepare_stage, self._generate_stage,
            self._decode_stage, self._validate_stage,
        ])
        return pipeline.invoke({"goal": goal, "context": context})["steps"]

    def _prepare_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "prompt": self._prompt(state["goal"], state["context"])}

    def _generate_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            provider, model, text = _run(model_catalog.generate_free_first(
                state["prompt"], self.model_name, private=True))
        except ProviderOutcomeUnknown as exc:
            raise PlannerOutcomeUnknown("planner generation outcome unknown; no automatic retry") from exc
        except ProviderError as exc:
            raise PlanError(f"planner model unavailable: {exc}") from exc
        self.last_route = (provider, model)
        return {**state, "provider": provider, "model": model, "text": text}

    def _decode_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            data = extract_json(state["text"])
        except ValueError as exc:
            raise PlanError(f"planner model returned no parseable JSON ({state['provider']}/{state['model']})") from exc
        return {**state, "data": data}

    def _validate_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        data = state["data"]
        steps = data.get("steps") if isinstance(data, dict) else data
        if not isinstance(steps, list) or not 1<=len(steps)<=8:
            raise PlanError("planner model must return1..8 concrete steps")
        risks = self.tool_risks
        for step in steps:
            if not isinstance(step, dict):
                raise PlanError("planner step must be an object")
            if step.get("tool") in (None, "null", ""):
                step.pop("tool", None)
            if step.get("tool") is not None and step["tool"] not in risks:
                raise PlanError("planner selected unregistered tool")
            floor = risks.get(step.get("tool") or "")
            raw = step.get("risk", Risk.READ.value)
            if floor is not None and raw in {r.value for r in Risk} and _ORDER.index(Risk(raw)) < _ORDER.index(floor):
                step["risk"] = floor.value
        return {**state, "steps": steps}


class FreeFirstExecutiveModel:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name if model_name is not None else _model_name()

    def complete(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"Task: {purpose}. Reply with ONLY a JSON object. For 'reason' use a nonempty result string. For 'reflect' use "
            '{"cause": "...", "fix": "...", "retry": true|false}.\n'
            f"Input: {json.dumps(payload, default=str)[:6000]}"
        )
        if purpose == "ideate":
            prompt = (
                "Generate distinct actionable proposals for the supplied objective. "
                "Respect the supplied constraints, but do not claim they are independently verified. "
                "Return ONLY a JSON object with ideas (exact requested count). Each candidate needs "
                "title, proposal, first_test (a concrete small test), risks (string list), and "
                "constraint_checks (each supplied constraint mapped to an explanation, including tradeoffs). "
                "Do not take actions or invent evidence. Input: " + json.dumps(payload)
            )
        try:
            provider, model, text = _run(model_catalog.generate_free_first(prompt, self.model_name, private=True))
        except ProviderOutcomeUnknown as exc:
            return {"available": False, "failure_kind": "outcome_unknown", "outcome": "unknown", "retry_allowed": False, "error": str(exc)}
        except ProviderError as exc:
            return {"available": False, "failure_kind": "provider_unavailable", "error": str(exc)}
        try:
            data = extract_json(text)
        except ValueError:
            return {"available":False,"failure_kind":"invalid_output","error":"executive model returned invalid JSON","route":f"{provider}/{model}"}
        if not isinstance(data, dict):
            return {"available":False,"failure_kind":"invalid_output","error":"executive model must return JSON object","route":f"{provider}/{model}"}
        valid = True
        if purpose == "reason":
            valid = isinstance(data.get("result"), str) and bool(data["result"].strip())
        elif purpose == "reflect":
            valid = (isinstance(data.get("cause"), str) and bool(data["cause"].strip())
                     and isinstance(data.get("fix"), str) and bool(data["fix"].strip())
                     and type(data.get("retry")) is bool)
        if not valid:
            return {"available": False, "failure_kind": "invalid_output", "error": "executive model purpose schema mismatch",
                    "route": f"{provider}/{model}"}
        data.setdefault("route", f"{provider}/{model}")
        return data


def bound_models(tool_risks: dict[str, Risk] | None = None) -> dict[str, Any]:
    """Models for GCWRuntime; empty when ATLAS_GCW_MODEL_ROUTING=off."""
    if os.getenv("ATLAS_GCW_MODEL_ROUTING", "free_first").lower() == "off":
        return {}
    return {"planner_model": FreeFirstPlannerModel(tool_risks), "executive_model": FreeFirstExecutiveModel()}
