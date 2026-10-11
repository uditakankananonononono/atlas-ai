"""P32|L32 M30 sequencing gate (offline, stdlib only).

Source line (line map v4, as relayed): "Sequencing: after all prior tasks are done, proceed to
the last task (transitional, no standalone deliverable)".
Source pin: instinct doc P32|L32, line map v4.

GATE MECHANISM ONLY. It decides whether a task-31 start is blocked, from marks the caller
declares for tasks 1..27. It does not do any task, start task 31 or send anything. The
coverage check comes from P246, the audit marks from P243 and the release decision from P247;
all three are loaded by file path and called, none is copied here. GATE_OPEN means only that
the supplied records satisfy the declared rule. It is not proof that any task is done.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

FEATURE = "sequencing_gate_p32"
SOURCE_LINES = ["P32|L32"]
TARGET_TASK = 31
FIRST_TASK = 1
LAST_TASK = 27
REQUIRED_TASKS = list(range(FIRST_TASK, LAST_TASK + 1))
MAX_TASKS = len(REQUIRED_TASKS)
MAX_DEPTH = 8
MAX_NODES = 300000
VERDICT_OPEN = "GATE_OPEN"
VERDICT_BLOCKED = "GATE_BLOCKED"
FORBIDDEN_CATEGORIES = ("Cc", "Zl", "Zp")
_REQ_FIELDS = ("line_map", "evidence", "audit_entries", "tasks", "start_task")
_REQUIRED = ("line_map", "tasks", "start_task")
_LISTS = ("line_map", "evidence", "audit_entries", "tasks")
_LINE_ID = re.compile(r"P[1-9][0-9]*\|L[1-9][0-9]*")
_LEAF = (str, int, bool, float, type(None))
GATE_ID = "task_marks"
METHOD_LIMITS = (
    "GATE_OPEN means only that the supplied coverage declarations and audit marks satisfy the "
    "declared rule for tasks 1..27. It does not verify that any task was done, that any mark is "
    "true, or that a task is missing from the caller's task list. The module starts nothing and "
    "sends nothing."
)

_HERE = Path(__file__).resolve().parent


def _sibling(name):
    key = "_p32_sibling_" + name
    mod = sys.modules.get(key)
    if mod is None:
        spec = importlib.util.spec_from_file_location(key, _HERE / (name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return mod


def _err(code):
    return ValueError("P32:" + code)


def _scan(value, field, depth, budget):
    """Exact-type walk: refuse subclasses and control characters; never echo values."""
    budget[0] += 1
    if budget[0] > MAX_NODES:
        raise _err("too_deep")
    if depth > MAX_DEPTH:
        raise _err("too_deep")
    t = type(value)
    if t is dict:
        for k, v in value.items():
            if type(k) is not str:
                raise _err("bad_type:" + field)
            _scan(k, field, depth + 1, budget)
            _scan(v, field, depth + 1, budget)
    elif t is list:
        for v in value:
            _scan(v, field, depth + 1, budget)
    elif t is str:
        if any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in value):
            raise _err("control_chars:" + field)
    elif t not in _LEAF:
        raise _err("bad_type:" + field)


def _tasks(raw):
    if len(raw) > MAX_TASKS:
        raise _err("limit_exceeded:tasks")
    mapped, lines = {}, set()
    for item in raw:
        if type(item) is not dict:
            raise _err("bad_type:tasks")
        if any(k not in ("task", "line_id") for k in item):
            raise _err("unknown_field:tasks")
        if "task" not in item or "line_id" not in item:
            raise _err("missing_field:tasks")
        n = item["task"]
        if type(n) is not int or not FIRST_TASK <= n <= LAST_TASK:
            raise _err("bad_task_number")
        line = item["line_id"]
        if type(line) is not str or not _LINE_ID.fullmatch(line):
            raise _err("bad_line_id")
        if n in mapped:
            raise _err("duplicate_task")
        if line in lines:
            raise _err("duplicate_line")
        mapped[n] = line
        lines.add(line)
    return mapped


def _marks(entries):
    audit = _sibling("audit_round_p243")
    ledger = audit.create_ledger()
    for e in entries:
        try:
            ledger = audit.add_entry(ledger, e)
        except ValueError as exc:
            kind = (str(exc).split(":") + ["entry"])[1]
            raise _err("audit_refused:" + kind) from None
    marks = {}
    for row in ledger.entries:
        marks.setdefault(row[1], []).append(row[3])
    return marks


def _coverage(req):
    cov = _sibling("line_coverage_p246")
    classes = sorted({r["class"] for r in req["line_map"] if type(r) is dict and type(r.get("class")) is str
                      and r["class"]})
    try:
        out = cov.compute_line_coverage({"line_map": req["line_map"], "evidence": req["evidence"],
                                         "include_classes": classes})
    except ValueError:
        raise _err("coverage_refused") from None
    row_ids = {"P%d|L%d" % (int(str(r["P"])), int(str(r["L"]))) for r in req["line_map"]}
    return {c["line_id"] for c in out["covered"]}, row_ids


def check_sequencing_gate(request):
    if type(request) is not dict:
        raise _err("bad_type:request")
    if any(k not in _REQ_FIELDS for k in request):
        raise _err("unknown_field:request")
    for f in _REQUIRED:
        if f not in request:
            raise _err("missing_field:" + f)
    for f in _LISTS:
        if f in request and type(request[f]) is not list:
            raise _err("bad_type:" + f)
    for f in _REQ_FIELDS:
        if f in request:
            _scan(request[f], f, 0, [0])
    start = request["start_task"]
    if type(start) is not int or start != TARGET_TASK:
        raise _err("bad_target")
    mapped = _tasks(request["tasks"])
    req = {"line_map": request["line_map"], "evidence": request.get("evidence", []),
           "audit_entries": request.get("audit_entries", [])}
    covered, row_ids = _coverage(req)
    marks = _marks(req["audit_entries"])

    complete, blocked = [], []
    for n in REQUIRED_TASKS:
        why = []
        line = mapped.get(n)
        if line is None:
            why.append("unmapped")
        else:
            if line not in row_ids:
                why.append("line_not_in_map")
            elif line not in covered:
                why.append("line_not_covered")
            m = marks.get("task-%d" % n)
            if not m:
                why.append("no_audit_entry")
            elif any(x != "pass" for x in m):
                why.append("audit_not_pass")
        if why:
            blocked.append({"task": n, "reasons": why})
        else:
            complete.append(n)

    gate = _sibling("candy_gate_p247")
    decision = gate.evaluate(
        {"gates": [{"id": GATE_ID, "kind": "all_present",
                    "required": ["task-%d" % n for n in REQUIRED_TASKS]}]},
        {GATE_ID: {"present": ["task-%d" % n for n in complete]}})
    allowed = decision["release"]
    return {
        "feature": FEATURE, "source_lines": list(SOURCE_LINES),
        "verdict": VERDICT_OPEN if allowed else VERDICT_BLOCKED,
        "start_allowed": allowed, "target_task": TARGET_TASK,
        "required_tasks": list(REQUIRED_TASKS), "complete_tasks": complete, "blocked_tasks": blocked,
        "counts": {"required": len(REQUIRED_TASKS), "complete": len(complete), "blocked": len(blocked)},
        "release_decision": decision,
        "claims": {
            "basis": "declared marks and evidence records only; nothing was read or checked",
            "task_work_done": False, "marks_truth_verified": False, "task31_started": False,
            "candy_line_sent": False, "universal_closure": False},
        "method_limits": METHOD_LIMITS, "action": "none",
    }


def render(request):
    r = check_sequencing_gate(request)
    c = r["counts"]
    tail = "not blocked by declared marks" if r["start_allowed"] else "blocked"
    lines = ["sequencing gate P32|L32: %s (%d of %d tasks complete, task %d start %s)"
             % (r["verdict"], c["complete"], c["required"], TARGET_TASK, tail)]
    lines += ["task %d blocked: %s" % (b["task"], ",".join(b["reasons"])) for b in r["blocked_tasks"]]
    return "\n".join(lines)
