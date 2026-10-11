"""S2.11 / c33.content tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c33/content.py"
_spec = importlib.util.spec_from_file_location("c33_content", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c33_content"] = m
_spec.loader.exec_module(m)


class Content(unittest.TestCase):
    def test_original_drafts_with_originality(self):
        out = m.draft(["gloss launch", "study setup"])
        self.assertEqual(out["draft_count"], 2)
        self.assertEqual(out["drafts"][0]["draft"],
                         "a field note on gloss launch: an original take, built from first-hand notes and her own angle")
        self.assertEqual(out["drafts"][1]["originality"], 1.0)

    def test_near_duplicate_refused(self):
        src = [{"id": "s1", "text": "a field note on gloss launch an original take built from first-hand notes and her own angle"}]
        with self.assertRaises(ValueError) as cm:
            m.draft(["gloss launch"], sources=src)
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_COPY")

    def test_posting_and_accounts_refused_via_guard(self):
        # Removing either guard call must fail this test.
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], post=True)
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_AUTOPOST")
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], create_accounts=True)
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")

    def test_one_account_per_platform_enforced(self):
        # enforced check: first official account per platform is a proposal, not prose
        out = m.draft(["t"], create_accounts=["instagram"], accounts=[])
        self.assertEqual(out["account_proposals"],
                         [{"platform": "instagram", "official": True}])
        # second account on the same platform refuses
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], create_accounts=["instagram"],
                    accounts=[{"platform": "instagram", "official": True}])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")
        # a fake/alt existing account also blocks a new one
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], create_accounts=["instagram"],
                    accounts=[{"platform": "instagram", "official": False}])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")
        # two new accounts on the same platform in one call refuse
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], create_accounts=["instagram", "instagram"], accounts=[])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_FAKEACCT")
        # different platforms pass
        out = m.draft(["t"], create_accounts=["instagram", "linkedin"], accounts=[])
        self.assertEqual(len(out["account_proposals"]), 2)
        # no account path: key absent
        self.assertNotIn("account_proposals", m.draft(["t"]))

    def test_themes_type_pins(self):
        # auditor survivors content-49/51/55/66/68/75
        for bad in (True, "x", 5, {"a": 1}):
            with self.assertRaises(ValueError) as cm:
                m.draft(bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:themes")
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"] * (m.MAX_THEMES + 1))
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_OVERSIZE")

    def test_sources_type_pins(self):
        # auditor survivors content-58/60/61/78/83/84
        for bad in (True, 5, {"a": 1}, "x"):
            with self.assertRaises(ValueError) as cm:
                m.draft(["t"], sources=bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:sources")
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], sources=[{"id": "a", "text": "t"}] * (m.MAX_SOURCES + 1))
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:sources")
        with self.assertRaises(ValueError) as cm:
            m.draft(["t"], sources=["x"])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:source")

    def test_create_accounts_type_pins(self):
        # auditor survivors content-82/86
        for bad in ("instagram", 5, {"a": 1}):
            with self.assertRaises(ValueError) as cm:
                m.draft(["t"], create_accounts=bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:create_accounts")

    def test_accounts_registry_validated_before_coercion(self):
        # auditor CORE defect: accounts=True crashed TypeError before validation
        for bad in (True, {"platform": "instagram"}, "x", 5):
            with self.assertRaises(ValueError) as cm:
                m.draft(["ai"], create_accounts=["x"], accounts=bad)
            self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_BAD_TYPE:existing")
        out = m.draft(["ai"], create_accounts=["x"], accounts=None)  # absent registry ok
        self.assertEqual(out["account_proposals"], [{"platform": "x", "official": True}])
        out = m.draft(["ai"], create_accounts=["x"], accounts=())
        self.assertEqual(len(out["account_proposals"]), 1)

    def test_originality_partial_overlap(self):
        # auditor survivors content-64/89: originality = round(1.0 - jaccard, 6)
        src = [{"id": "s1", "text": "a field note on gloss launch an original take extraword"}]
        out = m.draft(["gloss launch"], sources=src)
        self.assertEqual(out["drafts"][0]["originality"], 0.5)

    def test_bounds(self):
        with self.assertRaises(ValueError) as cm:
            m.draft([])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_EMPTY:themes")
        with self.assertRaises(ValueError) as cm:
            m.draft(["a\nc"])
        self.assertEqual(str(cm.exception), "SOCIAL_REFUSED_CONTROL_CHARS:theme")

    def test_determinism(self):
        self.assertEqual(m.draft(["a", "b"]), m.draft(["a", "b"]))


if __name__ == "__main__":
    unittest.main()
