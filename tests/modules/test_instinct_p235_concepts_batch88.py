"""Tests for P235 concepts batch 88 (combinatorial enumeration)."""

import itertools
import random
import re
import unittest

from app.modules.instinct_doc import p235_concepts_batch88 as m
from app.modules.instinct_doc import p235_concepts_registry as reg

MAX_ITEMS = reg.MAX_ITEMS


def refusal(code):
    return "P235:" + code


class TestSubsetsList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.subsets_list([1, 2]), [[], [1], [2], [1, 2]])
        self.assertEqual(m.subsets_list([3]), [[], [3]])
        self.assertEqual(m.subsets_list([2, 1]),
                         [[], [1], [2], [1, 2]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.subsets_list([1, 1])
        self.assertEqual(str(ctx.exception),
                         refusal("subsets_list:duplicate:items"))
        with self.assertRaises(ValueError) as ctx:
            m.subsets_list([])
        self.assertEqual(str(ctx.exception),
                         refusal("subsets_list:empty:items"))
        with self.assertRaises(ValueError) as ctx:
            m.subsets_list(list(range(14)))
        self.assertEqual(str(ctx.exception),
                         refusal("subsets_list:too_many:items"))

    def test_cap(self):
        self.assertEqual(len(m.subsets_list(list(range(13)))), 8192)

    def test_oracle(self):
        def oracle(items):
            ordered = sorted(items)
            out = []
            for mask in range(2 ** len(ordered)):
                out.append([ordered[i] for i in range(len(ordered))
                            if mask >> i & 1])
            out.sort(key=lambda s: (len(s), s))
            return out
        rng = random.Random(8801)
        for _ in range(60):
            n = rng.randint(1, 9)
            items = rng.sample(range(-50, 50), n)
            self.assertEqual(m.subsets_list(items), oracle(items))


class TestPermutationsList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.permutations_list([2, 1]), [[1, 2], [2, 1]])
        self.assertEqual(m.permutations_list([3, 1, 2]),
                         [[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1],
                          [3, 1, 2], [3, 2, 1]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.permutations_list([1, 1])
        self.assertEqual(str(ctx.exception),
                         refusal("permutations_list:duplicate:items"))
        with self.assertRaises(ValueError) as ctx:
            m.permutations_list(list(range(8)))
        self.assertEqual(str(ctx.exception),
                         refusal("permutations_list:too_many:items"))

    def test_cap(self):
        self.assertEqual(len(m.permutations_list(list(range(7)))), 5040)

    def test_oracle(self):
        def oracle(items):
            return [list(p) for p in
                    itertools.permutations(sorted(items))]
        rng = random.Random(8803)
        for _ in range(60):
            n = rng.randint(1, 6)
            items = rng.sample(range(-30, 30), n)
            self.assertEqual(m.permutations_list(items), oracle(items))


class TestCombinationSumLists(unittest.TestCase):
    def test_pruning_work_pins(self):
        # These two zero-output pins do not distinguish single
        # pruning guards because the guards cover each other on
        # these inputs. Positive-output inputs can distinguish a
        # removed reachability skip.
        import time
        for candidates, target in (
                (list(range(2, 22, 2)), 299),
                (list(range(2, 1002, 2)), 1001),
                (list(range(2, 22, 2)) + [299], 299),
                (list(range(2, 102, 2)) + [1001], 1001)):
            start = time.monotonic()
            m.combination_sum_lists(candidates, target)
            self.assertLess(time.monotonic() - start, 3.0)

    def test_canonical(self):
        self.assertEqual(m.combination_sum_lists([2, 3], 6),
                         [[2, 2, 2], [3, 3]])
        self.assertEqual(m.combination_sum_lists([2, 3, 6, 7], 7),
                         [[2, 2, 3], [7]])
        self.assertEqual(m.combination_sum_lists([5], 3), [])

    def test_deep_single_candidate(self):
        # the recursion-depth regression input: one candidate, a
        # large in-domain target, exactly one combination
        self.assertEqual(m.combination_sum_lists([1], 1000),
                         [[1] * 1000])

    def test_count_boundary(self):
        # [1, 2] sums to t in exactly t//2 + 1 ways
        self.assertEqual(len(m.combination_sum_lists([1, 2], 2000)),
                         1001)

    def test_dead_end_inputs_return_fast(self):
        # audit regression inputs: output is empty, and the walk
        # must not visit dead-end prefixes at all
        self.assertEqual(
            m.combination_sum_lists(list(range(2, 22, 2)), 299), [])
        self.assertEqual(
            m.combination_sum_lists(list(range(2, 1002, 2)), 1001),
            [])

    def test_work_budget_refusal(self):
        with self.assertRaises(ValueError) as ctx:
            m.combination_sum_lists(list(range(1, 10001)), 10000)
        self.assertEqual(str(ctx.exception), refusal(
            "combination_sum_lists:too_much:work"))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.combination_sum_lists([1], 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "combination_sum_lists:out_of_range:target"))
        with self.assertRaises(ValueError) as ctx:
            m.combination_sum_lists([0, 2], 4)
        self.assertEqual(str(ctx.exception), refusal(
            "combination_sum_lists:out_of_range:candidates[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.combination_sum_lists([1], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "combination_sum_lists:out_of_range:target"))
        with self.assertRaises(ValueError) as ctx:
            m.combination_sum_lists([1, 2, 3], MAX_ITEMS)
        self.assertEqual(str(ctx.exception), refusal(
            "combination_sum_lists:too_many:output"))

    def test_oracle(self):
        def oracle(candidates, target):
            found = set()
            longest = target // min(candidates)
            for length in range(1, longest + 1):
                for combo in itertools.product(candidates,
                                               repeat=length):
                    if (sum(combo) == target
                            and list(combo) == sorted(combo)):
                        found.add(combo)
            return sorted([list(c) for c in found])
        rng = random.Random(8804)
        for _ in range(60):
            candidates = rng.sample(range(1, 10), rng.randint(1, 4))
            target = rng.randint(1, 18)
            self.assertEqual(m.combination_sum_lists(candidates, target),
                             oracle(candidates, target))


class TestPartitionPalindromeLists(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.partition_palindrome_lists("aab"),
                         [["a", "a", "b"], ["aa", "b"]])
        self.assertEqual(m.partition_palindrome_lists("x"), [["x"]])
        self.assertEqual(m.partition_palindrome_lists("ab"),
                         [["a", "b"]])
        self.assertEqual(m.partition_palindrome_lists("aA"),
                         [["a", "A"]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.partition_palindrome_lists("")
        self.assertEqual(str(ctx.exception), refusal(
            "partition_palindrome_lists:empty:text"))
        with self.assertRaises(ValueError) as ctx:
            m.partition_palindrome_lists("a" * 17)
        self.assertEqual(str(ctx.exception), refusal(
            "partition_palindrome_lists:too_long:text"))
        with self.assertRaises(ValueError) as ctx:
            m.partition_palindrome_lists("a" * 16)
        self.assertEqual(str(ctx.exception), refusal(
            "partition_palindrome_lists:too_many:output"))

    def test_exact_counts(self):
        self.assertEqual(m.partition_palindrome_lists("aaa"),
                         [["a", "a", "a"], ["a", "aa"], ["aa", "a"],
                          ["aaa"]])
        self.assertEqual(len(m.partition_palindrome_lists("aaaa")), 8)
        self.assertEqual(len(m.partition_palindrome_lists("a" * 14)),
                         8192)

    def test_cap(self):
        self.assertEqual(len(m.partition_palindrome_lists("a" * 13)),
                         4096)
        with self.assertRaises(ValueError) as ctx:
            m.partition_palindrome_lists("a" * 15)
        self.assertEqual(str(ctx.exception), refusal(
            "partition_palindrome_lists:too_many:output"))

    def test_oracle(self):
        def oracle(text):
            n = len(text)
            out = []
            for mask in range(2 ** (n - 1)):
                parts = []
                run = text[0]
                for i in range(1, n):
                    if mask >> (i - 1) & 1:
                        parts.append(run)
                        run = text[i]
                    else:
                        run += text[i]
                parts.append(run)
                if all(p == p[::-1] for p in parts):
                    out.append(parts)
            out.sort()
            return out
        rng = random.Random(8805)
        alphabet = "aab"
        for _ in range(60):
            text = "".join(rng.choice(alphabet)
                           for _ in range(rng.randint(1, 9)))
            self.assertEqual(m.partition_palindrome_lists(text),
                             oracle(text))


class TestRestoreIpAddresses(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.restore_ip_addresses("25525511135"),
                         ["255.255.11.135", "255.255.111.35"])
        self.assertEqual(m.restore_ip_addresses("0000"), ["0.0.0.0"])
        self.assertEqual(m.restore_ip_addresses("101023"),
                         ["1.0.10.23", "1.0.102.3", "10.1.0.23",
                          "10.10.2.3", "101.0.2.3"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.restore_ip_addresses("12a4")
        self.assertEqual(str(ctx.exception), refusal(
            "restore_ip_addresses:bad_value:digits"))
        with self.assertRaises(ValueError) as ctx:
            m.restore_ip_addresses("123")
        self.assertEqual(str(ctx.exception), refusal(
            "restore_ip_addresses:bad_length:digits"))
        with self.assertRaises(ValueError) as ctx:
            m.restore_ip_addresses("1" * 13)
        self.assertEqual(str(ctx.exception), refusal(
            "restore_ip_addresses:bad_length:digits"))

    def test_oracle(self):
        def oracle(digits):
            out = []
            spots = range(1, len(digits))
            for a, b, c in itertools.combinations(spots, 3):
                parts = [digits[:a], digits[a:b], digits[b:c],
                         digits[c:]]
                ok = True
                for p in parts:
                    if not p or len(p) > 3:
                        ok = False
                    elif len(p) > 1 and p[0] == "0":
                        ok = False
                    elif int(p) > 255:
                        ok = False
                if ok:
                    out.append(".".join(parts))
            out.sort()
            return out
        rng = random.Random(8806)
        for _ in range(60):
            digits = "".join(rng.choice("0123456789")
                             for _ in range(rng.randint(4, 12)))
            self.assertEqual(m.restore_ip_addresses(digits),
                             oracle(digits))


class TestBraceExpandList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.brace_expand_list("{a,b}c{d,e}f"),
                         ["acdf", "acef", "bcdf", "bcef"])
        self.assertEqual(m.brace_expand_list("abcd"), ["abcd"])
        self.assertEqual(m.brace_expand_list("{b,a}"), ["a", "b"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.brace_expand_list("{a,b")
        self.assertEqual(str(ctx.exception),
                         refusal("brace_expand_list:bad_value:text"))
        with self.assertRaises(ValueError) as ctx:
            m.brace_expand_list("{ab}")
        self.assertEqual(str(ctx.exception),
                         refusal("brace_expand_list:bad_value:text"))
        with self.assertRaises(ValueError) as ctx:
            m.brace_expand_list("A")
        self.assertEqual(str(ctx.exception),
                         refusal("brace_expand_list:bad_value:text"))
        with self.assertRaises(ValueError) as ctx:
            m.brace_expand_list("{a,b}" * 14)
        self.assertEqual(str(ctx.exception),
                         refusal("brace_expand_list:too_many:output"))

    def test_grammar_edges(self):
        self.assertEqual(m.brace_expand_list("{a}"), ["a"])
        self.assertEqual(m.brace_expand_list("x{a,b}y{c}z"),
                         ["xaycz", "xbycz"])
        for bad in ("{}", "{a,}", "{,a}", "a{b", "{a,b}{", "{a,,b}"):
            with self.assertRaises(ValueError) as ctx:
                m.brace_expand_list(bad)
            self.assertEqual(str(ctx.exception),
                             refusal("brace_expand_list:bad_value:text"))

    def test_cap(self):
        self.assertEqual(len(m.brace_expand_list("{a,b}" * 13)), 8192)
        self.assertEqual(len(m.brace_expand_list("{a,b,c,d}" * 6)),
                         4096)
        with self.assertRaises(ValueError) as ctx:
            m.brace_expand_list("{a,b,c,d}" * 7)
        self.assertEqual(str(ctx.exception),
                         refusal("brace_expand_list:too_many:output"))

    def test_oracle(self):
        def oracle(text):
            groups = []
            for token in re.findall(r"\{[^}]*\}|[a-z]", text):
                if token.startswith("{"):
                    groups.append(sorted(token[1:-1].split(",")))
                else:
                    groups.append([token])
            return sorted("".join(p)
                          for p in itertools.product(*groups))
        rng = random.Random(8808)
        for _ in range(60):
            atoms = []
            for _ in range(rng.randint(1, 5)):
                if rng.random() < 0.5:
                    atoms.append(rng.choice("abcd"))
                else:
                    opts = rng.sample("abcd", rng.randint(1, 3))
                    atoms.append("{" + ",".join(opts) + "}")
            text = "".join(atoms)
            self.assertEqual(m.brace_expand_list(text), oracle(text))


class TestTowerOfHanoiMoves(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.tower_of_hanoi_moves(2),
                         [["A", "B"], ["A", "C"], ["B", "C"]])
        self.assertEqual(m.tower_of_hanoi_moves(1), [["A", "C"]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.tower_of_hanoi_moves(0)
        self.assertEqual(str(ctx.exception),
                         refusal("tower_of_hanoi_moves:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.tower_of_hanoi_moves(14)
        self.assertEqual(str(ctx.exception),
                         refusal("tower_of_hanoi_moves:too_many:n"))

    def test_exact_lengths(self):
        self.assertEqual(len(m.tower_of_hanoi_moves(4)), 15)
        self.assertEqual(len(m.tower_of_hanoi_moves(10)), 1023)

    def test_huge_n_gated_before_exponent(self):
        with self.assertRaises(ValueError) as ctx:
            m.tower_of_hanoi_moves(10 ** 9)
        self.assertEqual(str(ctx.exception),
                         refusal("tower_of_hanoi_moves:too_many:n"))

    def test_cap(self):
        self.assertEqual(len(m.tower_of_hanoi_moves(13)), 8191)

    def test_oracle(self):
        def oracle(n):
            # independent: simulate the move sequence on real pegs
            # and accept only a sequence that legally solves it;
            # the sequence itself comes from the iterative
            # smallest-disk cycle rule.
            pegs = {"A": list(range(n, 0, -1)), "B": [], "C": []}
            order = (("A", "C", "B") if n % 2 else ("A", "B", "C"))
            out = []
            while len(pegs["C"]) < n:
                for src, dst in ((order[0], order[1]),
                                 (order[0], order[2]),
                                 (order[1], order[2])):
                    if len(pegs["C"]) == n:
                        break
                    if pegs[src] and (not pegs[dst]
                                      or pegs[src][-1] < pegs[dst][-1]):
                        frm, to = src, dst
                    elif pegs[dst] and (not pegs[src]
                                        or pegs[dst][-1] < pegs[src][-1]):
                        frm, to = dst, src
                    else:
                        continue
                    pegs[to].append(pegs[frm].pop())
                    out.append([frm, to])
            return out
        for n in range(1, 8):
            self.assertEqual(m.tower_of_hanoi_moves(n), oracle(n))


class TestFactorizationLists(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.factorization_lists(12),
                         [[2, 2, 3], [2, 6], [3, 4], [12]])
        self.assertEqual(m.factorization_lists(16),
                         [[2, 2, 2, 2], [2, 2, 4], [2, 8], [4, 4],
                          [16]])
        self.assertEqual(m.factorization_lists(2), [[2]])
        self.assertEqual(m.factorization_lists(7), [[7]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.factorization_lists(1)
        self.assertEqual(str(ctx.exception),
                         refusal("factorization_lists:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.factorization_lists(10001)
        self.assertEqual(str(ctx.exception),
                         refusal("factorization_lists:out_of_range:n"))

    def test_oracle(self):
        def oracle(n):
            out = []

            def walk(remaining, start, picked):
                out.append(picked + [remaining])
                d = max(start, 2)
                while d * d <= remaining:
                    if remaining % d == 0:
                        walk(remaining // d, d, picked + [d])
                    d += 1
            walk(n, 2, [])
            return sorted(out)
        for n in list(range(2, 60)) + [97, 120, 360, 1024]:
            self.assertEqual(m.factorization_lists(n), oracle(n))


class TestStrobogrammaticList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.strobogrammatic_list(1), ["0", "1", "8"])
        self.assertEqual(m.strobogrammatic_list(2),
                         ["11", "69", "88", "96"])
        self.assertEqual(m.strobogrammatic_list(3),
                         ["101", "111", "181", "609", "619", "689",
                          "808", "818", "888", "906", "916", "986"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.strobogrammatic_list(0)
        self.assertEqual(str(ctx.exception),
                         refusal("strobogrammatic_list:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.strobogrammatic_list(12)
        self.assertEqual(str(ctx.exception),
                         refusal("strobogrammatic_list:too_many:n"))
        with self.assertRaises(ValueError) as ctx:
            m.strobogrammatic_list(10 ** 9)
        self.assertEqual(str(ctx.exception),
                         refusal("strobogrammatic_list:too_many:n"))

    def test_cap(self):
        self.assertEqual(len(m.strobogrammatic_list(10)), 2500)
        self.assertEqual(len(m.strobogrammatic_list(11)), 7500)

    def test_oracle(self):
        rot = {"0": "0", "1": "1", "6": "9", "8": "8", "9": "6"}

        def oracle(n):
            out = []
            for combo in itertools.product("01689", repeat=n):
                if n > 1 and combo[0] == "0":
                    continue
                s = "".join(combo)
                if s == "".join(rot[c] for c in reversed(s)):
                    out.append(s)
            return sorted(out)
        for n in (1, 2, 3, 4):
            self.assertEqual(m.strobogrammatic_list(n), oracle(n))


class TestBinaryStringsNoConsecutive(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.binary_strings_no_consecutive(1),
                         ["0", "1"])
        self.assertEqual(m.binary_strings_no_consecutive(2),
                         ["00", "01", "10"])
        self.assertEqual(m.binary_strings_no_consecutive(3),
                         ["000", "001", "010", "100", "101"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.binary_strings_no_consecutive(0)
        self.assertEqual(str(ctx.exception), refusal(
            "binary_strings_no_consecutive:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.binary_strings_no_consecutive(19)
        self.assertEqual(str(ctx.exception), refusal(
            "binary_strings_no_consecutive:too_many:n"))
        with self.assertRaises(ValueError) as ctx:
            m.binary_strings_no_consecutive(10 ** 9)
        self.assertEqual(str(ctx.exception), refusal(
            "binary_strings_no_consecutive:too_many:n"))

    def test_cap(self):
        self.assertEqual(len(m.binary_strings_no_consecutive(18)),
                         6765)

    def test_oracle(self):
        def oracle(n):
            return sorted("".join(bits)
                          for bits in itertools.product("01", repeat=n)
                          if "11" not in "".join(bits))
        for n in range(1, 9):
            self.assertEqual(m.binary_strings_no_consecutive(n),
                             oracle(n))


class TestRegistryKnowsBatch88(unittest.TestCase):
    def test_registry_knows_batch88(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("subsets_list", "factorization_lists",
                     "permutations_list", "combination_sum_lists",
                     "partition_palindrome_lists", "restore_ip_addresses",
                     "strobogrammatic_list", "brace_expand_list",
                     "binary_strings_no_consecutive",
                     "tower_of_hanoi_moves"):
            self.assertIn(name, names)
        self.assertEqual(reg.IMPLEMENTED_SO_FAR, 758)


if __name__ == "__main__":
    unittest.main()
