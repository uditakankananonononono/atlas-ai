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
import dataclasses
import importlib.util
import io
import os
import subprocess
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

CONFLICT_ONLY = "- CLAIM: cache flush works [VERIFIED] but also [UNVERIFIED]\n"


class FencePairingTests(unittest.TestCase):
    """CommonMark fence pairing: same delimiter char, run at least as long
    as the opener; info string allowed on the opener only."""

    def test_mismatched_fence_char_does_not_close(self):
        text = "````python\n~~~\nCLAIM: hidden [VERIFIED]\n````\nCLAIM: outside [UNVERIFIED]"
        self.assertEqual([c.text for c in cs.extract_claims(text)], ["outside [UNVERIFIED]"])

    def test_shorter_fence_run_does_not_close(self):
        text = "````\n```\nCLAIM: hidden [VERIFIED]\n````\nCLAIM: outside [UNVERIFIED]"
        self.assertEqual([c.text for c in cs.extract_claims(text)], ["outside [UNVERIFIED]"])

    def test_opener_info_string_allowed(self):
        text = "```python\nCLAIM: hidden [VERIFIED]\n```\nCLAIM: seen [VERIFIED]"
        self.assertEqual([c.text for c in cs.extract_claims(text)], ["seen [VERIFIED]"])

    def test_longer_closer_closes(self):
        text = "```\nCLAIM: hidden [VERIFIED]\n`````\nCLAIM: seen [UNVERIFIED]"
        self.assertEqual([c.text for c in cs.extract_claims(text)], ["seen [UNVERIFIED]"])

    def test_tilde_fence_hides_backtick_runs(self):
        text = "~~~\n```\nCLAIM: hidden [VERIFIED]\n~~~\nCLAIM: seen [VERIFIED]"
        self.assertEqual([c.text for c in cs.extract_claims(text)], ["seen [VERIFIED]"])

    def test_pathological_fence_table_mix_terminates(self):
        # unclosed/mismatched fences and a truncated table run at EOF: the
        # single-pass scan must terminate and grade the visible claims
        text = (
            "````\n| Claim | Label |\n|---|---|\n| trapped | VERIFIED |\n"
            "~~~\n```\nCLAIM: trapped too [VERIFIED]\n"
            "````\nCLAIM: free [UNVERIFIED]\n| Claim | Label |\n"
        )
        claims = cs.extract_claims(text)
        self.assertEqual([c.text for c in claims], ["free [UNVERIFIED]"])
        result = cs.check_text(text)
        self.assertFalse(result["ok"])  # trailing truncated label table
        self.assertEqual(result["structural_ambiguous"][0]["line"], 10)


class StructuralHeaderTests(unittest.TestCase):
    def test_two_label_columns_fail_with_typed_finding(self):
        result = cs.check_text("| Claim | Label | Status |\n|---|---|---|\n| x | VERIFIED | UNVERIFIED |")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["structural_ambiguous"]), 1)
        self.assertIn("2 label columns", result["structural_ambiguous"][0]["reason"])
        self.assertEqual(result["structural_ambiguous"][0]["line"], 3)

    def test_short_label_table_run_one_line_fails_closed(self):
        result = cs.check_text("| Claim | Label |")
        self.assertFalse(result["ok"])
        self.assertEqual(result["structural_ambiguous"][0]["line"], 1)
        self.assertIn("truncated claim table", result["structural_ambiguous"][0]["reason"])

    def test_short_label_table_run_two_lines_fails_closed(self):
        result = cs.check_text("| Claim | Label |\n|---|---|")
        self.assertFalse(result["ok"])
        self.assertIn("truncated claim table", result["structural_ambiguous"][0]["reason"])

    def test_short_pipe_run_without_label_column_ignored(self):
        result = cs.check_text("| Name | Value |\n| a | 1 |")
        self.assertEqual(result["structural_ambiguous"], [])
        self.assertTrue(result["vacuous"])  # zero claims: still not ok
        self.assertFalse(result["ok"])

    def test_short_row_missing_label_cell_is_typed_unmarked(self):
        result = cs.check_text("| Claim | Label | Note |\n|---|---|---|\n| x |\n")
        self.assertFalse(result["ok"])
        self.assertEqual(result["unmarked"][0]["reason"], "missing label cell in row")


class MarkerAmbiguityTests(unittest.TestCase):
    def test_unknown_token_alongside_recognized_is_structural_ambiguous(self):
        result = cs.check_text("CLAIM: x [UNKNOWN] [VERIFIED]")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["structural_ambiguous"]), 1)
        self.assertIn("UNKNOWN", result["structural_ambiguous"][0]["reason"])

    def test_unknown_only_marker_is_unmarked_with_required_wording(self):
        result = cs.check_text("CLAIM: x [UNKNOWN]")
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["unmarked"]), 1)
        self.assertIn("no recognized token present", result["unmarked"][0]["reason"])

    def test_recognized_only_marker_still_marked(self):
        result = cs.check_text("CLAIM: x [VERIFIED]")
        self.assertTrue(result["ok"])
        self.assertEqual(result["structural_ambiguous"], [])


class VacuityTests(unittest.TestCase):
    def test_empty_document_is_vacuous_not_ok(self):
        result = cs.check_text("")
        self.assertFalse(result["ok"])
        self.assertTrue(result["vacuous"])

    def test_prose_only_document_is_vacuous_not_ok(self):
        result = cs.check_text("# report\n\njust prose\n")
        self.assertFalse(result["ok"])
        self.assertTrue(result["vacuous"])

    def test_document_with_claims_is_not_vacuous(self):
        result = cs.check_text(LEDGER)
        self.assertFalse(result["vacuous"])
        self.assertTrue(result["ok"])

    def test_zero_claim_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "empty.md"
            path.write_text("# no claims\n")
            result = cs.check_file(path)
            self.assertFalse(result["ok"])
            self.assertTrue(result["vacuous"])


class GuardPinTests(unittest.TestCase):
    def test_empty_labels_refused(self):
        with self.assertRaisesRegex(ValueError, "at least one accepted label"):
            cs.check_text(LEDGER, labels=[])

    def test_claim_is_frozen(self):
        claim = cs.extract_claims(LEDGER)[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            claim.status = "UNVERIFIED"

    def test_conflicting_only_cli_run_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "conflict.md"
            path.write_text(CONFLICT_ONLY)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cs.main([str(path)])
            self.assertEqual(rc, 1)
            self.assertIn("CONFLICTING", buf.getvalue())

    def test_mixed_run_with_vacuous_file_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.md"
            good.write_text(LEDGER)
            empty = Path(d) / "empty.md"
            empty.write_text("# nothing\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cs.main([str(good), str(empty)])
            self.assertEqual(rc, 1)
            self.assertIn("VACUOUS", buf.getvalue())


class SubprocessCliTests(unittest.TestCase):
    """Runs `python -m app.reports.claim_status` in a real subprocess against
    a staged copy of MODULE_PATH, so mutation runs exercise the mutated file
    and the __main__ guard is pinned by execution, not by import."""

    def _stage(self, root):
        pkg = Path(root) / "app" / "reports"
        pkg.mkdir(parents=True)
        (Path(root) / "app" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "claim_status.py").write_text(MODULE_PATH.read_text())

    def _run(self, root, *args):
        env = dict(os.environ, PYTHONPATH=str(root))
        return subprocess.run(
            [sys.executable, "-m", "app.reports.claim_status", *args],
            cwd=root, env=env, capture_output=True, text=True, timeout=30,
        )

    def test_module_cli_exit_codes_and_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            self._stage(d)
            good = Path(d) / "good.md"
            good.write_text(LEDGER)
            bad = Path(d) / "bad.md"
            bad.write_text(LEDGER_BAD)
            conflict = Path(d) / "conflict.md"
            conflict.write_text(CONFLICT_ONLY)
            empty = Path(d) / "empty.md"
            empty.write_text("# no claims\n")
            ok_run = self._run(d, str(good))
            self.assertEqual(ok_run.returncode, 0, ok_run.stderr)
            self.assertIn("all marked", ok_run.stdout)
            bad_run = self._run(d, str(bad))
            self.assertEqual(bad_run.returncode, 1)
            self.assertIn("UNMARKED", bad_run.stdout)
            conflict_run = self._run(d, str(conflict))
            self.assertEqual(conflict_run.returncode, 1)
            self.assertIn("CONFLICTING", conflict_run.stdout)
            empty_run = self._run(d, str(empty))
            self.assertEqual(empty_run.returncode, 2)


if __name__ == "__main__":
    unittest.main()
