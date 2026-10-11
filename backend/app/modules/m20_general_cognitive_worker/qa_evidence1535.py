"""Row 1535 Quality Assurance: evaluate supplied requirement/test evidence.

Pure computation over caller-supplied requirements (with predeclared typed
acceptance conditions) and caller-supplied observations. It reports which
requirements the supplied observations satisfy, refute, leave missing or leave
unresolved. It does not run tests, does not claim any physical test was
performed, grants no release authority, and persists nothing.
"""
from __future__ import annotations

import math
from datetime import datetime

MAX_REQUIREMENTS = 64
MAX_OBSERVATIONS = 512
MAX_CONDITIONS = 16
MAX_REPEATS = 16
MAX_ID = 128

_REQUEST_FIELDS = {"requirements", "observations", "defect_policy", "caller_release_requested"}
_OPS = {
    "<": lambda v, t: v < t,
    "<=": lambda v, t: v <= t,
    ">": lambda v, t: v > t,
    ">=": lambda v, t: v >= t,
    "==": lambda v, t: v == t,
    "!=": lambda v, t: v != t,
}
SATISFIED, REFUTED, MISSING, UNRESOLVED = "SATISFIED", "REFUTED", "MISSING", "UNRESOLVED"


class QAEvidenceError(ValueError):
    """Exact, input-derived refusal of a malformed request."""


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _ident(x):
    return isinstance(x, str) and 0 < len(x) <= MAX_ID


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    return dt.tzinfo is not None and dt.utcoffset() is not None


def _validate_requirements(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_REQUIREMENTS:
        raise QAEvidenceError(f"requirements must have 1..{MAX_REQUIREMENTS} items")
    seen, out = set(), []
    for item in raw:
        if not isinstance(item, dict):
            raise QAEvidenceError("requirement must be an object")
        rid = item.get("id")
        if not _ident(rid):
            raise QAEvidenceError(f"requirement id must be a non-empty string up to {MAX_ID} chars")
        if rid in seen:
            raise QAEvidenceError(f"duplicate requirement id: {rid}")
        seen.add(rid)
        mode = item.get("mode", "all")
        if mode not in ("all", "any"):
            raise QAEvidenceError(f"requirement {rid} mode must be 'all' or 'any'")
        reps = item.get("min_repeats", 1)
        if isinstance(reps, bool) or not isinstance(reps, int) or not 1 <= reps <= MAX_REPEATS:
            raise QAEvidenceError(f"requirement {rid} min_repeats must be an integer 1..{MAX_REPEATS}")
        conds = item.get("conditions")
        if not isinstance(conds, list) or not 1 <= len(conds) <= MAX_CONDITIONS:
            raise QAEvidenceError(f"requirement {rid} conditions must have 1..{MAX_CONDITIONS} items")
        parsed = []
        for i, c in enumerate(conds):
            where = f"requirement {rid} condition {i}"
            if not isinstance(c, dict):
                raise QAEvidenceError(f"{where} must be an object")
            if not _ident(c.get("test_id")) or not _ident(c.get("metric")):
                raise QAEvidenceError(f"{where} test_id and metric must be non-empty strings up to {MAX_ID} chars")
            op, thr = c.get("op"), c.get("threshold")
            if not isinstance(op, str) or (op not in _OPS and op != "between"):
                raise QAEvidenceError(f"{where} op is not supported")
            if op == "between":
                if (not isinstance(thr, list) or len(thr) != 2 or not all(_is_num(x) for x in thr)
                        or thr[0] > thr[1]):
                    raise QAEvidenceError(f"{where} threshold must be [low, high] with low <= high")
            elif not _is_num(thr):
                raise QAEvidenceError(f"{where} threshold must be a finite number")
            parsed.append((c["test_id"], c["metric"], op, thr))
        out.append((rid, mode, reps, parsed))
    return out


def _validate_observations(raw, policy):
    if not isinstance(raw, list) or len(raw) > MAX_OBSERVATIONS:
        raise QAEvidenceError(f"observations must have 0..{MAX_OBSERVATIONS} items")
    seen, good, defects = set(), [], []
    for item in raw:
        if not isinstance(item, dict):
            raise QAEvidenceError("observation must be an object")
        oid = item.get("id")
        if not _ident(oid):
            raise QAEvidenceError(f"observation id must be a non-empty string up to {MAX_ID} chars")
        if oid in seen:
            raise QAEvidenceError(f"duplicate observation id: {oid}")
        seen.add(oid)
        if not _ident(item.get("test_id")) or not _ident(item.get("metric")):
            raise QAEvidenceError(f"observation {oid} test_id and metric must be non-empty strings up to {MAX_ID} chars")
        if not _is_num(item.get("value")):
            raise QAEvidenceError(f"observation {oid} value must be a finite number")
        run_id = item.get("run_id")
        if run_id is not None and not _ident(run_id):
            raise QAEvidenceError(f"observation {oid} run_id must be a non-empty string up to {MAX_ID} chars")
        bad = None
        if item.get("signed") is not True:
            bad = "signed"
        elif not _ident(item.get("source")):
            bad = "source"
        elif not _parse_time(item.get("time")):
            bad = "time"
        if bad:
            if policy == "refuse":
                raise QAEvidenceError(f"observation {oid} defective: {bad}")
            defects.append({"observation_id": oid, "field": bad})
            continue
        good.append((oid, item["test_id"], item["metric"], item["value"], run_id))
    return good, defects


def _holds(op, value, thr):
    if op == "between":
        return thr[0] <= value <= thr[1]
    return _OPS[op](value, thr)


def _combine(mode, statuses):
    if mode == "all":
        for s in (REFUTED, UNRESOLVED, MISSING):
            if s in statuses:
                return s
        return SATISFIED
    if SATISFIED in statuses:
        return SATISFIED
    if UNRESOLVED in statuses:
        return UNRESOLVED
    if all(s == REFUTED for s in statuses):
        return REFUTED
    return MISSING


def evaluate_qa_evidence(request):
    if not isinstance(request, dict):
        raise QAEvidenceError("request must be an object")
    for key in sorted(request):
        if key not in _REQUEST_FIELDS:
            raise QAEvidenceError(f"unknown request field: {key}")
    policy = request.get("defect_policy")
    if policy not in ("refuse", "flag"):
        raise QAEvidenceError("defect_policy must be 'refuse' or 'flag'")
    reqs = _validate_requirements(request.get("requirements"))
    good, defects = _validate_observations(request.get("observations"), policy)
    reqs.sort(key=lambda r: r[0])
    good.sort(key=lambda o: o[0])
    defects.sort(key=lambda d: d["observation_id"])

    wanted = {(t, m) for _, _, _, cs in reqs for t, m, _, _ in cs}
    wanted_tests = {t for t, _ in wanted}
    unmapped = [o[0] for o in good if o[1] not in wanted_tests]
    mismatched = [o[0] for o in good if o[1] in wanted_tests and (o[1], o[2]) not in wanted]

    # conflicts: same test/metric/run with differing values
    groups = {}
    for oid, t, m, v, run_id in good:
        if run_id is not None:
            groups.setdefault((t, m, run_id), []).append((oid, v))
    conflicts = []
    conflicted = set()
    for (t, m, run_id) in sorted(groups):
        items = groups[(t, m, run_id)]
        if len({v for _, v in items}) > 1:
            conflicts.append({"test_id": t, "metric": m, "run_id": run_id,
                              "observation_ids": [i for i, _ in items]})
            conflicted.add((t, m))

    trace, summary = [], []
    for rid, mode, reps, conds in reqs:
        cond_out, statuses = [], []
        for t, m, op, thr in conds:
            rel = [o for o in good if o[1] == t and o[2] == m]
            sup = [o for o in rel if _holds(op, o[3], thr)]
            ref = [o for o in rel if not _holds(op, o[3], thr)]
            # repeats: one run counts once; observations without run_id are separate runs
            runs = {o[4] if o[4] is not None else ("id", o[0]) for o in sup}
            if (t, m) in conflicted:
                st = UNRESOLVED
            elif ref:
                st = REFUTED
            elif len(runs) >= reps:
                st = SATISFIED
            else:
                st = MISSING
            statuses.append(st)
            cond_out.append({"test_id": t, "metric": m, "op": op, "threshold": thr, "status": st,
                             "supporting": [o[0] for o in sup], "refuting": [o[0] for o in ref],
                             "distinct_supporting_runs": len(runs), "min_repeats": reps})
        status = _combine(mode, statuses)
        trace.append({"requirement_id": rid, "mode": mode, "status": status, "conditions": cond_out})
        summary.append({"id": rid, "status": status})

    satisfied = [s["id"] for s in summary if s["status"] == SATISFIED]
    unsupported = {s["id"]: s["status"] for s in summary if s["status"] != SATISFIED}
    return {
        "release_status": "EVIDENCE-SUPPORTED" if not unsupported else "RELEASE-UNREADY",
        "release_authority": False,
        "release_granted": False,
        "caller_release_flag_ignored": "caller_release_requested" in request,
        "physical_test_claimed": False,
        "persisted": False,
        "effects": [],
        "basis": "evaluation of supplied observations against predeclared acceptance conditions; no test was run",
        "requirements": summary,
        "coverage": {"requirements_total": len(reqs), "satisfied_ids": satisfied, "unsupported": unsupported},
        "unmapped_observations": unmapped,
        "mismatched_observations": mismatched,
        "conflicts": conflicts,
        "defects": defects,
        "audit_trace": trace,
    }
