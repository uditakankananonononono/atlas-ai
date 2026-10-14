"""P235 concepts batch 21 (201-210, text metrics/transforms): red-first tests."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch21Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch21 as m
        self.m = m

    def test_syllable_estimate(self):
        self.assertEqual(self.m.syllable_estimate("hello"), 2)
        self.assertEqual(self.m.syllable_estimate("beautiful"), 3)
        self.assertEqual(self.m.syllable_estimate("rhythm"), 0)
        self.assertEqual(self.m.syllable_estimate(""), 0)
        with self.assertRaises(ValueError) as c:
            self.m.syllable_estimate("x" * 10_001)
        self.assertEqual(str(c.exception),
                         "P235:syllable_estimate:too_many:text")
        self.assertEqual(self.m.syllable_estimate("x" * 10_000), 0)

    def test_unique_bigram_count(self):
        self.assertEqual(self.m.unique_bigram_count("abca"), 3)
        self.assertEqual(self.m.unique_bigram_count(""), 0)
        self.assertEqual(self.m.unique_bigram_count("a"), 0)
        self.assertEqual(self.m.unique_bigram_count("aaaa"), 1)

    def test_vowel_consonant_ratio_exact(self):
        self.assertEqual(self.m.vowel_consonant_ratio_exact("abc"), Fraction(1, 2))
        self.assertEqual(self.m.vowel_consonant_ratio_exact("AEIOUbcdfg"),
                         Fraction(1, 1))
        with self.assertRaises(ValueError) as c:
            self.m.vowel_consonant_ratio_exact("aeiou")
        self.assertEqual(str(c.exception),
                         "P235:vowel_consonant_ratio_exact:no_consonants")

    def test_repeated_word_count(self):
        self.assertEqual(self.m.repeated_word_count("the cat and the dog"), 1)
        self.assertEqual(self.m.repeated_word_count("no repeats here"), 0)
        self.assertEqual(self.m.repeated_word_count("a a a B b"), 2)
        self.assertEqual(self.m.repeated_word_count(""), 0)

    def test_punctuation_count(self):
        self.assertEqual(self.m.punctuation_count("Hello, World!"), 2)
        self.assertEqual(self.m.punctuation_count("plain"), 0)
        self.assertEqual(self.m.punctuation_count("..."), 3)

    def test_line_length_max(self):
        self.assertEqual(self.m.line_length_max("ab\ncdef\nx"), 4)
        self.assertEqual(self.m.line_length_max(""), 0)
        self.assertEqual(self.m.line_length_max("one"), 3)

    def test_paragraph_count(self):
        self.assertEqual(self.m.paragraph_count("a\n\nb\n\n\nc"), 3)
        self.assertEqual(self.m.paragraph_count(""), 0)
        self.assertEqual(self.m.paragraph_count("no breaks"), 1)
        self.assertEqual(self.m.paragraph_count("\n\n\n"), 0)

    def test_tab_to_spaces(self):
        self.assertEqual(self.m.tab_to_spaces("a\tb", 4), "a   b")
        self.assertEqual(self.m.tab_to_spaces("\tx", 8), "        x")
        self.assertEqual(self.m.tab_to_spaces("no\ttabs\there", 4),
                         "no  tabs    here")
        with self.assertRaises(ValueError) as c:
            self.m.tab_to_spaces("a\tb", 0)
        self.assertEqual(str(c.exception), "P235:tab_to_spaces:bad_value:width")
        # width cap: 64 passes, 65 refuses
        self.assertEqual(self.m.tab_to_spaces("\tx", 64),
                         " " * 64 + "x")
        with self.assertRaises(ValueError) as c:
            self.m.tab_to_spaces("\tx", 65)
        self.assertEqual(str(c.exception), "P235:tab_to_spaces:too_big:width")
        # output cap: 1,562 tabs at width 64 yield 99,968 chars; 1,563
        # yield 100,032 and refuse
        self.assertEqual(len(self.m.tab_to_spaces("\t" * 1_562, 64)),
                         99_968)
        with self.assertRaises(ValueError) as c:
            self.m.tab_to_spaces("\t" * 1_563, 64)
        self.assertEqual(str(c.exception),
                         "P235:tab_to_spaces:too_many:output")
        # the cap counts total produced characters, independent of
        # newline column resets: multiline input at the cap passes
        at_cap = "\t" * 781 + "\n" + "\t" * 781 + "x" * 31
        self.assertEqual(len(self.m.tab_to_spaces(at_cap, 64)), 100_000)
        # one more character over the multiline cap refuses
        over_cap = "\t" * 781 + "\n" + "\t" * 781 + "x" * 32
        with self.assertRaises(ValueError) as c:
            self.m.tab_to_spaces(over_cap, 64)
        self.assertEqual(str(c.exception),
                         "P235:tab_to_spaces:too_many:output")
        # the original leak shape: nine 1,000-tab lines reset col every
        # line but produce 576,009 characters in total
        with self.assertRaises(ValueError) as c:
            self.m.tab_to_spaces(("\t" * 1_000 + "\n") * 9, 64)
        self.assertEqual(str(c.exception),
                         "P235:tab_to_spaces:too_many:output")

    def test_pig_latin_word(self):
        self.assertEqual(self.m.pig_latin_word("hello"), "ellohay")
        self.assertEqual(self.m.pig_latin_word("apple"), "appleyay")
        # y is treated as a consonant everywhere: "sky" is all-cluster.
        self.assertEqual(self.m.pig_latin_word("sky"), "skyay")
        self.assertEqual(self.m.pig_latin_word("string"), "ingstray")
        with self.assertRaises(ValueError) as c:
            self.m.pig_latin_word("hello world")
        self.assertEqual(str(c.exception),
                         "P235:pig_latin_word:bad_value:word")
        with self.assertRaises(ValueError):
            self.m.pig_latin_word("")

    def test_soundex_code(self):
        self.assertEqual(self.m.soundex_code("Robert"), "R163")
        self.assertEqual(self.m.soundex_code("Rupert"), "R163")
        self.assertEqual(self.m.soundex_code("Ashcraft"), "A261")
        self.assertEqual(self.m.soundex_code("Tymczak"), "T522")
        self.assertEqual(self.m.soundex_code("Lee"), "L000")
        with self.assertRaises(ValueError) as c:
            self.m.soundex_code("H3llo")
        self.assertEqual(str(c.exception),
                         "P235:soundex_code:bad_value:word")


if __name__ == "__main__":
    unittest.main()
