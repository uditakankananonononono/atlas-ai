"""Tests for compliance_registry_p266 (P266/L212). Stdlib unittest, no installs.

Module path can be overridden with P266_MODULE_PATH (stub RED run, mutant runs).
"""
from __future__ import annotations

import copy
import importlib.util
import itertools
import os
import pathlib
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT = _ROOT / "backend/app/modules/instinct_doc/compliance_registry_p266.py"
_PATH = pathlib.Path(os.environ.get("P266_MODULE_PATH", _DEFAULT))
_spec = importlib.util.spec_from_file_location("compliance_registry_p266_under_test", _PATH)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

PRESENCE = {"C01": "binding_ref", "C02": "inventory_ref", "C05": "other", "C08": "test_log_ref", "C13": "audit_ref"}
UNCHECKED = ["C03", "C04", "C06", "C07", "C09", "C10", "C11", "C12", "C14"]


def item(line="L1", clause="C08", claim="complete", evidence=None):
    if evidence is None:
        evidence = [{"kind": PRESENCE.get(clause, "other"), "ref": "r1"}]
    return {"line_ref": line, "clause_id": clause, "claim": claim, "evidence": evidence}


def verdict(**kw):
    return M.check_bindings([item(**kw)])["items"][0]["verdict"]


class Registry(unittest.TestCase):
    def test_fourteen_clauses_in_order(self):
        self.assertEqual([c["id"] for c in M.CLAUSES], ["C%02d" % i for i in range(1, 15)])

    def test_texts_come_from_the_line(self):
        texts = {c["id"]: c["text"] for c in M.CLAUSES}
        self.assertEqual(texts["C01"], "Bind every line")
        self.assertEqual(texts["C05"], "Do not claim completion without evidence")
        self.assertEqual(texts["C11"], "Improve novelty through ChatGPT as judge")
        self.assertEqual(texts["C14"], "Then send the candy line")

    def test_checkability_and_kinds(self):
        for c in M.CLAUSES:
            if c["id"] in PRESENCE:
                self.assertEqual(c["checkability"], "presence", c["id"])
                self.assertEqual(tuple(c["required_evidence_kinds"]), (PRESENCE[c["id"]],), c["id"])
            else:
                self.assertEqual(c["checkability"], "not_checkable_offline", c["id"])
                self.assertEqual(tuple(c["required_evidence_kinds"]), (), c["id"])

    def test_registry_is_immutable(self):
        self.assertIsInstance(M.CLAUSES, tuple)
        with self.assertRaises(TypeError):
            M.CLAUSES[0]["text"] = "x"
        with self.assertRaises(Exception):
            M.CLAUSES[0]["required_evidence_kinds"].append("x")

    def test_evidence_kinds_fixed(self):
        self.assertEqual(set(M.EVIDENCE_KINDS), {"binding_ref", "inventory_ref", "test_log_ref", "audit_ref", "other"})


class ItemVerdicts(unittest.TestCase):
    def test_complete_with_required_kind_is_bound(self):
        for c in PRESENCE:
            self.assertEqual(verdict(clause=c), "BOUND", c)

    def test_complete_without_evidence_is_missing(self):
        for c in PRESENCE:
            self.assertEqual(verdict(clause=c, evidence=[]), "MISSING_EVIDENCE", c)

    def test_wrong_kind_is_missing(self):
        self.assertEqual(verdict(clause="C08", evidence=[{"kind": "audit_ref", "ref": "x"}]), "MISSING_EVIDENCE")

    def test_blank_ref_does_not_count(self):
        for ref in ("", "   ", "\t\n"):
            self.assertEqual(verdict(clause="C08", evidence=[{"kind": "test_log_ref", "ref": ref}]), "MISSING_EVIDENCE", repr(ref))

    def test_extra_irrelevant_evidence_ok_and_needs_only_one_good(self):
        ev = [{"kind": "other", "ref": "z"}, {"kind": "test_log_ref", "ref": "a"}, {"kind": "test_log_ref", "ref": " "}]
        self.assertEqual(verdict(clause="C08", evidence=ev), "BOUND")

    def test_open_claims_need_no_evidence(self):
        for claim in ("in_progress", "not_started"):
            self.assertEqual(verdict(clause="C08", claim=claim, evidence=[]), "OPEN", claim)
            self.assertEqual(verdict(clause="C08", claim=claim), "OPEN", claim)

    def test_not_checkable_never_bound(self):
        for c in UNCHECKED:
            for claim in ("complete", "in_progress", "not_started"):
                self.assertEqual(verdict(clause=c, claim=claim), "NOT_CHECKABLE_OFFLINE", (c, claim))
                self.assertEqual(verdict(clause=c, claim=claim, evidence=[]), "NOT_CHECKABLE_OFFLINE", (c, claim))

    def test_evidence_omitted_key(self):
        it = {"line_ref": "L", "clause_id": "C08", "claim": "complete"}
        self.assertEqual(M.check_bindings([it])["items"][0]["verdict"], "MISSING_EVIDENCE")


class LineVerdicts(unittest.TestCase):
    def line(self, items, expected=None):
        r = M.check_bindings(items, expected_lines=expected)
        return {x["line_ref"]: x["verdict"] for x in r["lines"]}

    def test_unbound_expected_line(self):
        r = M.check_bindings([item("A")], expected_lines=["A", "B"])
        self.assertEqual({x["line_ref"]: x["verdict"] for x in r["lines"]}, {"A": "BOUND", "B": "UNBOUND"})

    def test_empty_items_with_expected(self):
        r = M.check_bindings([], expected_lines=["A"])
        self.assertEqual(r["lines"], [{"line_ref": "A", "verdict": "UNBOUND", "clause_ids": []}])
        self.assertEqual(M.check_bindings([])["lines"], [])

    def test_unexpected_lines_listed(self):
        r = M.check_bindings([item("A"), item("Z")], expected_lines=["A"])
        self.assertEqual(r["unexpected_lines"], ["Z"])
        self.assertEqual(M.check_bindings([item("A")])["unexpected_lines"], [])

    def test_precedence(self):
        miss = item("L", "C08", evidence=[])
        opn = item("L", "C13", "in_progress")
        ok = item("L", "C01")
        unc = item("L", "C04")
        self.assertEqual(self.line([miss, opn, ok, unc])["L"], "MISSING_EVIDENCE")
        self.assertEqual(self.line([opn, ok, unc])["L"], "OPEN")
        self.assertEqual(self.line([ok, unc])["L"], "BOUND_WITH_UNCHECKED")
        self.assertEqual(self.line([unc])["L"], "UNCHECKED_ONLY")
        self.assertEqual(self.line([ok])["L"], "BOUND")

    def test_clause_ids_sorted(self):
        r = M.check_bindings([item("L", "C13"), item("L", "C01")])
        self.assertEqual(r["lines"][0]["clause_ids"], ["C01", "C13"])

    def test_counts(self):
        r = M.check_bindings([item("A"), item("B", "C08", evidence=[]), item("C", "C04"), item("D", "C13", "in_progress")], expected_lines=["A", "B", "C", "D", "E"])
        self.assertEqual(r["counts"]["items"], {"BOUND": 1, "MISSING_EVIDENCE": 1, "NOT_CHECKABLE_OFFLINE": 1, "OPEN": 1})
        self.assertEqual(r["counts"]["lines"]["UNBOUND"], 1)
        self.assertEqual(sum(r["counts"]["lines"].values()), 5)


class Refusals(unittest.TestCase):
    def bad(self, items, **kw):
        with self.assertRaises(ValueError):
            M.check_bindings(items, **kw)

    def test_shape(self):
        self.bad("x")
        self.bad(None)
        self.bad({"a": 1})
        self.bad(["x"])
        self.bad([item(line="")])
        self.bad([item(line="  ")])
        self.bad([item(line=3)])
        self.bad([item(clause="C99")])
        self.bad([item(clause="c08")])
        self.bad([item(clause=None)])
        self.bad([item(claim="done")])
        self.bad([item(claim=True)])

    def test_missing_keys(self):
        for k in ("line_ref", "clause_id", "claim"):
            it = item()
            del it[k]
            self.bad([it])

    def test_evidence_shape(self):
        self.bad([item(evidence="x")])
        self.bad([item(evidence=["x"])])
        self.bad([item(evidence=({"kind": "test_log_ref", "ref": "r"},))])
        self.bad([item(evidence=[{"kind": "audit_ref"}])])
        self.bad([item(evidence=[{"kind": "audit_ref", "ref": 5}])])
        self.bad([item(evidence=[{"kind": "mystery", "ref": "r"}])])
        self.bad([item(evidence=[{"kind": 1, "ref": "r"}])])

    def test_duplicates(self):
        self.bad([item("A", "C08"), item("A", "C08")])
        M.check_bindings([item("A", "C08"), item("B", "C08"), item("A", "C13")])
        self.bad([item()], expected_lines=["A", "A"])
        self.bad([item()], expected_lines=[1])
        self.bad([item()], expected_lines="AB")
        self.bad([item()], expected_lines=[""])

    def test_item_count_n_and_n_plus_1(self):
        items = [item("L%d" % i) for i in range(5)]
        self.assertEqual(M.check_bindings(items, max_items=5)["counts"]["items"], {"BOUND": 5})
        self.bad(items, max_items=4)

    def test_evidence_count_n_and_n_plus_1(self):
        ev = [{"kind": "other", "ref": str(i)} for i in range(3)]
        M.check_bindings([item(clause="C05", evidence=ev)], max_evidence=3)
        self.bad([item(clause="C05", evidence=ev)], max_evidence=2)

    def test_text_length_n_and_n_plus_1(self):
        M.check_bindings([item(line="a" * 10)], max_text=10)
        self.bad([item(line="a" * 11)], max_text=10)
        M.check_bindings([item(evidence=[{"kind": "test_log_ref", "ref": "r" * 10}])], max_text=10)
        self.bad([item(evidence=[{"kind": "test_log_ref", "ref": "r" * 11}])], max_text=10)
        self.bad([item()], expected_lines=["x" * 11], max_text=10)

    def test_bad_bounds(self):
        for k in ("max_items", "max_evidence", "max_text"):
            for v in (0, -1, True, 1.5, None, "5"):
                self.bad([item()], **{k: v})

    def test_refusal_evaluates_nothing(self):
        items = [item("A"), item("A")]
        with self.assertRaises(ValueError):
            M.check_bindings(items)


class Properties(unittest.TestCase):
    def test_input_not_mutated(self):
        items = [item("B", "C13"), item("A", "C01"), item("A", "C04")]
        before = copy.deepcopy(items)
        M.check_bindings(items, expected_lines=["Q", "A"])
        self.assertEqual(items, before)

    def test_order_independent_and_sorted(self):
        items = [item("B", "C13"), item("A", "C01"), item("A", "C04"), item("C", "C08", evidence=[])]
        base = M.check_bindings(items, expected_lines=["C", "A", "B", "D"])
        for perm in itertools.permutations(items):
            self.assertEqual(base, M.check_bindings(list(perm), expected_lines=["D", "B", "A", "C"]))
        keys = [(x["line_ref"], x["clause_id"]) for x in base["items"]]
        self.assertEqual(keys, sorted(keys))
        lines = [x["line_ref"] for x in base["lines"]]
        self.assertEqual(lines, sorted(lines))

    def test_exhaustive_small_domain(self):
        clauses = ["C01", "C04", "C08"]
        claims = ["complete", "in_progress"]
        evs = [[], [{"kind": "binding_ref", "ref": "r"}], [{"kind": "test_log_ref", "ref": "r"}]]
        allowed = {"BOUND", "MISSING_EVIDENCE", "OPEN", "NOT_CHECKABLE_OFFLINE"}
        for c, cl, ev in itertools.product(clauses, claims, evs):
            v = M.check_bindings([item("L", c, cl, ev)])["items"][0]["verdict"]
            self.assertIn(v, allowed)
            if c == "C04":
                self.assertEqual(v, "NOT_CHECKABLE_OFFLINE")
            elif cl == "in_progress":
                self.assertEqual(v, "OPEN")
            else:
                need = {"C01": "binding_ref", "C08": "test_log_ref"}[c]
                self.assertEqual(v, "BOUND" if any(e["kind"] == need for e in ev) else "MISSING_EVIDENCE")

    def test_limits_honest_and_no_pass_flag(self):
        r = M.check_bindings([item()])
        for k in ("evidence_truth_verified", "whole_line_fulfilment_claimed", "global_enforcement", "network", "account_use", "executes_anything"):
            self.assertIs(r["limits"][k], False, k)
        flat = repr(r).lower()
        for word in ("compliant", "passed", "approved", "complete_ok"):
            self.assertNotIn(word, flat)
        self.assertEqual(r["registry_version"], M.REGISTRY_VERSION)

    def test_evidence_kinds_present_sorted(self):
        ev = [{"kind": k, "ref": "r"} for k in ("other", "audit_ref", "test_log_ref", "binding_ref", "inventory_ref")]
        x = M.check_bindings([item("L", "C08", evidence=ev)])["items"][0]
        self.assertEqual(x["evidence_kinds_present"], ["audit_ref", "binding_ref", "inventory_ref", "other", "test_log_ref"])

    def test_item_result_fields(self):
        x = M.check_bindings([item("L", "C08")])["items"][0]
        self.assertEqual(sorted(x), ["checkability", "claim", "clause_id", "evidence_kinds_present", "line_ref", "missing_evidence_kinds", "verdict"])
        self.assertEqual(x["evidence_kinds_present"], ["test_log_ref"])
        self.assertEqual(x["missing_evidence_kinds"], [])
        y = M.check_bindings([item("L", "C08", evidence=[])])["items"][0]
        self.assertEqual(y["missing_evidence_kinds"], ["test_log_ref"])


if __name__ == "__main__":
    unittest.main()
