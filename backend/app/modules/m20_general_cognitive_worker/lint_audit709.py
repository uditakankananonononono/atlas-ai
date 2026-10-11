"""Row709 Linting: audit a SUPPLIED lint report against a SUPPLIED ruleset.

Pure and finite. Nothing is linted, executed or scanned here: the report is a caller-supplied
snapshot and is not verified or authenticated. The audit checks the report against its own
ruleset and says which findings block. See docs/M20_LINT709_CONTRACT.md.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

ALGORITHM = "lint_report_audit_v1"
PREFIX = "LINT709"
SEVERITIES = ("error", "warning", "info")
MAX_RULES = 64
MAX_FINDINGS = 256
MAX_ID = 64
MAX_SEVERITY = 16
MAX_PATH = 128
MAX_REASON = 200
MAX_LINE = 1000000
# blanket fences, applied before any per-character work
MAX_CONTAINERS = 580     # legitimate maximum is 579: top, two lists, 64 rules, 256 findings, 256 suppressions
MAX_KEYS = 8
MAX_OTHER_LIST = 64
MAX_KEY_CHARS = 64
MAX_RAW_STR = 10000
MAX_DEPTH = 5
LIMITS = [
    "the report is caller-supplied: nothing is linted, executed or scanned, and it is not verified or authenticated",
    "rule ids, paths and line numbers are labels only and are not checked against any file or ruleset source",
    "a clean status means the supplied report has no blocking finding and is consistent with its own ruleset, not that the code is clean",
    "completeness is not assessed: findings a linter should have reported but did not are invisible here",
    "suppression reasons are checked only for presence, not for being true or adequate",
]
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
_FORBIDDEN = frozenset({"Cc", "Cf", "Zl", "Zp"})
_LIST_CAPS = {"rules": MAX_RULES, "findings": MAX_FINDINGS}


def _refuse(reason: str, field: str) -> None:
    raise ValueError("%s_REFUSED_%s:%s" % (PREFIX, reason, field))


def _admit(value: Any, field: str, role: str, depth: int, stack: list, count: list) -> None:
    t = type(value)
    if t is str:
        if len(value) > MAX_RAW_STR:
            _refuse("OVERSIZE", field)
    elif t is dict or t is list:
        count[0] += 1
        if depth > MAX_DEPTH or count[0] > MAX_CONTAINERS:
            _refuse("OVERSIZE", field)
        stack.append((value, field, role, depth))
    elif isinstance(value, (dict, list)):
        _refuse("BAD_TYPE", field)


def _preflight(data: dict) -> None:
    """Cardinality first: containers only, no per-character work, children admitted by count."""
    stack = [(data, "input", "top", 0)]
    count = [1]
    while stack:
        node, field, role, depth = stack.pop()
        if type(node) is dict:
            if len(node) > MAX_KEYS:
                _refuse("OVERSIZE", field)
            for k, v in node.items():
                if type(k) is str and len(k) > MAX_KEY_CHARS:
                    _refuse("OVERSIZE", field)
                if role == "top" and k in ("rules", "findings"):
                    _admit(v, k, k, depth + 1, stack, count)
                elif role == "finding" and k == "suppression":
                    _admit(v, "suppression", "suppression", depth + 1, stack, count)
                else:
                    _admit(v, field, "other", depth + 1, stack, count)
        else:
            if len(node) > _LIST_CAPS.get(role, MAX_OTHER_LIST):
                _refuse("OVERSIZE", field)
            for v in node:
                if role in ("rules", "findings") and type(v) is dict:
                    count[0] += 1
                    if depth + 1 > MAX_DEPTH or count[0] > MAX_CONTAINERS:
                        _refuse("OVERSIZE", field)
                    stack.append((v, field, "rule" if role == "rules" else "finding", depth + 1))
                else:
                    _admit(v, field, "other", depth + 1, stack, count)


def _no_non_str_keys(node: Any) -> None:
    stack = [node]
    while stack:
        n = stack.pop()
        if type(n) is dict:
            for k, v in n.items():
                if type(k) is not str:
                    _refuse("BAD_TYPE", "key")
                stack.append(v)
        elif type(n) is list:
            stack.extend(n)


def _keys(obj: dict, required: tuple, field: str) -> None:
    if any(k not in required for k in obj):
        _refuse("UNKNOWN", field)
    for k in required:
        if k not in obj:
            _refuse("MISSING", k)


def _text(value: Any, field: str, cap: int) -> str:
    if type(value) is not str:
        _refuse("BAD_TYPE", field)
    if len(value) > cap:
        _refuse("OVERSIZE", field)
    if any(unicodedata.category(c) in _FORBIDDEN for c in value):
        _refuse("CONTROL_CHARS", field)
    return value


def _ident(value: Any, field: str) -> str:
    _text(value, field, MAX_ID)
    if not _ID.fullmatch(value):
        _refuse("BAD_FORMAT", field)
    return value


def _severity(value: Any) -> str:
    _text(value, "severity", MAX_SEVERITY)
    if value not in SEVERITIES:
        _refuse("BAD_VALUE", "severity")
    return value


def _path(value: Any) -> str:
    _text(value, "path", MAX_PATH)
    if not _PATH.fullmatch(value) or any(s in (".", "..") for s in value.split("/")):
        _refuse("BAD_FORMAT", "path")
    return value


def _caps_pass(data: dict) -> None:
    """Each field's own raw cap before any scan of that field, across the whole report."""
    for rule in data["rules"]:
        if type(rule) is dict:
            for f, cap in (("rule_id", MAX_ID), ("severity", MAX_SEVERITY)):
                v = rule.get(f)
                if type(v) is str and len(v) > cap:
                    _refuse("OVERSIZE", f)
    for fd in data["findings"]:
        if type(fd) is not dict:
            continue
        for f, cap in (("rule_id", MAX_ID), ("severity", MAX_SEVERITY), ("path", MAX_PATH)):
            v = fd.get(f)
            if type(v) is str and len(v) > cap:
                _refuse("OVERSIZE", f)
        sup = fd.get("suppression")
        if type(sup) is dict:
            v = sup.get("reason")
            if type(v) is str and len(v) > MAX_REASON:
                _refuse("OVERSIZE", "reason")


def _rule(raw: Any) -> tuple:
    if type(raw) is not dict:
        _refuse("BAD_TYPE", "rules")
    _keys(raw, ("rule_id", "severity"), "rules")
    return _ident(raw["rule_id"], "rule_id"), _severity(raw["severity"])


def _finding(raw: Any) -> dict:
    if type(raw) is not dict:
        _refuse("BAD_TYPE", "findings")
    _keys(raw, ("rule_id", "severity", "path", "line", "suppression"), "findings")
    rid = _ident(raw["rule_id"], "rule_id")
    sev = _severity(raw["severity"])
    path = _path(raw["path"])
    line = raw["line"]
    if type(line) is not int:
        _refuse("BAD_TYPE", "line")
    if not 1 <= line <= MAX_LINE:
        _refuse("BAD_VALUE", "line")
    sup = raw["suppression"]
    reason = None
    if sup is not None:
        if type(sup) is not dict:
            _refuse("BAD_TYPE", "suppression")
        _keys(sup, ("reason",), "suppression")
        reason = _text(sup["reason"], "reason", MAX_REASON)
    return {"rule_id": rid, "severity": sev, "path": path, "line": line, "suppressed": sup is not None,
            "reason_present": reason is not None and reason.strip() != ""}


def audit(data: Any) -> dict:
    """Audit a supplied lint report. Raises ValueError('LINT709_REFUSED_<REASON>:<field>') on malformed input."""
    if type(data) is not dict:
        _refuse("BAD_TYPE", "input")
    _preflight(data)
    _no_non_str_keys(data)
    _keys(data, ("ruleset", "rules", "findings"), "input")
    ruleset = _ident(data["ruleset"], "ruleset")
    for f in ("rules", "findings"):
        if type(data[f]) is not list:
            _refuse("BAD_TYPE", f)
    if not data["rules"]:
        _refuse("EMPTY", "rules")
    _caps_pass(data)
    declared = {}
    for raw in data["rules"]:
        rid, sev = _rule(raw)
        if rid in declared:
            _refuse("DUPLICATE", "rules")
        declared[rid] = sev
    findings = [_finding(raw) for raw in data["findings"]]

    counts = {s: 0 for s in SEVERITIES}
    blocking, suppressed_errors, violations, seen = [], [], [], set()
    used = set()
    for i, fd in enumerate(findings, 1):
        counts[fd["severity"]] += 1
        rid = fd["rule_id"]
        used.add(rid)
        if rid not in declared:
            violations.append({"index": i, "code": "unknown_rule"})
        elif declared[rid] != fd["severity"]:
            violations.append({"index": i, "code": "severity_mismatch"})
        if fd["suppressed"] and not fd["reason_present"]:
            violations.append({"index": i, "code": "suppression_reason_blank"})
        key = (rid, fd["path"], fd["line"])
        if key in seen:
            violations.append({"index": i, "code": "duplicate_finding"})
        seen.add(key)
        is_error = fd["severity"] == "error" or declared.get(rid) == "error"
        if is_error:
            entry = {"index": i, "rule_id": rid, "path": fd["path"], "line": fd["line"]}
            if fd["suppressed"] and fd["reason_present"]:
                suppressed_errors.append(entry)
            else:
                blocking.append(entry)
    violations.sort(key=lambda v: (v["index"], v["code"]))
    status = "blocked" if blocking else "report_inconsistent" if violations else "clean"
    return {"algorithm": ALGORITHM, "ruleset": ruleset, "status": status, "rule_count": len(declared),
            "finding_count": len(findings), "counts_by_severity": counts, "blocking": blocking,
            "suppressed_errors": suppressed_errors, "violations": violations,
            "rules_without_findings": sorted(set(declared) - used), "suppression_requires_reason": True,
            "limits": list(LIMITS), "linter_executed": False, "source_scanned": False,
            "findings_verified": False, "completeness_assessed": False}
