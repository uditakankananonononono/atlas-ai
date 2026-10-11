"""c30.policy.clean_text retro repair pins: Cf refusal, cap-first ordering, strict str type."""
import sys
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.modules.c30 import policy  # noqa: E402


def code(*a, **k):
    try:
        policy.clean_text(*a, **k)
    except ValueError as e:
        return str(e)
    return None


class FormatChars(unittest.TestCase):
    def test_cf_characters_refused(self):
        for ch in ("\u00ad", "\u2060", "\u200b", "\u200c", "\u200d", "\u200e", "\ufeff", "\u202e", "\u2066"):
            self.assertEqual(code("ab" + ch + "cd", "T", "f", 50), "T_REFUSED_CONTROL_CHARS:f", hex(ord(ch)))
            self.assertEqual(code("ab" + ch + "cd", "T", "f", 50, allow_ws=True), "T_REFUSED_CONTROL_CHARS:f", hex(ord(ch)))

    def test_category_tuple_lists_cf(self):
        self.assertEqual(set(policy.FORBIDDEN_CATEGORIES), {"Cc", "Zl", "Zp", "Cf"})

    def test_allow_ws_carve_out_is_lf_cr_tab_only(self):
        self.assertEqual(policy.clean_text("a\nb\rc\td", "T", "f", 50, allow_ws=True), "a\nb\rc\td")
        for ch in ("\x0b", "\x0c", "\x85", "\u2028", "\u2029", "\x00"):
            self.assertEqual(code("a" + ch + "b", "T", "f", 50, allow_ws=True), "T_REFUSED_CONTROL_CHARS:f", hex(ord(ch)))
        self.assertEqual(code("a\nb", "T", "f", 50), "T_REFUSED_CONTROL_CHARS:f")

    def test_plain_text_unicode_still_accepted(self):
        for ok in ("Acme Corp", "caf\u00e9", "\u65e5\u672c\u8a9e", "a b", "\u00a0x"):
            self.assertEqual(policy.clean_text(ok, "T", "f", 50), ok)


class CapFirst(unittest.TestCase):
    def test_over_cap_refused_as_too_long_before_blank_or_control_checks(self):
        self.assertEqual(code("\x00" * 10, "T", "f", 5), "T_REFUSED_TEXT_TOO_LONG:f")
        self.assertEqual(code(" " * 10, "T", "f", 5), "T_REFUSED_TEXT_TOO_LONG:f")
        self.assertEqual(code("\u200b" * 10, "T", "f", 5), "T_REFUSED_TEXT_TOO_LONG:f")
        self.assertEqual(code(" " * 10, "T", "f", 5, allow_blank=True), "T_REFUSED_TEXT_TOO_LONG:f")

    def test_over_cap_never_reaches_category_scan(self):
        calls = []
        real = policy.unicodedata

        class Spy(types.SimpleNamespace):
            def category(self, c):
                calls.append(c)
                return real.category(c)
        policy.unicodedata = Spy()
        try:
            self.assertEqual(code("x" * 100, "T", "f", 5), "T_REFUSED_TEXT_TOO_LONG:f")
            self.assertEqual(calls, [])
            self.assertEqual(policy.clean_text("abcde", "T", "f", 5), "abcde")
            self.assertEqual(len(calls), 5)
        finally:
            policy.unicodedata = real

    def test_cap_boundary_is_raw_length(self):
        self.assertEqual(policy.clean_text("a" * 5, "T", "f", 5), "a" * 5)
        self.assertEqual(code("a" * 6, "T", "f", 5), "T_REFUSED_TEXT_TOO_LONG:f")
        # padding counts against the cap: raw length, not stripped length
        self.assertEqual(code("  ab  ", "T", "f", 5), "T_REFUSED_TEXT_TOO_LONG:f")

    def test_type_first_then_cap_then_blank_then_control(self):
        self.assertEqual(code(None, "T", "f", 5), "T_REFUSED_BAD_TYPE:f")
        self.assertEqual(code("", "T", "f", 5), "T_REFUSED_EMPTY:f")
        self.assertEqual(code("\x00", "T", "f", 5), "T_REFUSED_CONTROL_CHARS:f")
        self.assertEqual(code("", "T", "f", 5, allow_blank=True), None)


class StrictType(unittest.TestCase):
    def test_str_subclass_refused(self):
        class S(str):
            pass

        class Evil(str):
            def strip(self, *a):
                raise AssertionError("subclass method ran")

            def __len__(self):
                raise AssertionError("subclass method ran")
        for v in (S("ok"), Evil("ok")):
            self.assertEqual(code(v, "T", "f", 50), "T_REFUSED_BAD_TYPE:f")

    def test_non_str_refused(self):
        for v in (True, False, 1, 1.5, None, b"ab", ["a"], {"a": 1}, bytearray(b"a")):
            self.assertEqual(code(v, "T", "f", 50), "T_REFUSED_BAD_TYPE:f", repr(v))

    def test_plain_str_returned_as_is(self):
        self.assertIs(type(policy.clean_text("ok", "T", "f", 50)), str)


class ExecutionOrder(unittest.TestCase):
    """Resource-order contract: oversized exact-str input never reaches strip or the scan."""

    @staticmethod
    def trace(value, limit, **kw):
        events = []

        def prof(frame, event, arg):
            if event == "c_call":
                events.append(getattr(arg, "__name__", ""))
        sys.setprofile(prof)
        try:
            try:
                policy.clean_text(value, "T", "f", limit, **kw)
            except ValueError:
                pass
        finally:
            sys.setprofile(None)
        return events

    def test_strip_never_entered_for_oversized_exact_str(self):
        for v in ("x" * 100, " " * 100, "\x00" * 100, "\u200b" * 100, "  ab  "):
            for kw in ({}, {"allow_blank": True}, {"allow_ws": True}):
                ev = self.trace(v, 5, **kw)
                self.assertNotIn("strip", ev, (v[:3], kw))
                self.assertNotIn("category", ev, (v[:3], kw))

    def test_in_cap_value_does_reach_strip_after_len(self):
        ev = self.trace("abc", 5)
        self.assertIn("strip", ev)
        self.assertIn("category", ev)
        self.assertLess(ev.index("len"), ev.index("strip"))
        self.assertLess(ev.index("strip"), ev.index("category"))

    def test_wrong_type_never_reaches_len_or_strip(self):
        for v in (None, 5, b"abc", True):
            ev = self.trace(v, 5)
            self.assertNotIn("strip", ev)
            self.assertNotIn("len", ev)


if __name__ == "__main__":
    unittest.main()
