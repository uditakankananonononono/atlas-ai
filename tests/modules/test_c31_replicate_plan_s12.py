"""S1.2 / c31.replicate_plan tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/replicate_plan.py"
_spec = importlib.util.spec_from_file_location("c31_replicate_plan", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_replicate_plan"] = m
_spec.loader.exec_module(m)

TOOLS = [{"name": "cellcog", "license": "proprietary", "capabilities": ["web agents"]},
         {"name": "openbrowser", "license": "mit", "capabilities": ["testing", "web agents"]}]


class ReplicatePlan(unittest.TestCase):
    def test_routing_and_tickets(self):
        out = m.plan(TOOLS)
        self.assertEqual(out["ticket_count"], 3)
        self.assertEqual(out["integrate_count"], 2)      # mit entries
        self.assertEqual(out["build_ourselves_count"], 1)  # proprietary
        self.assertTrue(all(t["acceptance_tests_first"] for t in out["tickets"]))
        routes = {(t["tool"], t["capability"]): t["route"] for t in out["tickets"]}
        self.assertEqual(routes[("cellcog", "web agents")], "build_ourselves")
        self.assertEqual(routes[("openbrowser", "testing")], "integrate")
        self.assertEqual(out["tickets"][0]["capability"], "testing")  # sorted

    def test_closed_copy_refused(self):
        with self.assertRaises(ValueError) as cm:
            m.plan(TOOLS, copy_closed=True)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_UNLICENSED")
        out = m.plan([{"name": "o", "license": "mit", "capabilities": ["x"]}], copy_closed=True)
        self.assertEqual(out["ticket_count"], 1)  # open licenses unaffected

    def test_no_source(self):
        with self.assertRaises(ValueError) as cm:
            m.plan([])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_NOSOURCE")

    def test_bad_license(self):
        with self.assertRaises(ValueError) as cm:
            m.plan([{"name": "x", "license": "weird"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_LICENSE:weird")

    def test_control_chars(self):
        with self.assertRaises(ValueError) as cm:
            m.plan([{"name": "x", "capabilities": ["a\u2028b"]}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_CONTROL_CHARS:capability")

    def test_survivor_pins_g1(self):
        TOOL = {"name": "openbrowser", "license": "mit", "capabilities": ["testing"]}
        # replicate_plan-24/28: tools must be a non-bool list/tuple
        for bad in (True, "x", 42):
            with self.assertRaises(ValueError) as cm:
                m.plan(bad)
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_NOSOURCE")
        # replicate_plan-26: cap enforced
        big = [dict(TOOL, name="t%d" % i) for i in range(m.MAX_TOOLS + 1)]
        with self.assertRaises(ValueError) as cm:
            m.plan(big)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_OVERSIZE")
        # replicate_plan-30: non-dict tool element
        with self.assertRaises(ValueError) as cm:
            m.plan(["notadict"])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:tool")
        # replicate_plan-33: capabilities must be a list/tuple
        with self.assertRaises(ValueError) as cm:
            m.plan([dict(TOOL, capabilities="testing")])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:capabilities")

    def test_determinism(self):
        self.assertEqual(m.plan(TOOLS), m.plan(TOOLS))


if __name__ == "__main__":
    unittest.main()
