"""Guard: every repo-relative path field in audits/coverage-register.json resolves.

The register is the coverage source of truth; docs/IMPLEMENTATION_AUDIT.md is
generated from it. A path that does not resolve is a stale pointer left behind
by a module move or rename. Field conventions:

- implementation_path / test_path: one path, or several joined by '; '.
- test_case: either a bare test function label (no path component) or
  '<path>::<test name>'; only the path prefix is checked.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "audits" / "coverage-register.json"


def _register_paths(row):
    for key in ("implementation_path", "test_path"):
        value = row.get(key)
        if value:
            for part in value.split(";"):
                part = part.strip()
                if part:
                    yield key, part
    test_case = row.get("test_case")
    if test_case and "::" in test_case:
        yield "test_case", test_case.split("::", 1)[0].strip()


def test_every_register_path_resolves():
    rows = json.loads(REGISTER.read_text())["rows"]
    stale = [
        (row["row"], key, path)
        for row in rows
        for key, path in _register_paths(row)
        if not (ROOT / path).is_file()
    ]
    assert stale == []


def test_register_path_fields_are_repo_relative():
    rows = json.loads(REGISTER.read_text())["rows"]
    for row in rows:
        for key, path in _register_paths(row):
            assert not path.startswith("/"), (row["row"], key, path)
            assert ".." not in Path(path).parts, (row["row"], key, path)
