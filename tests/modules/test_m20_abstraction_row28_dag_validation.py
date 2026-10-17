"""Row 28 rollup() DAG-validation repair tests (bounded data-integrity repair:
schema-valid plans with duplicate ids, unknown dependency refs, or cycles were
silently dropped/duplicated in rollup output). Guards refuse degenerate DAGs
with ValueError BEFORE any rollup level computation; valid-plan
representation is byte-preserved. Route boundary unchanged; HTTP candidate
tests are native-tier and skip without real fastapi/pydantic."""
import unittest

from app.modules.m20_general_cognitive_worker.metacognition import AbstractionShifter
from app.modules.m20_general_cognitive_worker.schemas import PlanNode


def node(nid, title, deps=()):
    return PlanNode(id=nid, title=title, depends_on=list(deps))


class TestRollupDagValidation(unittest.TestCase):
    def setUp(self):
        self.s = AbstractionShifter()

    def test_duplicate_ids_refused(self):
        plan = [node("a", "x"), node("a", "y")]
        for level in ("strategy", "streams", "steps"):
            with self.assertRaises(ValueError, msg=level):
                self.s.rollup("g", plan, level=level)

    def test_unknown_dependency_ref_refused(self):
        plan = [node("a", "x", ["ghost"])]
        with self.assertRaisesRegex(ValueError, "unknown ids"):
            self.s.rollup("g", plan, level="steps")

    def test_cycle_refused_all_levels(self):
        plan = [node("a", "x", ["b"]), node("b", "y", ["a"])]
        for level in ("strategy", "streams", "steps"):
            with self.assertRaisesRegex(ValueError, "acyclic", msg=level):
                self.s.rollup("g", plan, level=level)

    def test_self_loop_refused(self):
        with self.assertRaisesRegex(ValueError, "acyclic"):
            self.s.rollup("g", [node("a", "x", ["a"])], level="streams")

    def test_rooted_cycle_refused_before_recursive_descent(self):
        # a root PLUS a detached cycle: streams used to silently drop the cycle,
        # and a root-reaching cycle would hit unbounded recursion in _descendants
        plan = [node("r", "root"), node("a", "x", ["b"]), node("b", "y", ["a"])]
        with self.assertRaisesRegex(ValueError, "acyclic"):
            self.s.rollup("g", plan, level="streams")

    def test_long_chain_no_recursion_limit(self):
        plan = [node(f"n{i}", f"t{i}", [f"n{i-1}"] if i else []) for i in range(5000)]
        out = self.s.rollup("g", plan, level="steps")
        self.assertEqual(len(out["steps"]), 5000)

    def test_top_container_and_item_types_refused(self):
        for bad in ("notalist", 42, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.s.rollup("g", bad, level="steps")
        with self.assertRaises(ValueError):
            self.s.rollup("g", [{"id": "a", "title": "x"}], level="steps")

    def test_valid_plan_representation_preserved(self):
        a = PlanNode(title="market research", tool="web_search")
        b = PlanNode(title="draft report", depends_on=[a.id])
        c = PlanNode(title="build prototype", tool="python_sandbox")
        plan = [a, b, c]
        strategy = self.s.rollup("launch product", plan, level="strategy")
        self.assertEqual(strategy["level"], "strategy")
        self.assertIn("3 steps", strategy["summary"])
        streams = self.s.rollup("launch product", plan, level="streams")
        self.assertEqual(len(streams["streams"]), 2)
        research = [x for x in streams["streams"] if x["root"] == "market research"][0]
        self.assertEqual(research["descendants"], ["draft report"])
        steps = self.s.rollup("launch product", plan, level="steps")
        self.assertEqual(len(steps["steps"]), 3)
        with self.assertRaisesRegex(ValueError, "unknown level"):
            self.s.rollup("g", plan, level="quantum")
        empty = self.s.rollup("g", [], level="steps")
        self.assertEqual(empty["steps"], [])


if __name__ == "__main__":
    unittest.main()
