"""P235 concepts, batch 18 (bitwise/encodings, 171-180). Offline, stdlib only."""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_BITS = 10_000
MAX_HEX_DIGITS = MAX_BITS // 4
MAX_BYTES = MAX_BITS // 8


def _bounded_uint(fail, n, name="n"):
    check_int(fail, n, name)
    if n < 0:
        fail("bad_value:%s" % name)
    if n.bit_length() > MAX_BITS:
        fail("too_many:%s" % name)
    return n


def bit_count(n):
    fail = make_fail("bit_count")
    _bounded_uint(fail, n)
    return bin(n).count("1")


def count_trailing_zeros(n):
    fail = make_fail("count_trailing_zeros")
    _bounded_uint(fail, n)
    if n == 0:
        fail("bad_value:n")
    count = 0
    while n % 2 == 0:
        n //= 2
        count += 1
    return count


def highest_set_bit(n):
    fail = make_fail("highest_set_bit")
    _bounded_uint(fail, n)
    if n == 0:
        fail("bad_value:n")
    return n.bit_length() - 1


def is_bit_set(n, k):
    fail = make_fail("is_bit_set")
    _bounded_uint(fail, n)
    check_int(fail, k, "k")
    if k < 0:
        fail("bad_value:k")
    if k > MAX_BITS:
        fail("too_many:k")
    return (n >> k) & 1 == 1


def reverse_bits_fixed(n, k):
    fail = make_fail("reverse_bits_fixed")
    _bounded_uint(fail, n)
    check_int(fail, k, "k")
    if k < 1:
        fail("bad_value:k")
    if k > MAX_BITS:
        fail("too_many:k")
    if n.bit_length() > k:
        fail("too_many:n")
    out = 0
    for i in range(k):
        if (n >> i) & 1:
            out |= 1 << (k - 1 - i)
    return out


def single_number_xor(items):
    fail = make_fail("single_number_xor")
    check_items(fail, items, "items")
    if not items:
        fail("empty:items")
    x = 0
    for i, v in enumerate(items):
        check_int(fail, v, "items[%d]" % i)
        x ^= v
    return x


def int_to_hex_string(n):
    fail = make_fail("int_to_hex_string")
    _bounded_uint(fail, n)
    return format(n, "x")


def hex_string_to_int(text):
    fail = make_fail("hex_string_to_int")
    check_str(fail, text, "hex")
    if not text:
        fail("bad_value:hex")
    if len(text) > MAX_HEX_DIGITS:
        fail("too_many:hex")
    for ch in text:
        if ch not in "0123456789abcdefABCDEF":
            fail("bad_value:hex")
    return int(text, 16)


def int_to_bytes_be(n, width):
    fail = make_fail("int_to_bytes_be")
    _bounded_uint(fail, n)
    check_int(fail, width, "width")
    if width < 1:
        fail("bad_value:width")
    if width > MAX_BYTES:
        fail("too_many:width")
    if n.bit_length() > width * 8:
        fail("too_many:n")
    return [(n >> (8 * i)) & 0xFF for i in range(width - 1, -1, -1)]


def bytes_to_int_be(items):
    fail = make_fail("bytes_to_int_be")
    check_items(fail, items, "bytes")
    if len(items) > MAX_BYTES:
        fail("too_many:bytes")
    out = 0
    for i, v in enumerate(items):
        check_int(fail, v, "bytes[%d]" % i)
        if v < 0 or v > 255:
            fail("bad_value:bytes")
        out = (out << 8) | v
    return out
