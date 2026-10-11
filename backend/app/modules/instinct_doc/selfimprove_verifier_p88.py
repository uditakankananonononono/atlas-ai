"""P88|L76 deliverable 12: verifier for a declared self-improvement mechanism (register -> propose -> re-score -> accept/reject).

Pure stdlib. It checks the CONSISTENCY of caller-supplied recorded fixtures. It does not run, import or
implement any mechanism, never claims a module improves itself and does not touch the P61 line. All field names,
verdicts and refusal codes are interpretation choices; see docs/INSTINCT_P88_L76_SELFIMPROVE_VERIFIER_CONTRACT.md.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

CONTRACT_ID = "P88|L76"
MAX_ID = 64
MAX_HOOK = 128
MAX_DELTA = 128
MAX_TASKS = 32
MAX_ABS = 10 ** 12
DECISIONS = ("accept", "reject")
RECORD_KEYS = {"id", "mechanism", "accept_threshold", "min_improvement", "tasks"}
MECH_KEYS = {"declared", "hook_ref"}
TASK_REQUIRED = {"id", "baseline_score"}
TASK_KEYS = TASK_REQUIRED | {"delta", "rescored", "decision"}
LIMITS = (
    "verifies the consistency of caller-supplied recorded fixtures only: the declared mechanism is not executed, imported or called, and scores and decisions are taken as given",
    "does not implement module self-improvement and does not touch the separate P61 line",
    "roundtrip_consistent means the recorded fixtures agree with the accept rule recomputed here; it is not evidence that the module improves itself or that the named hook exists",
    "every field name, verdict, refusal code and the accept rule (rescored - baseline >= min_improvement and rescored >= accept_threshold) is an interpretation choice, not taken from the source line",
    "scores are compared with exact arithmetic on the given binary values",
)


def _fail(code: str):
    raise ValueError("P88:" + code)


def _str(value: Any, name: str, limit: int, blank_empty: bool = True) -> str:
    if type(value) is not str:
        _fail(f"bad_type:{name}")
    if blank_empty and not value.strip():
        _fail(f"empty_field:{name}")
    if len(value) > limit:
        _fail(f"text_too_long:{name}")
    return value


def _num(value: Any, name: str, lo: int = -MAX_ABS):
    if type(value) not in (int, float):
        _fail(f"bad_type:{name}")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(f"bad_value:{name}")
    if not lo <= value <= MAX_ABS:
        _fail(f"bad_value:{name}")
    return value


def _task(raw: Any) -> dict:
    if type(raw) is not dict:
        _fail("bad_type:task")
    if any(type(k) is not str or k not in TASK_KEYS for k in raw):
        _fail("unknown_fields:task")
    for name in ("id", "baseline_score"):
        if name not in raw:
            _fail(f"empty_field:{'task_id' if name == 'id' else name}")
    tid = _str(raw["id"], "task_id", MAX_ID)
    base = _num(raw["baseline_score"], "baseline_score")
    delta = raw.get("delta")
    if delta is not None:
        _str(delta, "delta", MAX_DELTA)
    rescored = raw.get("rescored")
    if rescored is not None:
        _num(rescored, "rescored")
    decision = raw.get("decision")
    if decision is not None:
        if type(decision) is not str:
            _fail("bad_type:decision")
        if decision not in DECISIONS:
            _fail("bad_value:decision")
    return {"id": tid, "base": base, "delta": delta, "rescored": rescored, "decision": decision}


def verify(record: Any) -> dict:
    """Verify one record. Raises ValueError('P88:<code>:<name>') on a malformed record."""
    if type(record) is not dict:
        _fail("bad_type:record")
    if any(type(k) is not str or k not in RECORD_KEYS for k in record):
        _fail("unknown_fields:record")
    for name in ("id", "mechanism", "accept_threshold", "min_improvement", "tasks"):
        if name not in record:
            _fail(f"empty_field:{name}")
    rid = _str(record["id"], "id", MAX_ID)
    mech = record["mechanism"]
    if type(mech) is not dict:
        _fail("bad_type:mechanism")
    if any(type(k) is not str or k not in MECH_KEYS for k in mech):
        _fail("unknown_fields:mechanism")
    for name in ("declared", "hook_ref"):
        if name not in mech:
            _fail(f"empty_field:{name}")
    declared = mech["declared"]
    if type(declared) is not bool:
        _fail("bad_type:declared")
    hook = _str(mech["hook_ref"], "hook_ref", MAX_HOOK, blank_empty=False)
    threshold = _num(record["accept_threshold"], "accept_threshold")
    min_imp = _num(record["min_improvement"], "min_improvement", lo=0)
    raw_tasks = record["tasks"]
    if type(raw_tasks) is not list:
        _fail("bad_type:tasks")
    if len(raw_tasks) > MAX_TASKS:
        _fail("limit_exceeded:tasks")

    def key(pair):
        i, t = pair
        tid = t.get("id") if type(t) is dict else None
        return (0, tid, i) if type(tid) is str else (1, "", i)

    parsed, seen = [], set()
    for _, raw in sorted(enumerate(raw_tasks), key=key):
        t = _task(raw)
        if t["id"] in seen:
            _fail(f"duplicate_task_id:{t['id']}")
        seen.add(t["id"])
        parsed.append(t)

    thr_f, min_f = Fraction(threshold), Fraction(min_imp)
    tasks_out, complete, incomplete, inconsistent = [], 0, 0, 0
    exercised = set()
    for t in parsed:
        stages = {"proposed": t["delta"] is not None, "rescored": t["rescored"] is not None, "decided": t["decision"] is not None}
        improvement_met = threshold_met = expected = None
        if stages["rescored"]:
            resc = Fraction(t["rescored"])
            improvement_met = resc - Fraction(t["base"]) >= min_f
            threshold_met = resc >= thr_f
            expected = "accept" if improvement_met and threshold_met else "reject"
        if not all(stages.values()):
            status = "incomplete"
            incomplete += 1
        elif t["decision"] != expected:
            status = "inconsistent"
            inconsistent += 1
        else:
            status = "complete"
            complete += 1
            exercised.add(expected)
        tasks_out.append({"id": t["id"], "stages": stages, "delta": t["delta"], "baseline_score": t["base"], "rescored": t["rescored"],
                          "decision": t["decision"], "expected_decision": expected, "improvement_met": improvement_met,
                          "threshold_met": threshold_met, "status": status})

    registered = declared and bool(hook.strip())
    reasons = []
    if not declared:
        reasons.append("not_declared")
    if not hook.strip():
        reasons.append("hook_ref_missing")
    if not parsed:
        reasons.append("no_fixture_tasks")
    if incomplete:
        reasons.append("incomplete_tasks")
    if inconsistent:
        reasons.append("decision_mismatch")
    if not registered:
        verdict = "no_mechanism_declared"
    elif not parsed or incomplete:
        verdict = "roundtrip_incomplete"
    elif inconsistent:
        verdict = "decision_inconsistent"
    else:
        verdict = "roundtrip_consistent"
    return {"contract": CONTRACT_ID, "id": rid, "verdict": verdict,
            "registration": {"declared": declared, "hook_ref": hook, "registered": registered},
            "tasks": tasks_out, "counts": {"tasks": len(parsed), "complete": complete, "incomplete": incomplete, "inconsistent": inconsistent},
            "both_decisions_exercised": exercised == set(DECISIONS), "reasons": sorted(reasons),
            "mechanism_executed": False, "improvement_claimed": False, "real_mechanism_verified": False, "limits": list(LIMITS)}
