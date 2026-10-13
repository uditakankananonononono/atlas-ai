"""P238|L187 improvement-factor audit: red-first tests."""
from __future__ import annotations

import copy
import unittest
from fractions import Fraction


def metric(mid="m1", before="2", after="10", evidence="ev-1"):
    return {"id": mid, "metric": "tasks per hour", "before": before,
            "after": after, "evidence_ref": evidence}


class ImprovementFactorTest(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import improvement_factor_p238 as m
        self.m = m

    def test_factor_recomputed_exactly(self):
        r = self.m.run([metric()])
        res = r["result"]
        self.assertEqual(r["status"], "audited")
        self.assertTrue(r["verification"]["verified"])
        row = res["metric_rows"][0]
        self.assertEqual(row["factor"], Fraction(5))  # 10 / 2, exact
        self.assertEqual(res["target_factor"], 1_000_000)
        self.assertEqual(res["metrics_meeting_target"], 0)
        self.assertEqual(res["verdict"], "TARGET_NOT_MET")
        self.assertEqual(res["doc_claims"],
                         [{"claim": "Sugarcode improved x1,000,000",
                           "asserted": False}])

    def test_target_met_only_when_real(self):
        r = self.m.audit([metric(before="1", after="1000000")])
        self.assertEqual(r["metrics_meeting_target"], 1)
        self.assertEqual(r["verdict"], "FACTORS_RECOMPUTED")

    def test_factor_uses_after_over_before_oracle(self):
        r = self.m.audit([metric(before="3/2", after="9/4")])
        self.assertEqual(r["metric_rows"][0]["factor"],
                         Fraction(9, 4) / Fraction(3, 2))

    def test_zero_before_and_regressions(self):
        with self.assertRaises(ValueError) as c:
            self.m.audit([metric(before="0")])
        self.assertTrue(str(c.exception).startswith("P238:bad_value:") and "before" in str(c.exception))
        r = self.m.audit([metric(before="10", after="2")])
        row = r["metric_rows"][0]
        self.assertEqual(row["factor"], Fraction(1, 5))
        self.assertIn("regression", row["flags"])

    def test_missing_evidence_flagged(self):
        m = metric(); del m["evidence_ref"]
        r = self.m.audit([m])
        self.assertIn("missing_evidence_ref", r["metric_rows"][0]["flags"])

    def test_bad_types_values_and_caps(self):
        with self.assertRaises(ValueError) as c:
            self.m.audit([metric(after=1.5)])
        self.assertTrue(str(c.exception).startswith("P238:bad_type:"))
        with self.assertRaises(ValueError) as c2:
            self.m.audit([metric(after="-5")])
        self.assertTrue(str(c2.exception).startswith("P238:bad_value:") and "after" in str(c2.exception))
        with self.assertRaises(ValueError) as c3:
            self.m.audit([metric("dup"), metric("dup")])
        self.assertTrue(str(c3.exception).startswith("P238:duplicate_id:"))
        with self.assertRaises(ValueError) as c4:
            self.m.audit([metric("m%d" % i) for i in range(self.m.MAX_METRICS + 1)])
        self.assertTrue(str(c4.exception).startswith("P238:too_many:metrics"))
        with self.assertRaises(ValueError):
            self.m.audit("not a list")
        with self.assertRaises(ValueError):
            self.m.audit([])

    def test_caller_mutation_caught_by_verify(self):
        metrics = [metric()]
        r = self.m.run(copy.deepcopy(metrics))
        mutated = copy.deepcopy(metrics)
        mutated[0]["after"] = "999999999"
        v = self.m.verify(mutated, r["result"])
        self.assertFalse(v["verified"])
        self.assertIn("metrics_sha256", v["failed"])


    def test_verify_compares_every_field(self):
        data = [metric()]
        r = self.m.run(copy.deepcopy(data))
        result = r["result"]
        self.assertTrue(r["verification"]["verified"])
        for field in self.m._KEYS:
            tampered = copy.deepcopy(result)
            v = tampered[field]
            if type(v) is bool:
                tampered[field] = not v
            elif type(v) is int:
                tampered[field] = v + 1
            elif type(v) is str:
                tampered[field] = v + " TAMPERED"
            elif type(v) is list:
                tampered[field] = [] if v else ["TAMPERED"]
            elif type(v) is dict:
                tampered[field] = dict(v, tampered=1)
            vv = self.m.verify(copy.deepcopy(data), tampered)
            self.assertFalse(vv["verified"], field)
            self.assertIn(field, vv["failed"], field)

    def test_verify_catches_nested_asserted_tamper(self):
        data = [metric()]
        r = self.m.run(copy.deepcopy(data))
        nested = copy.deepcopy(r["result"])
        claims = nested["doc_claims"]
        self.assertTrue(claims and "asserted" in claims[0])
        claims[0]["asserted"] = not claims[0]["asserted"]
        vv = self.m.verify(copy.deepcopy(data), nested)
        self.assertFalse(vv["verified"])
        self.assertIn("doc_claims", vv["failed"])

if __name__ == "__main__":
    unittest.main()
