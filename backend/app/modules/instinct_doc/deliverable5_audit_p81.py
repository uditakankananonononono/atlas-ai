"""Deliverable 5 presence audit (feature-doc line P81|L69).

Source line: "5. Vast amounts of code, tests, verification scripts, and
mathematical formulas." This module checks, per project, whether each of those
four categories is PRESENT among the artifacts that the per-project deliverable
checker measured (files that exist, are non-empty, and match their declared
SHA256). It reports presence and counts only.

It is not a proof of quality, vastness, execution or correctness. "Vast" has no
threshold in the source, so none is applied; a caller may pass minimum counts,
and those are reported as caller-declared parameters.

It consumes the checker's result dict as data. It does not import the checker,
read files, run code or use the network. Category labels come from the caller.
Path hints and content markers are name-and-pattern heuristics and can be wrong.
Content text is only used when it hashes to the artifact's measured SHA256.

Standard library only.
"""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Optional

CATEGORIES = ("code", "test", "verification_script", "formula")
KINDS = ("dataset", "tool", "code", "test", "verification_script", "formula", "real_life_data",
         "external_validation", "benchmark_output")
STATUSES = ("FILE_HASH_MATCH", "NOT_REGULAR_FILE", "EMPTY_FILE", "TOO_LARGE", "CHANGED_DURING_READ",
            "HASH_MISMATCH", "UNREADABLE_OR_UNSAFE", "DUPLICATE_CONTENT")
COUNTED = "FILE_HASH_MATCH"
UNVERIFIED_FIELDS = ("repository_created", "dataset_use", "real_life_data", "tool_execution",
                     "test_execution", "external_validation", "benchmark_execution", "sota")
SOURCE_LINE = "P81|L69"

CODE_EXT = frozenset({".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb", ".sh"})
SCRIPT_EXT = frozenset({".py", ".sh", ".js"})
PROSE_EXT = frozenset({".tex", ".md", ".rst", ".txt"})
TEST_DIRS = frozenset({"tests", "test", "__tests__"})
VERIFY_DIRS = frozenset({"verification", "verify"})

TEST_RE = re.compile(r"\bdef test_|\bassert\b|@Test\b|\bexpect\(|\bit\(|\btest\(|\bdescribe\(")
_MATH_CHARS = "\u2211\u222b\u221a\u2202\u2248\u2264\u2265\u2207"
FORMULA_RE = re.compile(
    r"\\(?:frac|sum|int|sqrt|partial|alpha|beta|begin\{equation\})|\$[^$\n]+\$|\\\[|\\\(|[" + _MATH_CHARS + "]"
)
_SRC_REF = re.compile(r"P\d+\|L\d+")

BOUNDARY = (
    "Presence audit of the artifacts the checker counted. The result is presence only, not quality, "
    "not vastness, not execution, not correctness. Path hints and content markers are name and "
    "pattern heuristics. Category labels come from the caller. Minimum counts, when given, are "
    "caller-declared parameters, not a measure of what the source line asks for."
)


class AuditInputError(ValueError):
    pass


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split(path: str):
    parts = path.split("/")
    base = parts[-1]
    dot = base.rfind(".")
    ext = base[dot:].lower() if dot > 0 else ""
    stem = base[:dot] if dot > 0 else base
    return parts[:-1], base, stem, ext


def _is_test_name(base: str) -> bool:
    return base.startswith("test_") or re.search(r"_test\.[^.]+$", base) is not None or ".test." in base or ".spec." in base


def _hint_code(path: str) -> bool:
    _, base, _, ext = _split(path)
    return ext in CODE_EXT and not _is_test_name(base)


def _hint_test(path: str) -> bool:
    dirs, base, _, ext = _split(path)
    return ext in CODE_EXT and (_is_test_name(base) or any(d in TEST_DIRS for d in dirs))


def _hint_verification(path: str) -> bool:
    dirs, _, stem, ext = _split(path)
    return ext in SCRIPT_EXT and (stem.startswith(("verify", "check", "validate")) or any(d in VERIFY_DIRS for d in dirs))


def _hint_formula(path: str) -> bool:
    _, base, _, ext = _split(path)
    if ext in PROSE_EXT:
        return True
    return ext in (".py", ".ipynb") and any(w in base.lower() for w in ("formula", "math", "equation"))


HINTS = {"code": _hint_code, "test": _hint_test, "verification_script": _hint_verification, "formula": _hint_formula}
MARKERS = {"test": (TEST_RE, "no test marker found in hash-bound content"),
           "formula": (FORMULA_RE, "no formula marker found in hash-bound content")}


def _nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _count(v) -> bool:
    return type(v) is int and v >= 0


def _validate_result(r) -> None:
    if not isinstance(r, dict):
        raise AuditInputError("result must be a dict")
    required = ("project_id", "source_lines", "artifacts", "measured_artifact_count",
                "measured_artifact_counts", "doc_lines_fulfilled") + UNVERIFIED_FIELDS
    for key in required:
        if key not in r:
            raise AuditInputError(f"result is missing {key}")
    if not _nonempty_str(r["project_id"]):
        raise AuditInputError("project_id must be a non-empty string")
    refs = r["source_lines"]
    if not isinstance(refs, list) or not refs or not all(isinstance(x, str) and _SRC_REF.fullmatch(x) for x in refs):
        raise AuditInputError("source_lines must be a non-empty list of Pn|Ln references")
    if not isinstance(r["artifacts"], list):
        raise AuditInputError("artifacts must be a list")
    ids, paths = set(), set()
    recount = {k: 0 for k in KINDS}
    for a in r["artifacts"]:
        if not isinstance(a, dict) or not all(k in a for k in ("id", "kind", "path", "sha256", "status")):
            raise AuditInputError("each artifact needs id, kind, path, sha256 and status")
        if not (_nonempty_str(a["id"]) and _nonempty_str(a["path"]) and isinstance(a["sha256"], str)):
            raise AuditInputError("artifact id, path and sha256 must be strings (id and path non-empty)")
        if a["kind"] not in KINDS:
            raise AuditInputError(f"unknown artifact kind {a['kind']!r}")
        if a["status"] not in STATUSES:
            raise AuditInputError(f"unknown artifact status {a['status']!r}")
        if a["id"] in ids or a["path"] in paths:
            raise AuditInputError("duplicate artifact id or path")
        ids.add(a["id"])
        paths.add(a["path"])
        if a["status"] == COUNTED:
            recount[a["kind"]] += 1
    counts = r["measured_artifact_counts"]
    if not isinstance(counts, dict) or set(counts) != set(KINDS) or not all(_count(v) for v in counts.values()):
        raise AuditInputError("measured_artifact_counts must have exactly the nine kinds with non-negative integers")
    if counts != recount:
        raise AuditInputError("measured_artifact_counts do not match the counted artifacts")
    if not _count(r["measured_artifact_count"]) or r["measured_artifact_count"] != sum(recount.values()):
        raise AuditInputError("measured_artifact_count does not match the counted artifacts (counts mismatch)")
    if r["doc_lines_fulfilled"] is not False:
        raise AuditInputError("result claims doc_lines_fulfilled; refusing to audit")
    for f in UNVERIFIED_FIELDS:
        if r[f] != "UNVERIFIED":
            raise AuditInputError(f"result sets {f} to something other than UNVERIFIED")


def _validate_minimums(minimum_counts) -> dict:
    if minimum_counts is None:
        return {}
    if not isinstance(minimum_counts, dict):
        raise AuditInputError("minimum_counts must be a dict")
    for k, v in minimum_counts.items():
        if k not in CATEGORIES:
            raise AuditInputError(f"minimum_counts has unknown category {k!r}")
        if not _count(v):
            raise AuditInputError("minimum_counts values must be non-negative integers")
    return dict(minimum_counts)


def audit_project(result: dict, *, contents: Optional[dict] = None, minimum_counts: Optional[dict] = None) -> dict:
    """Audit one checker result. Inputs are not modified."""
    _validate_result(result)
    minimums = _validate_minimums(minimum_counts)
    if contents is not None:
        if not isinstance(contents, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in contents.items()):
            raise AuditInputError("contents must be a dict of path to str")
    data = copy.deepcopy(result)
    arts = data["artifacts"]
    by_path = {a["path"]: a for a in arts}
    bound, checked, rejected = {}, [], []
    for path in sorted(contents or {}):
        text = contents[path]
        a = by_path.get(path)
        if a is None:
            reason = "path is not a declared artifact"
        elif a["status"] != COUNTED:
            reason = "artifact was not counted by the checker"
        elif _sha(text) != a["sha256"]:
            reason = "content does not match the artifact sha256"
        else:
            bound[path] = text
            checked.append(path)
            continue
        rejected.append({"path": path, "reason": reason})
    categories = {}
    for cat in CATEGORIES:
        counted = [a for a in arts if a["kind"] == cat and a["status"] == COUNTED]
        notes, corroborated = [], 0
        for a in counted:
            ok = HINTS[cat](a["path"])
            if not ok:
                notes.append(f"{a['path']}: path does not look like a {cat} (heuristic)")
            if a["path"] in bound and cat in MARKERS:
                pattern, message = MARKERS[cat]
                if not pattern.search(bound[a["path"]]):
                    ok = False
                    notes.append(f"{a['path']}: {message}")
            corroborated += 1 if ok else 0
        if not counted:
            verdict = "ABSENT"
        elif corroborated:
            verdict = "PRESENT_CORROBORATED"
        else:
            verdict = "PRESENT_UNCORROBORATED"
        categories[cat] = {
            "verdict": verdict, "counted": len(counted), "corroborated": corroborated,
            "artifact_ids": [a["id"] for a in counted], "notes": notes,
            "meets_declared_minimum": (len(counted) >= minimums[cat]) if cat in minimums else None,
        }
    met = [c["meets_declared_minimum"] for c in categories.values() if c["meets_declared_minimum"] is not None]
    other = {}
    for kind in KINDS:
        if kind in CATEGORIES:
            continue
        n = sum(1 for a in arts if a["kind"] == kind and a["status"] == COUNTED)
        if n:
            other[kind] = n
    return {
        "deliverable": "5", "source_line": SOURCE_LINE, "project_id": data["project_id"],
        "source_lines": data["source_lines"], "cites_p81_l69": SOURCE_LINE in data["source_lines"],
        "categories": categories,
        "all_four_present": all(c["verdict"] != "ABSENT" for c in categories.values()),
        "all_four_corroborated": all(c["verdict"] == "PRESENT_CORROBORATED" for c in categories.values()),
        "not_counted": [{"id": a["id"], "kind": a["kind"], "path": a["path"], "status": a["status"]}
                        for a in arts if a["kind"] in CATEGORIES and a["status"] != COUNTED],
        "other_kinds_counted_not_audited": other,
        "contents_checked": checked, "contents_rejected": rejected,
        "minimum_counts_are_caller_declared": bool(minimums),
        "all_declared_minimums_met": all(met) if met else None,
        "doc_line_fulfilled": False, "vastness_threshold": None,
        "unverified": {"quality": "UNVERIFIED", "vastness": "UNVERIFIED",
                       "execution": "UNVERIFIED", "correctness": "UNVERIFIED"},
        "boundary": BOUNDARY,
    }


def audit_projects(results: list, *, contents_by_project: Optional[dict] = None,
                   minimum_counts: Optional[dict] = None) -> dict:
    if not isinstance(results, list) or not results:
        raise AuditInputError("results must be a non-empty list")
    ids = []
    for r in results:
        _validate_result(r)
        ids.append(r["project_id"])
    if len(ids) != len(set(ids)):
        raise AuditInputError("duplicate project_id in results")
    if contents_by_project is not None:
        if not isinstance(contents_by_project, dict) or not set(contents_by_project) <= set(ids):
            raise AuditInputError("contents_by_project must be a dict keyed by project_id of audited projects")
    reports = [audit_project(r, contents=(contents_by_project or {}).get(r["project_id"]),
                             minimum_counts=minimum_counts) for r in results]
    return {
        "projects": reports,
        "rollup": {
            "projects": len(reports),
            "all_four_present": sum(1 for p in reports if p["all_four_present"]),
            "all_four_corroborated": sum(1 for p in reports if p["all_four_corroborated"]),
            "absent_by_category": {c: sum(1 for p in reports if p["categories"][c]["verdict"] == "ABSENT")
                                   for c in CATEGORIES},
        },
        "doc_line_fulfilled": False,
    }
