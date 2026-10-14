"""P235 concepts batch 64: list algorithms IV.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_N = 100_000
MAX_PILE = 1_000_000_000
MAX_DAY = 365
MAX_COST = 100_000
MAX_NUM = 100_000_000
MAX_WORD = 100
MAX_WORDS = 1_000


def _int_list(fail, values, name="items", allow_empty=False):
    check_items(fail, values, name)
    if not values and not allow_empty:
        fail("empty:%s" % name)
    if len(values) > MAX_ITEMS:
        fail("too_many:%s" % name)
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))


def count_pairs_abs_diff_k(items, k):
    """Count of pairs (i, j), i < j, with |items[i] - items[j]| == k."""
    fail = make_fail("count_pairs_abs_diff_k")
    _int_list(fail, items)
    check_int(fail, k, "k")
    if k < 0 or k > MAX_N:
        fail("out_of_range:k")
    total = 0
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(items[i] - items[j]) == k:
                total += 1
    return total


def koko_eating_bananas(piles, h):
    """Smallest eating speed finishing every pile within h hours.

    Each hour eats up to speed bananas from one pile; a pile needs
    ceil(p / speed) hours. Speed is a positive integer.
    """
    fail = make_fail("koko_eating_bananas")
    _int_list(fail, piles, "piles")
    check_int(fail, h, "h")
    for i, v in enumerate(piles):
        if v < 1 or v > MAX_PILE:
            fail("out_of_range:piles[%d]" % i)
    if h < len(piles) or h > MAX_PILE:
        fail("out_of_range:h")

    def hours(speed):
        return sum((p + speed - 1) // speed for p in piles)

    lo, hi = 1, max(piles)
    while lo < hi:
        mid = (lo + hi) // 2
        if hours(mid) <= h:
            hi = mid
        else:
            lo = mid + 1
    return lo


def count_largest_groups(n):
    """Group 1..n by digit sum; count of groups with the largest size."""
    fail = make_fail("count_largest_groups")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_N:
        fail("out_of_range:n")
    sizes = {}
    for v in range(1, n + 1):
        s = 0
        x = v
        while x:
            s += x % 10
            x //= 10
        sizes[s] = sizes.get(s, 0) + 1
    best = max(sizes.values())
    return sum(1 for v in sizes.values() if v == best)


def max_69_number(num):
    """Largest value from flipping at most one digit 6 to 9."""
    fail = make_fail("max_69_number")
    check_int(fail, num, "num")
    if num < 1 or num > MAX_NUM:
        fail("out_of_range:num")
    digits = list(str(num))
    for i, ch in enumerate(digits):
        if ch == "6":
            digits[i] = "9"
            break
    return int("".join(digits))


def defuse_bomb_circular(code, k):
    """Replace each cell by the sum of the next k cells, circular.

    Negative k sums the previous -k cells instead; k == 0 zeroes
    every cell.
    """
    fail = make_fail("defuse_bomb_circular")
    _int_list(fail, code, "code")
    check_int(fail, k, "k")
    n = len(code)
    if abs(k) > n:
        fail("out_of_range:k")
    out = []
    for i in range(n):
        if k > 0:
            total = sum(code[(i + 1 + t) % n] for t in range(k))
        elif k < 0:
            total = sum(code[(i - 1 - t) % n] for t in range(-k))
        else:
            total = 0
        out.append(total)
    return out


def count_good_meals(deliciousness):
    """Count of pairs summing to a power of two."""
    fail = make_fail("count_good_meals")
    _int_list(fail, deliciousness, "deliciousness")
    for i, v in enumerate(deliciousness):
        if v < 0 or v > MAX_N:
            fail("out_of_range:deliciousness[%d]" % i)
    total = 0
    n = len(deliciousness)
    for i in range(n):
        for j in range(i + 1, n):
            s = deliciousness[i] + deliciousness[j]
            if s and (s & (s - 1)) == 0:
                total += 1
    return total


def find_words_with_chars(words, chars):
    """Total length of words formable from the chars multiset.

    Only lowercase ASCII a-z is accepted, for chars and words.
    """
    fail = make_fail("find_words_with_chars")
    check_items(fail, words, "words")
    check_str(fail, chars, "chars")
    if not words:
        fail("empty:words")
    if len(words) > MAX_WORDS:
        fail("too_many:words")
    if len(chars) > MAX_WORD:
        fail("too_long:chars")
    if any(not ("a" <= c <= "z") for c in chars):
        fail("bad_char:chars")
    from collections import Counter
    have = Counter(chars)
    total = 0
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if len(w) > MAX_WORD:
            fail("too_long:words[%d]" % i)
        if any(not ("a" <= c <= "z") for c in w):
            fail("bad_char:words[%d]" % i)
        need = Counter(w)
        if all(have[c] >= need[c] for c in need):
            total += len(w)
    return total


def min_operations_make_increasing(items):
    """Increments needed to make the list strictly increasing.

    Each operation adds 1 to a cell; cells never decrease.
    """
    fail = make_fail("min_operations_make_increasing")
    _int_list(fail, items)
    total = 0
    prev = items[0]
    for v in items[1:]:
        if v <= prev:
            total += prev + 1 - v
            v = prev + 1
        prev = v
    return total


def min_cost_travel_days(days, costs):
    """Cheapest way to cover every travel day with 1, 7, 30 day passes.

    days is a strictly increasing list in 1..365; costs is the
    three positive pass prices in the 1, 7, 30 order.
    """
    fail = make_fail("min_cost_travel_days")
    _int_list(fail, days, "days")
    check_items(fail, costs, "costs")
    if len(costs) != 3:
        fail("bad_length:costs")
    for i, v in enumerate(costs):
        check_int(fail, v, "costs[%d]" % i)
        if v < 1 or v > MAX_COST:
            fail("out_of_range:costs[%d]" % i)
    for i, v in enumerate(days):
        if v < 1 or v > MAX_DAY:
            fail("out_of_range:days[%d]" % i)
        if i and v <= days[i - 1]:
            fail("not_sorted:days[%d]" % i)
    n = len(days)
    best = [0] * (n + 1)
    for i in range(1, n + 1):
        cur = best[i - 1] + costs[0]
        for dur, price in ((7, costs[1]), (30, costs[2])):
            j = i
            while j > 0 and days[j - 1] > days[i - 1] - dur:
                j -= 1
            cand = best[j] + price
            if cand < cur:
                cur = cand
        best[i] = cur
    return best[n]


def deck_partition_gcd(deck):
    """True when the deck splits into equal groups of size two-plus.

    Each group holds one value only; possible exactly when the gcd
    of the value counts is at least 2.
    """
    fail = make_fail("deck_partition_gcd")
    _int_list(fail, deck, "deck")
    counts = {}
    for v in deck:
        counts[v] = counts.get(v, 0) + 1
    from math import gcd
    g = 0
    for c in counts.values():
        g = gcd(g, c)
    return g >= 2
