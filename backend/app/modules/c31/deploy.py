"""S1.7 / c31.deploy - deploy-1000-builders planner.

Source excerpt (verbatim): "build thousands of real business, running real
operations by themselves... Have 1000s of workers (like all of the above)
working on this".

Plan a fleet of up to 1000 SUPPLIED synthetic builder jobs under a global
concurrency cap with per-job budget accounting. The list is supplied, never
generated here; 1000 is the cap, not a guarantee.
Nothing is executed: this is a deterministic plan for jobs and waves, not
running businesses or workers. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
FLEET_SIZE = 1000
ROLES = ("researcher", "analyst", "builder", "writer", "critic", "auditor")


def plan(jobs, concurrency, spend=False):
    """Build the deterministic wave plan for a supplied job list.

    jobs: list of {"id": str, "cost": int>=1} - must contain at most
    FLEET_SIZE jobs. Pass exactly FLEET_SIZE for the canonical 1000-builder
    run. spend=True requests paid workers and is refused.
    """
    if spend:
        raise ValueError("FLEET_REFUSED_SPEND")  # autonomous spend never happens
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
        raise ValueError("FLEET_REFUSED_BAD_TYPE:concurrency")
    # bool needs no separate guard: not a list/tuple, refusal covers it (pinned)
    if not isinstance(jobs, (list, tuple)):
        raise ValueError("FLEET_REFUSED_BAD_TYPE:jobs")
    if not jobs:
        raise ValueError("FLEET_REFUSED_EMPTY:jobs")
    if len(jobs) > FLEET_SIZE:
        raise ValueError("FLEET_REFUSED_OVERCAP:%d>%d" % (len(jobs), FLEET_SIZE))
    parsed = []
    seen = set()
    for j in jobs:
        if not isinstance(j, dict):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:job")
        jid = policy.clean_text(j.get("id"), PREFIX, "job_id", 64)
        if jid in seen:
            raise ValueError("FLEET_REFUSED_DUPLICATE:" + jid)
        seen.add(jid)
        cost = j.get("cost", 1)
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 1:
            raise ValueError("FLEET_REFUSED_BAD_TYPE:cost")
        parsed.append({"id": jid, "cost": cost,
                       "role": ROLES[len(parsed) % len(ROLES)]})
    actual_concurrency = min(concurrency, len(parsed))
    waves = []
    for start in range(0, len(parsed), actual_concurrency):
        chunk = parsed[start:start + actual_concurrency]
        waves.append({"wave": len(waves) + 1, "jobs": [j["id"] for j in chunk],
                      "cost": sum(j["cost"] for j in chunk), "size": len(chunk)})
    return {"job_count": len(parsed), "jobs": parsed, "waves": waves,
            "wave_count": len(waves), "total_cost": sum(j["cost"] for j in parsed),
            "requested_concurrency": concurrency,
            "actual_concurrency": actual_concurrency,
            "scope": policy.scope(
                ["up to 1000 supplied jobs", "deterministic wave plan",
                 "global concurrency cap", "per-wave budget accounting"],
                ["executing any job", "autonomous operation", "spend (refused)"],
                "supplied job list")}


def report(jobs, concurrency, spend=False):
    return plan(jobs, concurrency, spend)
