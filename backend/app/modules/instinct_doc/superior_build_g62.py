"""Instinct-doc group 62: research-to-superior-build acceptance pipeline.

Source request (instinct doc, group 62, paragraphs 53/135/214/222):
"Research successful people, startups, ventures and patents; build better
versions."

The landed units (c32.dossier, c31.replicate_plan, c37.patents) stop at
dossiers, ticket lists and claim drafts over supplied records. The missing
link built here: given supplied research artifacts about a reference success
(capabilities plus measured metrics) and supplied measurements of our own
build, derive a gap analysis, turn "better versions" into measurable
superiority targets, emit acceptance-tests-first build tickets for every
gap, and attach a verification receipt that recomputes every reported
field from the original task inputs. A supplied "superior" claim is never
trusted: verify() re-derives capability sets, targets, verdicts, tickets
and counts and compares them field by field, with exact-key validation of
the result envelope. Honest limit: verify() shares the validation and
ticket-format helpers with analyze(), so the receipt proves internal
consistency between task and result - it is not an independent measurement
of the build.

Offline, stdlib only, deterministic. Nothing is fetched and nothing is
executed: research records and build measurements are caller-supplied.
Metrics must be non-negative and finite; direction is "higher" (default) or
"lower". Superiority is strict: at margin 1.0 the build must beat the
reference, not tie it.
"""
from __future__ import annotations

import math

from app.modules.c30 import policy

PREFIX = "G62"
MAX_SUBJECTS = 64
MAX_CAPABILITIES = 256
MAX_METRICS = 256
MAX_VALUE = 10 ** 18
DEFAULT_MARGIN = 1.0
MAX_MARGIN = 10.0
HIGHER = "higher"
LOWER = "lower"

SUPERIOR = "SUPERIOR"
NOT_SUPERIOR = "NOT_SUPERIOR"
INCOMPLETE = "INCOMPLETE_EVIDENCE"


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse("BAD_TYPE", field)
    if isinstance(value, float) and not math.isfinite(value):
        _refuse("NON_FINITE", field)
    if value < 0:
        _refuse("NEGATIVE", field)
    if value > MAX_VALUE:
        _refuse("OVERSIZE", field)
    return value


def _margin(value):
    # margin below 1 is refused: a sub-1 margin manufactures superiority
    # (higher: the target drops below the reference; lower: the division can
    # overflow the target to infinity). 1.0 means strictly beat the reference.
    if value is None:
        return DEFAULT_MARGIN
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse("BAD_TYPE", "margin")
    if not math.isfinite(float(value)) or value < 1 or value > MAX_MARGIN:
        _refuse("BAD_MARGIN", "margin")
    return float(value)


def _capabilities(value, field):
    if isinstance(value, bool) or not isinstance(value, (list, tuple)):
        _refuse("BAD_TYPE", field)
    if len(value) > MAX_CAPABILITIES:
        _refuse("OVERSIZE", field)
    return sorted({policy.clean_text(c, PREFIX, field, 128) for c in value})


def _reference_metrics(value, field):
    if isinstance(value, bool) or not isinstance(value, dict):
        _refuse("BAD_TYPE", field)
    if len(value) > MAX_METRICS:
        _refuse("OVERSIZE", field)
    out = {}
    for k, v in value.items():
        name = policy.clean_text(k, PREFIX, field, 128)
        if isinstance(v, dict):
            if set(v) - {"value", "direction"}:
                _refuse("BAD_KEYS", field)
            direction = v.get("direction", HIGHER)
            if direction not in (HIGHER, LOWER):
                _refuse("BAD_DIRECTION", field)
            out[name] = (direction, _number(v.get("value"), field))
        else:
            out[name] = (HIGHER, _number(v, field))
    return out


def _build_metrics(value, field):
    if isinstance(value, bool) or not isinstance(value, dict):
        _refuse("BAD_TYPE", field)
    if len(value) > MAX_METRICS:
        _refuse("OVERSIZE", field)
    return {policy.clean_text(k, PREFIX, field, 128): _number(v, field) for k, v in value.items()}


def _subject(value):
    if not isinstance(value, dict):
        _refuse("BAD_TYPE", "subject")
    if set(value) - {"name", "reference_capabilities", "build_capabilities",
                     "reference_metrics", "build_metrics"}:
        _refuse("BAD_KEYS", "subject")
    return {
        "name": policy.clean_text(value.get("name"), PREFIX, "name", 128),
        "reference_capabilities": _capabilities(value.get("reference_capabilities", []),
                                                "reference_capabilities"),
        "build_capabilities": _capabilities(value.get("build_capabilities", []),
                                            "build_capabilities"),
        "reference_metrics": _reference_metrics(value.get("reference_metrics", {}),
                                                "reference_metrics"),
        "build_metrics": _build_metrics(value.get("build_metrics", {}), "build_metrics"),
    }


def _task(task):
    if not isinstance(task, dict):
        _refuse("BAD_TYPE", "task")
    if set(task) - {"subjects", "margin"}:
        _refuse("BAD_KEYS", "task")
    subjects = task.get("subjects")
    if isinstance(subjects, bool) or not isinstance(subjects, (list, tuple)):
        _refuse("BAD_TYPE", "subjects")
    if not subjects:
        _refuse("EMPTY", "subjects")
    if len(subjects) > MAX_SUBJECTS:
        _refuse("OVERSIZE", "subjects")
    return [_subject(s) for s in subjects], _margin(task.get("margin"))


def _gap_ticket(name, capability):
    return {"kind": "capability_gap", "subject": name, "capability": capability,
            "acceptance_tests_first": True,
            "acceptance": "capability present: %s" % capability}


def _metric_ticket(name, metric, direction, reference, target, margin):
    op = ">" if direction == HIGHER else "<"
    return {"kind": "metric_gap", "subject": name, "metric": metric, "direction": direction,
            "acceptance_tests_first": True,
            "acceptance": "%s %s %r (reference %r, margin %r)" % (metric, op, target, reference, margin)}


def _evidence_ticket(name, metric):
    return {"kind": "evidence_gap", "subject": name, "metric": metric,
            "acceptance_tests_first": True,
            "acceptance": "measure %s for the build" % metric}


def analyze(task):
    """Gap analysis + superiority targets + build tickets over supplied records."""
    subjects, margin = _task(task)
    out_subjects = []
    tickets = []
    tally = {SUPERIOR: 0, NOT_SUPERIOR: 0, INCOMPLETE: 0}
    for s in subjects:
        missing = [c for c in s["reference_capabilities"] if c not in s["build_capabilities"]]
        matched = [c for c in s["reference_capabilities"] if c in s["build_capabilities"]]
        targets = []
        for metric in sorted(s["reference_metrics"]):
            direction, reference = s["reference_metrics"][metric]
            target = reference * margin if direction == HIGHER else reference / margin
            if not math.isfinite(float(target)):
                _refuse("NON_FINITE", "target")
            actual = s["build_metrics"].get(metric)
            if actual is None:
                verdict = "unevaluable"
                tickets.append(_evidence_ticket(s["name"], metric))
            else:
                better = actual > target if direction == HIGHER else actual < target
                verdict = "superior" if better else "not_superior"
                if not better:
                    tickets.append(_metric_ticket(s["name"], metric, direction,
                                                  reference, target, margin))
            targets.append({"metric": metric, "direction": direction,
                            "reference": reference, "target": target,
                            "actual": actual, "verdict": verdict})
        for c in missing:
            tickets.append(_gap_ticket(s["name"], c))
        if missing or any(t["verdict"] == "not_superior" for t in targets):
            verdict = NOT_SUPERIOR
        elif not targets:
            verdict = INCOMPLETE  # no numeric bar: presence is not superiority
        elif any(t["verdict"] == "unevaluable" for t in targets):
            verdict = INCOMPLETE
        else:
            verdict = SUPERIOR
        tally[verdict] += 1
        out_subjects.append({"name": s["name"], "verdict": verdict,
                             "missing_capabilities": missing,
                             "matched_capabilities": matched,
                             "metric_targets": targets,
                             "reference_metric_count": len(s["reference_metrics"]),
                             "build_metric_count": len(s["build_metrics"])})
    tickets.sort(key=lambda t: (t["subject"], t["kind"],
                                t.get("capability") or t.get("metric") or ""))
    return {"margin": margin, "subjects": out_subjects, "tickets": tickets,
            "subject_count": len(out_subjects), "ticket_count": len(tickets),
            "verdicts": tally,
            "scope": policy.scope(
                ["gap analysis over supplied research artifacts",
                 "measurable superiority targets with strict comparison",
                 "acceptance-tests-first build tickets for every gap",
                 "independent task-bound verification receipt via verify()"],
                ["live research or fetching of any kind",
                 "executing the builds the tickets describe",
                 "superiority on axes without supplied numeric metrics",
                 "negative-valued metrics", "weighting across metrics"],
                "caller-supplied research artifacts and build measurements")}


def verify(task, result):
    """Independent re-check: recompute every reported field from the task.

    Nothing in `result` is trusted. Capability sets, per-metric targets and
    verdicts, subject verdicts, the ticket list and every count are
    re-derived here on a separate code path and compared field by field.
    """
    checks = ["structure", "exact_keys", "margin", "subjects", "metric_targets",
              "verdicts", "tickets", "counts", "scope"]
    failed = []
    subjects, margin = _task(task)  # re-validates the original inputs
    if not isinstance(result, dict):
        return {"verified": False, "failed": ["structure"], "checks": checks}
    if set(result) != {"margin", "subjects", "tickets", "subject_count",
                       "ticket_count", "verdicts", "scope"}:
        failed.append("exact_keys")
    if result.get("margin") != margin:
        failed.append("margin")
    expected_subjects = []
    expected_tickets = []
    tally = {SUPERIOR: 0, NOT_SUPERIOR: 0, INCOMPLETE: 0}
    for s in subjects:
        missing = sorted(c for c in s["reference_capabilities"]
                         if c not in set(s["build_capabilities"]))
        matched = sorted(c for c in s["reference_capabilities"]
                         if c in set(s["build_capabilities"]))
        targets = []
        for metric in sorted(s["reference_metrics"]):
            direction, reference = s["reference_metrics"][metric]
            target = reference * margin if direction == HIGHER else reference / margin
            if not math.isfinite(float(target)):
                _refuse("NON_FINITE", "target")
            actual = s["build_metrics"].get(metric)
            if actual is None:
                verdict = "unevaluable"
                expected_tickets.append(_evidence_ticket(s["name"], metric))
            else:
                better = actual > target if direction == HIGHER else actual < target
                verdict = "superior" if better else "not_superior"
                if not better:
                    expected_tickets.append(_metric_ticket(s["name"], metric, direction,
                                                           reference, target, margin))
            targets.append({"metric": metric, "direction": direction,
                            "reference": reference, "target": target,
                            "actual": actual, "verdict": verdict})
        for c in missing:
            expected_tickets.append(_gap_ticket(s["name"], c))
        if missing or any(t["verdict"] == "not_superior" for t in targets):
            verdict = NOT_SUPERIOR
        elif not targets:
            verdict = INCOMPLETE  # no numeric bar: presence is not superiority
        elif any(t["verdict"] == "unevaluable" for t in targets):
            verdict = INCOMPLETE
        else:
            verdict = SUPERIOR
        tally[verdict] += 1
        expected_subjects.append({"name": s["name"], "verdict": verdict,
                                  "missing_capabilities": missing,
                                  "matched_capabilities": matched,
                                  "metric_targets": targets,
                                  "reference_metric_count": len(s["reference_metrics"]),
                                  "build_metric_count": len(s["build_metrics"])})
    expected_tickets.sort(key=lambda t: (t["subject"], t["kind"],
                                         t.get("capability") or t.get("metric") or ""))
    got_subjects = result.get("subjects")
    if got_subjects != expected_subjects:
        named = "subjects"
        if isinstance(got_subjects, list) and len(got_subjects) == len(expected_subjects):
            for got, want in zip(got_subjects, expected_subjects):
                if isinstance(got, dict) and got.get("metric_targets") != want["metric_targets"]:
                    named = "metric_targets"
                    break
        failed.append(named)
    if result.get("verdicts") != tally:
        failed.append("verdicts")
    if result.get("tickets") != expected_tickets:
        failed.append("tickets")
    if result.get("subject_count") != len(expected_subjects) or \
            result.get("ticket_count") != len(expected_tickets):
        failed.append("counts")
    if result.get("scope") != analyze(task)["scope"]:
        failed.append("scope")
    return {"verified": not failed, "failed": sorted(set(failed)), "checks": checks}


def run(task):
    """analyze() + verification receipt; a failed receipt flips the status."""
    result = analyze(task)
    receipt = verify(task, result)
    return {"status": "solved" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
