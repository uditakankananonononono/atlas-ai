"""P235 concepts batch 85: bit manipulation II.

Eight small, deterministic, pure functions with input
validation, declared resource caps, and coded refusals; two
earlier entries were replaced by batch 92 after auditor
screens. No external deps.
Integer arguments stay inside signed 32-bit range (0..2^32-1 for
swap_odd_even_bits and rotate_bits_right.value; k stays
0..INT32_MAX) and lists inside MAX_ITEMS, so the heaviest
call (xor_max_pair at cap: 10000 values times 31 trie levels)
stays near three hundred thousand node visits.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1
UINT32_MAX = 2 ** 32 - 1

def _int32_list(fail, xs, name, lo=INT32_MIN, hi=INT32_MAX):
    """Validate a nonempty list of ints inside lo..hi."""
    check_items(fail, xs, name)
    if not xs:
        fail("empty:%s" % name)
    for i, v in enumerate(xs):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < lo or v > hi:
            fail("out_of_range:%s[%d]" % (name, i))
    return xs

def _param(fail, v, name, lo, hi):
    check_int(fail, v, name)
    if v < lo or v > hi:
        fail("out_of_range:%s" % name)
    return v

def xor_max_pair(items):
    """Largest bitwise xor over any pair of list values.

    Values are non-negative 31-bit integers; a binary trie walks
    each value against the rest level by level."""
    fail = make_fail("xor_max_pair")
    _int32_list(fail, items, "items", lo=0, hi=INT32_MAX)
    if len(items) < 2:
        fail("too_few:items")
    trie = {}
    for v in items:
        node = trie
        for level in range(30, -1, -1):
            bit = (v >> level) & 1
            node = node.setdefault(bit, {})
    best = 0
    for v in items:
        node = trie
        current = 0
        for level in range(30, -1, -1):
            bit = (v >> level) & 1
            want = 1 - bit
            if want in node:
                current |= 1 << level
                node = node[want]
            else:
                node = node[bit]
        if current > best:
            best = current
    return best

def bitwise_and_of_range(m, n):
    """Bitwise AND of every integer from m through n inclusive.

    Only the common high prefix survives; 0 <= m <= n."""
    fail = make_fail("bitwise_and_of_range")
    _param(fail, m, "m", 0, INT32_MAX)
    _param(fail, n, "n", 0, INT32_MAX)
    if m > n:
        fail("bad_value:range")
    shift = 0
    while m != n:
        m >>= 1
        n >>= 1
        shift += 1
    return m << shift

def binary_gap_max(n):
    """Longest run of zeros bounded by ones in the binary form of n,
    or 0 when no such run exists."""
    fail = make_fail("binary_gap_max")
    _param(fail, n, "n", 1, INT32_MAX)
    best = run = 0
    seen_one = False
    while n:
        if n & 1:
            if seen_one and run > best:
                best = run
            seen_one = True
            run = 0
        elif seen_one:
            run += 1
        n >>= 1
    return best

def complement_fixed_bits(n):
    """Flip every bit of n across its own minimal bit length.

    Zero has length one, so it complements to 1."""
    fail = make_fail("complement_fixed_bits")
    _param(fail, n, "n", 0, INT32_MAX)
    length = max(1, n.bit_length())
    return ((1 << length) - 1) ^ n

def rotate_bits_right(value, k):
    """Circular right rotation of a 32-bit word by k positions.

    k is normalized modulo 32, so k = 32 is the identity and
    k = 33 rotates by one."""
    fail = make_fail("rotate_bits_right")
    _param(fail, value, "value", 0, UINT32_MAX)
    _param(fail, k, "k", 0, INT32_MAX)
    shift = k % 32
    if shift == 0:
        return value
    return ((value >> shift) | (value << (32 - shift))) & UINT32_MAX

def xor_sum_subsets(items):
    """Sum of the xor total of every subset of items.

    The empty subset contributes 0. Values are non-negative
    31-bit integers."""
    fail = make_fail("xor_sum_subsets")
    _int32_list(fail, items, "items", lo=0, hi=INT32_MAX)
    spread = 0
    for v in items:
        spread |= v
    return spread << (len(items) - 1)

def swap_odd_even_bits(n):
    """Swap adjacent bit pairs of n read as a 32-bit word."""
    fail = make_fail("swap_odd_even_bits")
    _param(fail, n, "n", 0, UINT32_MAX)
    return (((n & 0xAAAAAAAA) >> 1) | ((n & 0x55555555) << 1))

def divide_two_ints_bits(dividend, divisor):
    """Integer quotient truncated toward zero, computed by shifted
    subtraction. The divisor cannot be zero; the single overflowing
    case (-2^31 / -1) clamps to 2^31 - 1."""
    fail = make_fail("divide_two_ints_bits")
    _param(fail, dividend, "dividend", INT32_MIN, INT32_MAX)
    _param(fail, divisor, "divisor", INT32_MIN, INT32_MAX)
    if divisor == 0:
        fail("bad_value:divisor")
    negative = (dividend < 0) != (divisor < 0)
    top = abs(dividend)
    bottom = abs(divisor)
    quotient = 0
    for level in range(31, -1, -1):
        if (top >> level) >= bottom:
            quotient |= 1 << level
            top -= bottom << level
    if negative:
        quotient = -quotient
    if quotient > INT32_MAX:
        return INT32_MAX
    if quotient < INT32_MIN:
        return INT32_MIN
    return quotient
