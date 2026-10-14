"""P235 concepts batch 18 (171-180, bitwise/encodings): red-first tests."""
from __future__ import annotations

import unittest


class Batch18Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch18 as m
        self.m = m

    def test_bit_count(self):
        self.assertEqual(self.m.bit_count(0), 0)
        self.assertEqual(self.m.bit_count(0b1011), 3)
        self.assertEqual(self.m.bit_count(2 ** 100), 1)
        with self.assertRaises(ValueError):
            self.m.bit_count(-1)
        with self.assertRaises(ValueError) as c:
            self.m.bit_count(1 << 10_000)
        self.assertEqual(str(c.exception), "P235:bit_count:too_many:n")

    def test_count_trailing_zeros(self):
        self.assertEqual(self.m.count_trailing_zeros(8), 3)
        self.assertEqual(self.m.count_trailing_zeros(12), 2)
        self.assertEqual(self.m.count_trailing_zeros(1), 0)
        with self.assertRaises(ValueError) as c:
            self.m.count_trailing_zeros(0)
        self.assertEqual(str(c.exception),
                         "P235:count_trailing_zeros:bad_value:n")

    def test_highest_set_bit(self):
        self.assertEqual(self.m.highest_set_bit(1), 0)
        self.assertEqual(self.m.highest_set_bit(8), 3)
        self.assertEqual(self.m.highest_set_bit(0b1011), 3)
        with self.assertRaises(ValueError) as c:
            self.m.highest_set_bit(0)
        self.assertEqual(str(c.exception),
                         "P235:highest_set_bit:bad_value:n")

    def test_is_bit_set(self):
        self.assertTrue(self.m.is_bit_set(5, 0))
        self.assertFalse(self.m.is_bit_set(5, 1))
        self.assertTrue(self.m.is_bit_set(5, 2))
        with self.assertRaises(ValueError):
            self.m.is_bit_set(5, -1)
        with self.assertRaises(ValueError) as c:
            self.m.is_bit_set(5, 10_001)
        self.assertEqual(str(c.exception), "P235:is_bit_set:too_many:k")

    def test_reverse_bits_fixed(self):
        self.assertEqual(self.m.reverse_bits_fixed(0b0001, 4), 8)
        self.assertEqual(self.m.reverse_bits_fixed(0b1011, 4), 13)
        self.assertEqual(self.m.reverse_bits_fixed(0, 8), 0)
        with self.assertRaises(ValueError) as c:
            self.m.reverse_bits_fixed(16, 4)
        self.assertEqual(str(c.exception),
                         "P235:reverse_bits_fixed:too_many:n")
        with self.assertRaises(ValueError):
            self.m.reverse_bits_fixed(1, 0)

    def test_single_number_xor(self):
        self.assertEqual(self.m.single_number_xor([4, 1, 2, 1, 2]), 4)
        self.assertEqual(self.m.single_number_xor([7]), 7)
        self.assertEqual(self.m.single_number_xor([0, 5, 0]), 5)
        with self.assertRaises(ValueError) as c:
            self.m.single_number_xor([])
        self.assertEqual(str(c.exception),
                         "P235:single_number_xor:empty:items")

    def test_int_to_hex_string(self):
        self.assertEqual(self.m.int_to_hex_string(255), "ff")
        self.assertEqual(self.m.int_to_hex_string(0), "0")
        self.assertEqual(self.m.int_to_hex_string(4096), "1000")
        with self.assertRaises(ValueError):
            self.m.int_to_hex_string(-16)
        with self.assertRaises(ValueError) as c:
            self.m.int_to_hex_string(1 << 10_000)
        self.assertEqual(str(c.exception),
                         "P235:int_to_hex_string:too_many:n")

    def test_hex_string_to_int(self):
        self.assertEqual(self.m.hex_string_to_int("ff"), 255)
        self.assertEqual(self.m.hex_string_to_int("FF"), 255)
        self.assertEqual(self.m.hex_string_to_int("0"), 0)
        with self.assertRaises(ValueError) as c:
            self.m.hex_string_to_int("")
        self.assertEqual(str(c.exception),
                         "P235:hex_string_to_int:bad_value:hex")
        with self.assertRaises(ValueError):
            self.m.hex_string_to_int("xyz")
        with self.assertRaises(ValueError) as c2:
            self.m.hex_string_to_int("f" * 2_501)
        self.assertEqual(str(c2.exception),
                         "P235:hex_string_to_int:too_many:hex")

    def test_int_to_bytes_be(self):
        self.assertEqual(self.m.int_to_bytes_be(256, 2), [1, 0])
        self.assertEqual(self.m.int_to_bytes_be(255, 1), [255])
        self.assertEqual(self.m.int_to_bytes_be(0, 3), [0, 0, 0])
        with self.assertRaises(ValueError) as c:
            self.m.int_to_bytes_be(256, 1)
        self.assertEqual(str(c.exception),
                         "P235:int_to_bytes_be:too_many:n")
        with self.assertRaises(ValueError):
            self.m.int_to_bytes_be(1, 0)
        with self.assertRaises(ValueError):
            self.m.int_to_bytes_be(-1, 2)

    def test_bytes_to_int_be(self):
        self.assertEqual(self.m.bytes_to_int_be([1, 0]), 256)
        self.assertEqual(self.m.bytes_to_int_be([]), 0)
        self.assertEqual(self.m.bytes_to_int_be([255]), 255)
        with self.assertRaises(ValueError) as c:
            self.m.bytes_to_int_be([256])
        self.assertEqual(str(c.exception),
                         "P235:bytes_to_int_be:bad_value:bytes")
        with self.assertRaises(ValueError):
            self.m.bytes_to_int_be([1, -1])

    def test_bytes_int_cap_alignment(self):
        # the pair is inverse over the same domain: 1,250 bytes (10,000
        # bits) is the cap on both sides
        raw = [255] * 1_250
        n = self.m.bytes_to_int_be(raw)
        self.assertEqual(self.m.int_to_bytes_be(n, 1_250), raw)
        with self.assertRaises(ValueError) as c:
            self.m.bytes_to_int_be([0] * 1_251)
        self.assertEqual(str(c.exception),
                         "P235:bytes_to_int_be:too_many:bytes")


if __name__ == "__main__":
    unittest.main()
