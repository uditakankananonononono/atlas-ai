"""Connects persisted task records to the uncertainty gate (Atlas spec 4.2.3/4.2.7/4.2.8).

Reads real Episode records (schemas.Episode: actions[].tool, .succeeded, .outcome_unknown,
.started_at) as stored by EpisodicMemory / DurableEpisodicMemory (m20_episodes) and replays
each action outcome, in start order, into an OutcomeMetacognition learner keyed by tool name.
Unknown outcomes (outcome_unknown=True) are excluded and counted, never treated as success
or failure. Episode.outcome ABANDONED is not used to infer action results.

Limits: observation-only learner (its strategy callables refuse to execute); evidence is the
tool-level success history in stored episodes, not correctness of an arbitrary new task;
the recorded `succeeded` flag is whatever the executor reported. Nothing here authorises an
action: use UncertaintyGate.decide(), and high stakes always require real authority.
"""
from __future__ import annotations
from typing import Iterable, Tuple

from .outcome_metacognition_1975_2009 import OutcomeMetacognition
from .uncertainty_gate_metacognition import UncertaintyGate


def _refuse(_task):
    raise RuntimeError("observation-only learner: strategy execution is not available here")


def collect_action_outcomes(episodes: Iterable) -> Tuple[list, dict]:
    """Return ([(started_at, tool, succeeded_bool), ...] sorted, stats)."""
    rows, unknown, malformed = [], 0, 0
    for ep in episodes:
        for a in getattr(ep, "actions", None) or []:
            tool = getattr(a, "tool", None)
            ok = getattr(a, "succeeded", None)
            if not isinstance(tool, str) or not tool or not isinstance(ok, bool):
                malformed += 1
                continue
            if getattr(a, "outcome_unknown", False):
                unknown += 1
                continue
            rows.append((getattr(a, "started_at", None), tool, ok))
    try:
        rows.sort(key=lambda r: (r[0] is None, r[0]))
    except TypeError:
        raise ValueError("action started_at values must be mutually comparable")
    return rows, {"counted": len(rows), "unknown_excluded": unknown, "malformed_skipped": malformed}


def gate_from_episodes(episodes: Iterable, stakes_policy=None) -> Tuple[UncertaintyGate, dict]:
    rows, stats = collect_action_outcomes(episodes)
    tools = sorted({t for _, t, _ in rows})
    if not tools:
        raise ValueError("no counted action outcomes in the supplied episodes")
    learner = OutcomeMetacognition({t: _refuse for t in tools})
    for _, tool, ok in rows:
        learner.record(tool, learner.confidence(tool), ok)
    return UncertaintyGate(learner, stakes_policy), stats
