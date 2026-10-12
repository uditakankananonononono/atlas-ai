"""Row 83 / concept acceptance ledger for m20 modules.

Source excerpt (supplied text): "add 1,000 AGI-like intelligence concepts".
Builds a per-module ledger: public function count, test files that name the
module, and (optionally) the result of actually running those test files.
A module is TEST_PASSED only when a run in this call passed every referenced
test file. A module is a candidate concept, not a verified AGI-like
intelligence concept: this ledger cannot judge whether code is intelligent.
Compared with the 1,000 target, the count of TEST_PASSED modules is reported
as is. Stdlib only.
"""
from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

TARGET = 1000
M20 = "backend/app/modules/m20_general_cognitive_worker"


def _public_funcs(path):
    try:
        tree = ast.parse(path.read_text("utf-8", "replace"))
    except (SyntaxError, ValueError):
        return None
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not n.name.startswith("_"))


def _modules(root):
    d = root / M20
    return sorted(p for p in d.glob("*.py")
                  if p.stem != "__init__" and not p.stem.endswith("_routes"))


def _test_index(root, stems):
    tests = sorted((root / "tests").rglob("test_*.py"))
    pats = {s: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(s) + r"(?![A-Za-z0-9_])") for s in stems}
    idx = {s: [] for s in stems}
    for t in tests:
        text = t.read_text("utf-8", "replace")
        for s, pat in pats.items():
            if pat.search(text):
                idx[s].append(str(t.relative_to(root)))
    return idx


def _run(root, files, timeout):
    """Run each test file separately; return {file: True/False/None(timeout)}."""
    res = {}
    for f in files:
        try:
            p = subprocess.run([sys.executable, "-m", "pytest", "--noconftest", "-q", "-x", f],
                               cwd=str(root), capture_output=True, timeout=timeout, check=False)
            res[f] = p.returncode == 0
        except subprocess.TimeoutExpired:
            res[f] = None
    return res


def build(repo_root, run_tests=False, timeout=120, target=TARGET):
    if isinstance(run_tests, bool) is False or isinstance(target, bool) or not isinstance(target, int):
        raise ValueError("CONCEPT_LEDGER_REFUSED_BAD_TYPE")
    root = pathlib.Path(repo_root)
    mods = _modules(root)
    idx = _test_index(root, [m.stem for m in mods])
    results = _run(root, sorted({f for v in idx.values() for f in v}), timeout) if run_tests else {}
    rows = []
    for m in mods:
        files = idx[m.stem]
        n = _public_funcs(m)
        if n is None:
            verdict = "UNPARSEABLE"
        elif not files:
            verdict = "UNTESTED"
        elif not run_tests:
            verdict = "TEST_REFERENCED_NOT_RUN"
        elif all(results[f] is True for f in files):
            verdict = "TEST_PASSED"
        elif any(results[f] is False for f in files):
            verdict = "TEST_FAILED"
        else:
            verdict = "TEST_TIMEOUT"
        rows.append({"module": m.stem, "public_functions": n, "test_files": files, "verdict": verdict})
    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    passed = counts.get("TEST_PASSED", 0)
    return {"target": target, "modules": len(rows), "verdict_counts": counts,
            "test_passed": passed, "shortfall_vs_target": max(0, target - passed),
            "complete": passed >= target, "rows": rows,
            "scope": {"implemented": ["module inventory", "static test reference index",
                                      "optional per-file test execution"],
                      "not_implemented": ["judgment that a module is an AGI-like concept",
                                          "behavioral acceptance beyond the referenced tests",
                                          "Sugarcode concepts"],
                      "data_source": "working tree at " + str(root)}}
