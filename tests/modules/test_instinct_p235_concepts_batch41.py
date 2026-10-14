"""Tests for P235 concepts batch 41 (401-410)."""
import posixpath
import random
import re
import string
import unittest
from collections import Counter
from fractions import Fraction
from itertools import permutations

from app.modules.instinct_doc import p235_concepts_batch41 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch41Test(unittest.TestCase):
    def test_compare_version_strings(self):
        self.assertEqual(m.compare_version_strings("1.01", "1.001"), 0)
        self.assertEqual(m.compare_version_strings("1.2", "1.10"), -1)
        self.assertEqual(m.compare_version_strings("7.5.3", "7.5"), 1)
        rng = random.Random(4101)
        for _ in range(60):
            va = [rng.randint(0, 15) for _ in range(rng.randint(1, 4))]
            vb = [rng.randint(0, 15) for _ in range(rng.randint(1, 4))]
            a = ".".join(map(str, va))
            b = ".".join(map(str, vb))
            n = max(len(va), len(vb))
            ta = tuple(va + [0] * (n - len(va)))
            tb = tuple(vb + [0] * (n - len(vb)))
            want = -1 if ta < tb else (1 if ta > tb else 0)
            self.assertEqual(m.compare_version_strings(a, b), want, (a, b))
        for bad in ("", "1..2", "1.a", "1.２"):
            with self.assertRaises(ValueError, msg=bad):
                m.compare_version_strings(bad, "1")

    def test_simplify_path_unix(self):
        self.assertEqual(m.simplify_path_unix("/a/./b/../../c/"), "/c")
        self.assertEqual(m.simplify_path_unix("/../"), "/")
        self.assertEqual(m.simplify_path_unix("/home//foo/"), "/home/foo")
        # oracle: posixpath.normpath agrees on absolute inputs without
        # symlink semantics (both treat '..' textually)
        rng = random.Random(4102)
        parts = ["a", "bb", ".", "..", "", "ccc"]
        for _ in range(80):
            p = "/" + "/".join(rng.choice(parts)
                               for _ in range(rng.randint(0, 6)))
            if p.startswith("//"):
                continue  # POSIX keeps exactly two leading slashes
            self.assertEqual(m.simplify_path_unix(p),
                             posixpath.normpath(p), p)
        with self.assertRaises(ValueError):
            m.simplify_path_unix("relative/path")

    def test_min_window_substring(self):
        self.assertEqual(m.min_window_substring("ADOBECODEBANC", "ABC"),
                         "BANC")
        self.assertEqual(m.min_window_substring("aa", "aa"), "aa")
        self.assertEqual(m.min_window_substring("ab", "b"), "b")
        self.assertEqual(m.min_window_substring("ab", "c"), "")
        # oracle: brute-force every window, multiset containment
        rng = random.Random(4103)
        alpha = "ab"
        for _ in range(60):
            text = "".join(rng.choice(alpha)
                           for _ in range(rng.randint(0, 12)))
            chars = "".join(rng.choice(alpha)
                            for _ in range(rng.randint(1, 3)))
            need = Counter(chars)
            want = ""
            for i in range(len(text)):
                for j in range(i + 1, len(text) + 1):
                    if want and j - i >= len(want):
                        break
                    win = text[i:j]
                    have = Counter(win)
                    if all(have[c] >= n for c, n in need.items()):
                        want = win
                        break
            self.assertEqual(m.min_window_substring(text, chars), want,
                             (text, chars))
        with self.assertRaises(ValueError):
            m.min_window_substring("abc", "")

    def test_group_anagrams_list(self):
        got = m.group_anagrams_list(
            ["eat", "tea", "tan", "ate", "nat", "bat"])
        self.assertEqual(got, [["eat", "tea", "ate"], ["tan", "nat"],
                               ["bat"]])
        # oracle: Counter key grouping, first-appearance order
        rng = random.Random(4104)
        pool = ["ab", "ba", "abc", "bca", "cab", "xy", "yx", "z"]
        for _ in range(40):
            words = [rng.choice(pool) for _ in range(rng.randint(1, 12))]
            seen = {}
            order = []
            for w in words:
                key = tuple(sorted(Counter(w).items()))
                if key not in seen:
                    seen[key] = []
                    order.append(key)
                seen[key].append(w)
            self.assertEqual(m.group_anagrams_list(words),
                             [seen[k] for k in order], words)
        with self.assertRaises(ValueError):
            m.group_anagrams_list([])
        with self.assertRaises(ValueError):
            m.group_anagrams_list(["a", ""])

    def test_largest_number_concat(self):
        self.assertEqual(m.largest_number_concat([3, 30, 34, 5, 9]),
                         "9534330")
        self.assertEqual(m.largest_number_concat([0, 0]), "0")
        self.assertEqual(m.largest_number_concat([10, 2]), "210")
        # oracle: exhaustive permutations on tiny inputs
        rng = random.Random(4105)
        for _ in range(30):
            vals = [rng.randint(0, 99) for _ in range(rng.randint(1, 5))]
            want = max("".join(parts)
                       for parts in permutations(map(str, vals)))
            if want.startswith("0"):
                want = "0"
            self.assertEqual(m.largest_number_concat(vals), want, vals)
        with self.assertRaises(ValueError):
            m.largest_number_concat([-1])
        with self.assertRaises(ValueError):
            m.largest_number_concat([])

    def test_base_convert_digits(self):
        self.assertEqual(m.base_convert_digits("ff", 16, 2), "11111111")
        self.assertEqual(m.base_convert_digits("101", 2, 10), "5")
        self.assertEqual(m.base_convert_digits("0", 2, 36), "0")
        self.assertEqual(m.base_convert_digits("z", 36, 10), "35")
        # oracle: int(x, base) then stdlib-free re-encode
        rng = random.Random(4106)
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        for _ in range(60):
            fb = rng.randint(2, 36)
            tb = rng.randint(2, 36)
            raw = "".join(rng.choice(digits[:fb])
                          for _ in range(rng.randint(1, 8)))
            n = int(raw, fb)
            if n == 0:
                want = "0"
            else:
                out = []
                while n:
                    out.append(digits[n % tb])
                    n //= tb
                want = "".join(reversed(out))
            self.assertEqual(m.base_convert_digits(raw, fb, tb), want,
                             (raw, fb, tb))
        with self.assertRaises(ValueError):
            m.base_convert_digits("2", 2, 10)
        with self.assertRaises(ValueError):
            m.base_convert_digits("1", 1, 10)
        with self.assertRaises(ValueError):
            m.base_convert_digits("", 2, 10)

    def test_fraction_decimal_cycle(self):
        self.assertEqual(m.fraction_decimal_cycle(1, 3), "0.(3)")
        self.assertEqual(m.fraction_decimal_cycle(1, 6), "0.1(6)")
        self.assertEqual(m.fraction_decimal_cycle(2, 1), "2")
        self.assertEqual(m.fraction_decimal_cycle(4, 2), "2")
        self.assertEqual(m.fraction_decimal_cycle(1, 7),
                         "0.(142857)")
        # oracle: re-expand the rendered form and compare to Fraction
        rng = random.Random(4107)
        pat = re.compile(r"^(\d+)\.(\d*)\((\d+)\)$")
        for _ in range(40):
            num = rng.randint(0, 500)
            den = rng.randint(1, 200)
            got = m.fraction_decimal_cycle(num, den)
            want = Fraction(num, den)
            mm = pat.match(got)
            if mm:
                whole = int(mm.group(1))
                head = mm.group(2)
                cyc = mm.group(3)
                reps = 60 // len(cyc) + 2
                digits = (head + cyc * reps)[:60]
            elif "." in got:
                whole = int(got.split(".")[0])
                digits = (got.split(".")[1] + "0" * 60)[:60]
            else:
                whole = int(got)
                digits = "0" * 60
            approx = Fraction(whole) + sum(
                Fraction(int(d), 10 ** (i + 1))
                for i, d in enumerate(digits))
            self.assertLessEqual(abs(approx - want),
                                 Fraction(1, 10 ** 40), (num, den, got))
        with self.assertRaises(ValueError):
            m.fraction_decimal_cycle(1, 0)
        with self.assertRaises(ValueError):
            m.fraction_decimal_cycle(-1, 2)

    def test_count_and_say_term(self):
        self.assertEqual(m.count_and_say_term(1), "1")
        self.assertEqual(m.count_and_say_term(4), "1211")
        self.assertEqual(m.count_and_say_term(5), "111221")
        # oracle: regex-based independent implementation
        def ref(n):
            term = "1"
            for _ in range(n - 1):
                term = "".join(
                    "%d%s" % (len(g.group(0)), g.group(1))
                    for g in re.finditer(r"(\d)\1*", term))
            return term

        for n in range(1, 12):
            self.assertEqual(m.count_and_say_term(n), ref(n))
        with self.assertRaises(ValueError):
            m.count_and_say_term(0)
        with self.assertRaises(ValueError):
            m.count_and_say_term(m.MAX_SAY_N + 1)
        m.count_and_say_term(m.MAX_SAY_N)

    def test_capitalize_sentences(self):
        self.assertEqual(m.capitalize_sentences("hello. are you ok?"),
                         "Hello. Are you ok?")
        self.assertEqual(m.capitalize_sentences("YES! fine."),
                         "YES! Fine.")
        self.assertEqual(m.capitalize_sentences("a.1b c"), "A.1B c")
        self.assertEqual(m.capitalize_sentences(""), "")
        # leading quotes/digits/brackets are skipped to the first letter
        self.assertEqual(m.capitalize_sentences('"hello. 123world'),
                         '"Hello. 123World')
        self.assertEqual(m.capitalize_sentences("(hi)! 'ok'"),
                         "(Hi)! 'Ok'")
        self.assertEqual(m.capitalize_sentences("...42"), "...42")
        # oracle: independent regex implementation
        def ref(text):
            return re.sub(r"(^|[.!?])([^.!?a-zA-Z]*)([a-z])",
                          lambda g: (g.group(1) + g.group(2)
                                     + g.group(3).upper()),
                          text)

        rng = random.Random(4112)
        pool = "ab .!?1\'"
        for _ in range(80):
            text = "".join(rng.choice(pool)
                           for _ in range(rng.randint(0, 20)))
            self.assertEqual(m.capitalize_sentences(text), ref(text),
                             text)
        with self.assertRaises(ValueError):
            m.capitalize_sentences("x" * (m.MAX_TEXT + 1))
        m.capitalize_sentences("x" * m.MAX_TEXT)

    def test_work_caps(self):
        # version components parse as bounded ints only
        m.compare_version_strings("9" * m.MAX_VERSION_DIGITS + ".1",
                                  "0.1")
        with self.assertRaises(ValueError):
            m.compare_version_strings(
                "9" * (m.MAX_VERSION_DIGITS + 1), "1")
        with self.assertRaises(ValueError):
            m.compare_version_strings("1." * (m.MAX_TEXT // 2) + "1",
                                      "1")
        # anagram words are length-capped
        m.group_anagrams_list(["x" * m.MAX_WORD_LEN])
        with self.assertRaises(ValueError):
            m.group_anagrams_list(["x" * (m.MAX_WORD_LEN + 1)])

    def test_isomorphic_strings_check(self):
        self.assertTrue(m.isomorphic_strings_check("egg", "add"))
        self.assertFalse(m.isomorphic_strings_check("foo", "bar"))
        self.assertTrue(m.isomorphic_strings_check("paper", "title"))
        self.assertFalse(m.isomorphic_strings_check("ab", "aa"))
        # oracle: first-occurrence encoding, independent of the module
        rng = random.Random(4110)
        alpha = "abcd"
        for _ in range(50):
            a = "".join(rng.choice(alpha)
                        for _ in range(rng.randint(0, 8)))
            b = "".join(rng.choice(alpha) for _ in range(len(a)))

            def norm(s):
                table = {}
                out = []
                for ch in s:
                    if ch not in table:
                        table[ch] = len(table)
                    out.append(table[ch])
                return out

            self.assertEqual(m.isomorphic_strings_check(a, b),
                             norm(a) == norm(b), (a, b))
        with self.assertRaises(ValueError):
            m.isomorphic_strings_check("a", True)

    def test_registry_knows_batch41(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 41]
        self.assertEqual(len(names), 10)
        for name in ("compare_version_strings", "simplify_path_unix",
                     "min_window_substring", "group_anagrams_list",
                     "largest_number_concat", "base_convert_digits",
                     "fraction_decimal_cycle", "count_and_say_term",
                     "capitalize_sentences", "isomorphic_strings_check"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
