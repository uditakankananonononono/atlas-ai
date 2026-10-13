"""P237|L186 merge-condition audit: red-first tests."""
from __future__ import annotations

import copy
import unittest


def payload(meemee=None, claire=None):
    return {"meemee": {"capabilities": meemee if meemee is not None else ["exact-arithmetic", "concept-registry"]},
            "claire": {"capabilities": claire if claire is not None else ["concept-registry"]}}


class MergeConditionTest(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import merge_condition_p237 as m
        self.m = m

    def test_condition_met_recomputed(self):
        r = self.m.run(payload())
        res = r["result"]
        self.assertEqual(r["status"], "evaluated")
        self.assertTrue(r["verification"]["verified"])
        self.assertEqual(res["extra_capabilities"], ["exact-arithmetic"])
        self.assertEqual(res["shared_capabilities"], ["concept-registry"])
        self.assertEqual(res["verdict"], "MERGE_CONDITION_MET")
        self.assertEqual(res["doc_claims"],
                         [{"claim": "Meemee merged into Claire",
                           "asserted": False,
                           "note": "merge never performed by this unit; the condition is recomputed only"}])

    def test_condition_not_met(self):
        r = self.m.evaluate(payload(meemee=["concept-registry"]))
        self.assertEqual(r["extra_capabilities"], [])
        self.assertEqual(r["verdict"], "MERGE_CONDITION_NOT_MET")
        r2 = self.m.evaluate(payload(meemee=[]))
        self.assertEqual(r2["verdict"], "MERGE_CONDITION_NOT_MET")

    def test_bad_types_and_unknown_fields(self):
        with self.assertRaises(ValueError) as c:
            self.m.evaluate(payload(meemee=[True]))
        self.assertTrue(str(c.exception).startswith("P237:bad_type:"))
        with self.assertRaises(ValueError) as c2:
            self.m.evaluate({"meemee": {"capabilities": []}})
        self.assertTrue(str(c2.exception).startswith("P237:missing_field:"))
        bad = payload(); bad["merged"] = True
        with self.assertRaises(ValueError) as c3:
            self.m.evaluate(bad)
        self.assertTrue(str(c3.exception).startswith("P237:unknown_field:"))
        with self.assertRaises(ValueError):
            self.m.evaluate("not a dict")

    def test_duplicates_and_caps(self):
        with self.assertRaises(ValueError) as c:
            self.m.evaluate(payload(meemee=["x", "x"]))
        self.assertTrue(str(c.exception).startswith("P237:duplicate_capability:"))
        with self.assertRaises(ValueError) as c2:
            self.m.evaluate(payload(meemee=["c%d" % i for i in range(self.m.MAX_CAPABILITIES + 1)]))
        self.assertTrue(str(c2.exception).startswith("P237:too_many:capabilities"))

    def test_caller_mutation_caught_by_verify(self):
        p = payload()
        r = self.m.run(copy.deepcopy(p))
        mutated = copy.deepcopy(p)
        mutated["meemee"]["capabilities"].append("tampered")
        v = self.m.verify(mutated, r["result"])
        self.assertFalse(v["verified"])
        self.assertIn("fingerprint", v["failed"])

    def test_empty_capability_string_refused(self):
        with self.assertRaises(ValueError) as c:
            self.m.evaluate(payload(meemee=["  "]))
        self.assertTrue(str(c.exception).startswith("P237:empty_field:"))


if __name__ == "__main__":
    unittest.main()
