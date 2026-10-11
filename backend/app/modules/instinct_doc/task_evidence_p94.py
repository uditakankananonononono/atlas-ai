"""P94|L81 - task-execution evidence checker.

Source line, verbatim: "Execute all tasks: conduct research, build tools, verify claims,
check accuracy, generate results, improve until benchmark-beating and novel"

Offline, stdlib plus two landed repo modules: it composes, never copies, the
P246 coverage ledger (status words, declared_at validation, coverage check) and
the P65 claim-status check (grades the generated report). It records which of
six evidence marks a task declares. It does not run, verify or assess anything:
a mark with an evidence_ref is only DECLARED, a mark without one is UNVERIFIED,
and no evidence_ref is ever invented. Nothing here says a task was fulfilled or
that any result is accurate, benchmark-beating or novel.
"""
from __future__ import annotations

import unicodedata

from app.modules.instinct_doc import line_coverage_p246 as p246
from app.reports import claim_status as p65

LINE_ID = "P94|L81"
SOURCE_LINE = ("Execute all tasks: conduct research, build tools, verify claims, check accuracy, "
               "generate results, improve until benchmark-beating and novel")
CATEGORIES = ("research", "tools", "verify_claims", "accuracy", "results", "improve_until_benchmark")
DECLARED = "DECLARED"
UNVERIFIED = "UNVERIFIED"
MAX_TASKS = 1024
MAX_TASK_ID = 64
MAX_EVIDENCE_REF = 128
_REQUEST_FIELDS = ("tasks", "declared_at")
_TASK_FIELDS = ("task_id", "marks")
_MARK_FIELDS = ("category", "evidence_ref")


def _err(code: str) -> ValueError:
    return ValueError("P94:" + code)


def _has_control(text: str) -> bool:
    return any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in text)


def _text(value, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise _err("bad_type:" + name)
    if _has_control(value):
        raise _err("bad_chars:" + name)
    return value


def _parse_task(task) -> tuple:
    if not isinstance(task, dict):
        raise _err("bad_type:task")
    if any(k not in _TASK_FIELDS for k in task):
        raise _err("unknown_fields:task")
    if "task_id" not in task:
        raise _err("bad_type:task_id")
    task_id = _text(task["task_id"], "task_id")
    if any(c in task_id for c in "[]|"):
        raise _err("bad_chars:task_id")
    if not task_id.strip():
        raise _err("empty_field:task_id")
    if len(task_id) > MAX_TASK_ID:
        raise _err("text_too_long:task_id")
    marks = task.get("marks")
    if not isinstance(marks, list):
        raise _err("bad_type:marks")
    found = {}
    for mark in marks:
        if not isinstance(mark, dict):
            raise _err("bad_type:mark")
        if any(k not in _MARK_FIELDS for k in mark):
            raise _err("unknown_fields:mark")
        if "category" not in mark:
            raise _err("bad_type:category")
        category = _text(mark["category"], "category")
        if category not in CATEGORIES:
            raise _err("bad_category:" + category)
        ref = ""
        if "evidence_ref" in mark:
            ref = _text(mark["evidence_ref"], "evidence_ref")
            if len(ref) > MAX_EVIDENCE_REF:
                raise _err("text_too_long:evidence_ref")
            if not ref.strip():
                ref = ""
        if category in found:
            raise _err("duplicate_category:%s:%s" % (task_id, category))
        found[category] = ref
    return task_id, found


def check_task_evidence(request) -> dict:
    if not isinstance(request, dict):
        raise _err("bad_type:request")
    if any(k not in _REQUEST_FIELDS for k in request):
        raise _err("unknown_fields:request")
    tasks = request.get("tasks")
    if not isinstance(tasks, list):
        raise _err("bad_type:tasks")
    if not tasks:
        raise _err("empty_tasks")
    if len(tasks) > MAX_TASKS:
        raise _err("limit_exceeded:tasks")
    if "declared_at" not in request:
        raise _err("bad_type:declared_at")
    declared_at = _text(request["declared_at"], "declared_at")
    if not declared_at.strip():
        raise _err("empty_field:declared_at")

    parsed, seen = [], set()
    for task in tasks:
        task_id, found = _parse_task(task)
        if task_id in seen:
            raise _err("duplicate_task:" + task_id)
        seen.add(task_id)
        parsed.append((task_id, found))
    parsed.sort(key=lambda p: p[0])

    out_tasks, declared_total, unverified_total = [], 0, 0
    lines = ["# Task execution evidence (%s)" % LINE_ID]
    for task_id, found in parsed:
        cats, missing = {}, []
        for c in CATEGORIES:
            ref = found.get(c, "")
            if ref:
                cats[c] = {"mark": DECLARED, "evidence_ref": ref}
                declared_total += 1
            else:
                cats[c] = {"mark": UNVERIFIED, "evidence_ref": ""}
                missing.append(c)
                unverified_total += 1
            lines.append("CLAIM: task %s %s [%s]" % (task_id, c, cats[c]["mark"]))
        out_tasks.append({"task_id": task_id, "status": p246.COVERED if not missing else p246.UNCOVERED,
                          "categories": cats, "missing": missing})
    covered = sum(1 for t in out_tasks if t["status"] == p246.COVERED)
    report = "\n".join(lines)

    record = {"line_id": LINE_ID,
              "status": p246.COVERED if covered == len(out_tasks) else p246.UNCOVERED,
              "evidence_ref": "P94 task marks: %d tasks, %d declared, %d unverified"
                              % (len(out_tasks), declared_total, unverified_total),
              "declared_at": declared_at, "source": "self"}
    row = {"P": 94, "L": 81, "class": "NON-SCIENCE", "summary": SOURCE_LINE}
    try:
        ledger = p246.compute_line_coverage({"line_map": [row], "evidence": [dict(record)]})
    except p246.LineCoverageError:
        raise _err("bad_declared_at") from None
    chk = p65.check_text(report, {DECLARED, UNVERIFIED})
    return {
        "tasks": out_tasks,
        "counts": {"tasks": len(out_tasks), "covered": covered, "uncovered": len(out_tasks) - covered,
                   "declared_marks": declared_total, "unverified_marks": unverified_total},
        "coverage_record": record,
        "line_coverage": {"covered": ledger["counts"]["covered"], "uncovered": ledger["counts"]["uncovered"]},
        "report": report,
        "report_claim_status": {"ok": chk["ok"], "claims_total": chk["claims_total"], "marked": chk["marked"]},
        "claims": {
            "basis": "declared evidence marks supplied by the caller; nothing was run, read or checked",
            "verified": False,
            "task_fulfilled": False,
            "evidence_adequacy_assessed": False,
            "benchmark_beaten_or_novel_assessed": False,
        },
    }
