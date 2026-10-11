"""S2.5 / c32.image_brief tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/image_brief.py"
_spec = importlib.util.spec_from_file_location("c32_image_brief", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_image_brief"] = m
_spec.loader.exec_module(m)


class ImageBrief(unittest.TestCase):
    def test_brief_labeled_ai_generated(self):
        out = m.brief({"subject": "strawberry lip gloss", "style": "glossy-editorial"})
        self.assertIn("strawberry lip gloss", out["prompt"])
        self.assertIn("clearly AI-generated", out["prompt"])
        self.assertEqual(out["labels"], {"ai_generated": True, "no_deceptive_realism": True})
        self.assertEqual(out["style_board"]["style"], "glossy-editorial")

    def test_default_style(self):
        self.assertEqual(m.brief({"subject": "candle"})["style_board"]["style"], "soft-pastel")

    def test_deceptive_realism_refused(self):
        for flag in ("claim_real", "market_as_real"):
            with self.assertRaises(ValueError) as cm:
                m.brief({"subject": "x", flag: True})
            self.assertEqual(str(cm.exception), "TREND_REFUSED_DECEPTIVE")

    def test_bad_inputs(self):
        with self.assertRaises(ValueError) as cm:
            m.brief({"subject": "a\u2028b"})
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:subject")
        with self.assertRaises(ValueError) as cm:
            m.brief({"subject": "x", "style": "photoreal-real-person"})
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_STYLE:photoreal-real-person")
        with self.assertRaises(ValueError) as cm:
            m.brief(None)
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:concept")

    def test_determinism(self):
        self.assertEqual(m.brief({"subject": "x"}), m.brief({"subject": "x"}))


class ImageBriefPins(unittest.TestCase):
    def test_audience_validated_when_present(self):
        # auditor survivor image_brief-58
        for bad in (123, ["x"], {"a": 1}, True):
            with self.assertRaises(ValueError) as cm:
                m.brief({"subject": "s", "audience": bad})
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:audience")
        out = m.brief({"subject": "s"})  # absent audience is fine
        self.assertIsNone(out["style_board"]["audience"])


if __name__ == "__main__":
    unittest.main()
