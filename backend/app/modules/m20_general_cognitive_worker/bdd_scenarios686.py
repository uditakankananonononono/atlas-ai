"""Row 686 scoped capability: bounded execution of a declarative Given/When/Then DSL.

Executes a finite supplied set of scenarios over typed scalar state with two
allowlisted state operations (assign, increment) and explicit assertions.
Each scenario runs against fresh state; Then requires ALL assertions to hold.
Steps apply sequentially in listed order - simultaneous semantics is not
used, so step order is observable by construction. This is not a natural-
language interpreter, executes no arbitrary code, and certifies no repository
behavior: it evaluates the supplied declarative steps only.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

MAX_SCENARIOS = 16
MAX_SECTION_STEPS = 32
MAX_STEPS_CAP = 4096
DEFAULT_MAX_STEPS = 512
INT_LIMIT = 2 ** 62  # ints must satisfy abs(value) <= INT_LIMIT, before and after increment
MAX_STRING = 256
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")


def _literal(value: Any, field: str) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > INT_LIMIT:
            raise ValueError(f"{field} integer outside +/-2**62")
        return value
    if isinstance(value, str):
        if len(value) > MAX_STRING:
            raise ValueError(f"{field} string over {MAX_STRING} characters")
        return value
    raise ValueError(f"{field} requires a typed scalar literal (int, bool or string)")


def _var_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError(f"{field} requires an identifier like [A-Za-z_][A-Za-z0-9_]* up to 64 chars")
    return value


def _validate_step(step: Any, section: str, index: int) -> dict[str, Any]:
    field = f"{section}[{index}]"
    if not isinstance(step, dict):
        raise ValueError(f"{field} must be an object")
    if section in ("given", "when"):
        op = step.get("op")
        if op == "assign":
            if "value" not in step:
                raise ValueError(f"{field} assign requires value")
            return {"op": "assign", "var": _var_name(step.get("var"), field + ".var"),
                    "value": _literal(step["value"], field + ".value")}
        if op == "increment":
            if "by" not in step:
                raise ValueError(f"{field} increment requires by")
            by = step["by"]
            if isinstance(by, bool) or not isinstance(by, int) or abs(by) > INT_LIMIT:
                raise ValueError(f"{field}.by requires an integer within +/-2**62")
            return {"op": "increment", "var": _var_name(step.get("var"), field + ".var"), "by": by}
        raise ValueError(f"{field} unsupported op (allowlist: assign, increment)")
    kind = step.get("assert")
    if kind not in ("equals", "not_equals"):
        raise ValueError(f"{field} unsupported assert (allowlist: equals, not_equals)")
    if "value" not in step:
        raise ValueError(f"{field} assert requires value")
    return {"assert": kind, "var": _var_name(step.get("var"), field + ".var"),
            "value": _literal(step["value"], field + ".value")}


def _typed_equal(actual: Any, expected: Any) -> bool:
    # bool and int are distinct scalar types: True does not equal 1.
    return type(actual) is type(expected) and actual == expected


class _CapExceeded(Exception):
    pass


def _run_scenario(compiled: dict[str, list[dict[str, Any]]], counter: list[int]) -> dict[str, Any]:
    state: dict[str, Any] = {}

    def tick() -> None:
        if counter[0] >= counter[1]:
            raise _CapExceeded()
        counter[0] += 1

    def fail(section: str, index: int, step: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
        return {"status": "failed",
                "failure": {"section": section, "step_index": index, "step": step, "reason": reason, **extra}}

    for section in ("given", "when"):
        for index, step in enumerate(compiled[section]):
            tick()
            if step["op"] == "assign":
                state[step["var"]] = step["value"]
                continue
            var = step["var"]
            if var not in state:
                return fail(section, index, step, "unknown_variable", var=var)
            current = state[var]
            if not isinstance(current, int) or isinstance(current, bool):
                return fail(section, index, step, "type_mismatch", var=var,
                            actual_type=type(current).__name__)
            updated = current + step["by"]
            if abs(updated) > INT_LIMIT:
                return fail(section, index, step, "integer_overflow", var=var)
            state[var] = updated
    for index, step in enumerate(compiled["then"]):
        tick()
        var = step["var"]
        if var not in state:
            return fail("then", index, step, "unknown_variable", var=var)
        actual = state[var]
        equal = _typed_equal(actual, step["value"])
        if (step["assert"] == "equals" and not equal) or (step["assert"] == "not_equals" and equal):
            return fail("then", index, step, "assertion_failed", var=var,
                        expected=step["value"], actual=actual)
    return {"status": "passed", "failure": None}


def execute_scenarios(data: Any) -> dict[str, Any]:
    """Execute the supplied scenarios and return a deterministic, source-linked receipt."""
    if not isinstance(data, dict):
        raise ValueError("input must be an object with scenarios")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= MAX_SCENARIOS:
        raise ValueError(f"scenarios require a list of 1..{MAX_SCENARIOS} scenarios")
    max_steps = data.get("max_steps", DEFAULT_MAX_STEPS)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= MAX_STEPS_CAP:
        raise ValueError(f"max_steps requires an integer 1..{MAX_STEPS_CAP}")
    names: set[str] = set()
    compiled_all: list[dict[str, Any]] = []
    for position, raw in enumerate(scenarios):
        field = f"scenarios[{position}]"
        if not isinstance(raw, dict) or any(k not in raw for k in ("given", "when", "then")):
            raise ValueError(f"{field} requires given, when and then sections")
        name = raw.get("name", f"scenario-{position}")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field}.name requires a non-empty string")
        if name in names:
            raise ValueError(f"duplicate scenario name: {name}")
        names.add(name)
        compiled: dict[str, list[dict[str, Any]]] = {}
        for section in ("given", "when", "then"):
            steps = raw[section]
            if not isinstance(steps, list) or not 0 <= len(steps) <= MAX_SECTION_STEPS:
                raise ValueError(f"{field}.{section} requires a list of 0..{MAX_SECTION_STEPS} steps")
            compiled[section] = [_validate_step(step, section, i) for i, step in enumerate(steps)]
        compiled_all.append({"index": position, "name": name, "sections": compiled})

    counter = [0, max_steps]
    results: list[dict[str, Any]] = []
    capped = False
    for entry in compiled_all:
        if capped:
            results.append({"index": entry["index"], "name": entry["name"],
                            "status": "not_run", "failure": None})
            continue
        try:
            outcome = _run_scenario(entry["sections"], counter)
        except _CapExceeded:
            capped = True
            results.append({"index": entry["index"], "name": entry["name"],
                            "status": "incomplete", "failure": None})
            continue
        results.append({"index": entry["index"], "name": entry["name"], **outcome})
    if capped:
        status = "inconclusive_step_cap_exceeded"
    elif any(r["status"] == "failed" for r in results):
        status = "failures_present"
    else:
        status = "all_passed"
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return {
        "row": 686,
        "capability": "Behavior-Driven Development",
        "scope": "bounded_declarative_given_when_then_dsl_execution",
        "status": status,
        "scenarios": results,
        "steps_executed": counter[0],
        "max_steps": max_steps,
        "semantics": {
            "ordering": "sequential_in_listed_order",
            "simultaneous": False,
            "scenario_isolation": True,
            "then_requires": "all",
        },
        "provenance": {
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "repository_behavior_certified": False,
            "natural_language_interpreted": False,
            "arbitrary_code_executed": False,
            "external_task_scheduled": False,
        },
        "human_review_required": True,
    }
