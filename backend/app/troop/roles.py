"""Roles for the troop runner: planner, worker, reviewer.

Everything here is deterministic and stdlib only. The planner is a TEMPLATE
planner (a fixed mapping from task kind to a step list), not a language-model
planner. The worker runs registered Python callables. The reviewer applies
declarative checks. The runner talks to each role through a narrow interface
(plan / execute / review), so a model-backed role can replace any of them;
none is provided here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class PlanError(ValueError):
    pass


class WorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Step:
    id: str
    action: str
    args: dict = field(default_factory=dict)
    depends_on: tuple = ()
    check: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    task_id: str
    steps: tuple


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reasons: tuple = ()


class TemplatePlanner:
    KINDS = ("text_stats", "sum_table")

    def plan(self, task):
        kind = task.get("kind")
        tid = task.get("id")
        if kind == "text_stats":
            return Plan(tid, (
                Step("tokenize", "tokenize", {"text": task.get("text", "")}, (), {"type": "non_empty"}),
                Step("count", "count_words", {}, ("tokenize",), {"type": "non_empty"}),
                Step("report", "top_n", {"n": int(task.get("top_n", 5))}, ("count",), {"type": "non_empty"}),
            ))
        if kind == "sum_table":
            return Plan(tid, (
                Step("totals", "sum_columns", {"rows": task.get("rows", [])}, (), {"type": "non_empty"}),
            ))
        raise PlanError(f"unknown task kind: {kind!r}")


def _tokenize(args, inputs, attempt, feedback):
    return re.findall(r"\w+", str(args["text"]).lower())


def _count_words(args, inputs, attempt, feedback):
    out = {}
    for w in inputs["tokenize"]:
        out[w] = out.get(w, 0) + 1
    return out


def _top_n(args, inputs, attempt, feedback):
    items = sorted(inputs["count"].items(), key=lambda kv: (-kv[1], kv[0]))
    return items[: args["n"]]


def _sum_columns(args, inputs, attempt, feedback):
    totals = {}
    for row in args["rows"]:
        for k, v in row.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise WorkerError(f"non-numeric value in column {k!r}")
            totals[k] = totals.get(k, 0) + v
    return totals


class ActionWorker:
    def __init__(self):
        self._actions = {"tokenize": _tokenize, "count_words": _count_words,
                        "top_n": _top_n, "sum_columns": _sum_columns}

    def register(self, name, fn):
        self._actions[name] = fn

    def execute(self, step, inputs, attempt, feedback):
        fn = self._actions.get(step.action)
        if fn is None:
            raise WorkerError(f"unknown action: {step.action}")
        return fn(step.args, inputs, attempt, feedback)


class RuleReviewer:
    def review(self, step, output):
        c = step.check or {}
        t = c.get("type")
        if t is None:
            return Verdict(True)
        if t == "non_empty":
            ok = output is not None and (not hasattr(output, "__len__") or len(output) > 0)
            return Verdict(ok, () if ok else ("non_empty: output is empty",))
        if t == "equals":
            ok = output == c.get("value")
            return Verdict(ok, () if ok else (f"equals: expected {c.get('value')!r}, got {output!r}",))
        if t == "keys":
            ok = isinstance(output, dict) and all(k in output for k in c.get("keys", ()))
            return Verdict(ok, () if ok else ("keys: missing required keys",))
        if t == "min_len":
            ok = hasattr(output, "__len__") and len(output) >= c.get("n", 0)
            return Verdict(ok, () if ok else (f"min_len: need at least {c.get('n')}",))
        return Verdict(False, (f"unknown check type: {t!r}",))
