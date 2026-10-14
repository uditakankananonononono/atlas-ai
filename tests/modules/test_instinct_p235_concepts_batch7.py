"""P235 batch 7 concepts (61-70): red-first, independent oracles."""
from __future__ import annotations

import unittest

NAMES = ("utf8_byte_length", "ascii_only_check", "line_count",
         "word_wrap_width", "indent_lines", "dedent_block", "reverse_words",
         "swap_case", "count_substring_overlapping", "roman_numeral_parse")


class Batch7Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch7 as m
        self.m = m

    def test_utf8_byte_length(self):
        self.assertEqual(self.m.utf8_byte_length("héllo"), len("héllo".encode("utf-8")))
        self.assertEqual(self.m.utf8_byte_length(""), 0)
        with self.assertRaises(ValueError):
            self.m.utf8_byte_length(b"bytes")

    def test_ascii_only_check(self):
        self.assertTrue(self.m.ascii_only_check("plain 123"))
        self.assertFalse(self.m.ascii_only_check("café"))
        with self.assertRaises(ValueError):
            self.m.ascii_only_check(12)

    def test_line_count(self):
        self.assertEqual(self.m.line_count("a\nb\nc"), 3)
        self.assertEqual(self.m.line_count(""), 0)
        self.assertEqual(self.m.line_count("one"), 1)

    def test_word_wrap_width(self):
        r = self.m.word_wrap_width("one two three four five", 11)
        self.assertEqual(r, ["one two", "three four", "five"])
        oracle = []
        line = ""
        for w in "one two three four five".split():
            cand = (line + " " + w).strip()
            if len(cand) <= 11:
                line = cand
            else:
                oracle.append(line)
                line = w
        oracle.append(line)
        self.assertEqual(r, oracle)
        with self.assertRaises(ValueError):
            self.m.word_wrap_width("supercalifragilistic", 5)
        with self.assertRaises(ValueError):
            self.m.word_wrap_width("ok", 0)

    def test_indent_lines(self):
        self.assertEqual(self.m.indent_lines("a\nb", 2), "  a\n  b")
        self.assertEqual(self.m.indent_lines("", 2), "")
        with self.assertRaises(ValueError):
            self.m.indent_lines("a", -1)

    def test_dedent_block(self):
        self.assertEqual(self.m.dedent_block("    a\n    b"), "a\nb")
        self.assertEqual(self.m.dedent_block("  a\n    b"), "a\n  b")
        self.assertEqual(self.m.dedent_block("a\nb"), "a\nb")

    def test_reverse_words(self):
        self.assertEqual(self.m.reverse_words("one two three"), "three two one")
        self.assertEqual(self.m.reverse_words("  spaced   out "), "out spaced")

    def test_swap_case(self):
        self.assertEqual(self.m.swap_case("aBc DeF"), "AbC dEf")
        oracle = "".join(ch.lower() if ch.isupper() else ch.upper() for ch in "aBc DeF")
        self.assertEqual(self.m.swap_case("aBc DeF"), oracle)

    def test_count_substring_overlapping(self):
        self.assertEqual(self.m.count_substring_overlapping("aaaa", "aa"), 3)
        self.assertEqual(self.m.count_substring_overlapping("abc", "x"), 0)
        oracle = sum(1 for i in range(len("aaaa") - 1) if "aaaa"[i:i + 2] == "aa")
        self.assertEqual(self.m.count_substring_overlapping("aaaa", "aa"), oracle)
        with self.assertRaises(ValueError):
            self.m.count_substring_overlapping("abc", "")

    def test_roman_numeral_parse(self):
        self.assertEqual(self.m.roman_numeral_parse("MCMXCIV"), 1994)
        self.assertEqual(self.m.roman_numeral_parse("XLII"), 42)
        self.assertEqual(self.m.roman_numeral_parse("MMMCMXCIX"), 3999)
        for bad in ("IIII", "VX", "IC", "MMMM", "hello", "", "MMMCMXCIXX"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.roman_numeral_parse(bad)

    def test_registry_covers_batch7(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 7}
        self.assertEqual(set(entries), set(NAMES))
        self.assertGreaterEqual(reg.IMPLEMENTED_SO_FAR, len(reg.ENTRIES))


    def test_max_text_is_explicit_literal(self):
        self.assertEqual(self.m._MAX_TEXT, 100_000)

    def test_roman_refuses_trailing_newline(self):
        with self.assertRaises(ValueError):
            self.m.roman_numeral_parse("IV\n")
        self.assertEqual(self.m.roman_numeral_parse("IV"), 4)
        self.assertEqual(self.m.roman_numeral_parse("MMXXVI"), 2026)

    def test_indent_lines_caps(self):
        with self.assertRaises(ValueError) as c:
            self.m.indent_lines("a", 10 ** 9)
        self.assertEqual(str(c.exception),
                         "P235:indent_lines:too_many:spaces")
        text = "abcd\n" * 20000  # 100_000 chars, 20_001 lines after split
        with self.assertRaises(ValueError) as c2:
            self.m.indent_lines(text, 8)
        self.assertEqual(str(c2.exception),
                         "P235:indent_lines:too_many:output")
        self.assertEqual(self.m.indent_lines("a\nb", 2), "  a\n  b")
        self.assertEqual(self.m.indent_lines("a", 0), "a")

if __name__ == "__main__":
    unittest.main()
