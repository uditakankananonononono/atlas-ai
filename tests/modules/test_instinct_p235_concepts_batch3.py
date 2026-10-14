"""P235 batch 3 concepts (text): red-first tests with independent oracles."""
from __future__ import annotations

import re
import unittest
import unicodedata

NAMES = ("token_histogram", "longest_common_prefix", "palindrome_check",
         "anagram_check_casefold", "camel_to_snake", "truncate_words",
         "strip_diacritics", "sentence_split_naive",
         "title_case_small_words", "csv_field_escape")


class Batch3Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch3 as m
        self.m = m

    def test_token_histogram(self):
        r = self.m.token_histogram("Hello, hello! World 42")
        oracle = {}
        for tok in re.findall(r"[a-z0-9]+", "Hello, hello! World 42".lower()):
            oracle[tok] = oracle.get(tok, 0) + 1
        self.assertEqual(dict(r), oracle)
        self.assertEqual(self.m.token_histogram(""), {})
        with self.assertRaises(ValueError):
            self.m.token_histogram(42)

    def test_longest_common_prefix(self):
        self.assertEqual(self.m.longest_common_prefix(["flower", "flow", "flight"]), "fl")
        self.assertEqual(self.m.longest_common_prefix(["a", "b"]), "")
        self.assertEqual(self.m.longest_common_prefix(["same", "same"]), "same")
        with self.assertRaises(ValueError):
            self.m.longest_common_prefix([])
        with self.assertRaises(ValueError):
            self.m.longest_common_prefix(["a", 1])

    def test_palindrome_check(self):
        self.assertTrue(self.m.palindrome_check("A man, a plan, a canal: Panama"))
        self.assertFalse(self.m.palindrome_check("hello"))
        self.assertTrue(self.m.palindrome_check(""))
        with self.assertRaises(ValueError):
            self.m.palindrome_check(None)

    def test_anagram_check_casefold(self):
        self.assertTrue(self.m.anagram_check_casefold("Listen", "Silent"))
        self.assertFalse(self.m.anagram_check_casefold("abc", "abd"))
        self.assertTrue(self.m.anagram_check_casefold("", ""))
        with self.assertRaises(ValueError):
            self.m.anagram_check_casefold("a", 1)

    def test_camel_to_snake(self):
        self.assertEqual(self.m.camel_to_snake("camelCaseName"), "camel_case_name")
        self.assertEqual(self.m.camel_to_snake("HTTPServer"), "http_server")
        self.assertEqual(self.m.camel_to_snake("simple"), "simple")
        with self.assertRaises(ValueError) as c:
            self.m.camel_to_snake("has space")
        self.assertTrue(str(c.exception).startswith("P235:camel_to_snake:bad_value"))

    def test_truncate_words(self):
        self.assertEqual(self.m.truncate_words("one two three four", 2), "one two")
        self.assertEqual(self.m.truncate_words("one two", 5), "one two")
        with self.assertRaises(ValueError):
            self.m.truncate_words("a b", 0)

    def test_strip_diacritics(self):
        r = self.m.strip_diacritics("Crème Brûlée")
        oracle = "".join(ch for ch in unicodedata.normalize("NFKD", "Crème Brûlée")
                         if not unicodedata.combining(ch))
        self.assertEqual(r, oracle)
        self.assertEqual(r, "Creme Brulee")
        with self.assertRaises(ValueError):
            self.m.strip_diacritics([])

    def test_sentence_split_naive(self):
        self.assertEqual(self.m.sentence_split_naive("One. Two! Three?"),
                         ["One", "Two", "Three"])
        self.assertEqual(self.m.sentence_split_naive("no terminator"),
                         ["no terminator"])
        self.assertEqual(self.m.sentence_split_naive(""), [])

    def test_title_case_small_words(self):
        small = ["and", "the", "of"]
        self.assertEqual(self.m.title_case_small_words("war and peace", small),
                         "War and Peace")
        self.assertEqual(self.m.title_case_small_words("the lord of the rings", small),
                         "The Lord of the Rings")
        with self.assertRaises(ValueError):
            self.m.title_case_small_words("ok", [""])

    def test_csv_field_escape(self):
        self.assertEqual(self.m.csv_field_escape("plain"), "plain")
        self.assertEqual(self.m.csv_field_escape('a,b'), '"a,b"')
        self.assertEqual(self.m.csv_field_escape('she said "hi"'), '"she said ""hi"""')
        self.assertEqual(self.m.csv_field_escape("line\nbreak"), '"line\nbreak"')
        with self.assertRaises(ValueError):
            self.m.csv_field_escape(1)

    def test_registry_covers_batch3(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        entries = {e["name"]: e for e in reg.ENTRIES if e["batch"] == 3}
        self.assertEqual(set(entries), set(NAMES))


    def test_camel_to_snake_refuses_trailing_newline(self):
        with self.assertRaises(ValueError) as c:
            self.m.camel_to_snake("camelCase\n")
        self.assertTrue(str(c.exception).startswith(
            "P235:camel_to_snake:bad_value:"))
        self.assertEqual(self.m.camel_to_snake("camelCase"), "camel_case")

    def test_text_caps(self):
        big = "a" * (self.m._MAX_TEXT + 1)
        for fn in (self.m.palindrome_check, self.m.strip_diacritics,
                   self.m.sentence_split_naive, self.m.csv_field_escape,
                   self.m.camel_to_snake, self.m.token_histogram):
            with self.assertRaises(ValueError) as c:
                fn(big)
            self.assertIn("too_many:", str(c.exception))
        with self.assertRaises(ValueError):
            self.m.anagram_check_casefold(big, "a")
        with self.assertRaises(ValueError):
            self.m.longest_common_prefix([big, "a"])
        with self.assertRaises(ValueError):
            self.m.truncate_words(big, 2)
        with self.assertRaises(ValueError):
            self.m.title_case_small_words(big, ["a"])

if __name__ == "__main__":
    unittest.main()
