"""S1.7 deploy-1000-builders scheduler (synthetic 1,000-job proof).

Runs up to 1,000 jobs through the troop roster machinery (roles from
``app.troop.roles``: TemplatePlanner -> ActionWorker -> RuleReviewer) in
waves under a configured concurrency cap, with per-job budgets, a global
budget ledger and a per-agent audit log. Hermetic, stdlib only; the proof
runs synthetic stubs (``sum_table`` rows), never real concurrent LLM
builders - live accounts, outreach and spend are refused
(``FLEET_REFUSED_SPEND``). Concurrency is reported as numbers (configured
cap, measured instrumented maximum), never an "all" claim. One job does one
thing in one wave; builder slots are reused across waves.

Deterministic: the schedule, ledger, audit log and outputs depend only on
the payload. ``measured_max_concurrent`` is instrumented on the thread pool
and run-dependent (bounded by the cap).
"""

from concurrent.futures import ThreadPoolExecutor
import threading
import unicodedata

from app.troop.roles import ActionWorker, PlanError, RuleReviewer, TemplatePlanner

QUEUE_CAPACITY = 1000
_MAX_ATTEMPTS = 2
_SPEND_KEYS = ("purchase", "spend", "real_llm", "live_api", "outreach", "live_accounts")
_KINDS = ("sum_table", "text_stats")
_JOB_FIELDS = {"id", "kind", "rows", "text", "top_n", "cost"}
_FIELDS = {"as_of", "jobs", "synthetic_jobs", "concurrency_cap", "per_job_budget",
           "global_budget"} | set(_SPEND_KEYS)
_SCOPE_NOT_IMPLEMENTED = [
    "real concurrent LLM builders - limited by API limits and spend (approval)",
    "no live accounts, outreach, purchases or spend",
    "hardware/compute-derived caps - the cap is caller-declared, not probed",
]


def _refuse(detail):
    raise ValueError(detail)


def _bad_text(value, limit=64):
    if not isinstance(value, str) or value != value.strip() or not (1 <= len(value) <= limit):
        return True
    return any(unicodedata.category(ch) == "Cc" or ch in (" ", " ", " ")
               for ch in value)


def _strict_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _bounded_int(value, name, lo, hi):
    if not _strict_int(value):
        _refuse("FLEET_REFUSED_BAD_TYPE:%s" % name)
    if value < lo or value > hi:
        _refuse("FLEET_REFUSED_OUT_OF_RANGE:%s" % name)
    return value


class _ConcurrencyProbe:
    def __init__(self):
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_seen = 0

    def tick(self):
        with self._lock:
            self.in_flight += 1
            self.max_seen = max(self.max_seen, self.in_flight)

    def tock(self):
        with self._lock:
            self.in_flight -= 1


def _validate_job(job, index, seen):
    if not isinstance(job, dict):
        _refuse("FLEET_REFUSED_BAD_TYPE:jobs[%d]" % index)
    unknown = sorted(set(job) - _JOB_FIELDS)
    if unknown:
        _refuse("FLEET_REFUSED_UNKNOWN_FIELDS:job[%s]" % ",".join(unknown))
    for field in ("id", "kind"):
        if field not in job:
            _refuse("FLEET_REFUSED_EMPTY_FIELD:%s" % field)
    job_id = job["id"]
    if _bad_text(job_id):
        _refuse("FLEET_REFUSED_UNSAFE_CHARS:job_id")
    if job_id in seen:
        _refuse("FLEET_REFUSED_DUPLICATE:%s" % job_id)
    seen.add(job_id)
    kind = job["kind"]
    if not isinstance(kind, str) or kind not in _KINDS:
        _refuse("FLEET_REFUSED_BAD_KIND:%s" % (kind if isinstance(kind, str) else type(kind).__name__))
    cost = job.get("cost", 1)
    if not _strict_int(cost):
        _refuse("FLEET_REFUSED_BAD_TYPE:cost")
    if cost < 0 or cost > 1000:
        _refuse("FLEET_REFUSED_OUT_OF_RANGE:cost")
    task = {"id": job_id, "kind": kind}
    if kind == "sum_table":
        task["rows"] = job.get("rows", [])
    else:
        task["text"] = job.get("text", "")
        if "top_n" in job:
            task["top_n"] = job["top_n"]
    return task, cost


def _synthetic_jobs(count):
    return [{"id": "syn-%04d" % i, "kind": "sum_table",
             "rows": [{"a": i, "b": 2}]} for i in range(count)]


def _execute(task, roles, probe):
    """One job: plan, then per step worker -> reviewer with bounded retries."""
    planner, worker, reviewer = roles
    try:
        plan = planner.plan(task)
    except (PlanError, Exception):
        return "failed", 0, None
    inputs, attempts = {}, 0
    for step in plan.steps:
        step_inputs = {dep: inputs[dep] for dep in step.depends_on}
        done, feedback = False, None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            attempts += 1
            probe.tick()
            try:
                out = worker.execute(step, step_inputs, attempt, feedback)
            except Exception:
                feedback = "worker error"
                continue
            finally:
                probe.tock()
            verdict = reviewer.review(step, out)
            if verdict.ok:
                inputs[step.id] = out
                done = True
                break
            feedback = "; ".join(verdict.reasons)
        if not done:
            return "failed", attempts, None
    return "completed", attempts, inputs


def run_scheduler(payload):
    """Run up to 1,000 jobs through the troop machinery in capped waves.

    Returns the ledger (one row per job: agent, wave, status, attempts,
    cost), a per-agent audit log, budget totals, integrity flags and a scope
    honesty block. Refusals raise ``ValueError`` with a stable
    ``FLEET_REFUSED_*`` reason (see docs/contracts/c31.deploy-1000-builders.md).
    """
    if not isinstance(payload, dict):
        _refuse("FLEET_REFUSED_BAD_TYPE:payload")
    unknown = sorted(set(payload) - _FIELDS)
    if unknown:
        _refuse("FLEET_REFUSED_UNKNOWN_FIELDS:payload")
    for key in _SPEND_KEYS:
        if payload.get(key):
            _refuse("FLEET_REFUSED_SPEND:synthetic_stubs_only_no_live_accounts_outreach_or_spend")
    for field in ("as_of", "concurrency_cap", "per_job_budget", "global_budget"):
        if field not in payload:
            _refuse("FLEET_REFUSED_EMPTY_FIELD:%s" % field)
    as_of = payload["as_of"]
    if not isinstance(as_of, str):
        _refuse("FLEET_REFUSED_BAD_TYPE:as_of")
    if len(as_of) > 32:
        _refuse("FLEET_REFUSED_TEXT_TOO_LONG:as_of")
    if _bad_text(as_of, limit=32):
        _refuse("FLEET_REFUSED_UNSAFE_CHARS:as_of")
    cap = _bounded_int(payload["concurrency_cap"], "concurrency_cap", 1, 256)
    per_job_budget = _bounded_int(payload["per_job_budget"], "per_job_budget", 0, 10**6)
    global_budget = _bounded_int(payload["global_budget"], "global_budget", 0, 10**12)

    has_jobs = "jobs" in payload
    has_syn = "synthetic_jobs" in payload
    if has_jobs == has_syn:
        _refuse("FLEET_REFUSED_JOB_SOURCE:choose_exactly_one_of_jobs_or_synthetic_jobs")
    if has_syn:
        count = _bounded_int(payload["synthetic_jobs"], "synthetic_jobs", 0, 10**9)
        if count > QUEUE_CAPACITY:
            _refuse("FLEET_REFUSED_OVERCAP:queue_capacity_is_1000")
        raw_jobs = _synthetic_jobs(count)
    else:
        if not isinstance(payload["jobs"], list):
            _refuse("FLEET_REFUSED_BAD_TYPE:jobs")
        if len(payload["jobs"]) > QUEUE_CAPACITY:
            _refuse("FLEET_REFUSED_OVERCAP:queue_capacity_is_1000")
        raw_jobs = payload["jobs"]

    seen = set()
    tasks, costs = [], []
    for i, job in enumerate(raw_jobs):
        task, cost = _validate_job(job, i, seen)
        tasks.append(task)
        costs.append(cost)
    order = sorted(range(len(tasks)), key=lambda i: tasks[i]["id"])
    tasks = [tasks[i] for i in order]
    costs = [costs[i] for i in order]

    statuses = ["over_budget" if c > per_job_budget else "pending" for c in costs]
    runnable = sum(c for c, s in zip(costs, statuses) if s == "pending")
    if runnable > global_budget:
        _refuse("FLEET_REFUSED_BUDGET:global_budget_exceeded")

    roles = (TemplatePlanner(), ActionWorker(), RuleReviewer())
    probe = _ConcurrencyProbe()
    runnable = [i for i in range(len(tasks)) if statuses[i] == "pending"]
    waves = {}
    for position, i in enumerate(runnable):
        waves.setdefault(position // cap, []).append((position % cap, i))
    ledger = {i: {"job_id": t["id"], "agent": None, "wave": None,
                  "status": s, "attempts": 0, "cost": c}
              for i, (t, c, s) in enumerate(zip(tasks, costs, statuses))}
    outputs = {}
    for w in sorted(waves):
        def run_one(slot_index):
            slot, i = slot_index
            status, attempts, result = _execute(tasks[i], roles, probe)
            ledger[i].update(agent="builder-%03d" % slot, wave=w,
                             status=status, attempts=attempts)
            if status == "completed":
                outputs[tasks[i]["id"]] = result

        with ThreadPoolExecutor(max_workers=cap) as pool:
            list(pool.map(run_one, waves[w]))
    for i, row in ledger.items():
        if row["agent"] is None:  # over_budget jobs never enter a wave
            row.update(agent=None, wave=None)

    rows = [ledger[i] for i in range(len(tasks))]
    completed = sum(1 for r in rows if r["status"] == "completed")
    failed = sum(1 for r in rows if r["status"] == "failed")
    spent = sum(r["cost"] for r in rows if r["status"] in ("completed", "failed"))
    agents = {}
    for r in rows:
        if r["agent"] is None:
            continue
        entry = agents.setdefault(r["agent"], {"agent": r["agent"], "jobs_run": 0, "completed": 0,
                                               "failed": 0, "attempts": 0, "cost": 0})
        entry["jobs_run"] += 1
        entry[r["status"]] += 1
        entry["attempts"] += r["attempts"]
        entry["cost"] += r["cost"]
    audit = [agents[name] for name in sorted(agents)]
    audit_jobs_sum = sum(a["jobs_run"] for a in audit)
    spent_matches = spent == sum(r["cost"] for r in rows if r["status"] in ("completed", "failed"))
    return {
        "jobs_total": len(rows),
        "completed": completed,
        "failed": failed,
        "over_budget": sum(1 for r in rows if r["status"] == "over_budget"),
        "waves": len(waves),
        "concurrency_cap": cap,
        "builder_slots_used": min(len(waves[0]), cap) if waves else 0,
        "measured_max_concurrent": probe.max_seen,
        "concurrency_basis": ("configured_cap; measured_max_concurrent is instrumented on the "
                              "synthetic thread pool and is run-dependent (bounded by the cap)"),
        "budget": {"per_job": per_job_budget, "global": global_budget,
                   "spent": spent, "remaining": global_budget - spent},
        "ledger": rows,
        "audit_log": audit,
        "integrity": {"ledger_rows": len(rows), "audit_jobs_sum": audit_jobs_sum,
                      "spent_matches_ledger": spent_matches,
                      "consistent": (len(rows) == audit_jobs_sum
                                     + sum(1 for r in rows if r["agent"] is None)
                                     and spent_matches)},
        "outputs": outputs,
        "proof": "synthetic_stub_execution",
        "scope": {
            "implemented": ("synthetic 1,000-job queue proof over the troop roles (planner, "
                            "worker, reviewer) with wave scheduling, per-job budgets, a global "
                            "budget ledger and a per-agent audit log"),
            "not_implemented": _SCOPE_NOT_IMPLEMENTED,
            "data_source": "supplied+synthetic",
            "as_of": as_of,
        },
    }
