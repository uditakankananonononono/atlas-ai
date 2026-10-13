import os, random, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ops import OPS
from genome import make_skill, Skill, source_for
from tasks import make_set, make_task, feedback, THEMES, apply_ops
from agent import Agent, solve, evaluate, rewrite, run_path

BUDGET = 1500
EXPECTED_REWRITE_PASSES = 6   # of 8 fixed rich tasks; deterministic

def theme2_tasks(seed, n, rich, need_unsolved_by_base=True):
    rng = random.Random(seed); out = []
    while len(out) < n:
        t = make_task(rng, f"x{len(out)}", [2])
        if t.target == THEMES[2] and t.rich == rich and (not need_unsolved_by_base or not evaluate([t], [], BUDGET)[0]):
            out.append(t)
    return out

class Basics(unittest.TestCase):
    def test_ops(self):
        self.assertEqual(OPS["dedupe"]((3, 1, 3, 2, 1)), (3, 1, 2))
        self.assertEqual(OPS["pair_sum"]((1, 2, 3)), (3, 5))
        self.assertEqual(OPS["running_max"]((1, 3, 2)), (1, 3, 3))

    def test_skill_is_executable_source(self):
        s = make_skill("s", ("dedupe", "sort"), "manual", [((3, 1, 3), (1, 3))])
        self.assertIn("OPS['dedupe']", s.procedure)
        self.assertEqual(s.fn((5, 5, 1)), (1, 5))
        self.assertTrue(s.run_tests())
        bad = make_skill("b", ("sort",), "manual", [((3, 1), (1, 3))]); bad.tests = [((3, 1), (3, 1))]
        self.assertFalse(bad.run_tests())

    def test_precondition_and_contract_inferred(self):
        s = make_skill("s", ("sort",), "manual", [((3, 1, 2), (1, 2, 3))])
        self.assertIn("distinct", s.precondition); self.assertIn("nonneg", s.precondition)
        self.assertIn("sorted", s.expected)
        self.assertFalse(s.applicable((1, 1, 2)))      # duplicates: precondition fails
        self.assertFalse(s.applicable((-1, 2)))
        self.assertTrue(s.applicable((4, 2)))

    def test_sets_disjoint_and_deterministic(self):
        a = make_set(3, "a", 30, list(range(7))); a2 = make_set(3, "a", 30, list(range(7)))
        self.assertEqual([t.signature() for t in a], [t.signature() for t in a2])
        v = make_set(3, "v", 30, list(range(10)), forbid={t.signature() for t in a})
        self.assertFalse({t.signature() for t in a} & {t.signature() for t in v})

    def test_search_uses_library_skill(self):
        t = theme2_tasks(1, 1, rich=True)[0]
        self.assertIsNone(solve(t, [], BUDGET)[0])      # base search runs out of budget
        good = make_skill("g", THEMES[2], "manual", list(zip(t.train_inputs, t.train_outputs)))
        p, _ = solve(t, [good], BUDGET)
        self.assertIsNotNone(p)
        self.assertTrue(feedback(t, lambda x: run_path(p, x))[0])

    def test_rewrite_fits_train_and_is_checked_on_hidden(self):
        from tasks2 import make_task2, EXTRA_A
        rng = random.Random(3); rich = []
        while len(rich) < 8:
            t = make_task2(rng, "r", [2], "full", EXTRA_A)
            if t.rich: rich.append(t)
        passed = 0
        for t in rich:
            ex = list(zip(t.train_inputs, t.train_outputs))
            fixed = rewrite(("sort_desc", "take3"), ex)
            self.assertIsNotNone(fixed)
            for i, o in ex:                              # always fits the examples it was given
                self.assertEqual(apply_ops(fixed, i), o)
            passed += feedback(t, lambda x: apply_ops(fixed, x))[0]
        # rewrite is NOT guaranteed correct: a fit can still fail hidden inputs (seen in this fixed sample)
        self.assertEqual(passed, EXPECTED_REWRITE_PASSES)
        self.assertLess(passed, 8)
        self.assertGreater(passed, 0)

class FailureRegression(unittest.TestCase):
    """A skill that passes its own tests but fails on unseen tasks must not be trusted."""
    def setUp(self):
        rng = random.Random(9)
        while True:   # a poor-example theme-2 task: dedupe is unobservable, [sort_desc, take3] fits
            t = make_task(rng, "p", [2])
            if not t.rich and t.target == THEMES[2]: break
        self.poor = t
        self.overfit = make_skill("ov", ("sort_desc", "take3"), "induced", list(zip(t.train_inputs, t.train_outputs)))
        self.val = theme2_tasks(5, 6, rich=True)
        self.unseen = theme2_tasks(6, 6, rich=True, need_unsolved_by_base=False); r = self.unseen[0]   # correct skill acquired from rich evidence (its inferred precondition is then permissive)
        self.correct = make_skill("ok", THEMES[2], "manual", list(zip(r.train_inputs, r.train_outputs)))
        self.unseen = theme2_tasks(6, 6, rich=True, need_unsolved_by_base=False)

    def test_overfit_passes_own_tests_but_fails_unseen(self):
        self.assertTrue(self.overfit.run_tests())
        fails = [not feedback(t, lambda x: self.overfit.fn(x))[0] for t in self.unseen]
        self.assertTrue(all(fails))
        self.assertTrue(all(feedback(t, lambda x: self.correct.fn(x))[0] for t in self.unseen))

    def test_gate_rejects_overfit_admits_correct_admit_all_takes_both(self):
        g = Agent("gated", BUDGET, self.val)
        self.assertFalse(g.consider(self.overfit, "t"))
        self.assertEqual(g.log[-1]["decision"], "reject_no_unseen_gain")
        self.assertTrue(g.consider(self.correct, "t"))
        a = Agent("admit_all", BUDGET, self.val)
        self.assertTrue(a.consider(self.overfit, "t"))     # the failure the gate exists to stop

    def test_tampered_skill_fails_own_tests(self):
        s = make_skill("s", ("sort",), "manual", [((2, 1), (1, 2))])
        s.tests = [((2, 1), (2, 1))]
        g = Agent("gated", BUDGET, self.val)
        self.assertFalse(g.consider(s, "t"))
        self.assertEqual(g.log[-1]["decision"], "reject_own_tests")

    def test_failure_case_recorded_on_used_skill(self):
        """A library skill used in a failing answer gets that failure recorded (deterministic task choice)."""
        rng = random.Random(11); used = None
        for _ in range(200):
            t = make_task(rng, "f", [2])
            if t.rich or t.target != THEMES[2]:
                continue
            p, _ = solve(t, [self.overfit], BUDGET)
            if p and any(u.skill is self.overfit for u in p) and not feedback(t, lambda x: run_path(p, x))[0]:
                used = t; break
        self.assertIsNotNone(used, "no poor theme-2 task where the overfit skill is used and fails")
        a = Agent("admit_all", BUDGET, self.val)
        a.library.append(self.overfit)
        before = len(self.overfit.failure_cases)
        a.step(used)
        self.assertEqual(len(self.overfit.failure_cases), before + 1)
        fc = self.overfit.failure_cases[-1]
        self.assertEqual(fc["task"], used.tid)
        self.assertNotEqual(fc["expected"], fc["got"])

if __name__ == "__main__":
    unittest.main()
