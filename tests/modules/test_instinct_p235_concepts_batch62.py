"""Tests for P235 concepts batch 62 (doc 611-620)."""
import random
import string
import unittest

from app.modules.instinct_doc import p235_concepts_batch62 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch62Test(unittest.TestCase):
    def test_is_pangram_ascii(self):
        self.assertTrue(m.is_pangram_ascii(
            "The quick brown fox jumps over the lazy dog"))
        self.assertFalse(m.is_pangram_ascii("abc"))
        # oracle: alphabet difference against the lowered letters
        rng = random.Random(6201)
        for _ in range(50):
            text = "".join(rng.choice(string.ascii_letters + " 123")
                           for _ in range(rng.randint(1, 120)))
            letters = {c for c in text.lower() if c.isalpha()}
            want = not (set(string.ascii_lowercase) - letters)
            self.assertEqual(m.is_pangram_ascii(text), want, text)
        with self.assertRaises(ValueError):
            m.is_pangram_ascii("pangram\u00e9")
        with self.assertRaises(ValueError):
            m.is_pangram_ascii("")

    def test_reverse_vowels_of_string(self):
        self.assertEqual(m.reverse_vowels_of_string("hello"), "holle")
        self.assertEqual(m.reverse_vowels_of_string("leetcode"),
                         "leotcede")
        # oracle: pull vowels out, lay them back reversed
        rng = random.Random(6202)
        for _ in range(60):
            text = "".join(rng.choice("aeiouxyzAEIO ")
                           for _ in range(rng.randint(1, 20)))
            vowels = [c for c in text if c in "aeiouAEIOU"]
            out = []
            for c in text:
                out.append(vowels.pop() if c in "aeiouAEIOU" else c)
            self.assertEqual(m.reverse_vowels_of_string(text),
                             "".join(out), text)

    def test_detect_capital_use(self):
        self.assertTrue(m.detect_capital_use("USA"))
        self.assertTrue(m.detect_capital_use("leetcode"))
        self.assertTrue(m.detect_capital_use("Google"))
        self.assertFalse(m.detect_capital_use("FlaG"))
        self.assertTrue(m.detect_capital_use("G"))
        # oracle: count uppercase letters and branch
        rng = random.Random(6203)
        for _ in range(60):
            word = "".join(rng.choice(string.ascii_letters)
                           for _ in range(rng.randint(1, 8)))
            ups = sum(1 for c in word if c.isupper())
            want = (ups == len(word) or ups == 0
                    or (ups == 1 and word[0].isupper()))
            self.assertEqual(m.detect_capital_use(word), want, word)
        with self.assertRaises(ValueError):
            m.detect_capital_use("Has2Digits")
        with self.assertRaises(ValueError):
            m.detect_capital_use("")

    def test_gcd_of_strings(self):
        self.assertEqual(m.gcd_of_strings("ABCABC", "ABC"), "ABC")
        self.assertEqual(m.gcd_of_strings("ABABAB", "ABAB"), "AB")
        self.assertEqual(m.gcd_of_strings("LEET", "CODE"), "")
        # oracle: try every candidate block, longest first
        rng = random.Random(6204)
        for _ in range(40):
            unit = "".join(rng.choice("ab")
                           for _ in range(rng.randint(1, 4)))
            a = unit * rng.randint(1, 4)
            b = unit * rng.randint(1, 4)
            if rng.random() < 0.3:
                b = b + "z"
            want = ""
            for size in range(min(len(a), len(b)), 0, -1):
                cand = a[:size]
                if (len(a) % size == 0 and len(b) % size == 0
                        and cand * (len(a) // size) == a
                        and cand * (len(b) // size) == b):
                    want = cand
                    break
            self.assertEqual(m.gcd_of_strings(a, b), want, (a, b))
        with self.assertRaises(ValueError):
            m.gcd_of_strings("", "AB")

    def test_longest_substring_k_distinct(self):
        self.assertEqual(m.longest_substring_k_distinct("eceba", 2),
                         3)
        self.assertEqual(m.longest_substring_k_distinct("aa", 1), 2)
        self.assertEqual(m.longest_substring_k_distinct("", 3), 0)
        # oracle: brute force over every window
        rng = random.Random(6205)
        for _ in range(50):
            text = "".join(rng.choice("abcd")
                           for _ in range(rng.randint(0, 14)))
            k = rng.randint(1, 3)
            want = 0
            for i in range(len(text) + 1):
                for j in range(i + 1, len(text) + 1):
                    if len(set(text[i:j])) <= k:
                        want = max(want, j - i)
            self.assertEqual(
                m.longest_substring_k_distinct(text, k), want,
                (text, k))
        with self.assertRaises(ValueError):
            m.longest_substring_k_distinct("abc", 0)

    def test_decode_ways_count(self):
        self.assertEqual(m.decode_ways_count("12"), 2)
        self.assertEqual(m.decode_ways_count("226"), 3)
        self.assertEqual(m.decode_ways_count("06"), 0)
        self.assertEqual(m.decode_ways_count("11106"), 2)
        # oracle: recursive walk over positions with memo
        from functools import lru_cache

        def ways(s):
            @lru_cache(maxsize=None)
            def go(i):
                if i == len(s):
                    return 1
                if s[i] == "0":
                    return 0
                total = go(i + 1)
                if i + 1 < len(s) and int(s[i:i + 2]) <= 26:
                    total += go(i + 2)
                return total
            return go(0)

        rng = random.Random(6206)
        for _ in range(50):
            digits = "".join(rng.choice("0123456789")
                             for _ in range(rng.randint(1, 9)))
            self.assertEqual(m.decode_ways_count(digits),
                             ways(digits), digits)
        with self.assertRaises(ValueError):
            m.decode_ways_count("1a2")
        with self.assertRaises(ValueError):
            m.decode_ways_count("")

    def test_goat_latin_words(self):
        self.assertEqual(m.goat_latin_words("I speak Goat Latin"),
                         "Imaa peaksmaaa oatGmaaaa atinLmaaaaa")
        # oracle: per-word transform recomputed with explicit slices
        rng = random.Random(6207)
        for _ in range(50):
            words = ["".join(rng.choice(string.ascii_letters)
                             for _ in range(rng.randint(1, 6)))
                     for _ in range(rng.randint(1, 5))]
            text = " ".join(words)
            out = []
            for idx, w in enumerate(words):
                if w[0].lower() in "aeiou":
                    g = w + "ma"
                else:
                    g = w[1:] + w[:1] + "ma"
                out.append(g + "a" * (idx + 1))
            self.assertEqual(m.goat_latin_words(text),
                             " ".join(out), text)
        with self.assertRaises(ValueError):
            m.goat_latin_words("two  spaces")
        with self.assertRaises(ValueError):
            m.goat_latin_words("has2 digits")

    def test_license_key_format(self):
        self.assertEqual(m.license_key_format("5F3Z-2e-9-w", 4),
                         "5F3Z-2E9W")
        self.assertEqual(m.license_key_format("2-5g-3-J", 2),
                         "2-5G-3J")
        # oracle: rebuild from the right in k-sized chunks
        rng = random.Random(6208)
        for _ in range(50):
            raw = "".join(rng.choice(string.ascii_letters
                                     + string.digits)
                          for _ in range(rng.randint(1, 12)))
            dashes = list(raw)
            for _ in range(rng.randint(0, 3)):
                dashes.insert(rng.randint(0, len(dashes)), "-")
            key = "".join(dashes)
            k = rng.randint(1, 5)
            clean = [c.upper() for c in raw]
            groups = []
            while clean:
                groups.append("".join(clean[-k:]))
                del clean[-k:]
            want = "-".join(reversed(groups))
            self.assertEqual(m.license_key_format(key, k), want,
                             (key, k))
        with self.assertRaises(ValueError):
            m.license_key_format("---", 2)
        with self.assertRaises(ValueError):
            m.license_key_format("ab", 0)
        with self.assertRaises(ValueError):
            m.license_key_format("a b", 1)

    def test_keyboard_row_words(self):
        self.assertEqual(
            m.keyboard_row_words(["Hello", "Alaska", "Dad",
                                  "Peace"]), ["Alaska", "Dad"])
        # oracle: row index per letter via a flat lookup
        row_of = {}
        for idx, row in enumerate("qwertyuiop asdfghjkl zxcvbnm"
                                  .split()):
            for ch in row:
                row_of[ch] = idx
        rng = random.Random(6209)
        pool = ["Hello", "Alaska", "Dad", "Peace", "top", "we",
                "asf", "zx", "pop", "lkl", "QW"]
        for _ in range(40):
            words = [rng.choice(pool)
                     for _ in range(rng.randint(1, 6))]
            want = [w for w in words
                    if len({row_of[c] for c in w.lower()}) == 1]
            self.assertEqual(m.keyboard_row_words(words), want,
                             words)
        # per-word cap: 100 chars accepted, 101 refused
        self.assertEqual(m.keyboard_row_words(["a" * 100]),
                         ["a" * 100])
        with self.assertRaises(ValueError) as ctx:
            m.keyboard_row_words(["a" * 101])
        self.assertIn("too_long:words[0]", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.keyboard_row_words(["ok", ""])
        with self.assertRaises(ValueError):
            m.keyboard_row_words(["caf\u00e9"])

    def test_jewels_and_stones_count(self):
        self.assertEqual(m.jewels_and_stones_count("aA", "aAAbbbb"),
                         3)
        self.assertEqual(m.jewels_and_stones_count("z", "ZZ"), 0)
        # oracle: membership tally via count per jewel kind
        rng = random.Random(6210)
        for _ in range(50):
            jewels = "".join(rng.sample(
                string.ascii_letters, rng.randint(1, 8)))
            stones = "".join(rng.choice(string.ascii_letters)
                             for _ in range(rng.randint(1, 15)))
            want = sum(stones.count(j) for j in set(jewels))
            self.assertEqual(m.jewels_and_stones_count(
                jewels, stones), want, (jewels, stones))
        with self.assertRaises(ValueError):
            m.jewels_and_stones_count("", "abc")
        with self.assertRaises(ValueError):
            m.jewels_and_stones_count("abc", "")

    def test_registry_knows_batch62(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 62]
        self.assertEqual(len(names), 10)
        for name in ("is_pangram_ascii", "reverse_vowels_of_string",
                     "detect_capital_use", "gcd_of_strings",
                     "longest_substring_k_distinct",
                     "decode_ways_count", "goat_latin_words",
                     "license_key_format", "keyboard_row_words",
                     "jewels_and_stones_count"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
