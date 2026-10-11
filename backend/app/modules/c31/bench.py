"""S1.4 / c31.bench - cognition-benchmark board.

Source excerpt (verbatim): "Superintelligence -AGI -able to completely mimic
humans".

A fixed battery of reasoning/planning/novelty tasks whose SUPPLIED measured
scores are recorded over runs; the board reports per-task aggregates
(latest/best only - full per-run history is NOT returned), the measured
ceiling and failures against supplied pass marks. It runs no models;
scores are recorded measurements, not adjectives. Substitute for X8.
Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
TASKS = ("reasoning", "planning", "novelty")
MAX_RUNS = 4096


def board(runs):
    """Aggregate supplied benchmark run records into the board."""
    # bool needs no separate guard: not a list/tuple, refusal covers it (pinned)
    if not isinstance(runs, (list, tuple)):
        raise ValueError("FLEET_REFUSED_BAD_TYPE:runs")
    if not runs:
        raise ValueError("FLEET_REFUSED_EMPTY:runs")
    if len(runs) > MAX_RUNS:
        raise ValueError("FLEET_REFUSED_OVERSIZE")
    by_task = {t: [] for t in TASKS}
    seen = set()
    for r in runs:
        if not isinstance(r, dict):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:run")
        rid = policy.clean_text(r.get("run_id"), PREFIX, "run_id", 64)
        if rid in seen:
            raise ValueError("FLEET_REFUSED_DUPLICATE:" + rid)
        seen.add(rid)
        task = r.get("task")
        if task not in TASKS:
            raise ValueError("FLEET_REFUSED_BAD_TASK:" + str(task)[:64])
        score = r.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) \
                or not 0.0 <= score <= 1.0:
            raise ValueError("FLEET_REFUSED_BAD_TYPE:score")
        pass_mark = r.get("pass_mark")
        if isinstance(pass_mark, bool) or not isinstance(pass_mark, (int, float)) \
                or not 0.0 <= pass_mark <= 1.0:
            raise ValueError("FLEET_REFUSED_BAD_TYPE:pass_mark")
        by_task[task].append({"run_id": rid, "score": score, "pass_mark": pass_mark,
                              "passed": score >= pass_mark})
    tasks_out = {}
    failures = []
    for task in TASKS:
        history = by_task[task]
        if not history:
            tasks_out[task] = {"runs": 0, "latest_score": None, "best_score": None,
                               "latest_passed": None}
            failures.append(task)  # never measured counts as not passed
            continue
        latest = history[-1]
        tasks_out[task] = {"runs": len(history), "latest_score": latest["score"],
                           "best_score": max(h["score"] for h in history),
                           "latest_passed": latest["passed"]}
        if not latest["passed"]:
            failures.append(task)
    ceiling = max(r["score"] for t in by_task.values() for r in t)
    return {"tasks": tasks_out, "measured_ceiling": ceiling,
            "failures": failures, "run_count": len(runs),
            "scope": policy.scope(
                ["fixed battery (reasoning/planning/novelty)",
                 "per-task aggregates (latest/best; per-run history not returned)",
                 "measured ceiling", "failures vs supplied pass marks"],
                ["running any model here", "superintelligence", "mimicking humans"],
                "supplied measured scores")}


def report(runs):
    return board(runs)
