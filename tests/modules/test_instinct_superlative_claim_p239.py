"""P239|L188 superlative claim audit: red-first tests."""
from __future__ import annotations

import copy
import unittest


def comparison(cid="c1", subject="sugarcode", competitor="rival-x",
               metric="exact-test pass rate", evidence="ev-1"):
    c = {"id": cid, "subject": subject, "competitor": competitor,
         "metric": metric}
    if evidence is not None:
        c["evidence_ref"] = evidence
    return c


class SuperlativeTest(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import superlative_claim_p239 as m
        self.m = m

    def test_claim_recorded_unverifiable_never_best(self):
        r = self.m.run([comparison()])
        res = r["result"]
        self.assertEqual(r["status"], "audited")
        self.assertTrue(r["verification"]["verified"])
        self.assertEqual(res["verdict"], "SUPERLATIVE_UNVERIFIABLE")
        for claim in res["doc_claims"]:
            self.assertFalse(claim["asserted"])
        claims = {c["claim"]: c for c in res["doc_claims"]}
        self.assertIn("both are the best in the world", claims)
        self.assertFalse(claims["both are the best in the world"]["verifiable"])
        self.assertEqual(res["subjects_covered"], ["sugarcode"])

    def test_verdict_never_best_even_with_full_evidence(self):
        comps = [comparison("c%d" % i, competitor="rival-%d" % i)
                 for i in range(20)]
        r = self.m.audit(comps)
        self.assertEqual(r["verdict"], "SUPERLATIVE_UNVERIFIABLE")
        self.assertNotIn("best", r["verdict"].lower())

    def test_missing_evidence_flagged(self):
        r = self.m.audit([comparison(evidence=None)])
        self.assertIn("missing_evidence_ref", r["comparison_rows"][0]["flags"])

    def test_bad_types_and_caps(self):
        with self.assertRaises(ValueError) as c:
            self.m.audit([comparison(cid=1)])
        self.assertTrue(str(c.exception).startswith("P239:bad_type:"))
        with self.assertRaises(ValueError) as c2:
            self.m.audit([comparison("dup"), comparison("dup")])
        self.assertTrue(str(c2.exception).startswith("P239:duplicate_id:"))
        with self.assertRaises(ValueError) as c3:
            self.m.audit([comparison("c%d" % i) for i in range(self.m.MAX_COMPARISONS + 1)])
        self.assertTrue(str(c3.exception).startswith("P239:too_many:comparisons"))
        with self.assertRaises(ValueError):
            self.m.audit([])
        with self.assertRaises(ValueError):
            self.m.audit("nope")
        bad = comparison(); bad["rank"] = 1
        with self.assertRaises(ValueError) as c4:
            self.m.audit([bad])
        self.assertTrue(str(c4.exception).startswith("P239:unknown_field:"))

    def test_caller_mutation_caught_by_verify(self):
        comps = [comparison()]
        r = self.m.run(copy.deepcopy(comps))
        mutated = copy.deepcopy(comps)
        mutated[0]["metric"] = "tampered"
        v = self.m.verify(mutated, r["result"])
        self.assertFalse(v["verified"])
        self.assertIn("fingerprint", v["failed"])

    def test_both_subjects_coverage_recomputed(self):
        r = self.m.audit([comparison(subject="sugarcode"),
                          comparison("c2", subject="claire-meemee")])
        self.assertEqual(sorted(r["subjects_covered"]),
                         ["claire-meemee", "sugarcode"])
        self.assertEqual(r["comparisons"], 2)


if __name__ == "__main__":
    unittest.main()
