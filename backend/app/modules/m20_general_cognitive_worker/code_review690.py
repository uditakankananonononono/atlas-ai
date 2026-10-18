"""Code review engine for ledger row 690 (Code Review: improves quality).

Parses a unified diff and applies deterministic, named, rule-based checks to
the ADDED lines only. These checks are heuristics (regex/line based); they are
not a semantic analysis of the code. Approval is recorded only for a distinct
human reviewer and never when blocking findings remain. Nothing here merges,
releases or mutates a repository. Stdlib only.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

BOUNDARY = ("Prepared review evidence only. No merge, release, deployment or "
            "repository mutation is performed.")
SEVERITIES = ("blocking", "warning", "nit")
DECISIONS = ("approve", "request_changes")


class CodeReviewError(ValueError):
    pass


class SelfApprovalError(CodeReviewError):
    pass


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, "\\": 92, '"': 34}


def _header_path(rest: str) -> str:
    """Path from the text after `+++ `, as written by git or `diff -u`.

    Git C-quotes names with special characters ("..." with \\ \" \t \n and octal
    escapes for UTF-8 bytes); the closing quote may be followed by a TAB and a
    timestamp. An unquoted name ends at the first TAB (git quotes real tabs, so a
    raw TAB is the `diff -u` timestamp separator).
    """
    if not rest.startswith('"'):
        return rest.split("\t")[0].strip()
    out = bytearray()
    i, n = 1, len(rest)
    while i < n:
        c = rest[i]
        if c == '"':
            tail = rest[i + 1:]
            if tail and not tail.startswith("\t"):
                raise CodeReviewError("malformed quoted path in file header")
            try:
                return out.decode("utf-8")
            except UnicodeDecodeError:
                # Lossy replacement would let distinct byte names collapse to one
                # string; the route layer is text-only (rejects surrogates), so refuse.
                raise CodeReviewError("quoted path is not valid UTF-8") from None
        if c == "\\":
            i += 1
            if i >= n:
                break
            e = rest[i]
            if e in "01234567":
                j = i
                while j < n and j < i + 3 and rest[j] in "01234567":
                    j += 1
                v = int(rest[i:j], 8)
                if v > 255:
                    raise CodeReviewError("malformed quoted path in file header")
                out.append(v)
                i = j
                continue
            if e not in _ESCAPES:
                raise CodeReviewError("malformed quoted path in file header")
            out.append(_ESCAPES[e])
        else:
            out.extend(c.encode("utf-8"))
        i += 1
    raise CodeReviewError("malformed quoted path in file header")


def parse_unified_diff(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str) or "@@" not in text:
        raise CodeReviewError("diff must be a unified diff containing at least one hunk")
    files: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    hunk = None  # [new_line, expected_add, expected_del, seen_add, seen_del]

    def close():
        if hunk and (hunk[3] != hunk[1] or hunk[4] != hunk[2]):
            raise CodeReviewError("hunk line counts do not match its header")

    for raw in text.split("\n"):
        if hunk is not None and hunk[3] == hunk[1] and hunk[4] == hunk[2] and (
                raw.startswith("diff ") or raw.startswith("--- ") or raw.startswith("+++ ")):
            hunk = None  # hunk fully consumed: next lines are file headers
        if raw.startswith("+++ ") and hunk is None:
            close(); hunk = None
            p = _header_path(raw[4:])
            p = p[2:] if p.startswith("b/") else p
            cur = {"path": p, "added": [], "removed": 0}
            files.append(cur)
            continue
        if raw.startswith("--- ") and hunk is None:
            continue
        m = _HUNK.match(raw)
        if m:
            if cur is None:
                raise CodeReviewError("hunk before file header")
            close()
            exp_del = 1 if m.group(2) is None else int(m.group(2))
            exp_add = 1 if m.group(4) is None else int(m.group(4))
            hunk = [int(m.group(3)), exp_add, exp_del, 0, 0]
            continue
        if raw.startswith("@@"):
            raise CodeReviewError("malformed hunk header")
        if hunk is None or cur is None:
            continue
        if raw.startswith("+"):
            cur["added"].append((hunk[0] + hunk[3], raw[1:])); hunk[3] += 1
        elif raw.startswith("-"):
            cur["removed"] += 1; hunk[4] += 1
        elif raw.startswith(" "):
            # A context line consumes one old and one new source line. It is
            # not an added line, but moves the next addition's source position.
            hunk[3] += 1; hunk[4] += 1
    close()
    if not files or not any(True for _ in files):
        raise CodeReviewError("no file sections found in diff")
    return files


_SECRET = re.compile(r"""(?i)\b(pass(word|wd)?|secret|token|api[_-]?key|private[_-]?key)\b\s*[:=]\s*['"][^'"\s]{8,}['"]""")
_RULES = [
    ("hardcoded-secret", "blocking", _SECRET, "Possible hard-coded credential literal"),
    ("conflict-marker", "blocking", re.compile(r"^(<<<<<<<|>>>>>>>|=======$)"), "Merge conflict marker left in code"),
    ("dynamic-exec", "blocking", re.compile(r"\b(eval|exec)\s*\("), "Dynamic code execution call"),
    ("bare-except", "warning", re.compile(r"^\s*except\s*:"), "Bare except swallows all errors"),
    ("debug-leftover", "warning", re.compile(r"\b(print\(|breakpoint\(|pdb\.set_trace|console\.log\()"), "Debug output left in code"),
    ("todo-marker", "warning", re.compile(r"\b(TODO|FIXME|XXX)\b"), "Unresolved TODO/FIXME marker"),
    ("trailing-whitespace", "nit", re.compile(r"[ \t]+$"), "Trailing whitespace"),
]
_MESSAGES = {r[0]: r[3] for r in _RULES}
# checklist item keyword -> rules that must be clear for the item to pass
_CHECK_MAP = [
    (("debug",), ("debug-leftover",)),
    (("secret", "credential"), ("hardcoded-secret",)),
    (("test",), ("missing-tests",)),
    (("conflict", "merge"), ("conflict-marker",)),
    (("exception", "error handling"), ("bare-except",)),
    (("todo",), ("todo-marker",)),
    (("whitespace", "style", "format"), ("trailing-whitespace", "long-line")),
    (("size", "small"), ("oversized-change",)),
    (("injection", "eval", "exec"), ("dynamic-exec",)),
]
_TEST_PATH = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.[a-z]+$|\.(spec|test)\.[a-z]+$")
_CODE_EXT = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".c", ".cc", ".cpp", ".cs", ".sh")


def review(diff: str, review_checklist, *, author: str, reviewer: str | None = None,
           requested_decision: str | None = None, max_added_lines: int = 400,
           max_line_length: int = 120) -> dict[str, Any]:
    if not isinstance(author, str) or not author.strip():
        raise CodeReviewError("author is required")
    if not isinstance(review_checklist, (list, tuple)) or not all(isinstance(c, str) for c in review_checklist):
        raise CodeReviewError("review_checklist must be a list of strings")
    if requested_decision is not None and requested_decision not in DECISIONS:
        raise CodeReviewError(f"requested_decision must be one of {DECISIONS}")
    norm = lambda s: " ".join(s.lower().split())
    if requested_decision == "approve":
        if not reviewer or not reviewer.strip():
            raise CodeReviewError("approval requires a reviewer")
        if norm(reviewer) == norm(author):
            raise SelfApprovalError("reviewer must differ from author")
    files = parse_unified_diff(diff)
    findings: list[dict[str, Any]] = []
    total_added = 0
    src_changed = tests_changed = False
    for f in files:
        path = f["path"]
        if _TEST_PATH.search(path):
            tests_changed = True
        elif path.endswith(_CODE_EXT) and f["added"]:
            src_changed = True
        total_added += len(f["added"])
        for lineno, text in f["added"]:
            for rule, sev, rx, msg in _RULES:
                if rx.search(text):
                    findings.append({"rule": rule, "severity": sev, "path": path, "line": lineno, "message": msg})
            if len(text) > max_line_length:
                findings.append({"rule": "long-line", "severity": "nit", "path": path, "line": lineno,
                                 "message": f"Line longer than {max_line_length} characters"})
    if src_changed and not tests_changed:
        findings.append({"rule": "missing-tests", "severity": "warning", "path": None, "line": None,
                         "message": "Source files changed with no test file changed"})
    if total_added > max_added_lines:
        findings.append({"rule": "oversized-change", "severity": "warning", "path": None, "line": None,
                         "message": f"{total_added} added lines exceeds {max_added_lines}"})
    fired = {f["rule"] for f in findings}
    checklist = []
    for item in review_checklist:
        low = item.lower()
        mapped = [r for keys, rs in _CHECK_MAP if any(k in low for k in keys) for r in rs]
        if not mapped:
            checklist.append({"item": item, "status": "needs_human", "rules": []})
        else:
            bad = sorted(set(mapped) & fired)
            checklist.append({"item": item, "status": "fail" if bad else "pass", "rules": sorted(set(mapped))})
    blockers = [f for f in findings if f["severity"] == "blocking"]
    approval = None
    if blockers or requested_decision == "request_changes":
        decision = "request_changes"
    elif requested_decision == "approve":
        decision = "approved_by_reviewer"
        approval = {"reviewer": reviewer, "author": author}
    else:
        decision = "no_issues_found" if not findings else "comments_only"
    return {
        "input_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "files": [f["path"] for f in files],
        "added_lines": total_added,
        "findings": findings,
        "checklist": checklist,
        "unresolved_blockers": blockers,
        "decision": decision,
        "approval": approval,
        "self_approval_forbidden": True,
        "heuristic_rules": sorted(_MESSAGES) + ["missing-tests", "oversized-change", "long-line"],
        "human_review_required": True,
        "boundary": BOUNDARY,
    }
