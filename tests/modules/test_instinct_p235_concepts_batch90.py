"""P235 batch 90: string indexes, transforms and matching."""
import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch90 as m
from app.modules.instinct_doc.p235_concepts_registry import MAX_ITEMS


def refusal(code):
    return "P235:" + code


class TestSuffixArrayBuild(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.suffix_array_build("banana"), [5, 3, 1, 0, 4, 2])
        self.assertEqual(m.suffix_array_build("dcba"), [3, 2, 1, 0])
        self.assertEqual(m.suffix_array_build("aaa"), [2, 1, 0])
        self.assertEqual(m.suffix_array_build(""), [])
        self.assertEqual(m.suffix_array_build("ababa"), [4, 2, 0, 3, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.suffix_array_build(123)
        self.assertEqual(str(ctx.exception),
                         refusal("suffix_array_build:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.suffix_array_build("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception),
                         refusal("suffix_array_build:too_many:s"))

    def test_cap(self):
        got = m.suffix_array_build("a" * MAX_ITEMS)
        self.assertEqual(got[0], MAX_ITEMS - 1)
        self.assertEqual(got[-1], 0)

    def test_oracle(self):
        rng = random.Random(9001)
        for _ in range(60):
            n = rng.randint(0, 30)
            s = "".join(rng.choice("abcab") for _ in range(n))
            want = sorted(range(n), key=lambda i: s[i:])
            self.assertEqual(m.suffix_array_build(s), want)


class TestBwtEncode(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.bwt_encode("banana"), "annb\x00aa")
        self.assertEqual(m.bwt_encode("a"), "a\x00")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.bwt_encode("")
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_encode:empty:s"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_encode("ab\x00c")
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_encode:bad_char:s[2]"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_encode(5)
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_encode:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_encode("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_encode:too_many:s"))

    def test_oracle(self):
        rng = random.Random(9003)
        for _ in range(60):
            n = rng.randint(1, 20)
            s = "".join(rng.choice("abcab") for _ in range(n))
            t = s + "\x00"
            rots = sorted(t[i:] + t[:i] for i in range(len(t)))
            want = "".join(r[-1] for r in rots)
            self.assertEqual(m.bwt_encode(s), want)


class TestBwtDecode(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.bwt_decode("annb\x00aa"), "banana")
        self.assertEqual(m.bwt_decode("a\x00"), "a")
        self.assertEqual(m.bwt_decode("\x00"), "")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.bwt_decode("")
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_decode:empty:t"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_decode("abc")
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_decode:bad_char:t"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_decode("a\x00b\x00c")
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_decode:bad_char:t"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_decode(None)
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_decode:bad_type:t"))
        with self.assertRaises(ValueError) as ctx:
            m.bwt_decode("\x00" + "a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception),
                         refusal("bwt_decode:too_many:t"))

    def test_oracle(self):
        rng = random.Random(9004)
        for _ in range(60):
            n = rng.randint(1, 25)
            s = "".join(rng.choice("abcabd") for _ in range(n))
            self.assertEqual(m.bwt_decode(m.bwt_encode(s)), s)

    def test_roundtrip_at_max(self):
        # encode accepts MAX_ITEMS and emits MAX_ITEMS + 1; decode
        # must accept that, one above the plain string cap
        s = "a" * MAX_ITEMS
        self.assertEqual(m.bwt_decode(m.bwt_encode(s)), s)

    def test_malformed_inputs_refused_exhaustively(self):
        # every one-sentinel string of lengths 2..6 over {a, b} is
        # either exactly bwt_encode's output for one input (and
        # decodes to it) or refused as malformed
        import itertools
        for length in range(2, 7):
            image = {}
            for chars in itertools.product("ab", repeat=length - 1):
                plain = "".join(chars)
                image[m.bwt_encode(plain)] = plain
            for pos in range(length):
                for rest in itertools.product("ab", repeat=length - 1):
                    row = list(rest)
                    row.insert(pos, "\x00")
                    t = "".join(row)
                    if t in image:
                        self.assertEqual(m.bwt_decode(t), image[t])
                    else:
                        with self.assertRaises(ValueError) as ctx:
                            m.bwt_decode(t)
                        self.assertEqual(str(ctx.exception), refusal(
                            "bwt_decode:bad_form:t"))


class TestMatchingStatisticsLengths(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.matching_statistics_lengths("ababc", "abc"),
                         [2, 1, 3, 2, 1])
        self.assertEqual(m.matching_statistics_lengths("", "abc"), [])
        self.assertEqual(m.matching_statistics_lengths("xyz", "abc"),
                         [0, 0, 0])
        self.assertEqual(m.matching_statistics_lengths("abc", ""), [0, 0, 0])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.matching_statistics_lengths(1, "a")
        self.assertEqual(str(ctx.exception), refusal(
            "matching_statistics_lengths:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.matching_statistics_lengths("a" * (MAX_ITEMS + 1), "a")
        self.assertEqual(str(ctx.exception), refusal(
            "matching_statistics_lengths:too_many:s"))
        with self.assertRaises(ValueError) as ctx:
            m.matching_statistics_lengths("a", "a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception), refusal(
            "matching_statistics_lengths:too_many:t"))

    def test_cap(self):
        got = m.matching_statistics_lengths("a" * MAX_ITEMS,
                                            "a" * MAX_ITEMS)
        self.assertEqual(got[0], MAX_ITEMS)
        self.assertEqual(got[-1], 1)

    def test_oracle(self):
        rng = random.Random(9012)
        for _ in range(60):
            ns = rng.randint(0, 15)
            nt = rng.randint(0, 8)
            s = "".join(rng.choice("ab") for _ in range(ns))
            t = "".join(rng.choice("ab") for _ in range(nt))
            want = []
            for i in range(ns):
                best = 0
                for j in range(nt):
                    k = 0
                    while i + k < ns and j + k < nt \
                            and s[i + k] == t[j + k]:
                        k += 1
                    best = max(best, k)
                want.append(best)
            self.assertEqual(m.matching_statistics_lengths(s, t), want)


class TestSmallestDistinctSubsequence(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.smallest_distinct_subsequence("bcabc"), "abc")
        self.assertEqual(
            m.smallest_distinct_subsequence("cbacdcbc"), "acdb")
        self.assertEqual(m.smallest_distinct_subsequence("cbad"), "cbad")
        self.assertEqual(m.smallest_distinct_subsequence(""), "")
        self.assertEqual(m.smallest_distinct_subsequence("abacb"), "abc")
        self.assertEqual(
            m.smallest_distinct_subsequence("ecbacba"), "eacb")

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.smallest_distinct_subsequence(5)
        self.assertEqual(str(ctx.exception), refusal(
            "smallest_distinct_subsequence:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.smallest_distinct_subsequence("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception), refusal(
            "smallest_distinct_subsequence:too_many:s"))

    def test_oracle(self):
        from itertools import combinations
        rng = random.Random(9015)
        for _ in range(60):
            n = rng.randint(0, 12)
            text = "".join(rng.choice("abcd") for _ in range(n))
            distinct = sorted(set(text))
            best = None
            for r in range(len(distinct), n + 1):
                found = None
                for pos in combinations(range(n), r):
                    sub = "".join(text[i] for i in pos)
                    if sorted(set(sub)) == distinct:
                        if found is None or sub < found:
                            found = sub
                if found is not None:
                    best = found
                    break
            if best is None and not distinct:
                best = ""
            self.assertEqual(
                m.smallest_distinct_subsequence(text), best)

    def test_cap(self):
        self.assertEqual(
            m.smallest_distinct_subsequence("a" * MAX_ITEMS), "a")


class TestManacherPalindromeRadii(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.manacher_palindrome_radii("aba"),
                         ([1, 2, 1], [0, 0, 0]))
        self.assertEqual(m.manacher_palindrome_radii("abba"),
                         ([1, 1, 1, 1], [0, 0, 2, 0]))
        self.assertEqual(m.manacher_palindrome_radii(""), ([], []))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.manacher_palindrome_radii(7)
        self.assertEqual(str(ctx.exception), refusal(
            "manacher_palindrome_radii:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.manacher_palindrome_radii("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception), refusal(
            "manacher_palindrome_radii:too_many:s"))

    def test_oracle(self):
        rng = random.Random(9006)
        for _ in range(60):
            n = rng.randint(0, 25)
            s = "".join(rng.choice("abc") for _ in range(n))
            d1, d2 = [], []
            for i in range(n):
                r = 1
                while i - r >= 0 and i + r < n and s[i - r] == s[i + r]:
                    r += 1
                d1.append(r)
                r = 0
                while i - r - 1 >= 0 and i + r < n \
                        and s[i - r - 1] == s[i + r]:
                    r += 1
                d2.append(r)
            self.assertEqual(m.manacher_palindrome_radii(s), (d1, d2))


class TestLyndonFactorization(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.lyndon_factorization("ababa"),
                         ["ab", "ab", "a"])
        self.assertEqual(m.lyndon_factorization("cba"), ["c", "b", "a"])
        self.assertEqual(m.lyndon_factorization(""), [])
        self.assertEqual(m.lyndon_factorization("aaa"), ["a", "a", "a"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.lyndon_factorization(b"ab")
        self.assertEqual(str(ctx.exception),
                         refusal("lyndon_factorization:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.lyndon_factorization("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception),
                         refusal("lyndon_factorization:too_many:s"))

    def test_oracle(self):
        def is_lyndon(w):
            return all(w < w[i:] + w[:i] for i in range(1, len(w)))
        rng = random.Random(9007)
        for _ in range(60):
            n = rng.randint(0, 25)
            s = "".join(rng.choice("abc") for _ in range(n))
            want = []
            rest = s
            while rest:
                cut = 1
                for j in range(2, len(rest) + 1):
                    if is_lyndon(rest[:j]):
                        cut = j
                want.append(rest[:cut])
                rest = rest[cut:]
            self.assertEqual(m.lyndon_factorization(s), want)


class TestDistinctPalindromeCount(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.distinct_palindrome_count("aba"), 3)
        self.assertEqual(m.distinct_palindrome_count("abba"), 4)
        self.assertEqual(m.distinct_palindrome_count("aaa"), 3)
        self.assertEqual(m.distinct_palindrome_count(""), 0)
        self.assertEqual(m.distinct_palindrome_count("abcde"), 5)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.distinct_palindrome_count(None)
        self.assertEqual(str(ctx.exception), refusal(
            "distinct_palindrome_count:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.distinct_palindrome_count("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception), refusal(
            "distinct_palindrome_count:too_many:s"))

    def test_cap(self):
        self.assertEqual(m.distinct_palindrome_count("a" * MAX_ITEMS),
                         MAX_ITEMS)

    def test_oracle(self):
        rng = random.Random(9008)
        for _ in range(60):
            n = rng.randint(0, 25)
            s = "".join(rng.choice("abc") for _ in range(n))
            seen = set()
            for i in range(n):
                for j in range(i + 1, n + 1):
                    w = s[i:j]
                    if w == w[::-1]:
                        seen.add(w)
            self.assertEqual(m.distinct_palindrome_count(s), len(seen))


class TestLz78EncodePairs(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.lz78_encode_pairs(""), [])
        self.assertEqual(m.lz78_encode_pairs("aaa"),
                         [(0, "a"), (1, "a")])
        self.assertEqual(m.lz78_encode_pairs("ab"),
                         [(0, "a"), (0, "b")])
        self.assertEqual(m.lz78_encode_pairs("abab"),
                         [(0, "a"), (0, "b"), (1, "b")])

    def test_trailing_phrase(self):
        # a final run that is itself a known phrase closes with an
        # empty-character pair
        self.assertEqual(m.lz78_encode_pairs("ababa"),
                         [(0, "a"), (0, "b"), (1, "b"), (1, "")])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.lz78_encode_pairs(11)
        self.assertEqual(str(ctx.exception),
                         refusal("lz78_encode_pairs:bad_type:s"))
        with self.assertRaises(ValueError) as ctx:
            m.lz78_encode_pairs("a" * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception),
                         refusal("lz78_encode_pairs:too_many:s"))

    def test_oracle(self):
        def want(s):
            dictionary = {"": 0}
            out = []
            cur = ""
            for ch in s:
                if cur + ch in dictionary:
                    cur = cur + ch
                else:
                    out.append((dictionary[cur], ch))
                    dictionary[cur + ch] = len(dictionary)
                    cur = ""
            if cur:
                out.append((dictionary[cur], ""))
            return out
        rng = random.Random(9011)
        for _ in range(60):
            n = rng.randint(0, 40)
            s = "".join(rng.choice("ab") for _ in range(n))
            self.assertEqual(m.lz78_encode_pairs(s), want(s))


class TestRepeatedStringMatchMin(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.repeated_string_match_min("abcd", "cdabcdab"), 3)
        self.assertEqual(m.repeated_string_match_min("a", "aa"), 2)
        self.assertEqual(m.repeated_string_match_min("abc", "wxyz"), -1)
        self.assertEqual(m.repeated_string_match_min("ab", "bab"), 2)
        self.assertEqual(m.repeated_string_match_min("abc", "abc"), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.repeated_string_match_min("", "a")
        self.assertEqual(str(ctx.exception), refusal(
            "repeated_string_match_min:empty:a"))
        with self.assertRaises(ValueError) as ctx:
            m.repeated_string_match_min("a", "")
        self.assertEqual(str(ctx.exception), refusal(
            "repeated_string_match_min:empty:b"))
        with self.assertRaises(ValueError) as ctx:
            m.repeated_string_match_min("a" * (MAX_ITEMS + 1), "a")
        self.assertEqual(str(ctx.exception), refusal(
            "repeated_string_match_min:too_many:a"))

    def test_oracle(self):
        rng = random.Random(9010)
        for _ in range(60):
            na = rng.randint(1, 6)
            a = "".join(rng.choice("ab") for _ in range(na))
            nb = rng.randint(1, 15)
            b = "".join(rng.choice("ab") for _ in range(nb))
            want = -1
            for k in range(1, (nb + na - 1) // na + 8):
                if b in a * k:
                    want = k
                    break
            self.assertEqual(m.repeated_string_match_min(a, b), want)


class TestRegistryKnowsBatch90(unittest.TestCase):
    def test_registry_knows_batch90(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("suffix_array_build", "matching_statistics_lengths",
                     "bwt_encode", "bwt_decode", "smallest_distinct_subsequence",
                     "manacher_palindrome_radii", "lyndon_factorization",
                     "distinct_palindrome_count", "lz78_encode_pairs",
                     "repeated_string_match_min"):
            self.assertIn(name, names)

    def test_registry_total(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        self.assertEqual(reg.IMPLEMENTED_SO_FAR, 758)
        self.assertEqual(len(reg.ENTRIES), 758)


if __name__ == "__main__":
    unittest.main()
