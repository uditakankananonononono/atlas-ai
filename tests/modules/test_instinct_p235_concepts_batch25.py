"""P235 concepts batch 25 (241-250, format validators/transforms): red-first."""
from __future__ import annotations

import unittest


class Batch25Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch25 as m
        self.m = m

    def test_ipv4_check(self):
        self.assertTrue(self.m.ipv4_check("192.168.0.1"))
        self.assertFalse(self.m.ipv4_check("192.168.0.1\n"))
        self.assertTrue(self.m.ipv4_check("0.0.0.0"))
        self.assertTrue(self.m.ipv4_check("255.255.255.255"))
        for bad in ("256.1.1.1", "01.2.3.4", "1.2.3", "1.2.3.4.5",
                    "1.2.3.a", "1..2.3", "1.2.3.4 ", "-1.2.3.4"):
            self.assertFalse(self.m.ipv4_check(bad), bad)
        with self.assertRaises(ValueError):
            self.m.ipv4_check("١.2.3.4")
        with self.assertRaises(ValueError):
            self.m.ipv4_check(123)

    def test_mac_address_check(self):
        self.assertTrue(self.m.mac_address_check("aa:bb:cc:dd:ee:ff"))
        self.assertFalse(self.m.mac_address_check("aa:bb:cc:dd:ee:ff\n"))
        self.assertTrue(self.m.mac_address_check("AA-BB-CC-DD-EE-FF"))
        self.assertTrue(self.m.mac_address_check("00:11:22:33:44:55"))
        for bad in ("aa:bb:cc:dd:ee", "aa:bb:cc:dd:ee:ff:00",
                    "aa-bb:cc:dd:ee:ff", "gg:bb:cc:dd:ee:ff",
                    "a:bb:cc:dd:ee:ff", "aaa:bb:cc:dd:ee:ff"):
            self.assertFalse(self.m.mac_address_check(bad), bad)

    def test_uuid_shape_check(self):
        self.assertTrue(self.m.uuid_shape_check(
            "123e4567-e89b-12d3-a456-426614174000"))
        self.assertFalse(self.m.uuid_shape_check(
            "123e4567-e89b-12d3-a456-426614174000\n"))
        self.assertTrue(self.m.uuid_shape_check(
            "123E4567-E89B-12D3-A456-426614174000"))
        for bad in ("123e4567-e89b-12d3-a456-42661417400",
                    "123e4567-e89b-12d3-a456-4266141740000",
                    "123e4567e89b-12d3-a456-426614174000",
                    "123g4567-e89b-12d3-a456-426614174000", ""):
            self.assertFalse(self.m.uuid_shape_check(bad), bad)

    def test_hex_color_check(self):
        self.assertTrue(self.m.hex_color_check("#fff"))
        self.assertFalse(self.m.hex_color_check("#fff\n"))
        self.assertTrue(self.m.hex_color_check("#FFaA00"))
        self.assertTrue(self.m.hex_color_check("#000000"))
        for bad in ("#ffff", "#ff", "fff", "#ggg", "#", "##fff"):
            self.assertFalse(self.m.hex_color_check(bad), bad)

    def test_email_shape_check(self):
        self.assertTrue(self.m.email_shape_check("a@b.co"))
        self.assertFalse(self.m.email_shape_check("a@b.co\n"))
        self.assertTrue(self.m.email_shape_check("first.last+tag@x.io"))
        self.assertTrue(self.m.email_shape_check("a@b.c"))
        for bad in ("a@b", "a@@b.co", "@b.co", "a@", "a b@c.co",
                    "a@b..co", "a@.co", "a@b."):
            self.assertFalse(self.m.email_shape_check(bad), bad)
        with self.assertRaises(ValueError):
            self.m.email_shape_check("a@b.c\u00e9")

    def test_isbn13_check(self):
        self.assertTrue(self.m.isbn13_check("9780306406157"))
        self.assertFalse(self.m.isbn13_check("9780306406158"))
        self.assertFalse(self.m.isbn13_check("978030640615"))
        self.assertFalse(self.m.isbn13_check("97803064061570"))
        self.assertFalse(self.m.isbn13_check("978030640615a"))
        # non-ASCII digits refuse with the exact coded message
        with self.assertRaises(ValueError) as c:
            self.m.isbn13_check("٩٧٨٠٣٠٦٤٠٦١٥٧")
        self.assertEqual(str(c.exception),
                         "P235:isbn13_check:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.isbn13_check(9780306406157)
        self.assertEqual(str(c.exception),
                         "P235:isbn13_check:bad_type:text")
        with self.assertRaises(ValueError) as c:
            self.m.isbn13_check(True)
        self.assertEqual(str(c.exception),
                         "P235:isbn13_check:bad_type:text")
        with self.assertRaises(ValueError) as c:
            self.m.isbn13_check("9" * 10_001)
        self.assertEqual(str(c.exception),
                         "P235:isbn13_check:too_many:text")

    def test_mask_digits_keep_last(self):
        self.assertEqual(self.m.mask_digits_keep_last("1234-5678-9012", 4),
                         "****-****-9012")
        self.assertEqual(self.m.mask_digits_keep_last("1234", 0), "****")
        self.assertEqual(self.m.mask_digits_keep_last("12", 4), "12")
        self.assertEqual(self.m.mask_digits_keep_last("no digits", 2),
                         "no digits")
        with self.assertRaises(ValueError):
            self.m.mask_digits_keep_last("123", -1)
        # ASCII digit discriminator: non-ASCII digit-like characters are
        # not digits here and pass through untouched
        self.assertEqual(self.m.mask_digits_keep_last("٩123", 1), "٩**3")
        self.assertEqual(self.m.mask_digits_keep_last("५5", 1), "५5")
        with self.assertRaises(ValueError) as c:
            self.m.mask_digits_keep_last("1234", True)
        self.assertEqual(str(c.exception),
                         "P235:mask_digits_keep_last:bad_type:keep")

    def test_redact_words(self):
        self.assertEqual(self.m.redact_words("the cat sat", ["cat"]),
                         "the [REDACTED] sat")
        self.assertEqual(self.m.redact_words("cat Cat cat", ["cat"]),
                         "[REDACTED] Cat [REDACTED]")
        self.assertEqual(self.m.redact_words("a b a b", ["a", "b"]),
                         "[REDACTED] [REDACTED] [REDACTED] [REDACTED]")
        self.assertEqual(self.m.redact_words("", ["a"]), "")
        # tabs and newlines separate tokens and are preserved
        self.assertEqual(self.m.redact_words("the\tcat\nsat", ["cat"]),
                         "the\t[REDACTED]\nsat")
        # a word over the per-word cap refuses
        with self.assertRaises(ValueError) as c:
            self.m.redact_words("text", ["x" * 1_001])
        self.assertEqual(str(c.exception),
                         "P235:redact_words:too_big:words[0]")
        self.assertEqual(self.m.redact_words(
            "x" * 1_000, ["x" * 1_000]), "[REDACTED]")
        with self.assertRaises(ValueError):
            self.m.redact_words("text", [""])
        with self.assertRaises(ValueError):
            self.m.redact_words("text", ["a b"])
        # strip boundary: word entries with edge or inner whitespace
        # refuse with the exact coded message
        for w in (" cat", "cat ", "c\tat"):
            with self.assertRaises(ValueError, msg=w) as c:
                self.m.redact_words("text", [w])
            self.assertEqual(str(c.exception),
                             "P235:redact_words:bad_value:words[0]")
        # leading/trailing whitespace in text is preserved exactly while
        # only whole interior tokens are replaced
        self.assertEqual(self.m.redact_words("  cat sat  ", ["cat"]),
                         "  [REDACTED] sat  ")
        self.assertEqual(self.m.redact_words("\tcat\n", ["cat"]),
                         "\t[REDACTED]\n")
        self.assertEqual(self.m.redact_words("catty cat", ["cat"]),
                         "catty [REDACTED]")
        with self.assertRaises(ValueError) as c:
            self.m.redact_words("text", [True])
        self.assertEqual(str(c.exception),
                         "P235:redact_words:bad_type:words[0]")

    def test_collapse_whitespace_runs(self):
        self.assertEqual(self.m.collapse_whitespace_runs("a  b\t\nc"),
                         "a b c")
        self.assertEqual(self.m.collapse_whitespace_runs(""), "")
        self.assertEqual(self.m.collapse_whitespace_runs("   "), "")
        self.assertEqual(self.m.collapse_whitespace_runs("  x  y "), "x y")
        self.assertEqual(self.m.collapse_whitespace_runs("clean"), "clean")
        with self.assertRaises(ValueError) as c:
            self.m.collapse_whitespace_runs(True)
        self.assertEqual(str(c.exception),
                         "P235:collapse_whitespace_runs:bad_type:text")

    def test_palindrome_sentence_check(self):
        self.assertTrue(self.m.palindrome_sentence_check(
            "A man, a plan, a canal: Panama"))
        self.assertFalse(self.m.palindrome_sentence_check("race a car"))
        self.assertTrue(self.m.palindrome_sentence_check(""))
        self.assertTrue(self.m.palindrome_sentence_check("12321"))
        self.assertTrue(self.m.palindrome_sentence_check("Madam"))
        self.assertFalse(self.m.palindrome_sentence_check("123212"))
        # ASCII filter discriminator: non-ASCII letters are removed, so
        # "ab" remains and these are NOT palindromes; without the filter
        # the Unicode letters would be kept and each would read as one
        self.assertFalse(self.m.palindrome_sentence_check("éabé"))
        self.assertFalse(self.m.palindrome_sentence_check("ßabß"))
        self.assertFalse(self.m.palindrome_sentence_check("ДabД"))


if __name__ == "__main__":
    unittest.main()
