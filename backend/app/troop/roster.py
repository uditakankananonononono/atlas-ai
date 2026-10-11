"""S1.3 agent-troop roster (offline, stdlib only).

Source (v2 mega-spec, S1.3, relayed by the integrator; I did not see the spec itself): "a whole troop of
agents"; "Autonomously build whole digital companies with autonomous worker ai bots".
Scope as relayed: typed worker roles (researcher, analyst, builder, writer, critic, auditor) with a
deterministic scheduler, budget ledger and per-agent audit log, wrapping the existing troop runner and roles.
Max concurrency is a configured number, reported back.

Jobs run one after another through the existing TroopRunner; the configured concurrency is the runner's
max_workers for the steps inside a job. Budget units are abstract counters, not money. No model, no network.
"""
from __future__ import annotations

from .fleet_common import SPEND, FleetRefusal, err, exact_keys, scan
from .roles import ActionWorker, PlanError, RuleReviewer, TemplatePlanner
from .runner import TroopRunner

UNIT = "S1.3"
FEATURE = "agent_troop_roster"
ROLES = ("researcher", "analyst", "builder", "writer", "critic", "auditor")
MAX_AGENTS = 50
MAX_JOBS = 200
MAX_CONCURRENCY = 16
MAX_UNITS = 10 ** 9
MAX_ID = 64
TASK_KINDS = TemplatePlanner.KINDS
_REQ = ("agents", "max_concurrency", "budget_units", "jobs")
METHOD_LIMITS = (
    "Fixture-runner bookkeeping prototype only. It is not an M20 or model troop and not autonomous companies: "
    "roles only decide which agent a job is assigned to and logged under, and the worker is the fixed toy "
    "ActionWorker. Jobs run sequentially; max_concurrency is the per-job runner pool size, not a count of "
    "agents running at once. Budget units are counters, not money."
)


def _id(v, what):
    if type(v) is not str or not v.strip() or len(v) > MAX_ID:
        raise err(UNIT, "bad_id:" + what)


def _int(v, what, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        raise err(UNIT, "bad_" + what)


def run_roster(request):
    """No worker injection: the worker is always the fixed fixture ActionWorker."""
    if type(request) is not dict:
        raise err(UNIT, "bad_type:request")
    exact_keys(request, UNIT, "request", _REQ, _REQ)
    scan(request, UNIT, "request", text_ok=("text",))
    agents, jobs = request["agents"], request["jobs"]
    if type(agents) is not list:
        raise err(UNIT, "bad_type:agents")
    if type(jobs) is not list:
        raise err(UNIT, "bad_type:jobs")
    _int(request["max_concurrency"], "max_concurrency", 1, MAX_CONCURRENCY)
    _int(request["budget_units"], "budget_units", 0, MAX_UNITS)
    if len(agents) > MAX_AGENTS:
        raise err(UNIT, "limit_exceeded:agents")
    if len(jobs) > MAX_JOBS:
        raise err(UNIT, "limit_exceeded:jobs")
    seen = set()
    for a in agents:
        exact_keys(a, UNIT, "agents", ("id", "role"), ("id", "role"))
        _id(a["id"], "agent")
        if a["role"] not in ROLES or type(a["role"]) is not str:
            raise err(UNIT, "bad_role")
        if a["id"] in seen:
            raise err(UNIT, "duplicate_agent")
        seen.add(a["id"])
    jids = set()
    for j in jobs:
        exact_keys(j, UNIT, "jobs", ("id", "role", "cost", "task"), ("id", "role", "cost", "task"))
        _id(j["id"], "job")
        if j["role"] not in ROLES or type(j["role"]) is not str:
            raise err(UNIT, "bad_role")
        _int(j["cost"], "cost", 0, MAX_UNITS)
        if type(j["task"]) is not dict or "id" in j["task"]:
            raise err(UNIT, "bad_task")
        if j["task"].get("kind") not in TASK_KINDS or type(j["task"].get("kind")) is not str:
            raise err(UNIT, "bad_task_kind")
        if j["id"] in jids:
            raise err(UNIT, "duplicate_job")
        jids.add(j["id"])

    conc = request["max_concurrency"]
    runner = TroopRunner(TemplatePlanner(), ActionWorker(), RuleReviewer(), max_workers=conc)
    remaining = request["budget_units"]
    by_role = {r: sorted(a["id"] for a in agents if a["role"] == r) for r in ROLES}
    load = {a["id"]: 0 for a in agents}
    logs = {a["id"]: [] for a in agents}
    seq = [0]

    def log(agent, job, event, **extra):
        seq[0] += 1
        logs[agent].append({"seq": seq[0], "job": job, "event": event, **extra})

    results, unassigned = {}, []
    for j in jobs:
        pool = by_role[j["role"]]
        if not pool:
            unassigned.append(j["id"])
            continue
        agent = min(pool, key=lambda i: (load[i], i))
        load[agent] += 1
        log(agent, j["id"], "assigned", cost=j["cost"])
        if j["cost"] > remaining:
            log(agent, j["id"], "refused", code=SPEND)
            results[j["id"]] = {"agent": agent, "status": "refused", "code": SPEND, "charged": 0}
            continue
        remaining -= j["cost"]
        try:
            run = runner.run({**j["task"], "id": j["id"]})
        except (PlanError, ValueError, TypeError):
            log(agent, j["id"], "failed", status="planner_error")
            results[j["id"]] = {"agent": agent, "status": "failed", "charged": j["cost"], "error": "planner_error"}
            continue
        log(agent, j["id"], "completed" if run.status == "completed" else "failed", status=run.status)
        results[j["id"]] = {"agent": agent, "status": run.status, "charged": j["cost"],
                            "runner_max_workers": run.max_workers}
    return {"feature": FEATURE, "roles": list(ROLES), "max_concurrency": conc,
            "roster": {a: next(x["role"] for x in agents if x["id"] == a) for a in sorted(logs)},
            "results": results, "unassigned": unassigned,
            "budget": {"total": request["budget_units"], "spent": request["budget_units"] - remaining,
                       "remaining": remaining, "unit": "abstract units, not money"},
            "audit_logs": {a: logs[a] for a in sorted(logs)},
            "claims": {"model_agents": False, "autonomous": False, "money_spent": False},
            "method_limits": METHOD_LIMITS, "action": "none"}
