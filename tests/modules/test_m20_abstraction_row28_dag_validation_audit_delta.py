"""Row 28 audit delta: close two REAL suite gaps found by independent mutation.

1. Duplicate TITLES are not a fault. Guards key on node ids; two schema-valid
   nodes may share a title. A mutant that refuses duplicate titles (false
   refusal of lawful plans) survived the v2 suite: no test exercised
   same-title/different-id plans. Pristine behavior also accepted them.
2. Guards fire before level dispatch. The patch comment refuses degenerate
   DAGs "first" and the v2 module docstring says "BEFORE any rollup level
   computation". A mutant that validates the level argument before the DAG
   guards survived: combined cyclic-plan + unknown-level inputs were unpinned.
"""
import unittest

from app.modules.m20_general_cognitive_worker.metacognition import AbstractionShifter
from app.modules.m20_general_cognitive_worker.schemas import PlanNode


def node(nid, title, deps=()):
    return PlanNode(id=nid, title=title, depends_on=list(deps))


class TestRollupDagValidationAuditDelta(unittest.TestCase):
    def setUp(self):
        self.s = AbstractionShifter()

    def test_duplicate_titles_are_not_a_fault(self):
        plan = [node("a", "same title"), node("b", "same title", ["a"])]
        for level in ("strategy", "streams", "steps"):
            out = self.s.rollup("g", plan, level=level)
            self.assertEqual(out["level"], level, msg=level)
        steps = self.s.rollup("g", plan, level="steps")
        self.assertEqual(len(steps["steps"]), 2)
        self.assertEqual([s["title"] for s in steps["steps"]], ["same title", "same title"])

    def test_guards_fire_before_level_dispatch(self):
        cyclic = [node("a", "x", ["b"]), node("b", "y", ["a"])]
        with self.assertRaisesRegex(ValueError, "acyclic"):
            self.s.rollup("g", cyclic, level="quantum")
        dup = [node("a", "x"), node("a", "y")]
        with self.assertRaisesRegex(ValueError, "unique"):
            self.s.rollup("g", dup, level="quantum")


if __name__ == "__main__":
    unittest.main()
