"""S1.1 / c31.tool_scan tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c31/tool_scan.py"
_spec = importlib.util.spec_from_file_location("c31_tool_scan", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c31_tool_scan"] = m
_spec.loader.exec_module(m)

TOOLS = [{"name": "cellcog", "license": "proprietary", "price_tier": "paid",
          "capabilities": ["web agents", "scraping"]},
         {"name": "openbrowser", "license": "mit", "price_tier": "free",
          "capabilities": ["web agents", "testing"]}]


class ToolScan(unittest.TestCase):
    def test_matrix_and_gaps(self):
        out = m.scan(TOOLS, atlas_modules=["scraping"])
        self.assertEqual(out["tool_count"], 2)
        self.assertEqual(out["capability_count"], 3)
        self.assertEqual(out["gap_list"], ["testing", "web agents"])
        self.assertEqual(out["gap_count"], 2)
        self.assertEqual(out["matrix"][0]["name"], "cellcog")  # sorted by name

    def test_no_source_refused(self):
        for bad in (None, True, "x", []):
            with self.assertRaises(ValueError) as cm:
                m.scan(bad)
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_NOSOURCE")

    def test_purchase_refused_via_guard(self):
        with self.assertRaises(ValueError) as cm:
            m.scan(TOOLS, purchase=True)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_SPEND")

    def test_vocab_and_duplicates(self):
        with self.assertRaises(ValueError) as cm:
            m.scan([{"name": "x", "license": "weird-license"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_LICENSE:weird-license")
        with self.assertRaises(ValueError) as cm:
            m.scan([{"name": "x", "price_tier": "pricey"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_PRICE_TIER:pricey")
        with self.assertRaises(ValueError) as cm:
            m.scan([{"name": "x"}, {"name": "x"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_DUPLICATE:x")

    def test_control_chars(self):
        with self.assertRaises(ValueError) as cm:
            m.scan([{"name": "a\nb"}])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_CONTROL_CHARS:name")

    def test_survivor_pins_g1(self):
        # tool_scan-4: cap enforced
        big = [dict(TOOLS[0], name="t%d" % i) for i in range(m.MAX_TOOLS + 1)]
        with self.assertRaises(ValueError) as cm:
            m.scan(big)
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_OVERSIZE")
        # tool_scan-9: non-dict tool element
        for bad in ("x", 42, ["name"]):
            with self.assertRaises(ValueError) as cm:
                m.scan([bad])
            self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:tool")
        # tool_scan-13: capabilities must be a list/tuple
        with self.assertRaises(ValueError) as cm:
            m.scan([dict(TOOLS[0], capabilities="web agents")])
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:capabilities")
        # tool_scan-15: atlas_modules must be a list/tuple
        with self.assertRaises(ValueError) as cm:
            m.scan(TOOLS, atlas_modules="scraping")
        self.assertEqual(str(cm.exception), "FLEET_REFUSED_BAD_TYPE:atlas_modules")

    def test_determinism(self):
        self.assertEqual(m.scan(TOOLS, ["scraping"]), m.scan(TOOLS, ["scraping"]))


if __name__ == "__main__":
    unittest.main()
