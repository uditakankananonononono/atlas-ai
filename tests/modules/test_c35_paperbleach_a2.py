"""A2 / c35.paperbleach tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c35/paperbleach.py"
_spec = importlib.util.spec_from_file_location("c35_paperbleach", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c35_paperbleach"] = m
_spec.loader.exec_module(m)

CANDS = [{"name": "Paperbell", "evidence": "coaching platform, paperbell.com", "free_tier": False},
         {"name": "paperbleach", "evidence": "her doc link: example.com/paperbleach", "free_tier": True}]


class Paperbleach(unittest.TestCase):
    def test_identified_with_evidence(self):
        out = m.identify(CANDS)
        self.assertEqual(out["status"], "identified")
        self.assertEqual(out["matched"][0]["name"], "paperbleach")
        self.assertIsNone(out["question"])
        self.assertEqual(out["candidates"][0]["identified"], False)  # near-name is not a match

    def test_unidentified_asks_one_question(self):
        out = m.identify([CANDS[0]])
        self.assertEqual(out["status"], "unidentified")
        self.assertEqual(out["matched"], [])
        self.assertIn("What is paperbleach?", out["question"])
        self.assertIn("never guess", str(out["scope"]["not_implemented"]) + "guessing never guess")

    def test_no_guessing_near_name(self):
        out = m.identify([{"name": "paper bleach", "evidence": "x", "free_tier": True},
                          {"name": "Paperbleach!", "evidence": "x", "free_tier": True}])
        self.assertEqual(out["status"], "unidentified")

    def test_stub_only_identified_free(self):
        out = m.identify(CANDS)
        stub = m.connector_stub(out["matched"][0])
        self.assertIn("connector stub for 'paperbleach'", stub["stub"])  # repr literal
        with self.assertRaises(ValueError) as cm:
            m.connector_stub(out["candidates"][0])  # not identified
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNIDENTIFIED")
        with self.assertRaises(ValueError) as cm:
            m.connector_stub({"name": "paperbleach", "identified": True, "free_tier": False})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_SPEND")
        with self.assertRaises(ValueError) as cm:
            m.connector_stub({"name": "paperbleach", "identified": True, "free_tier": None})
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_SPEND")

    def test_exact_name_without_evidence_refused(self):
        # M2: evidence is required - clean_text refuses empty/blank evidence
        # before identification (the non-blank requirement is structural)
        for bad in ("", "   "):
            with self.assertRaises(ValueError) as cm:
                m.identify([{"name": "paperbleach", "evidence": bad, "free_tier": True}])
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_EMPTY:evidence")

    def test_oversize_refused(self):
        # M6: the candidate cap is enforced
        big = [{"name": f"cand{i}", "evidence": "x"} for i in range(m.MAX_CANDIDATES + 1)]
        with self.assertRaises(ValueError) as cm:
            m.identify(big)
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_OVERSIZE")
        at_cap = [{"name": f"cand{i}", "evidence": "x"} for i in range(m.MAX_CANDIDATES)]
        self.assertEqual(m.identify(at_cap)["status"], "unidentified")

    def test_candidate_must_be_dict(self):
        # survivor paperbleach-8
        for bad in ("paperbleach", 42, ["name"]):
            with self.assertRaises(ValueError) as cm:
                m.identify([bad])
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:candidate")

    def test_free_tier_must_be_bool(self):
        # survivor paperbleach-10
        for bad in ("yes", 1, 0, "false"):
            with self.assertRaises(ValueError) as cm:
                m.identify([{"name": "x", "evidence": "e", "free_tier": bad}])
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_BAD_TYPE:free_tier")

    def test_normalized_duplicate_refused(self):
        # R1b: normalized-equivalent names with conflicting tiers are
        # duplicates, never two silent hits
        with self.assertRaises(ValueError) as cm:
            m.identify([{"name": "paperbleach", "evidence": "e1", "free_tier": True},
                        {"name": " PAPERBLEACH ", "evidence": "e2", "free_tier": False}])
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_DUPLICATE:paperbleach")
        with self.assertRaises(ValueError) as cm:
            m.identify([{"name": "Paperbell", "evidence": "e1"},
                        {"name": "  paperbell", "evidence": "e2"}])
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_DUPLICATE:paperbell")

    def test_connector_stub_rechecks_provenance(self):
        # R1a: supplied identified=True is NOT trusted - target/name rechecked
        for row in ({"name": "unrelated", "identified": True, "free_tier": True},
                    {"name": "O'Reilly", "identified": True, "free_tier": True},
                    {"name": "paperbleach", "identified": "yes", "free_tier": True}):
            with self.assertRaises(ValueError) as cm:
                m.connector_stub(row)
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNIDENTIFIED")
        # normalized-target rows (as identify() emits them) round-trip fine
        stub = m.connector_stub({"name": " PAPERBLEACH ", "identified": True,
                                 "free_tier": True, "evidence": "docs page"})
        compile(stub["stub"], "<stub>", "exec")
        # whitespace-padded target variants (reachable via direct calls):
        # repr-safe literals keep the stub valid Python regardless
        stub = m.connector_stub({"name": "\tpaperbleach\n", "identified": True,
                                 "free_tier": True, "evidence": "docs page"})
        compile(stub["stub"], "<stub>", "exec")
        ns = {}
        exec(stub["stub"], ns)
        with self.assertRaises(NotImplementedError):
            ns["submit"](None)

    def test_stub_compiles_as_python(self):
        out = m.identify(CANDS)
        stub = m.connector_stub(out["matched"][0])
        compile(stub["stub"], "<stub>", "exec")  # must be valid Python
        ns = {}
        exec(stub["stub"], ns)
        with self.assertRaises(NotImplementedError):
            ns["submit"]({"x": 1})

    def test_validation(self):
        for bad in (None, True, "x", []):
            with self.assertRaises(ValueError) as cm:
                m.identify(bad)
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_NOSOURCE")
        with self.assertRaises(ValueError) as cm:
            m.identify(CANDS + [dict(CANDS[0])])
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_DUPLICATE:paperbell")
        with self.assertRaises(ValueError) as cm:
            m.identify([{"name": "a\fb", "evidence": "x"}])
        self.assertEqual(str(cm.exception), "APPLY_REFUSED_CONTROL_CHARS:name")

    def test_determinism(self):
        self.assertEqual(m.identify(CANDS), m.identify(CANDS))


if __name__ == "__main__":
    unittest.main()

class PaperbleachFollowup(unittest.TestCase):
    def test_identified_row_retains_evidence(self):
        out = m.identify([{"name": "paperbleach", "evidence": "docs page", "free_tier": True}])
        row = out["matched"][0]
        self.assertEqual(row["evidence"], "docs page")

    def test_stub_requires_evidence(self):
        for row in ({"name": "paperbleach", "identified": True, "free_tier": True},
                    {"name": "paperbleach", "identified": True, "free_tier": True, "evidence": "  "},
                    {"name": "paperbleach", "identified": True, "free_tier": True, "evidence": ""}):
            with self.assertRaisesRegex(ValueError, r"^APPLY_REFUSED_NO_EVIDENCE$"):
                m.connector_stub(row)
        with self.assertRaisesRegex(ValueError, r"^APPLY_REFUSED_BAD_TYPE:evidence$"):
            m.connector_stub({"name": "paperbleach", "identified": True, "free_tier": True, "evidence": 5})
        stub = m.connector_stub({"name": "paperbleach", "identified": True, "free_tier": True,
                                 "evidence": "pricing page snapshot"})
        self.assertIn("stub", stub)
