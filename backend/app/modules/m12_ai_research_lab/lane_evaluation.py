"""Deterministic evaluation harness.

Cases declare checks over the runner's output; the runner itself is an
injected callable, so the harness evaluates anything (LLM calls, heuristic
pipelines, golden datasets) without owning I/O. Reports are sorted by
case_id and carry per-check evidence plus output hashes, so two runs of
the same suite over the same runner produce identical digests.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from numbers import Number
from typing import Any, Callable, List, Optional, Tuple

from .lane_models import (
    CheckResult,
    EvalCase,
    EvalCaseResult,
    EvalReport,
    canonical_json,
    sha256_hex,
)

SUPPORTED_CHECKS = (
    "exact",
    "json_equals",
    "contains",
    "not_contains",
    "regex",
    "numeric",
    "type",
)

_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "number": Number,
    "null": type(None),
}


def _hash_output(output: Any) -> str:
    try:
        return sha256_hex(canonical_json(output))
    except (TypeError, ValueError):
        return sha256_hex(repr(output))


def run_check(output: Any, check: dict) -> CheckResult:
    """Evaluate one declarative check against an output."""
    ctype = check.get("type")
    if ctype == "exact":
        ok = output == check.get("value")
        detail = f"expected {check.get('value')!r}, got {output!r}"
    elif ctype == "json_equals":
        try:
            ok = canonical_json(output) == canonical_json(check.get("value"))
            detail = "canonical JSON match" if ok else "canonical JSON differs"
        except (TypeError, ValueError) as exc:
            return CheckResult(check, False, f"unserializable value: {exc}")
    elif ctype == "contains":
        needle = check.get("value", "")
        ok = isinstance(output, str) and needle in output
        detail = f"output contains {needle!r}" if ok else f"{needle!r} not found"
    elif ctype == "not_contains":
        needle = check.get("value", "")
        ok = not (isinstance(output, str) and needle in output)
        detail = f"output avoids {needle!r}" if ok else f"{needle!r} present"
    elif ctype == "regex":
        pattern = check.get("pattern", "")
        if not isinstance(output, str):
            return CheckResult(check, False, "output is not a string")
        try:
            ok = re.search(pattern, output) is not None
        except re.error as exc:
            return CheckResult(check, False, f"invalid regex: {exc}")
        detail = f"pattern {pattern!r} matched" if ok else f"pattern {pattern!r} not found"
    elif ctype == "numeric":
        expected = check.get("value")
        tol = check.get("tolerance", 0)
        if not isinstance(output, Number) or isinstance(output, bool):
            return CheckResult(check, False, "output is not numeric")
        if not isinstance(expected, Number):
            return CheckResult(check, False, "check value is not numeric")
        ok = abs(output - expected) <= tol
        detail = f"|{output} - {expected}| = {abs(output - expected)} vs tol {tol}"
    elif ctype == "type":
        expected_type = _TYPE_MAP.get(check.get("value"))
        if expected_type is None:
            return CheckResult(check, False, f"unknown type name {check.get('value')!r}")
        ok = isinstance(output, expected_type) and not (
            expected_type is int and isinstance(output, bool)
        )
        detail = f"type is {type(output).__name__}, expected {check.get('value')}"
    else:
        return CheckResult(check, False, f"unsupported check type {ctype!r}")
    return CheckResult(check, bool(ok), detail)


Runner = Callable[[Any], Any]


def run_evaluation(
    cases: Tuple[EvalCase, ...] | List[EvalCase],
    runner: Runner,
    eval_id: Optional[str] = None,
    created_at_utc: Optional[str] = None,
) -> EvalReport:
    """Run all cases through the runner and build a deterministic report.

    A runner exception fails that case (recorded as evidence) instead of
    aborting the suite.
    """
    results: List[EvalCaseResult] = []
    for case in sorted(cases, key=lambda c: c.case_id):
        try:
            output = runner(case.input)
        except Exception as exc:
            results.append(
                EvalCaseResult(
                    case_id=case.case_id,
                    passed=False,
                    output_hash="",
                    checks=tuple(
                        CheckResult(c, False, f"runner raised: {type(exc).__name__}: {exc}")
                        for c in case.checks
                    ),
                )
            )
            continue
        check_results = tuple(run_check(output, c) for c in case.checks)
        results.append(
            EvalCaseResult(
                case_id=case.case_id,
                passed=all(r.passed for r in check_results),
                output_hash=_hash_output(output),
                checks=check_results,
            )
        )
    passed = sum(1 for r in results if r.passed)
    return EvalReport(
        eval_id=eval_id or f"eval-{uuid.uuid4().hex[:12]}",
        created_at_utc=created_at_utc or datetime.now(timezone.utc).isoformat(),
        case_results=tuple(results),
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
    )
