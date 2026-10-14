"""P235 concepts batch 63: list algorithms III.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_N = 100_000
MAX_TEXT = 10_000


def _int_list(fail, values, name="items", allow_empty=False):
    check_items(fail, values, name)
    if not values and not allow_empty:
        fail("empty:%s" % name)
    if len(values) > MAX_ITEMS:
        fail("too_many:%s" % name)
    for i, v in enumerate(values):
        check_int(fail, v, "%s[%d]" % (name, i))


def last_stone_weight(stones):
    """Weight left after smashing the two heaviest until one stays.

    Each smash of unequal stones leaves their difference; equal
    stones destroy each other. Empty input gives 0.
    """
    fail = make_fail("last_stone_weight")
    _int_list(fail, stones, "stones", allow_empty=True)
    for i, v in enumerate(stones):
        if v < 1:
            fail("bad_value:stones[%d]" % i)
    import heapq
    heap = [-v for v in stones]
    heapq.heapify(heap)
    while len(heap) > 1:
        a = -heapq.heappop(heap)
        b = -heapq.heappop(heap)
        if a != b:
            heapq.heappush(heap, -(a - b))
    return -heap[0] if heap else 0


def find_kth_positive_missing(items, k):
    """The kth positive int missing from a strictly increasing list.

    The sorted contract is validated for the whole list before the
    count is taken.
    """
    fail = make_fail("find_kth_positive_missing")
    _int_list(fail, items)
    check_int(fail, k, "k")
    if k < 1 or k > MAX_N:
        fail("out_of_range:k")
    for i, v in enumerate(items):
        if v < 1 or v > MAX_N:
            fail("out_of_range:items[%d]" % i)
        if i and v <= items[i - 1]:
            fail("not_sorted:items[%d]" % i)
    for i, v in enumerate(items):
        if v - (i + 1) >= k:
            return i + k
    return len(items) + k


def number_of_good_pairs(items):
    """Count of pairs (i, j), i < j, with equal values."""
    fail = make_fail("number_of_good_pairs")
    _int_list(fail, items)
    counts = {}
    total = 0
    for v in items:
        have = counts.get(v, 0)
        total += have
        counts[v] = have + 1
    return total


def shuffle_string(text, indices):
    """Rebuild ASCII text by placing each char at its index.

    indices must be a permutation of 0..len(text)-1.
    """
    fail = make_fail("shuffle_string")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    if not text.isascii():
        fail("bad_value:text")
    check_items(fail, indices, "indices")
    if len(indices) != len(text):
        fail("length_mismatch:indices")
    seen = [False] * len(text)
    for i, v in enumerate(indices):
        check_int(fail, v, "indices[%d]" % i)
        if v < 0 or v >= len(text):
            fail("out_of_range:indices[%d]" % i)
        if seen[v]:
            fail("duplicate:indices[%d]" % i)
        seen[v] = True
    out = [""] * len(text)
    for ch, v in zip(text, indices):
        out[v] = ch
    return "".join(out)


def find_all_anagrams_in_string(text, word):
    """Start indices where an anagram of word begins in text.

    Both must be non-empty ASCII; an empty window list is a normal
    result, not a refusal.
    """
    fail = make_fail("find_all_anagrams_in_string")
    for name, val in (("text", text), ("word", word)):
        check_str(fail, val, name)
        if not val:
            fail("empty:%s" % name)
        if len(val) > MAX_TEXT:
            fail("too_many:%s" % name)
        if not val.isascii():
            fail("bad_value:%s" % name)
    need = {}
    for ch in word:
        need[ch] = need.get(ch, 0) + 1
    out = []
    have = {}
    for i, ch in enumerate(text):
        have[ch] = have.get(ch, 0) + 1
        if i >= len(word):
            old = text[i - len(word)]
            have[old] -= 1
            if have[old] == 0:
                del have[old]
        if have == need:
            out.append(i - len(word) + 1)
    return out


def arithmetic_slices_count(items):
    """Number of subarrays of length at least 3 forming an AP."""
    fail = make_fail("arithmetic_slices_count")
    _int_list(fail, items)
    total = 0
    run = 0
    for i in range(2, len(items)):
        if items[i] - items[i - 1] == items[i - 1] - items[i - 2]:
            run += 1
            total += run
        else:
            run = 0
    return total


def count_binary_substrings(text):
    """Substrings with equal consecutive 0s and 1s in two groups.

    Counted over every window of the 0/1 ASCII string.
    """
    fail = make_fail("count_binary_substrings")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    for i, ch in enumerate(text):
        if ch not in "01":
            fail("bad_value:text[%d]" % i)
    groups = []
    cur = 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1]:
            cur += 1
        else:
            groups.append(cur)
            cur = 1
    groups.append(cur)
    return sum(min(a, b) for a, b in zip(groups, groups[1:]))


def min_add_to_make_valid_parens(text):
    """Insertions needed to balance a string of ( and )."""
    fail = make_fail("min_add_to_make_valid_parens")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    for i, ch in enumerate(text):
        if ch not in "()":
            fail("bad_value:text[%d]" % i)
    balance = 0
    adds = 0
    for ch in text:
        if ch == "(":
            balance += 1
        elif balance:
            balance -= 1
        else:
            adds += 1
    return adds + balance


def check_sorted_rotated(items):
    """Whether an int list is a rotation of a nondecreasing list.

    At most one descent may appear around the circle, including
    the wrap from last to first.
    """
    fail = make_fail("check_sorted_rotated")
    _int_list(fail, items)
    drops = 0
    for i in range(len(items)):
        if items[i] > items[(i + 1) % len(items)]:
            drops += 1
    return drops <= 1


def degree_of_array_shortest(items):
    """Length of the shortest window with the list's full degree.

    The degree is the highest frequency of any value; the window
    must contain every occurrence of one such value.
    """
    fail = make_fail("degree_of_array_shortest")
    _int_list(fail, items)
    first = {}
    last = {}
    counts = {}
    for i, v in enumerate(items):
        if v not in first:
            first[v] = i
        last[v] = i
        counts[v] = counts.get(v, 0) + 1
    degree = max(counts.values())
    best = len(items)
    for v, c in counts.items():
        if c == degree:
            span = last[v] - first[v] + 1
            if span < best:
                best = span
    return best
