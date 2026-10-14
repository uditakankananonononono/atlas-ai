"""P235 concepts batch 27 (261-270, letter ciphers/encodings): red-first."""
from __future__ import annotations

import unittest


class Batch27Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch27 as m
        self.m = m

    def test_atbash_cipher(self):
        self.assertEqual(self.m.atbash_cipher("abcxyz"), "zyxcba")
        self.assertEqual(self.m.atbash_cipher("AbC"), "ZyX")
        self.assertEqual(self.m.atbash_cipher("a-z!"), "z-a!")
        self.assertEqual(self.m.atbash_cipher(""), "")
        with self.assertRaises(ValueError):
            self.m.atbash_cipher("caf\u00e9")

    def test_a1z26_encode(self):
        self.assertEqual(self.m.a1z26_encode("abc"), "1-2-3")
        self.assertEqual(self.m.a1z26_encode("Az"), "1-26")
        with self.assertRaises(ValueError):
            self.m.a1z26_encode("")
        with self.assertRaises(ValueError):
            self.m.a1z26_encode("a1")
        with self.assertRaises(ValueError):
            self.m.a1z26_encode("a b")

    def test_a1z26_decode(self):
        self.assertEqual(self.m.a1z26_decode("1-2-3"), "abc")
        self.assertEqual(self.m.a1z26_decode("26"), "z")
        self.assertEqual(self.m.a1z26_decode("1-26-1"), "aza")
        for bad in ("", "0", "27", "1-", "-1", "a", "1--2", "01"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.a1z26_decode(bad)
        # a huge digit run refuses with the coded message, not a leaked
        # library error: parts are limited to two ASCII digits
        with self.assertRaises(ValueError) as c:
            self.m.a1z26_decode("9" * 5_000)
        self.assertEqual(str(c.exception),
                         "P235:a1z26_decode:bad_value:text")
        # empty input refuses with the exact coded message
        with self.assertRaises(ValueError) as c:
            self.m.a1z26_decode("")
        self.assertEqual(str(c.exception),
                         "P235:a1z26_decode:bad_value:text")
        with self.assertRaises(ValueError):
            self.m.a1z26_decode("٩")
        # direct discriminators for the ASCII digit guard
        for uni in ("۵", "²"):
            self.assertTrue(uni.isdigit(), uni)
            with self.assertRaises(ValueError, msg=uni) as c:
                self.m.a1z26_decode(uni)
            self.assertEqual(str(c.exception),
                             "P235:a1z26_decode:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.a1z26_decode(True)
        self.assertEqual(str(c.exception),
                         "P235:a1z26_decode:bad_type:text")

    def test_scrabble_score(self):
        self.assertEqual(self.m.scrabble_score("cabbage"), 14)
        self.assertEqual(self.m.scrabble_score("quiz"), 22)
        self.assertEqual(self.m.scrabble_score(""), 0)
        self.assertEqual(self.m.scrabble_score("AEIOULNSTR"), 10)
        with self.assertRaises(ValueError):
            self.m.scrabble_score("a1")
        with self.assertRaises(ValueError) as c:
            self.m.scrabble_score(True)
        self.assertEqual(str(c.exception),
                         "P235:scrabble_score:bad_type:text")

    def test_vigenere_encode(self):
        self.assertEqual(self.m.vigenere_encode("ATTACKATDAWN", "LEMON"),
                         "LXFOPVEFRNHR")
        self.assertEqual(self.m.vigenere_encode("attackatdawn", "lemon"),
                         "LXFOPVEFRNHR")
        # empty text and empty key refuse with exact coded messages
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_encode("", "KEY")
        self.assertEqual(str(c.exception),
                         "P235:vigenere_encode:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_encode("ABC", "")
        self.assertEqual(str(c.exception),
                         "P235:vigenere_encode:bad_value:key")
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_encode(True, "KEY")
        self.assertEqual(str(c.exception),
                         "P235:vigenere_encode:bad_type:text")
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_encode("ABC", True)
        self.assertEqual(str(c.exception),
                         "P235:vigenere_encode:bad_value:key")
        with self.assertRaises(ValueError):
            self.m.vigenere_encode("AB C", "KEY")
        with self.assertRaises(ValueError):
            self.m.vigenere_encode("ABC", "K3Y")
        # key length cap: 1,000 chars passes, 1,001 refuses with a code
        self.assertEqual(len(self.m.vigenere_encode("ABC", "K" * 1_000)),
                         3)
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_encode("ABC", "K" * 1_001)
        self.assertEqual(str(c.exception),
                         "P235:vigenere_encode:too_big:key")

    def test_vigenere_decode(self):
        self.assertEqual(self.m.vigenere_decode("LXFOPVEFRNHR", "LEMON"),
                         "ATTACKATDAWN")
        self.assertEqual(self.m.vigenere_decode("lxfopvefrnhr", "lemon"),
                         "ATTACKATDAWN")
        with self.assertRaises(ValueError):
            self.m.vigenere_decode("AB C", "KEY")
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_decode("", "KEY")
        self.assertEqual(str(c.exception),
                         "P235:vigenere_decode:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.vigenere_decode("ABC", "")
        self.assertEqual(str(c.exception),
                         "P235:vigenere_decode:bad_value:key")

    def test_nato_phonetic_render(self):
        self.assertEqual(self.m.nato_phonetic_render("ab"), "alfa bravo")
        self.assertEqual(self.m.nato_phonetic_render("Z"), "zulu")
        with self.assertRaises(ValueError):
            self.m.nato_phonetic_render("")
        with self.assertRaises(ValueError):
            self.m.nato_phonetic_render("a1")

    def test_t9_multitap_digits(self):
        self.assertEqual(self.m.t9_multitap_digits("hello"),
                         "44 33 555 555 666")
        self.assertEqual(self.m.t9_multitap_digits("a"), "2")
        self.assertEqual(self.m.t9_multitap_digits("pqrs"), "7 77 777 7777")
        with self.assertRaises(ValueError):
            self.m.t9_multitap_digits("hi!")
        with self.assertRaises(ValueError):
            self.m.t9_multitap_digits("")

    def test_alternating_case(self):
        self.assertEqual(self.m.alternating_case("hello"), "hElLo")
        # parity is by character index, spaces included
        self.assertEqual(self.m.alternating_case("a b"), "a b")
        self.assertEqual(self.m.alternating_case("a bc"), "a bC")
        self.assertEqual(self.m.alternating_case(""), "")
        self.assertEqual(self.m.alternating_case("ABC"), "aBc")

    def test_disemvowel_text(self):
        self.assertEqual(self.m.disemvowel_text("hello world"), "hll wrld")
        self.assertEqual(self.m.disemvowel_text("aeiou"), "")
        self.assertEqual(self.m.disemvowel_text("sky"), "sky")
        self.assertEqual(self.m.disemvowel_text("AEIOUbc"), "bc")


if __name__ == "__main__":
    unittest.main()
