"""Instinct-doc group 8: independently checked program-wide benchmark board.

Source request (instinct doc, group 8, paragraph 72): compare every project
against leading field benchmarks.

The landed c30.worldclass unit pairs supplied runs with supplied baselines
and prints margins. It has no project dimension at all and treats every
single-source baseline as usable. This module adds the two missing pieces:

1. "Every project": runs are keyed by project against a supplied project
   registry; a per-project coverage ledger reports UNMEASURED projects
   instead of silently omitting them, and unregistered projects are refused.
2. "Independently checked": a baseline only counts as checked when at
   least two independent registrable source domains (small eTLD+1
   approximation - subdomains of one site count as one source; stated
   limits, not the full public-suffix list) report values whose max-min
   spread fits a relative tolerance (default 5%), order-independent.
   Single-source baselines are computed but never support an AHEAD/BEHIND
   verdict; conflicting sources are reported and disqualify the comparison.
   A task-bound verify() recomputes every median, agreement check, verdict,
   ledger entry and count from the original task on a separate code path.

Offline, stdlib only, deterministic. Nothing is run or fetched: benchmark
runs and baseline figures are caller-supplied. Cross-source agreement
checks consistency, not truth; "leading" is by caller declaration.
"""
from __future__ import annotations

import math
from datetime import date
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = "G8"
MAX_PROJECTS = 256
MAX_RUNS = 2000
MAX_BASELINES = 2000
MAX_VALUE = 10 ** 18
EPSILON = 1e-9
DEFAULT_TOLERANCE = 0.05
MAX_TOLERANCE = 0.5
DATE_MIN = "2000-01-01"

AHEAD, BEHIND, TIED = "ahead", "behind", "tied"
CROSS, SINGLE, CONFLICT = "cross_checked", "single_source", "conflicting"
UNMEASURED = "UNMEASURED"
MEASURED_UNVERIFIED = "MEASURED_UNVERIFIED"
P_AHEAD, P_TIED, P_BEHIND = "AHEAD", "TIED", "BEHIND"


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _text(value, field, limit=200):
    return policy.clean_text(value, PREFIX, field, limit)


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse("BAD_TYPE", field)
    if isinstance(value, float) and not math.isfinite(value):
        _refuse("NON_FINITE", field)
    if abs(value) > MAX_VALUE:
        _refuse("OVERSIZE", field)
    return value


def _date(value, field):
    if not isinstance(value, str):
        _refuse("BAD_TYPE", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _refuse("BAD_DATE", field)
    if parsed.isoformat() != value or value < DATE_MIN:
        _refuse("BAD_DATE", field)
    return value


def _https(value, field):
    url = _text(value, field, 2000)
    try:
        parts = urlsplit(url)
    except ValueError:
        _refuse("BAD_URL", field)
    if parts.scheme.lower() != "https" or not parts.hostname \
            or parts.username is not None or parts.password is not None:
        _refuse("BAD_URL", field)
    return url, parts.hostname.lower()


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _agree_all(values, tolerance):
    """Order-independent agreement: max-min spread within relative tolerance."""
    lo, hi = min(values), max(values)
    return hi - lo <= tolerance * max(abs(hi), abs(lo), 1e-12)


_COMMON_SLD = frozenset({"ac", "co", "com", "net", "org", "gov", "edu", "mil"})


def _registrable(hostname):
    """Small eTLD+1 approximation (NOT the full public-suffix list).

    Last two labels, or last three when the penultimate label is a common
    second-level suffix under a two-letter TLD (co.uk, com.au, ...).
    Stated limit: multi-part suffixes outside this small set are treated as
    plain TLDs (a.blogspot.com groups as blogspot.com).
    """
    labels = [x for x in hostname.lower().split(".") if x]
    if len(labels) >= 3 and labels[-2] in _COMMON_SLD and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return hostname.lower()


def _task(task):
    if not isinstance(task, dict):
        _refuse("BAD_TYPE", "task")
    if set(task) - {"as_of", "projects", "runs", "baselines", "tolerance"}:
        _refuse("BAD_KEYS", "task")
    as_of = _date(task.get("as_of"), "as_of")
    projects = task.get("projects")
    if isinstance(projects, bool) or not isinstance(projects, (list, tuple)) or not projects:
        _refuse("EMPTY", "projects")
    if len(projects) > MAX_PROJECTS:
        _refuse("OVERSIZE", "projects")
    projects = [_text(p, "projects") for p in projects]
    if len(set(projects)) != len(projects):
        _refuse("DUPLICATE", "projects")
    tolerance = task.get("tolerance")
    if tolerance is None:
        tolerance = DEFAULT_TOLERANCE
    elif isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) \
            or not math.isfinite(float(tolerance)) or tolerance <= 0 or tolerance > MAX_TOLERANCE:
        _refuse("BAD_TOLERANCE", "tolerance")
    runs = task.get("runs", [])
    baselines = task.get("baselines", [])
    if not isinstance(runs, (list, tuple)) or isinstance(runs, bool):
        _refuse("BAD_TYPE", "runs")
    if not isinstance(baselines, (list, tuple)) or isinstance(baselines, bool):
        _refuse("BAD_TYPE", "baselines")
    if len(runs) > MAX_RUNS or len(baselines) > MAX_BASELINES:
        _refuse("OVERSIZE", "runs" if len(runs) > MAX_RUNS else "baselines")
    clean_runs, seen_ids = [], set()
    for r in runs:
        if not isinstance(r, dict):
            _refuse("BAD_TYPE", "runs")
        if set(r) - {"project", "benchmark", "metric", "higher_is_better",
                     "value", "run_id", "run_date"}:
            _refuse("BAD_KEYS", "runs")
        project = _text(r.get("project"), "project")
        if project not in set(projects):
            _refuse("UNREGISTERED", project)
        hib = r.get("higher_is_better")
        if not isinstance(hib, bool):
            _refuse("BAD_TYPE", "higher_is_better")
        run_id = _text(r.get("run_id"), "run_id")
        if run_id in seen_ids:
            _refuse("DUPLICATE", "run_id")
        seen_ids.add(run_id)
        run_date = _date(r.get("run_date"), "run_date")
        if run_date > as_of:
            _refuse("FUTURE", "run_date")
        clean_runs.append({"project": project,
                           "benchmark": _text(r.get("benchmark"), "benchmark"),
                           "metric": _text(r.get("metric"), "metric"),
                           "higher_is_better": hib,
                           "value": _number(r.get("value"), "value"),
                           "run_id": run_id, "run_date": run_date})
    clean_baselines = []
    dropped_future = 0
    for b in baselines:
        if not isinstance(b, dict):
            _refuse("BAD_TYPE", "baselines")
        if set(b) - {"benchmark", "metric", "name", "value", "source_url",
                     "reported_date"}:
            _refuse("BAD_KEYS", "baselines")
        url, domain = _https(b.get("source_url"), "source_url")
        domain = _registrable(domain)
        reported = _date(b.get("reported_date"), "reported_date")
        if reported > as_of:
            dropped_future += 1
            continue
        clean_baselines.append({"benchmark": _text(b.get("benchmark"), "benchmark"),
                                "metric": _text(b.get("metric"), "metric"),
                                "name": _text(b.get("name"), "name"),
                                "value": _number(b.get("value"), "value"),
                                "source_url": url, "domain": domain,
                                "reported_date": reported})
    return as_of, projects, clean_runs, clean_baselines, float(tolerance), dropped_future


def _margin(higher_is_better, ours, theirs):
    return ours - theirs if higher_is_better else theirs - ours


def _verdict(margin):
    if margin > EPSILON:
        return AHEAD
    if margin < -EPSILON:
        return BEHIND
    return TIED


def analyze(task):
    """Program-wide benchmark comparison with independent source checks."""
    as_of, projects, runs, baselines, tolerance, dropped_future = _task(task)
    # aggregate runs per (project, benchmark, metric) by median
    groups = {}
    for r in runs:
        groups.setdefault((r["project"], r["benchmark"], r["metric"]), []).append(r)
    aggregates = {}
    for key in sorted(groups):
        rs = groups[key]
        aggregates[key] = {"value": _median([r["value"] for r in rs]),
                           "run_count": len(rs),
                           "higher_is_better": rs[0]["higher_is_better"],
                           "run_ids": sorted(r["run_id"] for r in rs)}
    # independent source check per (benchmark, metric, name)
    bgroups = {}
    for b in baselines:
        bgroups.setdefault((b["benchmark"], b["metric"], b["name"]), []).append(b)
    checked = {}
    single_source = conflicting = 0
    for key in sorted(bgroups):
        bs = bgroups[key]
        by_domain = {}
        for b in bs:
            cur = by_domain.get(b["domain"])
            if cur is None or (b["reported_date"], b["source_url"]) > (cur["reported_date"], cur["source_url"]):
                by_domain[b["domain"]] = b
        reps = [by_domain[d] for d in sorted(by_domain)]
        if len(reps) == 1:
            status = SINGLE
            single_source += 1
            value = reps[0]["value"]
        elif _agree_all([r["value"] for r in reps], tolerance):
            status = CROSS
            value = _median([r["value"] for r in reps])
        else:
            status = CONFLICT
            conflicting += 1
            value = None
        checked[key] = {"status": status, "value": value,
                        "source_count": len(reps),
                        "domains": sorted(by_domain),
                        "values": [r["value"] for r in reps]}
    # comparisons
    comparisons = []
    for (project, benchmark, metric) in sorted(aggregates):
        agg = aggregates[(project, benchmark, metric)]
        matched = [k for k in sorted(checked) if k[0] == benchmark and k[1] == metric]
        for k in matched:
            c = checked[k]
            if c["status"] == CONFLICT:
                verdict = "unchecked_conflict"
                margin = relative = None
            else:
                margin = round(_margin(agg["higher_is_better"], agg["value"], c["value"]), 6)
                relative = round(margin / abs(c["value"]), 6) if c["value"] != 0 else None
                verdict = _verdict(_margin(agg["higher_is_better"], agg["value"], c["value"]))
            comparisons.append({"project": project, "benchmark": benchmark,
                                "metric": metric, "baseline_name": k[2],
                                "value": agg["value"], "baseline_value": c["value"],
                                "margin": margin, "relative_margin": relative,
                                "baseline_status": c["status"],
                                "source_count": c["source_count"],
                                "verdict": verdict})
    # per-project ledger
    ledger = []
    tally = {UNMEASURED: 0, MEASURED_UNVERIFIED: 0, P_AHEAD: 0, P_TIED: 0, P_BEHIND: 0}
    for project in projects:
        project_aggs = [k for k in sorted(aggregates) if k[0] == project]
        project_comps = [c for c in comparisons if c["project"] == project]
        checked_comps = [c for c in project_comps if c["baseline_status"] == CROSS]
        if not project_aggs:
            verdict = UNMEASURED
        elif not checked_comps:
            verdict = MEASURED_UNVERIFIED
        elif any(c["verdict"] == BEHIND for c in checked_comps):
            verdict = P_BEHIND
        elif all(c["verdict"] == AHEAD for c in checked_comps):
            verdict = P_AHEAD
        else:
            verdict = P_TIED
        tally[verdict] += 1
        ledger.append({"project": project, "verdict": verdict,
                       "benchmarks_measured": len(project_aggs),
                       "comparisons": len(project_comps),
                       "checked_comparisons": len(checked_comps),
                       "ahead": sum(1 for c in checked_comps if c["verdict"] == AHEAD),
                       "behind": sum(1 for c in checked_comps if c["verdict"] == BEHIND),
                       "tied": sum(1 for c in checked_comps if c["verdict"] == TIED)})
    measured = tally[P_AHEAD] + tally[P_TIED] + tally[P_BEHIND] + tally[MEASURED_UNVERIFIED]
    return {"as_of": as_of, "tolerance": tolerance,
            "aggregates": [{"project": k[0], "benchmark": k[1], "metric": k[2],
                            **aggregates[k]} for k in sorted(aggregates)],
            "baseline_checks": [{"benchmark": k[0], "metric": k[1], "name": k[2],
                                 **checked[k]} for k in sorted(checked)],
            "comparisons": comparisons, "project_ledger": ledger,
            "summary": {"project_count": len(projects), "verdicts": tally,
                        "measured_projects": measured,
                        "coverage": round(measured / len(projects), 6),
                        "comparisons": len(comparisons),
                        "single_source_baselines": single_source,
                        "conflicting_baselines": conflicting,
                        "future_baselines_dropped": dropped_future},
            "scope": policy.scope(
                ["per-project benchmark coverage ledger, UNMEASURED projects named",
                 "median aggregation across runs per project/benchmark/metric",
                 "independent two-domain source agreement check with tolerance",
                 "single-source and conflicting baselines never support verdicts",
                 "task-bound verification receipt via verify()"],
                ["running benchmarks", "fetching or verifying sources live",
                 "cross-source agreement proves consistency, not truth",
                 "leading is by caller declaration"],
                "caller-supplied runs, baselines and project registry", as_of)}


def verify(task, result):
    """Re-check: recompute every reported field from the task.

    Nothing in `result` is trusted: the envelope is validated for exact
    keys, then run aggregation, domain agreement, comparisons, the project
    ledger and the summary are re-derived from the task with separately
    written logic and compared field by field. Honest limit: verify()
    shares the validation helpers with analyze() (and recomputes the static
    scope block through it), so the receipt proves internal consistency
    between task and result - it is not an independent measurement of the
    underlying benchmark runs.
    """
    checks = ["structure", "exact_keys", "aggregates", "baseline_checks",
              "comparisons", "project_ledger", "summary", "scope"]
    if not isinstance(result, dict):
        return {"verified": False, "failed": ["structure"], "checks": checks}
    failed = []
    if set(result) != {"as_of", "tolerance", "aggregates", "baseline_checks",
                       "comparisons", "project_ledger", "summary", "scope"}:
        failed.append("exact_keys")
    as_of, projects, runs, baselines, tolerance, dropped_future = _task(task)

    # independent run aggregation: per project, fold runs one at a time
    agg = {}
    for r in runs:
        key = (r["project"], r["benchmark"], r["metric"])
        entry = agg.setdefault(key, {"values": [], "hib": r["higher_is_better"], "ids": []})
        entry["values"].append(r["value"])
        entry["ids"].append(r["run_id"])
    expected_aggregates = []
    for key in sorted(agg):
        entry = agg[key]
        vals = sorted(entry["values"])
        n = len(vals)
        median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        expected_aggregates.append({"project": key[0], "benchmark": key[1],
                                    "metric": key[2], "value": median,
                                    "run_count": n,
                                    "higher_is_better": entry["hib"],
                                    "run_ids": sorted(entry["ids"])})
    if result.get("aggregates") != expected_aggregates:
        failed.append("aggregates")

    # independent baseline check: count distinct domains, then test agreement
    bgroups = {}
    for b in baselines:
        bgroups.setdefault((b["benchmark"], b["metric"], b["name"]), {}) \
            .setdefault(b["domain"], []).append(b)
    checks_out = []
    single = conflicting = 0
    for key in sorted(bgroups):
        reps = []
        for domain in sorted(bgroups[key]):
            candidates = bgroups[key][domain]
            reps.append(sorted(candidates,
                               key=lambda b: (b["reported_date"], b["source_url"]))[-1])
        vals = [r["value"] for r in reps]
        if len(reps) == 1:
            status, value = SINGLE, vals[0]
            single += 1
        else:
            lo, hi = min(vals), max(vals)
            if hi - lo <= tolerance * max(abs(hi), abs(lo), 1e-12):
                ordered = sorted(vals)
                n = len(ordered)
                status = CROSS
                value = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
            else:
                status, value = CONFLICT, None
                conflicting += 1
        checks_out.append({"benchmark": key[0], "metric": key[1], "name": key[2],
                           "status": status, "value": value,
                           "source_count": len(reps),
                           "domains": sorted(bgroups[key]),
                           "values": vals})
    if result.get("baseline_checks") != checks_out:
        failed.append("baseline_checks")

    # independent comparisons: walk baseline checks outer, aggregates inner
    by_pair = {}
    for a in expected_aggregates:
        by_pair.setdefault((a["benchmark"], a["metric"]), []).append(a)
    expected_comps = []
    for chk in checks_out:
        for a in by_pair.get((chk["benchmark"], chk["metric"]), []):
            if chk["status"] == CONFLICT:
                expected_comps.append({"project": a["project"],
                                       "benchmark": a["benchmark"],
                                       "metric": a["metric"],
                                       "baseline_name": chk["name"],
                                       "value": a["value"], "baseline_value": None,
                                       "margin": None, "relative_margin": None,
                                       "baseline_status": CONFLICT,
                                       "source_count": chk["source_count"],
                                       "verdict": "unchecked_conflict"})
                continue
            raw = (a["value"] - chk["value"]) if a["higher_is_better"] \
                else (chk["value"] - a["value"])
            if raw > EPSILON:
                verdict = AHEAD
            elif raw < -EPSILON:
                verdict = BEHIND
            else:
                verdict = TIED
            expected_comps.append({"project": a["project"],
                                   "benchmark": a["benchmark"],
                                   "metric": a["metric"],
                                   "baseline_name": chk["name"],
                                   "value": a["value"], "baseline_value": chk["value"],
                                   "margin": round(raw, 6),
                                   "relative_margin": round(raw / abs(chk["value"]), 6)
                                   if chk["value"] != 0 else None,
                                   "baseline_status": chk["status"],
                                   "source_count": chk["source_count"],
                                   "verdict": verdict})
    expected_comps.sort(key=lambda c: (c["project"], c["benchmark"], c["metric"],
                                       c["baseline_name"]))
    if result.get("comparisons") != expected_comps:
        failed.append("comparisons")

    # independent ledger and summary
    ledger = []
    tally = {UNMEASURED: 0, MEASURED_UNVERIFIED: 0, P_AHEAD: 0, P_TIED: 0, P_BEHIND: 0}
    for project in projects:
        comps = [c for c in expected_comps if c["project"] == project]
        measured = [a for a in expected_aggregates if a["project"] == project]
        checked_comps = [c for c in comps if c["baseline_status"] == CROSS]
        if not measured:
            verdict = UNMEASURED
        elif not checked_comps:
            verdict = MEASURED_UNVERIFIED
        elif any(c["verdict"] == BEHIND for c in checked_comps):
            verdict = P_BEHIND
        elif all(c["verdict"] == AHEAD for c in checked_comps):
            verdict = P_AHEAD
        else:
            verdict = P_TIED
        tally[verdict] += 1
        ledger.append({"project": project, "verdict": verdict,
                       "benchmarks_measured": len(measured),
                       "comparisons": len(comps),
                       "checked_comparisons": len(checked_comps),
                       "ahead": sum(1 for c in checked_comps if c["verdict"] == AHEAD),
                       "behind": sum(1 for c in checked_comps if c["verdict"] == BEHIND),
                       "tied": sum(1 for c in checked_comps if c["verdict"] == TIED)})
    if result.get("project_ledger") != ledger:
        failed.append("project_ledger")
    measured_count = len(projects) - tally[UNMEASURED]
    expected_summary = {"project_count": len(projects), "verdicts": tally,
                        "measured_projects": measured_count,
                        "coverage": round(measured_count / len(projects), 6),
                        "comparisons": len(expected_comps),
                        "single_source_baselines": single,
                        "conflicting_baselines": conflicting,
                        "future_baselines_dropped": dropped_future}
    if result.get("summary") != expected_summary:
        failed.append("summary")
    if result.get("as_of") != as_of or result.get("tolerance") != tolerance:
        failed.append("summary")
    if result.get("scope") != analyze(task)["scope"]:
        failed.append("scope")
    return {"verified": not failed, "failed": sorted(set(failed)), "checks": checks}


def run(task):
    """analyze() + verification receipt; a failed receipt flips the status."""
    result = analyze(task)
    receipt = verify(task, result)
    return {"status": "solved" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
