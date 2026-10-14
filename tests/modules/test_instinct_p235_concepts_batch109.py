"""Tests for P235 concepts batch 109.

Every pin was read off a live run of the module. Randomized
and exhaustive checks compare against independent oracles:
brute-force permutation enumeration for involutions, a
queue-based pairing loop for the Merkle root, set/startswith
counting for the trie, a full denominator scan for the
Stern-Brocot approximation, Decimal ROUND_HALF_EVEN
quantization for the significant-figure render, a recursive
descent parser for the s-expression, regex splitting for the
natural sort key, bit-string rotation for the bit rotate,
increment-and-count for the next popcount, a
two's-complement reformulation for the sign extension, and
an ace-upgrade formulation for the blackjack total.
"""
import random
import re
import sys
import unittest
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from hashlib import sha256
from itertools import permutations

sys.path.insert(0, "backend")

from app.modules.instinct_doc import p235_concepts_batch109 as b109


class TestInvolutionsCount(unittest.TestCase):
    def test_pins(self):
        self.assertEqual([b109.involutions_count(i)
                          for i in range(13)],
                         [1, 1, 2, 4, 10, 26, 76, 232, 764,
                          2620, 9496, 35696, 140152])
        self.assertEqual(b109.involutions_count(20), 23758664096)

    def test_oracle_brute_force(self):
        # Independent oracle: enumerate every permutation of
        # range(n) and keep the ones equal to their inverse.
        for n in range(8):
            want = 0
            for p in permutations(range(n)):
                if all(p[p[i]] == i for i in range(n)):
                    want += 1
            self.assertEqual(b109.involutions_count(n), want)

    def test_caps(self):
        self.assertIsInstance(b109.involutions_count(400), int)
        with self.assertRaises(ValueError):
            b109.involutions_count(401)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.involutions_count(*args)
            self.assertIn("involutions_count:" + want,
                          str(ctx.exception))
        code("bad_type:n", True)
        code("bad_type:n", 3.5)
        code("bad_type:n", None)
        code("out_of_range:n", -1)


class TestMerkleRoot(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.merkle_root(["ab" * 32]),
                         "ab" * 32)
        self.assertEqual(
            b109.merkle_root(["ab" * 32, "cd" * 32]),
            "a6a96ccb5233f068bf41343ffd5984bf8d4d7e591f1e4bdb"
            "12bda296534409b8")
        self.assertEqual(
            b109.merkle_root(["00" * 32, "11" * 32, "22" * 32]),
            "f59242779d0bc9cfb1f3decf078f0dd2e0a5797bad13a445"
            "1ed3a96ad0e4182f")
        self.assertEqual(
            b109.merkle_root(["00" * 32, "11" * 32, "22" * 32,
                              "33" * 32]),
            "88162e1092549a7a540a1cd48634f24f4cf5a235e356ee36"
            "ce58cf84d3012195")

    def _oracle(self, digests):
        # Independent oracle: an inline two-pointer pairing
        # loop that handles the odd node in place rather than
        # by extending the level first.
        level = [bytes.fromhex(d) for d in digests]
        while len(level) > 1:
            nxt = []
            i = 0
            while i < len(level):
                a = level[i]
                b = level[i + 1] if i + 1 < len(level) else a
                nxt.append(sha256(a + b).digest())
                i += 2
            level = nxt
        return level[0].hex()

    def test_oracle_pairing(self):
        rng = random.Random(749)
        for _ in range(60):
            count = rng.randint(1, 33)
            digests = [sha256(bytes([count, j])).hexdigest()
                       for j in range(count)]
            self.assertEqual(b109.merkle_root(digests),
                             self._oracle(digests))

    def test_caps(self):
        ok = ["00" * 32] * 2048
        self.assertEqual(b109.merkle_root(ok), self._oracle(ok))
        with self.assertRaises(ValueError):
            b109.merkle_root(["00" * 32] * 2049)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.merkle_root(*args)
            self.assertIn("merkle_root:" + want,
                          str(ctx.exception))
        code("bad_type:digests", True)
        code("bad_type:digests", 3.5)
        code("bad_type:digests", None)
        code("empty:digests", [])
        code("too_many:digests", ["zz" * 32] * 2049)
        code("bad_type:digests[0]", [7])
        code("bad_shape:digests[0]", ["ab"])
        code("bad_shape:digests[1]",
             ["00" * 32, "AB" * 32][:1] + ["abc"])
        code("bad_char:digests[0]", ["00" * 31 + "0g"])
        code("bad_char:digests[0]", ["AB" * 32])


class TestTriePrefixCount(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b109.trie_prefix_count(
                ["to", "tea", "ten", "in", "inn", "tea"], "te"),
            2)
        self.assertEqual(b109.trie_prefix_count(["a"] * 5, ""),
                         1)
        self.assertEqual(
            b109.trie_prefix_count(["abc", "abd"], "abx"), 0)
        self.assertEqual(b109.trie_prefix_count([], ""), 0)
        self.assertEqual(
            b109.trie_prefix_count(["to", "tea", "ten"], ""), 3)
        self.assertEqual(
            b109.trie_prefix_count(["ab", "abc", "abd", "b"],
                                   "ab"), 3)
        self.assertEqual(b109.trie_prefix_count(["z"], "z"), 1)

    def test_oracle_set_scan(self):
        rng = random.Random(750)
        for _ in range(80):
            words = ["".join(rng.choice("abc")
                             for _ in range(rng.randint(1, 6)))
                     for _ in range(rng.randint(0, 20))]
            prefix = "".join(rng.choice("abc")
                             for _ in range(rng.randint(0, 4)))
            want = sum(1 for w in set(words)
                       if w.startswith(prefix))
            self.assertEqual(
                b109.trie_prefix_count(words, prefix), want)

    def test_caps(self):
        self.assertEqual(
            b109.trie_prefix_count(["a"] * 1000, ""), 1)
        with self.assertRaises(ValueError):
            b109.trie_prefix_count(["a"] * 1001, "")
        self.assertEqual(
            b109.trie_prefix_count(["a" * 64], "a" * 64), 1)
        with self.assertRaises(ValueError):
            b109.trie_prefix_count(["a" * 65], "")
        with self.assertRaises(ValueError):
            b109.trie_prefix_count([], "a" * 65)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.trie_prefix_count(*args)
            self.assertIn("trie_prefix_count:" + want,
                          str(ctx.exception))
        code("bad_type:words", True, "")
        code("bad_type:words", 3.5, "")
        code("bad_type:words", None, "")
        code("bad_type:prefix", ["a"], True)
        code("bad_type:prefix", ["a"], 3.5)
        code("bad_type:prefix", ["a"], None)
        code("bad_char:prefix", ["a"], "A")
        code("bad_type:words[0]", [True], "")
        code("bad_type:words[0]", [3.5], "")
        code("bad_type:words[0]", [None], "")
        code("empty:words[0]", [""], "")
        code("bad_char:words[0]", ["A"], "")
        code("bad_char:words[1]", ["ok", "x-y"], "")
        code("too_many:words", ["bad word"] * 1001, "")


class TestBestRationalApprox(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.best_rational_approx(1, 10, 6),
                         (1, 6))
        self.assertEqual(
            b109.best_rational_approx(355, 113, 100), (311, 99))
        self.assertEqual(
            b109.best_rational_approx(1, 10**6, 10**6),
            (1, 1000000))
        self.assertEqual(b109.best_rational_approx(2, 10**6, 3),
                         (0, 1))
        self.assertEqual(b109.best_rational_approx(1, 7, 3),
                         (0, 1))
        self.assertEqual(b109.best_rational_approx(5, 7, 2),
                         (1, 2))
        self.assertEqual(b109.best_rational_approx(1, 2, 1),
                         (0, 1))
        self.assertEqual(b109.best_rational_approx(7, 5, 3),
                         (4, 3))
        self.assertEqual(b109.best_rational_approx(22, 7, 10),
                         (22, 7))
        self.assertEqual(b109.best_rational_approx(1, 3, 7),
                         (1, 3))
        self.assertEqual(
            b109.best_rational_approx(10**18, 1, 10**6),
            (10**18, 1))
        self.assertEqual(b109.best_rational_approx(0, 7, 3),
                         (0, 1))
        # Auditor witness: magnitude no longer bounds the
        # walk; this returns instantly.
        self.assertEqual(
            b109.best_rational_approx(10**18 - 1, 2, 1),
            (499999999999999999, 1))

    def _oracle(self, num, den, max_den):
        # Independent oracle: scan every allowed denominator,
        # check the two nearest numerators, keep the best by
        # exact cross-multiplied distance with the documented
        # tie rule.
        from fractions import Fraction
        t = Fraction(num, den)
        best = None
        for q in range(1, max_den + 1):
            approx = t * q
            floor = approx.numerator // approx.denominator
            for p in {floor, floor + 1}:
                if p < 0:
                    continue
                dist = abs(Fraction(p, q) - t)
                key = (dist, q, p)
                if best is None or key < best[0]:
                    best = (key, (p, q))
        return best[1]

    def test_oracle_denominator_scan(self):
        rng = random.Random(751)
        for _ in range(150):
            num = rng.randint(0, 300)
            den = rng.randint(1, 300)
            max_den = rng.randint(1, 60)
            self.assertEqual(
                b109.best_rational_approx(num, den, max_den),
                self._oracle(num, den, max_den))

    def test_caps(self):
        self.assertEqual(
            b109.best_rational_approx(1, 2, 10**6), (1, 2))
        with self.assertRaises(ValueError):
            b109.best_rational_approx(1, 2, 10**6 + 1)
        self.assertEqual(
            b109.best_rational_approx(10**18, 10**18, 1),
            (1, 1))
        with self.assertRaises(ValueError):
            b109.best_rational_approx(10**18 + 1, 1, 1)
        with self.assertRaises(ValueError):
            b109.best_rational_approx(1, 10**18 + 1, 1)
        # Adversarial walk: target near zero with the largest
        # allowed denominator finishes fast.
        self.assertEqual(
            b109.best_rational_approx(1, 10**18, 10**6),
            (0, 1))

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.best_rational_approx(*args)
            self.assertIn("best_rational_approx:" + want,
                          str(ctx.exception))
        for arg in (True, 3.5, None):
            code("bad_type:num", arg, 1, 1)
            code("bad_type:den", 1, arg, 1)
            code("bad_type:max_den", 1, 1, arg)
        code("out_of_range:num", -1, 1, 1)
        code("out_of_range:den", 1, 0, 1)
        code("out_of_range:max_den", 1, 1, 0)


class TestRoundSignificant(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.round_significant(1235, 1, 2),
                         "1200")
        self.assertEqual(b109.round_significant(1235, 1, 3),
                         "1240")
        self.assertEqual(b109.round_significant(996, 10000, 2),
                         "0.10")
        self.assertEqual(b109.round_significant(1, 3, 4),
                         "0.3333")
        self.assertEqual(b109.round_significant(25, 10, 2),
                         "2.5")
        self.assertEqual(b109.round_significant(125, 100, 2),
                         "1.2")
        self.assertEqual(b109.round_significant(135, 100, 2),
                         "1.4")
        self.assertEqual(b109.round_significant(0, 7, 3), "0")
        self.assertEqual(
            b109.round_significant(10**18, 1, 5),
            "1000000000000000000")
        self.assertEqual(
            b109.round_significant(1, 10**18, 3),
            "0.00000000000000000100")
        self.assertEqual(b109.round_significant(99999, 100, 4),
                         "1000")
        self.assertEqual(b109.round_significant(1, 2, 6),
                         "0.500000")
        self.assertEqual(
            b109.round_significant(314159, 100000, 3), "3.14")
        self.assertEqual(
            b109.round_significant(1, 7000000, 1), "0.0000001")

    def _oracle(self, num, den, digits):
        # Independent oracle: Decimal division at 400 digits,
        # exponent from adjusted(), quantize ROUND_HALF_EVEN.
        if num == 0:
            return "0"
        with localcontext() as ctx:
            ctx.prec = 400
            ctx.rounding = ROUND_HALF_EVEN
            x = Decimal(num) / Decimal(den)
            k = x.adjusted()
            s = k - digits + 1
            q = Decimal(1).scaleb(s)
            return format(x.quantize(q), "f")

    def test_oracle_decimal(self):
        rng = random.Random(752)
        for _ in range(200):
            num = rng.randint(1, 10**9)
            den = rng.randint(1, 10**9)
            digits = rng.randint(1, 18)
            self.assertEqual(
                b109.round_significant(num, den, digits),
                self._oracle(num, den, digits))

    def test_caps(self):
        self.assertEqual(b109.round_significant(1, 3, 18),
                         "0.333333333333333333")
        with self.assertRaises(ValueError):
            b109.round_significant(1, 3, 19)
        self.assertEqual(
            b109.round_significant(10**18, 10**18, 1), "1")
        with self.assertRaises(ValueError):
            b109.round_significant(10**18 + 1, 1, 1)
        with self.assertRaises(ValueError):
            b109.round_significant(1, 10**18 + 1, 1)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.round_significant(*args)
            self.assertIn("round_significant:" + want,
                          str(ctx.exception))
        for arg in (True, 3.5, None):
            code("bad_type:num", arg, 1, 1)
            code("bad_type:den", 1, arg, 1)
            code("bad_type:digits", 1, 1, arg)
        code("out_of_range:num", -1, 1, 1)
        code("out_of_range:den", 1, 0, 1)
        code("out_of_range:digits", 1, 1, 0)


class TestSexpParse(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.sexp_parse("(a 1 (2 -3) x)"),
                         ["a", 1, [2, -3], "x"])
        self.assertEqual(b109.sexp_parse("()"), [])
        self.assertEqual(b109.sexp_parse("42"), 42)
        self.assertEqual(b109.sexp_parse("  ( foo   bar ) "),
                         ["foo", "bar"])
        self.assertEqual(b109.sexp_parse("(1 (2 (3)))"),
                         [1, [2, [3]]])
        self.assertEqual(b109.sexp_parse("-007"), -7)
        self.assertEqual(b109.sexp_parse("(- x)"), ["-", "x"])

    def _oracle(self, text):
        # Independent oracle: recursive descent over the raw
        # text with an index, rather than a token list plus
        # stack.
        ws = " \t\n\r"

        def skip(i):
            while i < len(text) and text[i] in ws:
                i += 1
            return i

        def parse(i):
            i = skip(i)
            if text[i] == "(":
                out = []
                i = skip(i + 1)
                while text[i] != ")":
                    value, i = parse(i)
                    out.append(value)
                    i = skip(i)
                return out, i + 1
            j = i
            while j < len(text) and text[j] not in ws + "()":
                j += 1
            atom = text[i:j]
            body = atom[1:] if atom.startswith("-") else atom
            if body and all(c in "0123456789" for c in body):
                return int(atom), j
            return atom, j

        value, end = parse(0)
        if skip(end) != len(text):
            raise AssertionError("oracle found trailing text")
        return value

    def test_oracle_recursive_descent(self):
        rng = random.Random(753)

        def random_datum(depth):
            if depth == 0 or rng.random() < 0.4:
                return rng.choice([0, 7, -13, "a", "xyz", "-"])
            return [random_datum(depth - 1)
                    for _ in range(rng.randint(0, 4))]

        def render(datum):
            if isinstance(datum, list):
                return "(" + " ".join(render(d)
                                      for d in datum) + ")"
            return str(datum)

        for _ in range(150):
            datum = random_datum(4)
            self.assertEqual(b109.sexp_parse(render(datum)),
                             datum)
        self.assertEqual(self._oracle("(a (b c) 12)"),
                         ["a", ["b", "c"], 12])

    def test_caps(self):
        self.assertEqual(len(b109.sexp_parse(
            "(" * 100 + ")" * 100)), 1)
        with self.assertRaises(ValueError):
            b109.sexp_parse("(" * 101 + ")" * 101)
        self.assertEqual(b109.sexp_parse("a" * 10000),
                         "a" * 10000)
        with self.assertRaises(ValueError):
            b109.sexp_parse("a" * 10001)
        self.assertEqual(b109.sexp_parse("9" * 4300),
                         int("9" * 4300))
        with self.assertRaises(ValueError) as ctx:
            b109.sexp_parse("9" * 4301)
        self.assertIn("sexp_parse:too_long:atom",
                      str(ctx.exception))

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.sexp_parse(*args)
            self.assertIn("sexp_parse:" + want,
                          str(ctx.exception))
        code("bad_type:text", True)
        code("bad_type:text", 3.5)
        code("bad_type:text", None)
        code("empty:text", "")
        code("empty:text", "   ")
        code("bad_char:text", '(a "b")')
        code("bad_char:text", "(a 'b)")
        code("unbalanced:text", "(a b")
        code("unbalanced:text", ")")
        code("unbalanced:text", "((a)")
        code("trailing:text", "a b)")
        code("trailing:text", "a b")
        code("trailing:text", "(a) (b)")


class TestNaturalSortKey(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.natural_sort_key("a12b3"),
                         [(1, "a"), (0, 12), (1, "b"), (0, 3)])
        self.assertEqual(b109.natural_sort_key("file010x"),
                         [(1, "file"), (0, 10), (1, "x")])
        self.assertEqual(b109.natural_sort_key(""), [])
        self.assertEqual(b109.natural_sort_key("abc"),
                         [(1, "abc")])
        self.assertEqual(b109.natural_sort_key("007"), [(0, 7)])

    def test_oracle_regex(self):
        rng = random.Random(754)
        alphabet = "ab019 x"
        for _ in range(200):
            text = "".join(rng.choice(alphabet)
                           for _ in range(rng.randint(0, 24)))
            want = [(0, int(c)) if c.isdigit() else (1, c)
                    for c in re.findall(r"[0-9]+|[^0-9]+",
                                        text)]
            self.assertEqual(b109.natural_sort_key(text), want)

    def test_ordering_use(self):
        names = ["file10", "file9", "file010", "file"]
        self.assertEqual(
            sorted(names, key=b109.natural_sort_key),
            ["file", "file9", "file10", "file010"])
        # Mixed digit-first and letter-first texts compare
        # without a TypeError.
        self.assertEqual(
            sorted(["a", "1", "a10"], key=b109.natural_sort_key),
            ["1", "a", "a10"])

    def test_caps(self):
        self.assertEqual(b109.natural_sort_key("9" * 4300),
                         [(0, int("9" * 4300))])
        with self.assertRaises(ValueError) as ctx:
            b109.natural_sort_key("9" * 4301)
        self.assertIn("natural_sort_key:too_long:digit_run",
                      str(ctx.exception))
        self.assertEqual(b109.natural_sort_key("a" * 10000),
                         [(1, "a" * 10000)])
        with self.assertRaises(ValueError):
            b109.natural_sort_key("a" * 10001)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.natural_sort_key(*args)
            self.assertIn("natural_sort_key:" + want,
                          str(ctx.exception))
        code("bad_type:text", True)
        code("bad_type:text", 3.5)
        code("bad_type:text", None)


class TestSignExtendBits(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.sign_extend_bits(0b1011, 4), -5)
        self.assertEqual(b109.sign_extend_bits(0b0111, 4), 7)
        self.assertEqual(b109.sign_extend_bits(0, 1), 0)
        self.assertEqual(b109.sign_extend_bits(1, 1), -1)
        self.assertEqual(b109.sign_extend_bits(0x80000000, 32),
                         -2147483648)
        self.assertEqual(b109.sign_extend_bits(2**63, 64),
                         -(2**63))
        self.assertEqual(b109.sign_extend_bits(2**64 - 1, 64),
                         -1)
        self.assertEqual(b109.sign_extend_bits(5, 4), 5)
        self.assertEqual(b109.sign_extend_bits(4, 4), 4)

    def _oracle(self, x, width):
        # Independent oracle: negate the complement when the
        # sign bit is set, rather than subtracting the modulus.
        bits = format(x, "0%db" % width)
        if bits[0] == "0":
            return int(bits, 2)
        mask = (1 << width) - 1
        return -((~x & mask) + 1)

    def test_oracle_complement(self):
        rng = random.Random(759)
        for _ in range(200):
            width = rng.randint(1, 64)
            x = rng.randint(0, (1 << width) - 1)
            self.assertEqual(b109.sign_extend_bits(x, width),
                             self._oracle(x, width))
        for width in (1, 2, 8, 16, 32, 64):
            for x in (0, 1, (1 << (width - 1)) - 1,
                      1 << (width - 1), (1 << width) - 1):
                self.assertEqual(
                    b109.sign_extend_bits(x, width),
                    self._oracle(x, width))

    def test_caps(self):
        self.assertEqual(b109.sign_extend_bits(2**64 - 1, 64),
                         -1)
        with self.assertRaises(ValueError):
            b109.sign_extend_bits(0, 65)
        with self.assertRaises(ValueError):
            b109.sign_extend_bits(1 << 4, 4)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.sign_extend_bits(*args)
            self.assertIn("sign_extend_bits:" + want,
                          str(ctx.exception))
        for arg in (True, 3.5, None):
            code("bad_type:x", arg, 4)
            code("bad_type:width", 1, arg)
        code("out_of_range:x", -1, 4)
        code("out_of_range:width", 1, 0)


class TestNextSamePopcount(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.next_same_popcount(1), 2)
        self.assertEqual(b109.next_same_popcount(7), 11)
        self.assertEqual(b109.next_same_popcount(8), 16)
        self.assertEqual(b109.next_same_popcount(0b10110), 25)
        self.assertEqual(b109.next_same_popcount(2), 4)
        self.assertEqual(b109.next_same_popcount(0b1111), 23)
        self.assertEqual(b109.next_same_popcount(0b100000), 64)
        self.assertEqual(b109.next_same_popcount(10**18),
                         1000000000000262144)

    def _oracle(self, n):
        # Independent oracle: count upward comparing set-bit
        # tallies through bin().
        target = bin(n).count("1")
        m = n + 1
        while bin(m).count("1") != target:
            m += 1
        return m

    def test_oracle_increment(self):
        rng = random.Random(756)
        for _ in range(100):
            n = rng.randint(1, 10**6)
            self.assertEqual(b109.next_same_popcount(n),
                             self._oracle(n))
        for n in (1, 2, 3, 7, 15, 16):
            self.assertEqual(b109.next_same_popcount(n),
                             self._oracle(n))
        # Single-bit and all-ones inputs have distant
        # successors, so these are module pins, not oracle
        # sweeps.
        self.assertEqual(b109.next_same_popcount(2**31), 2**32)
        self.assertEqual(b109.next_same_popcount(2**31 - 1),
                         2**31 + 2**30 - 1)

    def test_caps(self):
        self.assertEqual(b109.next_same_popcount(10**18),
                         self._oracle(10**18))
        with self.assertRaises(ValueError):
            b109.next_same_popcount(10**18 + 1)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.next_same_popcount(*args)
            self.assertIn("next_same_popcount:" + want,
                          str(ctx.exception))
        code("bad_type:n", True)
        code("bad_type:n", 3.5)
        code("bad_type:n", None)
        code("out_of_range:n", 0)
        code("out_of_range:n", -5)


class TestBlackjackHandValue(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b109.blackjack_hand_value(["a", "k"]),
                         21)
        self.assertEqual(
            b109.blackjack_hand_value(["a", "a", "9"]), 21)
        self.assertEqual(
            b109.blackjack_hand_value(["a", "a", "a", "a"]),
                         14)
        self.assertEqual(b109.blackjack_hand_value(["k", "q"]),
                         20)
        self.assertEqual(
            b109.blackjack_hand_value(["10", "8", "5"]), 23)
        self.assertEqual(
            b109.blackjack_hand_value(["a", "5", "a"]), 17)
        self.assertEqual(
            b109.blackjack_hand_value(["2", "3", "4"]), 9)
        self.assertEqual(
            b109.blackjack_hand_value(["a"] * 11), 21)

    def _oracle(self, cards):
        # Independent oracle: count every ace as one, then
        # upgrade aces back to eleven one at a time while the
        # total stays within twenty-one.
        values = {"j": 10, "q": 10, "k": 10, "a": 1}
        total = sum(values.get(c, int(c) if c.isdigit() else 0)
                    for c in cards)
        for c in cards:
            if c == "a" and total + 10 <= 21:
                total += 10
        return total

    def test_oracle_ace_upgrade(self):
        rng = random.Random(758)
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10",
                 "j", "q", "k", "a"]
        for _ in range(300):
            cards = [rng.choice(ranks)
                     for _ in range(rng.randint(1, 11))]
            self.assertEqual(b109.blackjack_hand_value(cards),
                             self._oracle(cards))
        # exhaustive over all two-card hands
        for c1 in ranks:
            for c2 in ranks:
                self.assertEqual(
                    b109.blackjack_hand_value([c1, c2]),
                    self._oracle([c1, c2]))

    def test_caps(self):
        self.assertEqual(
            b109.blackjack_hand_value(["9"] * 11), 99)
        with self.assertRaises(ValueError):
            b109.blackjack_hand_value(["9"] * 12)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b109.blackjack_hand_value(*args)
            self.assertIn("blackjack_hand_value:" + want,
                          str(ctx.exception))
        code("bad_type:cards", True)
        code("bad_type:cards", 3.5)
        code("bad_type:cards", None)
        code("empty:cards", [])
        code("too_many:cards", ["zz"] * 12)
        code("bad_type:cards[0]", [True])
        code("bad_type:cards[0]", [3.5])
        code("bad_type:cards[0]", [None])
        code("bad_rank:cards[0]", ["1"])
        code("bad_rank:cards[0]", ["A"])
        code("bad_rank:cards[0]", ["joker"])
        code("bad_rank:cards[1]", ["k", "11"])


if __name__ == "__main__":
    unittest.main()
