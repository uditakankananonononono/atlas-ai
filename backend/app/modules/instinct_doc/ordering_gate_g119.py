"""G119 / instinct_doc.ordering_gate_g119 - computed ordering gate.

The pinned sequencing_gate_p32 rules on caller-declared task marks; its own
METHOD_LIMITS say GATE_OPEN "is not proof that any task is done". This module
closes that gap: for each task entry it computes the real state from the repo
itself - the module file exists and contains real implementations (AST scan
rejecting pass-only / ellipsis / NotImplementedError bodies), a real test file
exists with real test functions, and the tests are actually executed in a
subprocess and must pass. GATE_OPEN here means computed evidence, not marks.
It orders and verifies only: it starts nothing, sends nothing, spends nothing.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from app.modules.c30 import policy

PREFIX = "OGATE"
VERDICT_OPEN = "GATE_OPEN"
VERDICT_BLOCKED = "GATE_BLOCKED"
_STUB_MARKERS = ("todo: implement", "not implemented yet")
MAX_FILE_BYTES = 5_000_000
MAX_ENTRIES = 5000
TEST_TIMEOUT_S = 180


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _stub_functions(tree):
    """Names of module-level/def functions whose body is a real stub."""
    stubs = []
    for node in ast.walk(tree):
        if type(node) not in (ast.FunctionDef, ast.AsyncFunctionDef):
            continue
        body = [s for s in node.body
                if not (type(s) is ast.Expr and type(s.value) is ast.Constant
                        and type(s.value.value) is str)]  # docstrings are not code
        if not body:
            stubs.append(node.name)
            continue
        if all(type(s) is ast.Pass for s in body):
            stubs.append(node.name)
        elif all(type(s) is ast.Expr and type(s.value) is ast.Constant
                 and s.value.value is Ellipsis for s in body):
            stubs.append(node.name)
        elif all(type(s) is ast.Raise and _is_not_implemented_raise(s) for s in body):
            stubs.append(node.name)
    return sorted(set(stubs))


def _is_not_implemented_raise(stmt):
    exc = stmt.exc
    if type(exc) is ast.Name:
        return exc.id == "NotImplementedError"
    if type(exc) is ast.Call and type(exc.func) is ast.Name:
        return exc.func.id == "NotImplementedError"
    return False


def _real_functions(tree):
    return sorted({n.name for n in ast.walk(tree)
                   if type(n) in (ast.FunctionDef, ast.AsyncFunctionDef)}
                  - set(_stub_functions(tree)))


def _read_source(root, rel, field):
    if type(rel) is not str or not rel or "\\" in rel or rel.startswith("/") or ".." in rel.split("/"):
        _refuse("BAD_PATH", field)
    path = (root / rel).resolve()
    if not str(path).startswith(str(root) + "/"):
        _refuse("PATH_ESCAPE", field)
    if not path.is_file():
        return None, None
    if path.stat().st_size > MAX_FILE_BYTES:
        _refuse("OVERSIZE", field)
    try:
        return path, path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        _refuse("UNREADABLE", field)


def _check_module(root, rel):
    failures = []
    path, source = _read_source(root, rel, "module_path")
    if path is None:
        return {"exists": False, "real_functions": [], "stub_functions": [],
                "failures": ["module_missing"]}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"exists": True, "real_functions": [], "stub_functions": [],
                "failures": ["module_syntax_error"]}
    stubs = _stub_functions(tree)
    real = _real_functions(tree)
    if stubs:
        failures.append("module_has_stub_functions:%s" % ",".join(stubs))
    if not real:
        failures.append("module_has_no_real_functions")
    lowered = source.casefold()
    for marker in _STUB_MARKERS:
        if marker in lowered:
            failures.append("module_has_stub_marker:%s" % marker.replace(" ", "_"))
    return {"exists": True, "real_functions": real, "stub_functions": stubs,
            "failures": failures}


def _check_tests(root, rel):
    path, source = _read_source(root, rel, "test_path")
    if path is None:
        return {"exists": False, "test_functions": [], "failures": ["tests_missing"]}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"exists": True, "test_functions": [], "failures": ["tests_syntax_error"]}
    tests = sorted({n.name for n in ast.walk(tree)
                    if type(n) in (ast.FunctionDef, ast.AsyncFunctionDef)
                    and n.name.startswith("test_")})
    failures = [] if tests else ["tests_have_no_test_functions"]
    return {"exists": True, "test_functions": tests, "failures": failures}


def _run_tests(root, rel):
    """Really execute the test file in isolation; pass means exit code 0."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", rel, "-q", "--noconftest", "-x",
         "--basetemp", str(root / ".ogate_pytest_tmp")],
        cwd=str(root), capture_output=True, text=True, timeout=TEST_TIMEOUT_S)
    tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().split("\n")[-5:])
    return {"executed": True, "exit_code": proc.returncode,
            "passed": proc.returncode == 0, "output_tail": tail[-500:],
            "failures": [] if proc.returncode == 0 else ["tests_failed"]}


def evaluate(payload):
    """Compute the real gate verdict. payload:
    {as_of, repo_root, entries: [{task_id, module_path, test_path}], run_tests: bool}"""
    if type(payload) is not dict or set(payload) - {"as_of", "repo_root", "entries", "run_tests"}:
        _refuse("BAD_TYPE", "payload")
    policy.clean_text(payload.get("as_of"), PREFIX, "as_of", 10)
    if type(payload.get("repo_root")) is not str:
        _refuse("BAD_TYPE", "repo_root")
    root = Path(payload["repo_root"]).resolve()
    if not root.is_dir():
        _refuse("NOT_FOUND", "repo_root")
    entries = payload.get("entries")
    if type(entries) is not list or not entries or len(entries) > MAX_ENTRIES:
        _refuse("BAD_TYPE", "entries")
    run_tests = payload.get("run_tests", True)
    if type(run_tests) is not bool:
        _refuse("BAD_TYPE", "run_tests")
    seen, results = set(), []
    for e in entries:
        if type(e) is not dict or set(e) != {"task_id", "module_path", "test_path"}:
            _refuse("BAD_TYPE", "entry")
        tid = policy.clean_text(e["task_id"], PREFIX, "task_id", 200)
        if tid in seen:
            _refuse("DUPLICATE", "task_id")
        seen.add(tid)
        mod = _check_module(root, e["module_path"])
        tst = _check_tests(root, e["test_path"])
        execution = (_run_tests(root, e["test_path"])
                     if run_tests and not tst["failures"]
                     else {"executed": False, "passed": None,
                           "failures": [] if tst["failures"] else ["tests_not_executed"]})
        failures = mod["failures"] + tst["failures"] + execution["failures"]
        results.append({"task_id": tid, "module_path": e["module_path"],
                        "test_path": e["test_path"], "module": mod, "tests": tst,
                        "execution": execution, "computed_complete": not failures,
                        "failures": failures})
    done = sum(1 for r in results if r["computed_complete"])
    verdict = VERDICT_OPEN if done == len(results) else VERDICT_BLOCKED
    return {
        "as_of": payload["as_of"],
        "verdict": verdict,
        "computed": True,
        "tasks_total": len(results),
        "tasks_computed_complete": done,
        "results": results,
        "scope": policy.scope(
            ["completion computed from the repo itself: real AST stub scan of every "
             "module, real test-function collection, and real subprocess test "
             "execution that must exit 0",
             "GATE_OPEN requires every entry computed-complete; no declared marks "
             "are trusted anywhere in this gate"],
            ["ordering policy itself - this computes completion evidence; the pinned "
             "sequencing gate still owns the declared ordering rule",
             "source authentication of module content beyond stub structure",
             "starting, sending or spending - the gate decides only"],
            "live repository at repo_root", payload["as_of"]),
    }
