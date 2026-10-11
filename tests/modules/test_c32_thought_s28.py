"""S2.8 / c32.thought tests. Hermetic, stdlib unittest."""
import importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/c32/thought.py"
_spec = importlib.util.spec_from_file_location("c32_thought", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c32_thought"] = m
_spec.loader.exec_module(m)


class Thought(unittest.TestCase):
    def test_move_tagging_and_totals(self):
        out = m.analyze([{"id": "d1", "kind": "transcript",
                          "text": "Work from first principles. It is like a lever. A feedback loop emerges."},
                         {"id": "d2", "kind": "lyrics", "text": "A story of a journey."}])
        self.assertEqual(out["doc_count"], 2)
        self.assertEqual(out["move_totals"]["first_principles"], 1)
        self.assertEqual(out["move_totals"]["analogy"], 1)
        self.assertEqual(out["move_totals"]["systems"], 3)  # feedback, loop, emerges
        self.assertEqual(out["docs"][0]["id"], "d1")  # higher move_total first

    def test_audio_refused_with_recorded_limit(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "a", "kind": "audio", "text": "bytes"}])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_AUDIO")
        out = m.analyze([{"id": "d", "text": "plain"}])
        self.assertIn("audio transcription (no bundled ASR offline)",
                      out["scope"]["not_implemented"])

    def test_bad_inputs(self):
        with self.assertRaises(ValueError) as cm:
            m.analyze([])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_EMPTY:texts")
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "x", "kind": "video", "text": "t"}])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_KIND:video")
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "x\x00", "text": "t"}])
        self.assertEqual(str(cm.exception), "TREND_REFUSED_CONTROL_CHARS:id")

    def test_determinism(self):
        a = m.analyze([{"id": "d", "text": "why is this so? from scratch."}])
        self.assertEqual(a, m.analyze([{"id": "d", "text": "why is this so? from scratch."}]))


class ThoughtPins(unittest.TestCase):
    def test_texts_type_pins(self):
        # auditor survivors thought-36/38/39/41
        for bad in (True, "x", 5, {"a": 1}):
            with self.assertRaises(ValueError) as cm:
                m.analyze(bad)
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:texts")
        with self.assertRaises(ValueError) as cm:
            m.analyze([{"id": "a", "text": "t"}] * (m.MAX_TEXTS + 1))
        self.assertEqual(str(cm.exception), "TREND_REFUSED_OVERSIZE")
        for bad in ("x", 5, None, True):
            with self.assertRaises(ValueError) as cm:
                m.analyze([bad])
            self.assertEqual(str(cm.exception), "TREND_REFUSED_BAD_TYPE:text")


if __name__ == "__main__":
    unittest.main()
