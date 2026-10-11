"""S1.7 / c31.deploy tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/deploy.py"
_spec = importlib.util.spec_from_file_location("c31_deploy", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_deploy"] = m
_spec.loader.exec_module(m)

def jobs(n, cost=1):
    return [{"id": "job-%04d" % i, "cost": cost} for i in range(n)]


class Deploy(unittest.TestCase):
    def test_canonical_1000(self):
        out = m.plan(jobs(1000), concurrency=25)
        self.assertEqual(out["job_count"], 1000)
        self.assertEqual(out["wave_count"], 40)
        self.assertTrue(all(w["size"] == 25 for w in out["waves"]))
        self.assertEqual(out["actual_concurrency"], 25)
        self.assertEqual(out["total_cost"], 1000)
        self.assertEqual(out["jobs"][0]["role"], "researcher")  # roles cycle deterministically
        self.assertEqual(out["jobs"][5]["role"], "auditor")  # 6-role cycle: index 5 = auditor
        self.assertEqual(out["jobs"][1]["role"], "analyst")

    def test_concurrency_capped_by_jobs(self):
        out = m.plan(jobs(3), concurrency=25)
        self.assertEqual(out["actual_concurrency"], 3)
        self.assertEqual(out["wave_count"], 1)

    def test_overcap_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.plan(jobs(1001), concurrency=10)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_OVERCAP:1001>1000")
        out = m.plan(jobs(1000), concurrency=10)  # exactly at cap passes
        self.assertEqual(out["job_count"], 1000)

    def test_spend_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.plan(jobs(10), concurrency=2, spend=True)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_SPEND")
        self.assertIn("spend (refused)", m.plan(jobs(2), 1)["scope"]["not_implemented"])

    def test_validation(self):
        with self.assertRaises(ValueError) as cm:
            m.plan([], 1)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_EMPTY:jobs")
        with self.assertRaises(ValueError) as cm:
            m.plan(jobs(2) + [dict(jobs(1)[0])], 1)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_DUPLICATE:job-0000")
        with self.assertRaises(ValueError) as cm:
            m.plan([{"id": "a", "cost": 0}], 1)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:cost")
        with self.assertRaises(ValueError) as cm:
            m.plan([{"id": "a\n", "cost": 1}], 1)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_CONTROL_CHARS:job_id")
        with self.assertRaises(ValueError) as cm:
            m.plan(jobs(2), 0)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:concurrency")

    def test_survivor_pins_g2(self):
        # deploy-58/63: jobs typed non-bool list
        for bad in (True, "x", 42):
            with self.assertRaises(ValueError) as cm:
                m.plan(bad, 2)
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:jobs")
        # deploy-65: non-dict job
        with self.assertRaises(ValueError) as cm:
            m.plan(["notadict"], 2)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:job")
        # deploy-68: spend default is False - bare report/plan path works
        out = m.report(jobs(3), 2)
        self.assertEqual(out["job_count"], 3)
        # deploy-75: exact wave numbering 1..N
        out = m.plan(jobs(3), 2)
        self.assertEqual([w["wave"] for w in out["waves"]], [1, 2])
        self.assertEqual([w["size"] for w in out["waves"]], [2, 1])

    def test_determinism(self):
        self.assertEqual(m.plan(jobs(100, cost=3), 7), m.plan(jobs(100, cost=3), 7))


if __name__ == "__main__":
    unittest.main()
