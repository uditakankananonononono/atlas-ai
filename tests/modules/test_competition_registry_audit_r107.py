"""Row 107 audit tests."""
import importlib.util, pathlib, sys, unittest

_B = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m01_opportunity_discovery"
_s = importlib.util.spec_from_file_location("audit_r107", _B / "competition_registry_audit_r107.py")
m = importlib.util.module_from_spec(_s); sys.modules["audit_r107"] = m; _s.loader.exec_module(m)
_s2 = importlib.util.spec_from_file_location("u37", _B / "high_school_competitions_u37.py")
u = importlib.util.module_from_spec(_s2); sys.modules["u37"] = u; _s2.loader.exec_module(u)


def row(k, **kw):
    d = {"key": k, "category": "physics", "source_url": "https://x.org/" + k, "checked_at": "2026-10-11"}
    d.update(kw)
    return d


class Audit(unittest.TestCase):
    def test_flags(self):
        out = m.audit([row("a"), row("a"), row("b", source_url="http://x.org/b"),
                       row("c", checked_at="2026-08-01")], "2026-10-12")
        issues = sorted(f["issue"] for f in out["findings"])
        self.assertEqual(issues, ["DUPLICATE_KEY", "DUPLICATE_SOURCE_URL", "SOURCE_NOT_HTTPS", "STALE_SOURCE_CHECK"])
        self.assertFalse(out["clean"])

    def test_real_registry_today(self):
        out = m.audit(list(u.COMPETITIONS), "2026-10-12")
        self.assertEqual(out["rows"], len(u.COMPETITIONS))
        self.assertTrue(out["clean"], out["findings"])
        self.assertIn("not established", out["coverage_statement"])

    def test_real_registry_goes_stale(self):
        out = m.audit(list(u.COMPETITIONS), "2026-12-30")
        self.assertTrue(any(f["issue"] == "STALE_SOURCE_CHECK" for f in out["findings"]))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            m.audit([], "nope")


if __name__ == "__main__":
    unittest.main()
