"""Unit 10 [P65|L55]: claim-status check for reports.

Every claim in a report must carry an explicit status label (default VERIFIED
or UNVERIFIED); the check fails when a claim is unmarked or carries conflicting
labels. Claims are (a) body rows of a markdown table with a Label/Status
column and (b) lines beginning "CLAIM:" carrying a bracketed [LABEL] marker.

The module under test is stdlib-only; it is loaded by file path so the suite
runs in an isolated stdlib+pytest environment. In the integrated repo the same
file is importable as app.reports.claim_status (no package-relative imports).
CLAIM_STATUS_MODULE_PATH overrides the path so mutation runs can point this
suite at a mutated copy.
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(
    os.environ.get(
        "CLAIM_STATUS_MODULE_PATH",
        Path(__file__).resolve().parents[2] / "backend" / "app" / "reports" / "claim_status.py",
    )
)


def _load():
    spec = importlib.util.spec_from_file_location("claim_status_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolves cls.__module__ via sys.modules
    spec.loader.exec_module(module)
    return module


cs = _load()

LEDGER = """# Weekly report

Some prose that is not a claim.

| Claim | Label | Evidence |
|---|---|---|
| Core runs stdlib-only | VERIFIED | tests/test_x.py |
| Hosted route works | UNVERIFIED | not run |
"""

LEDGER_BAD = """# Weekly report

| Claim | Label | Evidence |
|---|---|---|
| Core runs stdlib-only | VERIFIED | tests/test_x.py |
| Hosted route works |  | not run |
| Cache is warm | SCOPED | only locally |
"""


class ExtractTableTests(unittest.TestCase):
    def test_table_claims_extracted_with_lines(self):
        claims = cs.extract_claims(LEDGER)
        self.assertEqual(len(claims), 2)
        self.assertEqual([c.status for c in claims], ["VERIFIED", "UNVERIFIED"])
        self.assertEqual([c.line for c in claims], [7, 8])
        self.assertTrue(all(c.source == "table" for c in claims))
        self.assertEqual(claims[0].text, "Core runs stdlib-only")

    def test_header_and_separator_are_not_claims(self):
        result = cs.check_text(LEDGER)
        self.assertEqual(result["claims_total"], 2)
        self.assertEqual(result["marked"], 2)
        self.assertTrue(result["ok"])

    def test_empty_label_cell_is_unmarked_with_exact_line(self):
        result = cs.check_text(LEDGER_BAD)
        self.assertFalse(result["ok"])
        self.assertEqual(result["unmarked"][0]["line"], 6)
        self.assertIn("empty", result["unmarked"][0]["reason"])

    def test_unknown_label_token_is_unmarked(self):
        result = cs.check_text(LEDGER_BAD)
        reasons = [u["reason"] for u in result["unmarked"]]
        self.assertTrue(any("SCOPED" in r for r in reasons), reasons)

    def test_status_column_name_and_case_normalization(self):
        text = "| Claim | Status | Note |\n|---|---|---|\n| It works | verified | x |\n"
        result = cs.check_text(text)
        self.assertTrue(result["ok"])
        self.assertEqual(result["claims"][0]["status"], "VERIFIED")

    def test_table_without_label_column_is_ignored(self):
        text = "| Name | Value |\n|---|---|\n| a | 1 |\n"
        self.assertEqual(cs.extract_claims(text), [])

    def test_fenced_code_blocks_are_ignored(self):
        text = "```\n| Claim | Label |\n|---|---|\n| fake | VERIFIED |\n```\n~~~\n- CLAIM: fake [VERIFIED]\n~~~\n"
        self.assertEqual(cs.extract_claims(text), [])


class MarkerTests(unittest.TestCase):
    def test_marker_claim_marked(self):
        result = cs.check_text("- CLAIM: cache is cold [VERIFIED]\n")
        self.assertTrue(result["ok"])
        self.assertEqual(result["claims"][0]["source"], "marker")
        self.assertEqual(result["claims"][0]["status"], "VERIFIED")

    def test_marker_claim_without_label_is_unmarked(self):
        result = cs.check_text("- CLAIM: cache is cold\n")
        self.assertFalse(result["ok"])
        self.assertEqual(result["unmarked"][0]["line"], 1)

    def test_plain_bullets_are_not_claims(self):
        self.assertEqual(cs.extract_claims("- just a bullet\n- another\n"), [])

    def test_marker_prefix_and_label_case_insensitive(self):
        result = cs.check_text("- claim: it works [verified]\n")
        self.assertTrue(result["ok"])
        self.assertEqual(result["claims"][0]["status"], "VERIFIED")

    def test_pipe_run_without_separator_is_not_a_table(self):
        text = "| Claim | Label |\n| a | VERIFIED |\n| b | VERIFIED |\n"
        self.assertEqual(cs.extract_claims(text), [])

    def test_conflicting_labels_fail(self):
        result = cs.check_text("- CLAIM: it works [VERIFIED] but also [UNVERIFIED]\n")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["conflicting"]), 1)
        self.assertEqual(result["conflicting"][0]["line"], 1)

    def test_custom_labels_multiword(self):
        labels = {"VERIFIED", "NOT BUILT"}
        text = "| Claim | Label |\n|---|---|\n| Ornith RL | NOT BUILT |\n| Docs | UNVERIFIED |\n"
        result = cs.check_text(text, labels=labels)
        self.assertFalse(result["ok"])  # UNVERIFIED is not in the custom set
        self.assertEqual(result["claims"][0]["status"], "NOT BUILT")
        self.assertEqual(result["unmarked"][0]["line"], 4)


class FileAndCliTests(unittest.TestCase):
    def _write(self, directory, name, content):
        path = Path(directory) / name
        path.write_text(content)
        return path

    def test_check_file_and_paths_aggregation(self):
        with tempfile.TemporaryDirectory() as d:
            good = self._write(d, "good.md", LEDGER)
            bad = self._write(d, "bad.md", LEDGER_BAD)
            empty = self._write(d, "empty.md", "# no claims here\n")
            self.assertTrue(cs.check_file(good)["ok"])
            self.assertFalse(cs.check_file(bad)["ok"])
            out = cs.check_paths([good, bad, empty])
            self.assertFalse(out["ok"])
            self.assertEqual(out["files_total"], 3)
            self.assertEqual(out["claims_total"], 5)
            self.assertEqual(out["files_with_zero_claims"], [str(empty)])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            good = self._write(d, "good.md", LEDGER)
            bad = self._write(d, "bad.md", LEDGER_BAD)
            empty = self._write(d, "empty.md", "# no claims\n")
            self.assertEqual(cs.main([str(good)]), 0)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cs.main([str(bad)])
            self.assertEqual(rc, 1)
            self.assertIn("bad.md:6", buf.getvalue())
            self.assertEqual(cs.main([str(empty)]), 2)
            self.assertEqual(cs.main([str(Path(d) / "missing.md")]), 2)

    def test_cli_labels_flag_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, "r.md", "| Claim | Label |\n|---|---|\n| a | verified |\n")
            self.assertEqual(cs.main(["--labels", "verified,unverified", str(path)]), 0)


class ModuleShapeTests(unittest.TestCase):
    def test_module_imports_stdlib_only(self):
        tree = ast.parse(MODULE_PATH.read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        roots.discard("__future__")
        self.assertLessEqual(roots, sys.stdlib_module_names)


if __name__ == "__main__":
    unittest.main()
