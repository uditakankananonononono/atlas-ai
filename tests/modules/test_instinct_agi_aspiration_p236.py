"""P236|L185 aspiration register: red-first tests."""
from __future__ import annotations

import copy
import unittest


def attempt(aid="a1", status="measured", ref="ev-1", metric="exact-test pass rate"):
    a = {"id": aid, "target_capability": "exact arithmetic",
         "approach": "add Fraction-oracle concepts", "status": status}
    if ref is not None:
        a["evidence_ref"] = ref
    if metric is not None:
        a["metric_note"] = metric
    return a


class AspirationTest(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import agi_aspiration_register_p236 as m
        self.m = m

    def test_happy_path_recompute(self):
        r = self.m.run([attempt(), attempt("a2", "tested", "ev-2", None),
                        attempt("a3", "proposed", None, None)])
        res = r["result"]
        self.assertEqual(r["status"], "registered")
        self.assertTrue(r["verification"]["verified"])
        self.assertEqual(res["state_counts"],
                         {"measured": 1, "tested": 1, "proposed": 1})
        self.assertEqual(res["verdict"], "ATTEMPTS_RECONCILED")
        self.assertEqual(res["doc_claims"],
                         [{"claim": "AGI-like capability achieved", "asserted": False},
                          {"claim": "try to make it into AGI-like capability",
                           "asserted": False,
                           "note": "aspiration recorded; attempts audited only"}])

    def test_measured_without_metric_flagged(self):
        r = self.m.register([attempt(metric=None)])
        row = r["attempt_rows"][0]
        self.assertIn("measured_without_metric", row["flags"])
        self.assertEqual(row["verdict"], "REVIEW")
        self.assertEqual(r["verdict"], "ATTEMPTS_INCOMPLETE")

    def test_tested_without_evidence_flagged(self):
        r = self.m.register([attempt(status="tested", ref=None, metric=None)])
        self.assertIn("tested_without_evidence", r["attempt_rows"][0]["flags"])
        self.assertEqual(r["verdict"], "ATTEMPTS_INCOMPLETE")

    def test_measured_without_evidence_flagged(self):
        r = self.m.register([attempt(ref=None)])
        self.assertIn("measured_without_evidence", r["attempt_rows"][0]["flags"])

    def test_bad_status_and_types(self):
        with self.assertRaises(ValueError) as c:
            self.m.register([attempt(status="AGI")])
        self.assertTrue(str(c.exception).startswith("P236:bad_value:status"))
        with self.assertRaises(ValueError) as c2:
            self.m.register([attempt(aid=1)])
        self.assertTrue(str(c2.exception).startswith("P236:bad_type:"))
        with self.assertRaises(ValueError):
            self.m.register("not a list")
        bad = attempt(); bad["achieved"] = True
        with self.assertRaises(ValueError) as c3:
            self.m.register([bad])
        self.assertTrue(str(c3.exception).startswith("P236:unknown_field:"))

    def test_duplicates_and_caps(self):
        with self.assertRaises(ValueError) as c:
            self.m.register([attempt("dup"), attempt("dup")])
        self.assertTrue(str(c.exception).startswith("P236:duplicate_id:"))
        with self.assertRaises(ValueError) as c2:
            self.m.register([attempt("a%d" % i) for i in range(self.m.MAX_ATTEMPTS + 1)])
        self.assertTrue(str(c2.exception).startswith("P236:too_many:attempts"))
        with self.assertRaises(ValueError) as c3:
            self.m.register([])
        self.assertTrue(str(c3.exception).startswith("P236:empty"))

    def test_caller_mutation_caught_by_verify(self):
        attempts = [attempt()]
        r = self.m.run(copy.deepcopy(attempts))
        mutated = copy.deepcopy(attempts)
        mutated[0]["approach"] = "tampered"
        v = self.m.verify(mutated, r["result"])
        self.assertFalse(v["verified"])
        self.assertIn("attempts_sha256", v["failed"])

    def test_verify_compares_every_field(self):
        # Tampering with any single _KEYS field must fail verification and
        # name that field - no field is trusted from the caller.
        attempts = [attempt()]
        r = self.m.run(copy.deepcopy(attempts))
        self.assertTrue(r["verification"]["verified"])
        tampers = {
            "feature": "other_feature",
            "source_lines": ["P999|L999"],
            "doc_line": "- tampered doc line",
            "measure": "tampered measure",
            "limits": [],
            "attempts_sha256": "0" * 64,
            "attempt_rows": [],
            "state_counts": {},
            "issues": 999,
            "verdict": "ATTEMPTS_INCOMPLETE",
            "doc_claims": [],
        }
        self.assertEqual(set(tampers), set(self.m._KEYS))
        for field, bad_value in tampers.items():
            tampered = copy.deepcopy(r["result"])
            tampered[field] = bad_value
            v = self.m.verify(copy.deepcopy(attempts), tampered)
            self.assertFalse(v["verified"], field)
            self.assertIn(field, v["failed"], field)

    def test_deterministic(self):
        attempts = [attempt(), attempt("a2", "proposed", None, None)]
        r1 = self.m.run(copy.deepcopy(attempts))
        r2 = self.m.run(copy.deepcopy(attempts))
        self.assertEqual(r1["result"]["attempts_sha256"], r2["result"]["attempts_sha256"])


if __name__ == "__main__":
    unittest.main()
