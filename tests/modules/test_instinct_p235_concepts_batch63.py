"""Tests for P235 concepts batch 63 (doc 621-630)."""
import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch63 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch63Test(unittest.TestCase):
    def test_last_stone_weight(self):
        self.assertEqual(m.last_stone_weight([2, 7, 4, 1, 8, 1]), 1)
        self.assertEqual(m.last_stone_weight([]), 0)
        self.assertEqual(m.last_stone_weight([5]), 5)
        # oracle: sort-and-pop smash loop
        rng = random.Random(6301)
        for _ in range(50):
            stones = [rng.randint(1, 20)
                      for _ in range(rng.randint(0, 10))]
            pile = sorted(stones)
            while len(pile) > 1:
                a = pile.pop()
                b = pile.pop()
                if a != b:
                    pile.append(a - b)
                    pile.sort()
            want = pile[0] if pile else 0
            self.assertEqual(m.last_stone_weight(stones), want,
                             stones)
        with self.assertRaises(ValueError):
            m.last_stone_weight([0])
        with self.assertRaises(ValueError):
            m.last_stone_weight([3, True])

    def test_find_kth_positive_missing(self):
        self.assertEqual(m.find_kth_positive_missing(
            [2, 3, 4, 7, 11], 5), 9)
        self.assertEqual(m.find_kth_positive_missing([1, 2, 3], 2),
                         5)
        # oracle: walk the positives counting skips
        rng = random.Random(6302)
        for _ in range(50):
            n = rng.randint(1, 8)
            items = sorted(rng.sample(range(1, 20), n))
            k = rng.randint(1, 10)
            missing = []
            v = 1
            have = set(items)
            while len(missing) < k:
                if v not in have:
                    missing.append(v)
                v += 1
            self.assertEqual(m.find_kth_positive_missing(items, k),
                             missing[k - 1], (items, k))
        with self.assertRaises(ValueError) as ctx:
            m.find_kth_positive_missing([1, 3, 2], 2)
        self.assertIn("not_sorted", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.find_kth_positive_missing([1, 2], 0)
        with self.assertRaises(ValueError):
            m.find_kth_positive_missing([0, 2], 1)

    def test_number_of_good_pairs(self):
        self.assertEqual(m.number_of_good_pairs([1, 2, 3, 1, 1, 3]),
                         4)
        self.assertEqual(m.number_of_good_pairs([1, 1, 1, 1]), 6)
        self.assertEqual(m.number_of_good_pairs([1, 2, 3]), 0)
        # oracle: exhaustive pair scan
        rng = random.Random(6303)
        for _ in range(50):
            vals = [rng.randint(0, 5)
                    for _ in range(rng.randint(1, 12))]
            want = sum(1 for i in range(len(vals))
                       for j in range(i + 1, len(vals))
                       if vals[i] == vals[j])
            self.assertEqual(m.number_of_good_pairs(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.number_of_good_pairs([])

    def test_shuffle_string(self):
        self.assertEqual(
            m.shuffle_string("codeleet", [4, 5, 6, 7, 0, 2, 1, 3]),
            "leetcode")
        # oracle: sort chars by their target index
        rng = random.Random(6304)
        for _ in range(50):
            n = rng.randint(1, 10)
            text = "".join(rng.choice("abcxyz")
                           for _ in range(n))
            idx = list(range(n))
            rng.shuffle(idx)
            want = "".join(ch for _, ch in
                           sorted(zip(idx, text)))
            self.assertEqual(m.shuffle_string(text, idx), want,
                             (text, idx))
        with self.assertRaises(ValueError):
            m.shuffle_string("ab", [0, 0])
        with self.assertRaises(ValueError):
            m.shuffle_string("ab", [0])
        with self.assertRaises(ValueError):
            m.shuffle_string("ab", [0, 2])

    def test_find_all_anagrams_in_string(self):
        self.assertEqual(
            m.find_all_anagrams_in_string("cbaebabacd", "abc"),
            [0, 6])
        self.assertEqual(
            m.find_all_anagrams_in_string("abab", "ab"), [0, 1, 2])
        # oracle: per-window multiset comparison
        from collections import Counter
        rng = random.Random(6305)
        for _ in range(50):
            text = "".join(rng.choice("abc")
                           for _ in range(rng.randint(1, 12)))
            word = "".join(rng.choice("abc")
                           for _ in range(rng.randint(1, 3)))
            need = Counter(word)
            want = [i for i in range(len(text) - len(word) + 1)
                    if Counter(text[i:i + len(word)]) == need]
            self.assertEqual(
                m.find_all_anagrams_in_string(text, word), want,
                (text, word))
        with self.assertRaises(ValueError):
            m.find_all_anagrams_in_string("abc", "")

    def test_arithmetic_slices_count(self):
        self.assertEqual(m.arithmetic_slices_count([1, 2, 3, 4]), 3)
        self.assertEqual(m.arithmetic_slices_count([1]), 0)
        self.assertEqual(
            m.arithmetic_slices_count([1, 2, 3, 4, 5]), 6)
        # oracle: enumerate every length>=3 subarray
        rng = random.Random(6306)
        for _ in range(50):
            vals = [rng.randint(0, 6)
                    for _ in range(rng.randint(1, 10))]
            want = 0
            for i in range(len(vals)):
                for j in range(i + 3, len(vals) + 1):
                    seg = vals[i:j]
                    if all(seg[t] - seg[t - 1] == seg[1] - seg[0]
                           for t in range(2, len(seg))):
                        want += 1
            self.assertEqual(m.arithmetic_slices_count(vals), want,
                             vals)

    def test_count_binary_substrings(self):
        self.assertEqual(m.count_binary_substrings("00110011"), 6)
        self.assertEqual(m.count_binary_substrings("10101"), 4)
        self.assertEqual(m.count_binary_substrings("000"), 0)
        # oracle: brute check of every substring
        rng = random.Random(6307)
        for _ in range(40):
            text = "".join(rng.choice("01")
                           for _ in range(rng.randint(1, 12)))
            want = 0
            for i in range(len(text)):
                for j in range(i + 2, len(text) + 1, 2):
                    seg = text[i:j]
                    half = len(seg) // 2
                    if (len(set(seg[:half])) == 1
                            and len(set(seg[half:])) == 1
                            and seg[0] != seg[-1]):
                        want += 1
            self.assertEqual(m.count_binary_substrings(text), want,
                             text)
        with self.assertRaises(ValueError):
            m.count_binary_substrings("01201")

    def test_min_add_to_make_valid_parens(self):
        self.assertEqual(m.min_add_to_make_valid_parens("())"), 1)
        self.assertEqual(m.min_add_to_make_valid_parens("((("), 3)
        self.assertEqual(m.min_add_to_make_valid_parens("()"), 0)
        self.assertEqual(m.min_add_to_make_valid_parens("()))(("), 4)
        # oracle: stack-based count of unmatched
        rng = random.Random(6308)
        for _ in range(50):
            text = "".join(rng.choice("()")
                           for _ in range(rng.randint(1, 12)))
            stack = 0
            unmatched_open_close = [0, 0]
            for ch in text:
                if ch == "(":
                    stack += 1
                elif stack:
                    stack -= 1
                else:
                    unmatched_open_close[1] += 1
            unmatched_open_close[0] = stack
            want = sum(unmatched_open_close)
            self.assertEqual(m.min_add_to_make_valid_parens(text),
                             want, text)
        with self.assertRaises(ValueError):
            m.min_add_to_make_valid_parens("(a)")

    def test_check_sorted_rotated(self):
        self.assertTrue(m.check_sorted_rotated([3, 4, 5, 1, 2]))
        self.assertFalse(m.check_sorted_rotated([2, 1, 3, 4]))
        self.assertTrue(m.check_sorted_rotated([1, 1, 1]))
        # oracle: try every rotation against the sorted form
        rng = random.Random(6309)
        for _ in range(60):
            vals = [rng.randint(0, 5)
                    for _ in range(rng.randint(1, 10))]
            want = any(vals[k:] + vals[:k] == sorted(vals)
                       for k in range(len(vals)))
            self.assertEqual(m.check_sorted_rotated(vals), want,
                             vals)
        with self.assertRaises(ValueError):
            m.check_sorted_rotated([])

    def test_degree_of_array_shortest(self):
        self.assertEqual(m.degree_of_array_shortest([1, 2, 2, 3, 1]),
                         2)
        self.assertEqual(
            m.degree_of_array_shortest([1, 2, 2, 3, 1, 4, 2]), 6)
        # oracle: enumerate windows, keep those at full degree
        from collections import Counter
        rng = random.Random(6310)
        for _ in range(40):
            vals = [rng.randint(0, 4)
                    for _ in range(rng.randint(1, 10))]
            degree = max(Counter(vals).values())
            want = len(vals)
            for i in range(len(vals)):
                for j in range(i + 1, len(vals) + 1):
                    seg = vals[i:j]
                    if max(Counter(seg).values()) == degree:
                        want = min(want, j - i)
            self.assertEqual(m.degree_of_array_shortest(vals),
                             want, vals)
        with self.assertRaises(ValueError):
            m.degree_of_array_shortest([])

    def test_registry_knows_batch63(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 63]
        self.assertEqual(len(names), 10)
        for name in ("last_stone_weight",
                     "find_kth_positive_missing",
                     "number_of_good_pairs", "shuffle_string",
                     "find_all_anagrams_in_string",
                     "arithmetic_slices_count",
                     "count_binary_substrings",
                     "min_add_to_make_valid_parens",
                     "check_sorted_rotated",
                     "degree_of_array_shortest"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
