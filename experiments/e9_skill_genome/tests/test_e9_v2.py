import os, random, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tasks2 import make_all, EXTRA_A, EXTRA_B, sig, CATS, make_task2, _hidden
from tasks import THEMES
from agent import evaluate
from agent2 import Agent2
from genome import make_skill
from run_v2 import random_lib

class TaskSetV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acq, cls.val, cls.test = make_all(4)
    def test_exact_strata(self):
        from collections import Counter
        self.assertEqual(Counter(t.cat for t in self.test), {c[0]: 20 for c in CATS})
        self.assertEqual(Counter(t.cat for t in self.val), {c[0]: 10 for c in CATS})
    def test_disjoint_sets(self):
        s = lambda ts: {sig(t) for t in ts}
        x = lambda ts: {i for t in ts for i in t.train_inputs}
        self.assertFalse(s(self.acq) & s(self.val) | s(self.acq) & s(self.test) | s(self.val) & s(self.test))
        self.assertFalse(x(self.test) & (x(self.acq) | x(self.val)))
        self.assertFalse(x(self.val) & x(self.acq))
    def test_extraB_never_sampled_as_extra_in_acquisition(self):
        used = {t.target[-1] for t in self.acq if t.target not in THEMES}
        self.assertFalse(used & set(EXTRA_B))
        b = [t for t in self.test if t.cat == "seen_extraB_heldout_sampling"]
        self.assertTrue(all(t.target[-1] in EXTRA_B for t in b))
    def test_hidden_inputs_not_fixed_probes(self):
        fixed = {tuple(t.hidden_inputs[:2]) for t in self.test}
        self.assertGreater(len(fixed), 5)
        self.assertTrue(len({t.hidden_inputs for t in self.test}) == len(self.test))

class Joint(unittest.TestCase):
    def test_random_control_exact_size(self):
        self.assertEqual(len(random_lib(1, 0, "x")), 0)
        self.assertEqual(len(random_lib(1, 5, "x")), 5)
    def test_joint_gate_and_audit(self):
        acq, val, test = make_all(2)
        ag = Agent2("gated", 1500, val, joint=True, audit=True)
        good = make_skill("g", THEMES[0], "manual", [((3, -1, 3), (1, 3))])
        junk = make_skill("j", ("mod3", "neg"), "manual", [((3, 4), (0, -1))])
        ag.consider(good, "t"); ag.consider(junk, "t")
        self.assertEqual(len(ag.pending), 2); self.assertEqual(ag.library, [])
        ag.joint_round()
        progs = [s.program for s in ag.library]
        self.assertIn(THEMES[0], progs)                  # set gain found, useful member kept
        self.assertNotIn(("mod3", "neg"), progs)        # no-contribution member eliminated
        # audit retires a skill with no validation contribution
        ag.library.append(junk); ag.audit_round()
        self.assertNotIn(junk, ag.library)

if __name__ == "__main__":
    unittest.main()
