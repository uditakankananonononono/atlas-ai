"""Row 28 rollup() streams-level deep-DAG repair tests (bounded caller repair:
a VALID deep DAG at level="streams" died with RecursionError because
_descendants was recursive). Repair: iterative preorder with identical output
order (all direct children first, then each child's subtree in plan order).
No arbitrary input cap; guard behavior and valid-plan outputs byte-preserved.
House-side: full mechanism tier via disclosed shim PlanNode (standin, not
real-schema proof)."""
import random
import unittest

from app.modules.m20_general_cognitive_worker.metacognition import AbstractionShifter
from app.modules.m20_general_cognitive_worker.schemas import PlanNode


def node(nid, title, deps=()):
    return PlanNode(id=nid, title=title, depends_on=list(deps))


def _reference_descendants(node_, plan):
    """The original recursive implementation, kept as the order oracle."""
    children = [n for n in plan if node_.id in n.depends_on]
    out = [c.title for c in children]
    for child in children:
        out.extend(_reference_descendants(child, plan))
    return out


def _random_dag(rng, size):
    plan = []
    for i in range(size):
        deps = [f"n{j}" for j in range(i) if rng.random() < 0.15]
        plan.append(node(f"n{i}", f"task-{i}", deps))
    rng.shuffle(plan)
    return plan


def _chain(size):
    return [node("n0", "task-0")] + [
        node(f"n{i}", f"task-{i}", [f"n{i-1}"]) for i in range(1, size)]


class TestIterativeDescendants(unittest.TestCase):
    def setUp(self):
        self.s = AbstractionShifter()

    def test_output_order_matches_recursive_reference(self):
        rng = random.Random(20261016)
        for trial in range(300):
            plan = _random_dag(rng, rng.randint(1, 60))
            roots = [n for n in plan if not n.depends_on]
            expected = [_reference_descendants(r, plan) for r in roots]
            streams = self.s.rollup("g", plan, level="streams")["streams"]
            self.assertEqual([s["descendants"] for s in streams], expected, msg=f"trial {trial}")

    def test_deep_chain_streams_no_recursion_error(self):
        for size in (1100, 2500, 6000):
            out = self.s.rollup("g", _chain(size), level="streams")
            self.assertEqual(len(out["streams"]), 1, msg=size)
            self.assertEqual(len(out["streams"][0]["descendants"]), size - 1, msg=size)

    def test_deep_chain_steps_unchanged(self):
        out = self.s.rollup("g", _chain(1100), level="steps")
        self.assertEqual(len(out["steps"]), 1100)

    def test_valid_outputs_preserved_all_levels(self):
        plan = [node("a", "x"), node("b", "y", ["a"]), node("c", "z", ["a"]),
                node("d", "w", ["b", "c"])]
        for level in ("strategy", "streams", "steps"):
            out = self.s.rollup("g", plan, level=level)
            self.assertEqual(out["level"], level, msg=level)
        # diamond plans list a shared descendant once per path (pre-existing
        # lossy-summary behavior, preserved byte-exactly - not a defect repair)
        self.assertEqual(self.s.rollup("g", plan, level="streams")["streams"],
                         [{"root": "x", "descendants": ["y", "z", "w", "w"]}])

    def test_duplicate_titles_still_accepted(self):
        plan = [node("a", "same title"), node("b", "same title", ["a"])]
        streams = self.s.rollup("g", plan, level="streams")
        self.assertEqual(streams["streams"], [{"root": "same title", "descendants": ["same title"]}])

    def test_guards_still_refuse_before_dispatch(self):
        cyclic = [node("a", "x", ["b"]), node("b", "y", ["a"])]
        with self.assertRaisesRegex(ValueError, "acyclic"):
            self.s.rollup("g", cyclic, level="streams")
        dup = [node("a", "x"), node("a", "y")]
        with self.assertRaisesRegex(ValueError, "unique"):
            self.s.rollup("g", dup, level="streams")


if __name__ == "__main__":
    unittest.main()
