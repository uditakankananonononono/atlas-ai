"""Tests for P235 concepts batch 85 (bit manipulation II)."""

import itertools
import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch85 as m
from app.modules.instinct_doc import p235_concepts_registry as reg

MAX_ITEMS = reg.MAX_ITEMS
INT32_MAX = 2 ** 31 - 1
INT32_MIN = -(2 ** 31)
UINT32_MAX = 2 ** 32 - 1

def refusal(code):
    return "P235:" + code

class TestXorMaxPair(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.xor_max_pair([3, 10, 5, 25, 2]), 28)
        self.assertEqual(m.xor_max_pair([0, 0]), 0)
        self.assertEqual(m.xor_max_pair([8, 7]), 15)
        self.assertEqual(m.xor_max_pair([INT32_MAX, 0]), INT32_MAX)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.xor_max_pair([5])
        self.assertEqual(str(ctx.exception),
                         refusal("xor_max_pair:too_few:items"))
        with self.assertRaises(ValueError) as ctx:
            m.xor_max_pair([])
        self.assertEqual(str(ctx.exception),
                         refusal("xor_max_pair:empty:items"))
        with self.assertRaises(ValueError) as ctx:
            m.xor_max_pair([1, -2])
        self.assertEqual(str(ctx.exception),
                         refusal("xor_max_pair:out_of_range:items[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.xor_max_pair([1, 2 ** 31])
        self.assertEqual(str(ctx.exception),
                         refusal("xor_max_pair:out_of_range:items[1]"))

    def test_cap(self):
        self.assertEqual(m.xor_max_pair(
            [0, INT32_MAX] + [i % 1024 for i in range(MAX_ITEMS - 2)]),
            INT32_MAX)
        with self.assertRaises(ValueError) as ctx:
            m.xor_max_pair([0] * (MAX_ITEMS + 1))
        self.assertEqual(str(ctx.exception),
                         refusal("xor_max_pair:too_many:items"))

    def test_oracle(self):
        def oracle(items):
            return max(a ^ b for a, b in itertools.combinations(items, 2))
        rng = random.Random(8503)
        for _ in range(60):
            items = [rng.randint(0, 500) for _ in range(rng.randint(2, 25))]
            self.assertEqual(m.xor_max_pair(items), oracle(items))

class TestBitwiseAndOfRange(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.bitwise_and_of_range(5, 7), 4)
        self.assertEqual(m.bitwise_and_of_range(0, 1), 0)
        self.assertEqual(m.bitwise_and_of_range(12, 15), 12)
        self.assertEqual(m.bitwise_and_of_range(9, 9), 9)
        self.assertEqual(m.bitwise_and_of_range(0, INT32_MAX), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.bitwise_and_of_range(7, 5)
        self.assertEqual(str(ctx.exception), refusal(
            "bitwise_and_of_range:bad_value:range"))
        with self.assertRaises(ValueError) as ctx:
            m.bitwise_and_of_range(-1, 5)
        self.assertEqual(str(ctx.exception), refusal(
            "bitwise_and_of_range:out_of_range:m"))

    def test_oracle(self):
        def oracle(lo, hi):
            total = lo
            for v in range(lo + 1, hi + 1):
                total &= v
            return total
        rng = random.Random(8504)
        for _ in range(60):
            lo = rng.randint(0, 500)
            hi = lo + rng.randint(0, 300)
            self.assertEqual(m.bitwise_and_of_range(lo, hi), oracle(lo, hi))

class TestBinaryGapMax(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.binary_gap_max(529), 4)
        self.assertEqual(m.binary_gap_max(9), 2)
        self.assertEqual(m.binary_gap_max(15), 0)
        self.assertEqual(m.binary_gap_max(32), 0)
        self.assertEqual(m.binary_gap_max(20), 1)
        self.assertEqual(m.binary_gap_max(1), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.binary_gap_max(0)
        self.assertEqual(str(ctx.exception),
                         refusal("binary_gap_max:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.binary_gap_max(2 ** 31)
        self.assertEqual(str(ctx.exception),
                         refusal("binary_gap_max:out_of_range:n"))

    def test_oracle(self):
        def oracle(n):
            parts = bin(n)[2:].split("1")
            gaps = [len(p) for p in parts[1:-1]]
            return max(gaps) if gaps else 0
        rng = random.Random(8505)
        for _ in range(200):
            n = rng.randint(1, INT32_MAX)
            self.assertEqual(m.binary_gap_max(n), oracle(n))

class TestComplementFixedBits(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.complement_fixed_bits(5), 2)
        self.assertEqual(m.complement_fixed_bits(1), 0)
        self.assertEqual(m.complement_fixed_bits(0), 1)
        self.assertEqual(m.complement_fixed_bits(10), 5)
        self.assertEqual(m.complement_fixed_bits(INT32_MAX), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.complement_fixed_bits(-1)
        self.assertEqual(str(ctx.exception), refusal(
            "complement_fixed_bits:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.complement_fixed_bits(2 ** 31)
        self.assertEqual(str(ctx.exception), refusal(
            "complement_fixed_bits:out_of_range:n"))

    def test_oracle(self):
        def oracle(n):
            bits = bin(n)[2:]
            flipped = "".join("0" if c == "1" else "1" for c in bits)
            return int(flipped, 2)
        rng = random.Random(8506)
        for _ in range(200):
            n = rng.randint(0, INT32_MAX)
            self.assertEqual(m.complement_fixed_bits(n), oracle(n))

class TestRotateBitsRight(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.rotate_bits_right(0b1, 1), 0x80000000)
        self.assertEqual(m.rotate_bits_right(0x80000000, 1), 0x40000000)
        self.assertEqual(m.rotate_bits_right(0x12345678, 8), 0x78123456)
        self.assertEqual(m.rotate_bits_right(0x12345678, 0), 0x12345678)

    def test_k_normalization(self):
        self.assertEqual(m.rotate_bits_right(0x12345678, 32), 0x12345678)
        self.assertEqual(m.rotate_bits_right(0x12345678, 33),
                         m.rotate_bits_right(0x12345678, 1))
        self.assertEqual(m.rotate_bits_right(0x12345678, INT32_MAX),
                         m.rotate_bits_right(0x12345678, INT32_MAX % 32))

    def test_boundaries(self):
        self.assertEqual(m.rotate_bits_right(UINT32_MAX, 7), UINT32_MAX)
        self.assertEqual(m.rotate_bits_right(UINT32_MAX, 0), UINT32_MAX)
        self.assertEqual(m.rotate_bits_right(0, 13), 0)
        with self.assertRaises(ValueError) as ctx:
            m.rotate_bits_right(2 ** 32, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "rotate_bits_right:out_of_range:value"))
        with self.assertRaises(ValueError) as ctx:
            m.rotate_bits_right(1, -1)
        self.assertEqual(str(ctx.exception), refusal(
            "rotate_bits_right:out_of_range:k"))
        with self.assertRaises(ValueError) as ctx:
            m.rotate_bits_right(1, 2 ** 31)
        self.assertEqual(str(ctx.exception), refusal(
            "rotate_bits_right:out_of_range:k"))

    def test_oracle(self):
        def oracle(value, k):
            bits = format(value, "032b")
            shift = k % 32
            rotated = bits[-shift:] + bits[:-shift] if shift else bits
            return int(rotated, 2)
        rng = random.Random(8507)
        for _ in range(200):
            value = rng.randint(0, 2 ** 32 - 1)
            k = rng.randint(0, 2 ** 31 - 1)
            self.assertEqual(m.rotate_bits_right(value, k),
                             oracle(value, k))

class TestXorSumSubsets(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.xor_sum_subsets([1, 3]), 6)
        self.assertEqual(m.xor_sum_subsets([2]), 2)
        self.assertEqual(m.xor_sum_subsets([5, 1, 6]), 28)
        self.assertEqual(m.xor_sum_subsets([0, 0, 0]), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.xor_sum_subsets([])
        self.assertEqual(str(ctx.exception),
                         refusal("xor_sum_subsets:empty:items"))
        with self.assertRaises(ValueError) as ctx:
            m.xor_sum_subsets([1, -1])
        self.assertEqual(str(ctx.exception),
                         refusal("xor_sum_subsets:out_of_range:items[1]"))

    def test_oracle(self):
        def oracle(items):
            total = 0
            for size in range(len(items) + 1):
                for combo in itertools.combinations(items, size):
                    acc = 0
                    for v in combo:
                        acc ^= v
                    total += acc
            return total
        rng = random.Random(8508)
        for _ in range(60):
            items = [rng.randint(0, 40) for _ in range(rng.randint(1, 12))]
            self.assertEqual(m.xor_sum_subsets(items), oracle(items))

class TestSwapOddEvenBits(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.swap_odd_even_bits(10), 5)
        self.assertEqual(m.swap_odd_even_bits(23), 43)
        self.assertEqual(m.swap_odd_even_bits(0), 0)
        self.assertEqual(m.swap_odd_even_bits(0xFFFFFFFF), 0xFFFFFFFF)
        self.assertEqual(m.swap_odd_even_bits(0xAAAAAAA8), 0x55555554)
        self.assertEqual(m.swap_odd_even_bits(0xAAAAAAAA), 0x55555555)
        self.assertEqual(m.swap_odd_even_bits(0x55555555), 0xAAAAAAAA)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.swap_odd_even_bits(2 ** 32)
        self.assertEqual(str(ctx.exception), refusal(
            "swap_odd_even_bits:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.swap_odd_even_bits(-1)
        self.assertEqual(str(ctx.exception), refusal(
            "swap_odd_even_bits:out_of_range:n"))

    def test_oracle(self):
        def oracle(n):
            bits = format(n, "032b")
            swapped = "".join(bits[i + 1] + bits[i]
                              for i in range(0, 32, 2))
            return int(swapped, 2)
        rng = random.Random(8509)
        for _ in range(200):
            n = rng.randint(0, 2 ** 32 - 1)
            self.assertEqual(m.swap_odd_even_bits(n), oracle(n))

class TestDivideTwoIntsBits(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.divide_two_ints_bits(43, 5), 8)
        self.assertEqual(m.divide_two_ints_bits(-7, 2), -3)
        self.assertEqual(m.divide_two_ints_bits(7, -2), -3)
        self.assertEqual(m.divide_two_ints_bits(0, 3), 0)
        self.assertEqual(m.divide_two_ints_bits(1, 3), 0)
        self.assertEqual(m.divide_two_ints_bits(INT32_MIN, -1), INT32_MAX)
        self.assertEqual(m.divide_two_ints_bits(INT32_MIN, 1), INT32_MIN)
        self.assertEqual(m.divide_two_ints_bits(INT32_MAX, INT32_MIN), 0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.divide_two_ints_bits(1, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "divide_two_ints_bits:bad_value:divisor"))
        with self.assertRaises(ValueError) as ctx:
            m.divide_two_ints_bits(2 ** 31, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "divide_two_ints_bits:out_of_range:dividend"))
        with self.assertRaises(ValueError) as ctx:
            m.divide_two_ints_bits(1, 2.0)
        self.assertEqual(str(ctx.exception), refusal(
            "divide_two_ints_bits:bad_type:divisor"))

    def test_oracle(self):
        def oracle(a, b):
            q = abs(a) // abs(b)
            if (a < 0) != (b < 0):
                q = -q
            return max(INT32_MIN, min(INT32_MAX, q))
        rng = random.Random(8510)
        for _ in range(200):
            a = rng.randint(INT32_MIN, INT32_MAX)
            b = 0
            while b == 0:
                b = rng.randint(INT32_MIN, INT32_MAX)
            self.assertEqual(m.divide_two_ints_bits(a, b), oracle(a, b))

class TestRegistryKnowsBatch85(unittest.TestCase):
    def test_registry_knows_batch85(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("xor_max_pair", "bitwise_and_of_range",
                     "binary_gap_max", "complement_fixed_bits",
                     "rotate_bits_right", "xor_sum_subsets",
                     "swap_odd_even_bits", "divide_two_ints_bits"):
            self.assertIn(name, names)

if __name__ == "__main__":
    unittest.main()
