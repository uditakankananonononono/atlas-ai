"""Test-only pins for the P266 compliance registry (runtime unchanged).

Pins default bounds, explicit bounds, expected_lines count bound, exact duplicate message,
the 14-clause presence/offline split and the doc wording. Non-collection expected_lines inputs
are deliberately NOT pinned here."""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT = _ROOT / "backend/app/modules/instinct_doc/compliance_registry_p266.py"
_PATH = pathlib.Path(os.environ.get("P266_MODULE_PATH", _DEFAULT))
_DOC = _ROOT / "docs/INSTINCT_COMPLIANCE_REGISTRY_P266_CONTRACT.md"
_spec = importlib.util.spec_from_file_location("compliance_registry_p266_pins_under_test", _PATH)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

PRESENCE = ("C01", "C02", "C05", "C08", "C13")
OFFLINE = ("C03", "C04", "C06", "C07", "C09", "C10", "C11", "C12", "C14")


def it(line="L1", clause="C01", claim="in_progress", evidence=None):
    d = {"line_ref": line, "clause_id": clause, "claim": claim}
    if evidence is not None:
        d["evidence"] = evidence
    return d


def items_n(n):
    return [it(line="L%d" % i) for i in range(n)]


class DefaultBounds(unittest.TestCase):
    def test_default_max_items_1000_accepted_1001_refused(self):
        self.assertEqual(M.check_bindings(items_n(1000))["counts"]["items"], {"OPEN": 1000})
        with self.assertRaises(ValueError) as cm:
            M.check_bindings(items_n(1001))
        self.assertEqual(str(cm.exception), "more than 1000 items")

    def test_default_max_evidence_50_accepted_51_refused(self):
        ev = lambda n: [{"kind": "other", "ref": "r"}] * n
        self.assertEqual(len(M.check_bindings([it(evidence=ev(50))])["items"]), 1)
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(evidence=ev(51))])
        self.assertEqual(str(cm.exception), "more than 50 evidence entries")

    def test_default_max_text_500_accepted_501_refused_line_ref(self):
        self.assertEqual(M.check_bindings([it(line="a" * 500)])["items"][0]["line_ref"], "a" * 500)
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(line="a" * 501)])
        self.assertEqual(str(cm.exception), "line_ref longer than 500 characters")

    def test_default_max_text_500_accepted_501_refused_evidence_ref(self):
        ok = [{"kind": "other", "ref": "r" * 500}]
        self.assertEqual(len(M.check_bindings([it(evidence=ok)])["items"]), 1)
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(evidence=[{"kind": "other", "ref": "r" * 501}])])
        self.assertEqual(str(cm.exception), "evidence ref longer than 500 characters")

    def test_default_max_text_applies_to_expected_lines(self):
        self.assertEqual(M.check_bindings([], expected_lines=["e" * 500])["lines"][0]["verdict"], "UNBOUND")
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([], expected_lines=["e" * 501])
        self.assertEqual(str(cm.exception), "expected line longer than 500 characters")

    def test_defaults_are_the_signature_defaults(self):
        import inspect
        p = inspect.signature(M.check_bindings).parameters
        self.assertEqual((p["max_items"].default, p["max_evidence"].default, p["max_text"].default), (1000, 50, 500))
        self.assertTrue(all(p[k].kind is inspect.Parameter.KEYWORD_ONLY for k in ("expected_lines", "max_items", "max_evidence", "max_text")))
        with self.assertRaises(TypeError):
            M.check_bindings([], None)  # no positional options


class ExplicitBounds(unittest.TestCase):
    NAMES = ("max_items", "max_evidence", "max_text")

    def test_bound_of_one_is_accepted(self):
        for n in self.NAMES:
            self.assertEqual(M.check_bindings([], **{n: 1})["items"], [], n)

    def test_bad_bounds_refused_with_name(self):
        for n in self.NAMES:
            for bad in (0, -1, True, False, 1.0, "1", None):
                with self.assertRaises(ValueError, msg="%s=%r" % (n, bad)) as cm:
                    M.check_bindings([], **{n: bad})
                self.assertEqual(str(cm.exception), "%s must be a positive integer" % n)

    def test_bad_bound_refused_even_with_valid_items(self):
        for n in self.NAMES:
            with self.assertRaises(ValueError):
                M.check_bindings(items_n(1), **{n: 0})

    def test_max_items_one_boundary(self):
        self.assertEqual(len(M.check_bindings(items_n(1), max_items=1)["items"]), 1)
        with self.assertRaises(ValueError) as cm:
            M.check_bindings(items_n(2), max_items=1)
        self.assertEqual(str(cm.exception), "more than 1 items")

    def test_max_evidence_one_boundary(self):
        e = {"kind": "other", "ref": "r"}
        self.assertEqual(len(M.check_bindings([it(evidence=[e])], max_evidence=1)["items"]), 1)
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(evidence=[e, e])], max_evidence=1)
        self.assertEqual(str(cm.exception), "more than 1 evidence entries")

    def test_max_text_boundary_uses_clause_id_length_three(self):
        self.assertEqual(len(M.check_bindings([it(line="L", clause="C01")], max_text=3)["items"]), 1)
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(line="L", clause="C01")], max_text=2)
        self.assertEqual(str(cm.exception), "clause_id longer than 2 characters")
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(line="LLLL", clause="C01")], max_text=3)
        self.assertEqual(str(cm.exception), "line_ref longer than 3 characters")
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it(evidence=[{"kind": "other", "ref": "rrrr"}])], max_text=3)
        self.assertEqual(str(cm.exception), "evidence ref longer than 3 characters")


class ExpectedLinesCount(unittest.TestCase):
    def test_default_1000_expected_lines_accepted_1001_refused(self):
        r = M.check_bindings([], expected_lines=["L%d" % i for i in range(1000)])
        self.assertEqual(r["counts"]["lines"], {"UNBOUND": 1000})
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([], expected_lines=["L%d" % i for i in range(1001)])
        self.assertEqual(str(cm.exception), "more than 1000 expected lines")

    def test_explicit_max_items_bounds_expected_lines(self):
        for n in (1, 3):
            r = M.check_bindings([], expected_lines=["L%d" % i for i in range(n)], max_items=n)
            self.assertEqual(len(r["lines"]), n)
            with self.assertRaises(ValueError) as cm:
                M.check_bindings([], expected_lines=["L%d" % i for i in range(n + 1)], max_items=n)
            self.assertEqual(str(cm.exception), "more than %d expected lines" % n)

    def test_expected_lines_tuple_set_accepted_and_list_of_empty(self):
        self.assertEqual(M.check_bindings([], expected_lines=[])["lines"], [])
        self.assertEqual(len(M.check_bindings([], expected_lines=("a", "b"))["lines"]), 2)


class ExpectedLinesType(unittest.TestCase):
    MSG = "expected_lines must be a list of strings"

    def test_non_collections_and_str_bytes_refused_with_exact_message(self):
        cases = {"int": 5, "dict": {"a": 1}, "generator": (x for x in "ab"), "str": "abc", "bytes": b"x",
                 "iterator": iter(["a"]), "float": 1.5, "bool": True}
        for name, v in cases.items():
            with self.assertRaises(ValueError, msg=name) as cm:
                M.check_bindings([], expected_lines=v)
            self.assertEqual(str(cm.exception), self.MSG, name)

    def test_empty_str_and_empty_bytes_refused_too(self):
        for v in ("", b""):
            with self.assertRaises(ValueError) as cm:
                M.check_bindings([], expected_lines=v)
            self.assertEqual(str(cm.exception), self.MSG)

    def test_list_tuple_set_frozenset_accepted(self):
        for v in (["a", "b"], ("a", "b"), {"a", "b"}, frozenset({"a", "b"})):
            r = M.check_bindings([], expected_lines=v)
            self.assertEqual([x["line_ref"] for x in r["lines"]], ["a", "b"], type(v).__name__)

    def test_none_means_no_expectation(self):
        r = M.check_bindings([it("L1")], expected_lines=None)
        self.assertEqual(r["unexpected_lines"], [])

    def test_non_string_elements_refused(self):
        for bad in ([1], [None], [b"a"], [["a"]]):
            with self.assertRaises(ValueError):
                M.check_bindings([], expected_lines=bad)

    def test_duplicate_expected_line_refused_exact(self):
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([], expected_lines=["a", "b", "a"])
        self.assertEqual(str(cm.exception), "duplicate expected line")


class DuplicateMessage(unittest.TestCase):
    def test_exact_message_with_asymmetric_ids(self):
        items = [it("L1", "C01"), it("L9", "C02"), it("L1", "C01")]
        with self.assertRaises(ValueError) as cm:
            M.check_bindings(items)
        self.assertEqual(str(cm.exception), "duplicate binding for L1 / C01")

    def test_message_orders_line_then_clause(self):
        with self.assertRaises(ValueError) as cm:
            M.check_bindings([it("C01", "C02"), it("C01", "C02")])
        self.assertEqual(str(cm.exception), "duplicate binding for C01 / C02")

    def test_same_line_other_clause_and_same_clause_other_line_are_not_duplicates(self):
        r = M.check_bindings([it("L1", "C01"), it("L1", "C02"), it("L2", "C01")])
        self.assertEqual(len(r["items"]), 3)

    def test_swapped_pair_is_not_a_duplicate(self):
        # (line_ref, clause_id) is ordered: ("C01","C02") differs from ("C02","C01") ids-wise
        self.assertEqual(len(M.check_bindings([it("C01", "C02"), it("C02", "C01")])["items"]), 2)


class ClauseSplit(unittest.TestCase):
    def test_presence_five_and_offline_nine(self):
        pres = [c["id"] for c in M.CLAUSES if c["checkability"] == "presence"]
        off = [c["id"] for c in M.CLAUSES if c["checkability"] == "not_checkable_offline"]
        self.assertEqual(tuple(pres), PRESENCE)
        self.assertEqual(tuple(off), OFFLINE)
        self.assertEqual((len(pres), len(off), len(M.CLAUSES)), (5, 9, 14))

    def test_offline_clauses_never_bound_whatever_claim_and_evidence(self):
        ev = [{"kind": k, "ref": "r"} for k in M.EVIDENCE_KINDS]
        for c in OFFLINE:
            for claim in M.CLAIMS:
                for e in (None, ev):
                    r = M.check_bindings([it("L", c, claim, e)])
                    self.assertEqual(r["items"][0]["verdict"], "NOT_CHECKABLE_OFFLINE", (c, claim))
                    self.assertEqual(r["lines"][0]["verdict"], "UNCHECKED_ONLY")

    def test_no_compliant_or_passed_anywhere_in_output(self):
        ev = [{"kind": k, "ref": "r"} for k in M.EVIDENCE_KINDS]
        items = [it("L", c.get("id"), "complete", ev) for c in M.CLAUSES]
        out = repr(M.check_bindings(items, expected_lines=["L", "X"]))
        for w in ("COMPLIANT", "PASSED", "compliant", "passed"):
            self.assertNotIn(w, out)

    def test_candy_clause_opaque_text_only(self):
        c14 = [c for c in M.CLAUSES if c["id"] == "C14"][0]
        self.assertEqual((c14["text"], c14["checkability"], tuple(c14["required_evidence_kinds"])), ("Then send the candy line", "not_checkable_offline", ()))


class OrderIndependentOfHashSeed(unittest.TestCase):
    """Output ordering must not depend on PYTHONHASHSEED. Subprocess with seeds 1..3 (hash-seed dependence disclosed)."""
    CODE = (
        "import importlib.util,json,sys\n"
        "s=importlib.util.spec_from_file_location('m',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
        "ev=[{'kind':k,'ref':'r'} for k in ('other','audit_ref','test_log_ref','binding_ref','inventory_ref')]\n"
        "items=[{'line_ref':l,'clause_id':'C08','claim':'complete','evidence':ev} for l in ('Lz','La','Lm','Lb','Lq')]\n"
        "r=m.check_bindings(items,expected_lines=['Lz','Lx','Lw','Lv'])\n"
        "print(json.dumps(r,sort_keys=False))\n"
    )

    def run_seed(self, seed):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        return subprocess.run([sys.executable, "-c", self.CODE, str(_PATH)], capture_output=True, text=True, env=env, check=True).stdout

    def test_same_output_for_seeds_1_2_3_and_sorted(self):
        outs = {s: self.run_seed(s) for s in (1, 2, 3)}
        self.assertEqual(len(set(outs.values())), 1)
        import json
        r = json.loads(outs[1])
        self.assertEqual(r["items"][0]["evidence_kinds_present"], ["audit_ref", "binding_ref", "inventory_ref", "other", "test_log_ref"])
        self.assertEqual(r["unexpected_lines"], ["La", "Lb", "Lm", "Lq"])
        self.assertEqual([x["line_ref"] for x in r["lines"]], ["La", "Lb", "Lm", "Lq", "Lv", "Lw", "Lx", "Lz"])


class DocWording(unittest.TestCase):
    def setUp(self):
        self.doc = _DOC.read_text(encoding="utf-8")

    def test_nine_clauses_wording(self):
        self.assertIn("Nine clauses", self.doc)
        self.assertNotIn("Seven-plus", self.doc)
        self.assertNotIn("Seven plus", self.doc)


if __name__ == "__main__":
    unittest.main()
