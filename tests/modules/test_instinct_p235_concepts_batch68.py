"""Tests for P235 concepts batch 68 (doc 671-680)."""
import random
import unittest
from functools import lru_cache

from app.modules.instinct_doc import p235_concepts_batch68 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch68Test(unittest.TestCase):
    def test_palindrome_partition_min_cuts(self):
        self.assertEqual(m.palindrome_partition_min_cuts("aab"), 1)
        self.assertEqual(m.palindrome_partition_min_cuts("abcde"), 4)
        self.assertEqual(m.palindrome_partition_min_cuts("aaa"), 0)
        # oracle: try every cut set
        rng = random.Random(6801)
        for _ in range(40):
            s = "".join(rng.choice("ab") for _ in range(
                rng.randint(1, 9)))
            n = len(s)

            def is_pal(x):
                return x == x[::-1]
            best = n - 1
            for mask in range(1 << (n - 1)):
                cuts = [i + 1 for i in range(n - 1)
                        if mask & (1 << i)]
                parts = []
                prev = 0
                for c in cuts + [n]:
                    parts.append(s[prev:c])
                    prev = c
                if all(is_pal(p) for p in parts):
                    best = min(best, len(cuts))
            self.assertEqual(m.palindrome_partition_min_cuts(s),
                             best, s)
        with self.assertRaises(ValueError):
            m.palindrome_partition_min_cuts("")

    def test_distinct_subsequences_count(self):
        self.assertEqual(m.distinct_subsequences_count(
            "rabbbit", "rabbit"), 3)
        self.assertEqual(m.distinct_subsequences_count(
            "babgbag", "bag"), 5)
        self.assertEqual(m.distinct_subsequences_count("abc", "d"), 0)
        # oracle: plain two-index recursion
        rng = random.Random(6802)
        for _ in range(40):
            s = "".join(rng.choice("abc")
                        for _ in range(rng.randint(0, 10)))
            t = "".join(rng.choice("abc")
                        for _ in range(rng.randint(0, 4)))

            @lru_cache(maxsize=None)
            def rec(i, j):
                if j == len(t):
                    return 1
                if i == len(s):
                    return 0
                take = rec(i + 1, j + 1) if s[i] == t[j] else 0
                return take + rec(i + 1, j)
            self.assertEqual(m.distinct_subsequences_count(s, t),
                             rec(0, 0), (s, t))

    def test_longest_repeating_substring_length(self):
        self.assertEqual(m.longest_repeating_substring_length(
            "aabca"), 1)
        self.assertEqual(m.longest_repeating_substring_length(
            "abcd"), 0)
        self.assertEqual(m.longest_repeating_substring_length(
            "aaaa"), 3)
        # oracle: collect every substring, count occurrences
        rng = random.Random(6803)
        for _ in range(40):
            s = "".join(rng.choice("ab")
                        for _ in range(rng.randint(0, 10)))
            best = 0
            for i in range(len(s)):
                for j in range(i + 1, len(s) + 1):
                    sub = s[i:j]
                    first = s.find(sub)
                    if (first != -1
                            and s.find(sub, first + 1) != -1):
                        best = max(best, len(sub))
            self.assertEqual(
                m.longest_repeating_substring_length(s), best, s)

    def test_word_break_check(self):
        self.assertTrue(m.word_break_check(
            "applepenapple", ["apple", "pen"]))
        self.assertFalse(m.word_break_check(
            "catsandog", ["cats", "dog", "sand", "and", "cat"]))
        self.assertTrue(m.word_break_check(
            "catsandog", ["cats", "dog", "sand", "and", "cat",
                          "an"]))
        # oracle: recursive segmentation with memo
        rng = random.Random(6804)
        for _ in range(60):
            words = ["".join(rng.choice("ab")
                             for _ in range(rng.randint(1, 3)))
                     for _ in range(rng.randint(1, 5))]
            s = "".join(rng.choice("ab")
                        for _ in range(rng.randint(1, 9)))
            ws = set(words)

            @lru_cache(maxsize=None)
            def rec(i):
                if i == len(s):
                    return True
                return any(s.startswith(w, i) and rec(i + len(w))
                           for w in ws)
            self.assertEqual(m.word_break_check(s, words), rec(0),
                             (s, words))
        with self.assertRaises(ValueError):
            m.word_break_check("Ab", ["ab"])
        with self.assertRaises(ValueError):
            m.word_break_check("ab", ["a" * 101])

    def test_glob_match_check(self):
        self.assertTrue(m.glob_match_check("aa", "*"))
        self.assertFalse(m.glob_match_check("aa", "a"))
        self.assertTrue(m.glob_match_check("adceb", "*a*b"))
        self.assertFalse(m.glob_match_check("acdcb", "a*c?b"))
        # oracle: recursive matcher with memo
        rng = random.Random(6805)
        for _ in range(60):
            s = "".join(rng.choice("ab")
                        for _ in range(rng.randint(0, 8)))
            p = "".join(rng.choice("ab*?")
                        for _ in range(rng.randint(0, 5)))

            @lru_cache(maxsize=None)
            def rec(i, j):
                if j == len(p):
                    return i == len(s)
                if p[j] == "*":
                    return (rec(i, j + 1)
                            or (i < len(s) and rec(i + 1, j)))
                if i < len(s) and p[j] in ("?", s[i]):
                    return rec(i + 1, j + 1)
                return False
            self.assertEqual(m.glob_match_check(s, p), rec(0, 0),
                             (s, p))
        with self.assertRaises(ValueError):
            m.glob_match_check("ab", "a" * 1001)

    def test_longest_valid_parens_length(self):
        self.assertEqual(m.longest_valid_parens_length("(()"), 2)
        self.assertEqual(m.longest_valid_parens_length(")()())"), 4)
        self.assertEqual(m.longest_valid_parens_length(""), 0)
        # oracle: check every substring with a balance counter
        rng = random.Random(6806)
        for _ in range(60):
            s = "".join(rng.choice("()")
                        for _ in range(rng.randint(0, 12)))

            def ok(x):
                bal = 0
                for ch in x:
                    bal += 1 if ch == "(" else -1
                    if bal < 0:
                        return False
                return bal == 0
            best = 0
            for i in range(len(s)):
                for j in range(i + 1, len(s) + 1):
                    if ok(s[i:j]):
                        best = max(best, j - i)
            self.assertEqual(m.longest_valid_parens_length(s),
                             best, s)
        with self.assertRaises(ValueError):
            m.longest_valid_parens_length("(a)")

    def test_count_palindromic_substrings(self):
        self.assertEqual(m.count_palindromic_substrings("aaa"), 6)
        self.assertEqual(m.count_palindromic_substrings("abc"), 3)
        self.assertEqual(m.count_palindromic_substrings(""), 0)
        # oracle: count every palindromic slice directly
        rng = random.Random(6807)
        for _ in range(50):
            s = "".join(rng.choice("ab")
                        for _ in range(rng.randint(0, 12)))
            want = sum(1 for i in range(len(s))
                       for j in range(i + 1, len(s) + 1)
                       if s[i:j] == s[i:j][::-1])
            self.assertEqual(m.count_palindromic_substrings(s),
                             want, s)

    def test_min_ascii_delete_sum(self):
        self.assertEqual(m.min_ascii_delete_sum("sea", "eat"), 231)
        self.assertEqual(m.min_ascii_delete_sum("delete", "leet"),
                         403)
        self.assertEqual(m.min_ascii_delete_sum("", ""), 0)
        # oracle: total ASCII minus twice the best common
        # subsequence weight, by independent recursion
        rng = random.Random(6808)
        for _ in range(40):
            a = "".join(rng.choice("abc")
                        for _ in range(rng.randint(0, 7)))
            b = "".join(rng.choice("abc")
                        for _ in range(rng.randint(0, 7)))

            @lru_cache(maxsize=None)
            def rec(i, j):
                if i == len(a) or j == len(b):
                    return 0
                if a[i] == b[j]:
                    return ord(a[i]) + rec(i + 1, j + 1)
                return max(rec(i + 1, j), rec(i, j + 1))
            want = (sum(map(ord, a)) + sum(map(ord, b))
                    - 2 * rec(0, 0))
            self.assertEqual(m.min_ascii_delete_sum(a, b), want,
                             (a, b))

    def test_longest_palindromic_subsequence_length(self):
        self.assertEqual(
            m.longest_palindromic_subsequence_length("bbbab"), 4)
        self.assertEqual(
            m.longest_palindromic_subsequence_length("cbbd"), 2)
        self.assertEqual(
            m.longest_palindromic_subsequence_length("a"), 1)
        # oracle: LCS of s against its reverse
        rng = random.Random(6809)
        for _ in range(40):
            s = "".join(rng.choice("abc")
                        for _ in range(rng.randint(1, 10)))
            t = s[::-1]
            n = len(s)
            dp = [[0] * (n + 1) for _ in range(n + 1)]
            for i in range(1, n + 1):
                for j in range(1, n + 1):
                    if s[i - 1] == t[j - 1]:
                        dp[i][j] = dp[i - 1][j - 1] + 1
                    else:
                        dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
            self.assertEqual(
                m.longest_palindromic_subsequence_length(s),
                dp[n][n], s)
        with self.assertRaises(ValueError):
            m.longest_palindromic_subsequence_length("")

    def test_regex_match_dot_star(self):
        self.assertFalse(m.regex_match_dot_star("aa", "a"))
        self.assertTrue(m.regex_match_dot_star("aa", "a*"))
        self.assertTrue(m.regex_match_dot_star("ab", ".*"))
        self.assertTrue(m.regex_match_dot_star("aab", "c*a*b"))
        self.assertFalse(m.regex_match_dot_star(
            "mississippi", "mis*is*p*."))
        # glob vs regex diverge on the shared pair ("ab", ".*")
        self.assertNotEqual(m.glob_match_check("ab", ".*"),
                            m.regex_match_dot_star("ab", ".*"))
        # oracle: recursive matcher with memo
        rng = random.Random(6810)
        for _ in range(60):
            s = "".join(rng.choice("ab")
                        for _ in range(rng.randint(0, 7)))
            elems = [rng.choice("ab.") for _ in
                     range(rng.randint(0, 4))]
            p = "".join(e + rng.choice(["", "*"]) for e in elems)

            @lru_cache(maxsize=None)
            def rec(i, j):
                if j == len(p):
                    return i == len(s)
                star = j + 1 < len(p) and p[j + 1] == "*"
                hit = (i < len(s)
                       and p[j] in (".", s[i]))
                if star:
                    return rec(i, j + 2) or (hit and rec(i + 1, j))
                return hit and rec(i + 1, j + 1)
            self.assertEqual(m.regex_match_dot_star(s, p),
                             rec(0, 0), (s, p))
        with self.assertRaises(ValueError):
            m.regex_match_dot_star("ab", "*a")
        with self.assertRaises(ValueError):
            m.regex_match_dot_star("ab", "a**")
        with self.assertRaises(ValueError):
            m.regex_match_dot_star("aB", "ab")

    def test_registry_knows_batch68(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("palindrome_partition_min_cuts",
                     "distinct_subsequences_count",
                     "longest_repeating_substring_length",
                     "word_break_check", "glob_match_check",
                     "longest_valid_parens_length",
                     "count_palindromic_substrings",
                     "min_ascii_delete_sum",
                     "longest_palindromic_subsequence_length",
                     "regex_match_dot_star"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
