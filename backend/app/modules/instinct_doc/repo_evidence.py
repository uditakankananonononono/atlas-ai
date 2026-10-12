"""Compute program registers from an actual checkout and executed checks.

No declaration becomes a verified requirement. Static evidence, locally executed
checks and absent external evidence have different labels. Local test execution
is opt-in and runs repository code, not a sandbox. Never use on untrusted repos.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".sql"}
DATA_SUFFIXES = {".csv", ".jsonl", ".ndjson", ".tsv"}
MAX_FILE_BYTES = 8_000_000
MAX_CAPTURE_BYTES = 1_000_000
MAX_FILES = 50000


class EvidenceError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def safe_file(root: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or not p.parts or any(x in ("..", ".git") for x in p.parts):
        raise EvidenceError("unsafe repository path")
    current = root
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            raise EvidenceError("symlink evidence forbidden")
    resolved = current.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise EvidenceError("evidence file missing or outside checkout")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise EvidenceError("evidence file exceeds bounded read limit")
    return resolved


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            timeout=20, check=False)
    if result.returncode:
        raise EvidenceError("git read failed: " + result.stderr.decode(errors="replace")[:200])
    if len(result.stdout) > MAX_FILE_BYTES:
        raise EvidenceError("git output exceeds bound")
    return result.stdout


def snapshot(root: Path):
    root = root.resolve()
    if git(root, "rev-parse", "--show-toplevel").decode().strip() != str(root):
        raise EvidenceError("root must be repository top level")
    names = sorted(set(git(root, "ls-files", "-z").decode().split("\0")) - {""})
    if len(names) > MAX_FILES:
        raise EvidenceError("repository exceeds file bound")
    files, errors = {}, []
    for name in names:
        try:
            data = safe_file(root, name).read_bytes()
            files[name] = {"sha256": digest(data), "bytes": len(data)}
        except EvidenceError as exc:
            errors.append({"path": name, "reason": str(exc)})
    return {"head": git(root, "rev-parse", "HEAD").decode().strip(),
            "origin": git(root, "config", "--get", "remote.origin.url").decode().strip(),
            "dirty": bool(status := git(root, "status", "--porcelain")),
            "status_digest": digest(status),
            "files": files, "errors": errors,
            "tree_digest": canonical_digest(files)}


def source_inventory(root, source_path):
    p = safe_file(root, source_path)
    data = p.read_bytes()
    if p.suffix == ".json":
        manifest = json.loads(data)
        if set(manifest) != {"schema_version", "url", "retrieved_at", "byte_count", "sha256", "rows"} or manifest["schema_version"] != 1:
            raise EvidenceError("invalid source manifest")
        if type(manifest["byte_count"]) is not int or manifest["byte_count"] <= 0 or not re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"]):
            raise EvidenceError("invalid source fingerprint")
        if not isinstance(manifest["rows"], list) or not 1 <= len(manifest["rows"]) <= 10000:
            raise EvidenceError("invalid manifest line inventory")
        rows, seen = [], set()
        for row in manifest["rows"]:
            if set(row) != {"id", "sha256"} or not re.fullmatch(r"export:L[1-9][0-9]*", row["id"]) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) or row["id"] in seen:
                raise EvidenceError("invalid or duplicate source manifest line")
            seen.add(row["id"])
            rows.append({**row, "status": "UNVERIFIED", "reason": "No semantic acceptance evidence bound"})
        return {"path": source_path, "sha256": manifest["sha256"], "rows": rows,
                "manifest_sha256": digest(data), "url": manifest["url"],
                "retrieved_at": manifest["retrieved_at"], "byte_count": manifest["byte_count"],
                "identity": "physical export line numbers; not historical paragraph P/L IDs",
                "source_text_included": False,
                "complete_dependency_scope_verified": False}
    text = data.decode("utf-8-sig")
    if not text.strip() or text.lstrip().lower().startswith(("<!doctype", "<html")):
        raise EvidenceError("source must be nonempty exported text, not HTML")
    rows = [{"id": f"export:L{number}", "sha256": digest(line.encode()),
             "status": "UNVERIFIED", "reason": "No semantic acceptance evidence bound"}
            for number, line in enumerate(text.splitlines(), 1) if line.strip()]
    return {"path": source_path, "sha256": digest(data), "rows": rows,
            "identity": "physical export line numbers; not historical paragraph P/L IDs",
            "complete_dependency_scope_verified": False}


def code_summary(root, files):
    code, tests, modules, findings = [], [], {}, []
    for name in files:
        path = Path(name)
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        text = safe_file(root, name).read_text(errors="replace")
        is_test = any(x in ("tests", "e2e", "__tests__") for x in path.parts) or path.name.startswith("test_")
        item = {"path": name, "lines": len(text.splitlines()), "sha256": files[name]["sha256"]}
        (tests if is_test else code).append(item)
        parts = path.parts
        if parts[:3] == ("backend", "app", "modules") and len(parts) > 4:
            module = parts[3]
            modules.setdefault(module, []).append(item)
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        body = node.body
                        if len(body) == 1 and isinstance(body[0], ast.Pass):
                            findings.append({"path": name, "line": node.lineno, "kind": "pass_only_function", "name": node.name})
            except SyntaxError as exc:
                findings.append({"path": name, "line": exc.lineno, "kind": "parse_error"})
    return {"code_files": len(code), "code_lines": sum(x["lines"] for x in code),
            "test_files": len(tests), "test_lines": sum(x["lines"] for x in tests),
            "modules": modules, "findings": findings, "coverage_percent": None,
            "boundary": "Tracked source line counts, not quality, fulfillment or executed test count"}


def datasets(root, files):
    rows = []
    for name in files:
        if Path(name).suffix not in DATA_SUFFIXES:
            continue
        try:
            text = safe_file(root, name).read_text(encoding="utf-8-sig")
            if Path(name).suffix in (".jsonl", ".ndjson"):
                count = sum(1 for line in text.splitlines() if line.strip() and json.loads(line) is not None)
            else:
                records = csv.reader(io.StringIO(text), delimiter="\t" if name.endswith(".tsv") else ",")
                next(records, None)
                count = sum(1 for row in records if row)
            rows.append({"path": name, "records": count, "sha256": files[name]["sha256"],
                         "source_status": "UNVERIFIED", "source": None,
                         "boundary": "Physical parsed records only; CSV header excluded; not necessarily provenance-verified datasets"})
        except (ValueError, UnicodeError, csv.Error, EvidenceError) as exc:
            rows.append({"path": name, "records": None, "source_status": "UNVERIFIED", "reason": str(exc)[:200]})
    return {"artifacts": rows, "artifact_count": len(rows), "provenance_verified_dataset_count": None,
            "boundary": "No invented external sources. JSON config files are not counted as datasets."}


def integrations(root, files):
    rows = []
    for name in files:
        if not name.startswith("backend/app/integrations/") or not name.endswith(".py"):
            continue
        text = safe_file(root, name).read_text(errors="replace")
        try:
            tree = ast.parse(text)
            imports = sorted({node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module} |
                             {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names})
        except SyntaxError:
            imports = []
        rows.append({"path": name, "sha256": files[name]["sha256"], "imports": imports,
                     "working_use": "UNVERIFIED", "reason": "Static adapter code is not a live operation receipt"})
    return {"adapters": rows, "working_external_tool_count": None}


def progress(root):
    log = git(root, "log", "-100", "--format=%H%x09%aI%x09%s").decode(errors="replace")
    return [{"commit": parts[0], "at": parts[1], "subject": parts[2],
             "status": "COMMIT_OBSERVED", "boundary": "Commit subject is not completion evidence"}
            for line in log.splitlines() if len(parts := line.split("\t", 2)) == 3]


def execute_tests(root: Path, test_paths, timeout=120):
    """Execute explicitly selected test files. Never trust caller result numbers.

    pytest/JUnit is a local observation, not independent proof. No shell is used.
    Malformed reports, skips, zero tests, timeouts and changing trees fail closed.
    """
    if not isinstance(test_paths, list) or not test_paths or len(test_paths) > 100:
        raise EvidenceError("select 1..100 test files explicitly")
    if type(timeout) is not int or not 1 <= timeout <= 600:
        raise EvidenceError("test timeout must be 1..600 seconds")
    root = root.resolve()
    before = snapshot(root)
    for name in test_paths:
        p = safe_file(root, name)
        if not name.startswith("tests/") or not p.name.startswith("test_") or p.suffix != ".py":
            raise EvidenceError("execution requires explicit tests/test_*.py paths")
        if name not in before["files"]:
            raise EvidenceError("test must be tracked")
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="atlas-evidence-") as td:
        report = Path(td) / "junit.xml"
        out_path = Path(td) / "stdout"
        err_path = Path(td) / "stderr"
        command = [sys.executable, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider",
                   "--junitxml=" + str(report), *test_paths]
        env = {key: value for key, value in os.environ.items() if key in
               {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}}
        env["PYTHONPATH"] = str(root / "backend")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        begin = time.monotonic()
        timed_out = False
        with out_path.open("wb") as out, err_path.open("wb") as err:
            proc = subprocess.Popen(command, cwd=root, stdout=out, stderr=err, env=env,
                                    start_new_session=True)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                timed_out, code = True, None
        duration = time.monotonic() - begin
        with out_path.open("rb") as stream:
            stdout = stream.read(MAX_CAPTURE_BYTES)
        with err_path.open("rb") as stream:
            stderr = stream.read(MAX_CAPTURE_BYTES)
        counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
        cases, parse_error = [], None
        raw_report = b""
        if report.exists() and report.stat().st_size <= MAX_FILE_BYTES:
            raw_report = report.read_bytes()
            try:
                if b"<!DOCTYPE" in raw_report or b"<!ENTITY" in raw_report:
                    raise EvidenceError("XML declarations forbidden")
                xml = ET.fromstring(raw_report)
                suites = list(xml.iter("testsuite"))
                if not suites:
                    raise EvidenceError("missing JUnit suite")
                for suite in suites:
                    for field in counts:
                        n = int(suite.get(field, "0"))
                        if n < 0:
                            raise EvidenceError("negative JUnit count")
                        counts[field] += n
                for case in xml.iter("testcase"):
                    state = "failed" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
                    cases.append({"name": case.get("name"), "classname": case.get("classname"), "status": state, "seconds": case.get("time")})
                if counts["tests"] != len(cases):
                    raise EvidenceError("JUnit totals disagree with test cases")
            except (ET.ParseError, ValueError) as exc:
                parse_error = str(exc)
        else:
            parse_error = "missing or oversized JUnit report"
        after = snapshot(root)
        stable = before["tree_digest"] == after["tree_digest"] and before["head"] == after["head"] and before["errors"] == after["errors"] and before["status_digest"] == after["status_digest"]
        passed = (code == 0 and not timed_out and not parse_error and stable and not before["errors"]
                  and counts["tests"] > 0 and all(c["status"] == "passed" for c in cases)
                  and not any(counts[k] for k in ("failures", "errors", "skipped")))
        return {"started_at": started, "duration_seconds": duration, "command": command,
                "selected_tests": test_paths, "exit_code": code, "timed_out": timed_out,
                "status": "SCOPED_PASS" if passed else "UNVERIFIED", "counts": counts,
                "cases": cases, "parse_error": parse_error, "tree_stable": stable,
                "head": before["head"], "tree_digest": before["tree_digest"],
                "junit_sha256": digest(raw_report), "junit_xml": raw_report.decode(errors="replace"),
                "stdout": stdout.decode(errors="replace"), "stderr": stderr.decode(errors="replace"),
                "output_truncated": out_path.stat().st_size > MAX_CAPTURE_BYTES or err_path.stat().st_size > MAX_CAPTURE_BYTES,
                "boundary": "Local selected-test observation; not independent review, benchmark victory or whole-requirement verification"}


def build_report(root: Path, source_path: str, test_paths=None):
    root = root.resolve()
    snap = snapshot(root)
    source = source_inventory(root, source_path)
    summary = code_summary(root, snap["files"])
    execution = execute_tests(root, test_paths) if test_paths else None
    plans = []
    for module, files in sorted(summary["modules"].items()):
        findings = [x for x in summary["findings"] if x["path"].startswith("backend/app/modules/" + module + "/")]
        plans.append({"module": module, "status": "PROPOSED_NOT_EXECUTED", "source_files": [x["path"] for x in files],
                      "observed_findings": findings,
                      "next_checks": ["Define source-bound acceptance criteria for this module", "Execute module tests and live adapter checks under approved scope"] +
                                     (["Inspect pass-only functions or syntax errors before acceptance"] if findings else []),
                      "boundary": "Evidence-driven verification plan, not an autonomous improvement or completed feature claim"})
    blockers = [{"id": row["id"], "status": "UNVERIFIED", "reason": row["reason"], "source_sha256": row["sha256"]} for row in source["rows"]]
    blockers += [{"id": "dependency-scope", "status": "UNVERIFIED", "reason": "Linked docs and historic chat requirements not exhaustively expanded"},
                 {"id": "external-judge", "status": "UNVERIFIED", "reason": "No executed authenticated ChatGPT judgments or quantified before/after improvements"},
                 {"id": "benchmark-victories", "status": "UNVERIFIED", "reason": "No independently executed field-leading comparator coverage"}]
    report = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
              "repository": {key: snap[key] for key in ("head", "origin", "dirty", "tree_digest", "status_digest", "errors")},
              "source": source, "progress": progress(root), "datasets": datasets(root, snap["files"]),
              "integrations": integrations(root, snap["files"]), "code_and_tests": summary,
              "executed_tests": execution,
              "benchmark_table": [] if not execution else [{"kind": "selected_test_execution", "seconds": execution["duration_seconds"], "tests": execution["counts"]["tests"], "status": execution["status"], "boundary": "Not a field benchmark; no comparator or novelty claim"}],
              "chatgpt_judge": {"status": "UNVERIFIED", "reports": [], "quantified_improvements": []},
              "self_improvement_plans": plans,
              "compliance": [{"line_id": row["id"], "source_sha256": row["sha256"], "status": "UNVERIFIED", "reason": row["reason"]} for row in source["rows"]],
              "blockers": blockers,
              "candy_gate": {"release": False, "reasons": ["Semantic source-line fulfillment unverified", "Dependency scope incomplete", "External judgments and benchmark coverage unverified"], "unverified_lines": len(source["rows"]),
                             "boundary": "Computed from actual inventory; no supplied done/green flags accepted"}}
    report["report_sha256"] = canonical_digest(report)
    return report
