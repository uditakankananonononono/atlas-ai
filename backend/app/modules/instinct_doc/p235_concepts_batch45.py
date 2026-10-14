"""P235 concepts, batch 45 (ordering checks, greedy II, 441-450).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TEXT = 10_000

MAX_WEIGHT = 10_000
MAX_TIME = 10**9


def _int_list(fail, values, name, cap=MAX_ITEMS):
    check_items(fail, values, name)
    if not values:
        fail("empty:%s" % name)
    if len(values) > cap:
        fail("too_many:%s" % name)
    out = []
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))
        out.append(v)
    return out


def monotonic_array_check(values):
    """True when the list is entirely nondecreasing or nonincreasing."""
    fail = make_fail("monotonic_array_check")
    vals = _int_list(fail, values, "values")
    up = down = True
    for i in range(1, len(vals)):
        if vals[i] > vals[i - 1]:
            down = False
        elif vals[i] < vals[i - 1]:
            up = False
    return up or down


def rank_transform_values(values):
    """Replace each value by its 1-based rank among distinct values."""
    fail = make_fail("rank_transform_values")
    vals = _int_list(fail, values, "values")
    ranks = {v: i + 1 for i, v in enumerate(sorted(set(vals)))}
    return [ranks[v] for v in vals]


def relative_sort_order(values, order):
    """values sorted by order membership first, rest ascending."""
    fail = make_fail("relative_sort_order")
    vals = _int_list(fail, values, "values")
    ord_vals = _int_list(fail, order, "order")
    seen = set()
    for i, v in enumerate(ord_vals):
        if v in seen:
            fail("duplicate:order[%d]" % i)
        seen.add(v)
    pos = {v: i for i, v in enumerate(ord_vals)}
    inside = [v for v in vals if v in pos]
    outside = sorted(v for v in vals if v not in pos)
    inside.sort(key=lambda v: pos[v])
    return inside + outside


def alien_dictionary_verify(words, alphabet):
    """True when words are lexicographically sorted per the alphabet."""
    fail = make_fail("alien_dictionary_verify")
    check_str(fail, alphabet, "alphabet")
    if alphabet == "":
        fail("empty:alphabet")
    if not alphabet.isascii() or not alphabet.isalpha():
        fail("bad_value:alphabet")
    if len(set(alphabet)) != len(alphabet):
        fail("duplicate:alphabet")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_ITEMS:
        fail("too_many:words")
    rank = {ch: i for i, ch in enumerate(alphabet)}
    keyed = []
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if w == "":
            fail("empty:words[%d]" % i)
        if len(w) > MAX_TEXT:
            fail("too_many:words[%d]" % i)
        for ch in w:
            if ch not in rank:
                fail("bad_value:words[%d]:char" % i)
        keyed.append([rank[ch] for ch in w])
    return all(keyed[i] <= keyed[i + 1]
               for i in range(len(keyed) - 1))


def arithmetic_progression_check(values):
    """True when the values can be rearranged into an AP."""
    fail = make_fail("arithmetic_progression_check")
    vals = _int_list(fail, values, "values")
    if len(vals) < 2:
        fail("too_few:values")
    vals.sort()
    d = vals[1] - vals[0]
    return all(vals[i] - vals[i - 1] == d
               for i in range(2, len(vals)))


def teemo_attack_duration(attacks, duration):
    """Total poisoned seconds from attacks each lasting duration."""
    fail = make_fail("teemo_attack_duration")
    vals = _int_list(fail, attacks, "attacks")
    check_int(fail, duration, "duration")
    if duration < 1 or duration > MAX_TIME:
        fail("bad_value:duration")
    prev = None
    for i, v in enumerate(vals):
        if v < 0 or v > MAX_TIME:
            fail("bad_value:attacks[%d]" % i)
        if prev is not None and v < prev:
            fail("bad_value:attacks:not_sorted")
        prev = v
    total = 0
    for i in range(1, len(vals)):
        total += min(duration, vals[i] - vals[i - 1])
    return total + duration


def num_rescue_boats(weights, limit):
    """Minimum boats carrying at most two people each."""
    fail = make_fail("num_rescue_boats")
    vals = _int_list(fail, weights, "weights")
    check_int(fail, limit, "limit")
    if limit < 1 or limit > MAX_WEIGHT:
        fail("bad_value:limit")
    for i, v in enumerate(vals):
        if v < 1 or v > limit:
            fail("bad_value:weights[%d]" % i)
    vals.sort()
    lo, hi = 0, len(vals) - 1
    boats = 0
    while lo <= hi:
        if vals[lo] + vals[hi] <= limit:
            lo += 1
        hi -= 1
        boats += 1
    return boats


def advantage_shuffle_pairs(nums_a, nums_b):
    """Permutation of a beating b at the most positions (Tian Ji)."""
    fail = make_fail("advantage_shuffle_pairs")
    a = _int_list(fail, nums_a, "nums_a")
    b = _int_list(fail, nums_b, "nums_b")
    if len(a) != len(b):
        fail("bad_value:length_mismatch")
    order = sorted(range(len(b)), key=lambda i: -b[i])
    a_sorted = sorted(a, reverse=True)
    out = [None] * len(a)
    weak = []
    ai = 0
    for i in order:
        if ai < len(a_sorted) and a_sorted[ai] > b[i]:
            out[i] = a_sorted[ai]
            ai += 1
        else:
            weak.append(i)
    rest = a_sorted[ai:]
    for pos, v in zip(weak, rest):
        out[pos] = v
    return out


def array_pair_sum_max(values):
    """Maximum sum of mins over pairs of the list."""
    fail = make_fail("array_pair_sum_max")
    vals = _int_list(fail, values, "values")
    if len(vals) % 2 != 0:
        fail("bad_value:odd_length")
    vals.sort()
    return sum(vals[::2])


def partition_labels_lengths(text):
    """Part sizes so each letter appears in exactly one part."""
    fail = make_fail("partition_labels_lengths")
    check_str(fail, text, "text")
    if text == "":
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    if not text.isascii() or not text.isalpha():
        fail("bad_value:text")
    last = {}
    for i, ch in enumerate(text):
        last[ch] = i
    out = []
    start = 0
    end = 0
    for i, ch in enumerate(text):
        if last[ch] > end:
            end = last[ch]
        if i == end:
            out.append(end - start + 1)
            start = i + 1
    return out
