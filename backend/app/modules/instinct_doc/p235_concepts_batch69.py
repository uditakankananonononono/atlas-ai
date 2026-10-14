"""P235 concepts batch 69: array algorithms V.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

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


def max_chunks_to_sorted(items):
    """Most chunks whose individually sorted join sorts the list.

    The list must be a permutation of 0..len-1; the chunk count is
    then the number of positions where the running maximum equals
    the index.
    """
    fail = make_fail("max_chunks_to_sorted")
    _int_list(fail, items)
    n = len(items)
    for i, v in enumerate(items):
        if v < 0 or v >= n:
            fail("out_of_range:items[%d]" % i)
    if len(set(items)) != n:
        fail("bad_value:items")
    running = 0
    chunks = 0
    for i, v in enumerate(items):
        if v > running:
            running = v
        if running == i:
            chunks += 1
    return chunks


def partition_disjoint_max(items):
    """Shortest left part with every value <= every value right.

    After this prefix length, the left maximum stays at or below
    the right minimum, so each part can be sorted independently.
    """
    fail = make_fail("partition_disjoint_max")
    _int_list(fail, items)
    if len(items) < 2:
        fail("too_few:items")
    n = len(items)
    right_min = [0] * n
    right_min[-1] = items[-1]
    for i in range(n - 2, -1, -1):
        right_min[i] = min(items[i], right_min[i + 1])
    left_max = items[0]
    for i in range(n - 1):
        if items[i] > left_max:
            left_max = items[i]
        if left_max <= right_min[i + 1]:
            return i + 1
    return n


def majority_candidates_n3(items):
    """All values held by more than a third of the list, ascending.

    At most two such values can exist.
    """
    fail = make_fail("majority_candidates_n3")
    _int_list(fail, items)
    counts = {}
    for v in items:
        counts[v] = counts.get(v, 0) + 1
    return sorted(v for v, c in counts.items()
                  if c * 3 > len(items))


def subarray_sum_k_count(items, k):
    """Count of contiguous subarrays whose values sum to k."""
    fail = make_fail("subarray_sum_k_count")
    _int_list(fail, items)
    check_int(fail, k, "k")
    seen = {0: 1}
    total = 0
    count = 0
    for v in items:
        total += v
        count += seen.get(total - k, 0)
        seen[total] = seen.get(total, 0) + 1
    return count


def min_size_subarray_sum(items, target):
    """Shortest window length with sum at least target; 0 if none.

    Every value must be a positive int.
    """
    fail = make_fail("min_size_subarray_sum")
    _int_list(fail, items)
    check_int(fail, target, "target")
    if target < 1 or target > MAX_N:
        fail("out_of_range:target")
    for i, v in enumerate(items):
        if v < 1 or v > MAX_N:
            fail("out_of_range:items[%d]" % i)
    best = 0
    left = 0
    total = 0
    for right, v in enumerate(items):
        total += v
        while total >= target:
            length = right - left + 1
            if best == 0 or length < best:
                best = length
            total -= items[left]
            left += 1
    return best


def shortest_unsorted_subarray(items):
    """Length of the shortest window whose sorting sorts the list.

    Returns 0 when the list is already non-decreasing.
    """
    fail = make_fail("shortest_unsorted_subarray")
    _int_list(fail, items)
    n = len(items)
    lo = n
    hi = -1
    peak = None
    for i, v in enumerate(items):
        if peak is not None and v < peak:
            hi = i
        else:
            peak = v
    trough = None
    for i in range(n - 1, -1, -1):
        v = items[i]
        if trough is not None and v > trough:
            lo = i
        else:
            trough = v
    return 0 if hi < lo else hi - lo + 1


def max_consecutive_ones_flips(items, k):
    """Longest run of ones after flipping at most k zeros.

    The list must be binary; k must be at least 0.
    """
    fail = make_fail("max_consecutive_ones_flips")
    _int_list(fail, items)
    check_int(fail, k, "k")
    if k < 0 or k > MAX_ITEMS:
        fail("out_of_range:k")
    for i, v in enumerate(items):
        if v not in (0, 1):
            fail("bad_value:items[%d]" % i)
    left = 0
    zeros = 0
    best = 0
    for right, v in enumerate(items):
        if v == 0:
            zeros += 1
        while zeros > k:
            if items[left] == 0:
                zeros -= 1
            left += 1
        if right - left + 1 > best:
            best = right - left + 1
    return best


def sum_subarray_minimums(items):
    """Sum of the minimum value over every contiguous subarray."""
    fail = make_fail("sum_subarray_minimums")
    _int_list(fail, items)
    n = len(items)
    left_span = [0] * n
    stack = []
    for i, v in enumerate(items):
        while stack and items[stack[-1]] > v:
            stack.pop()
        left_span[i] = i - stack[-1] if stack else i + 1
        stack.append(i)
    right_span = [0] * n
    stack = []
    total = 0
    for i in range(n - 1, -1, -1):
        v = items[i]
        while stack and items[stack[-1]] >= v:
            stack.pop()
        right_span[i] = stack[-1] - i if stack else n - i
        stack.append(i)
        total += v * left_span[i] * right_span[i]
    return total


def online_median_list(items):
    """Running median after each insertion, lower of the two middles.

    The median uses exact integer order; with an even count the
    lower middle value is reported.
    """
    fail = make_fail("online_median_list")
    _int_list(fail, items)
    import heapq
    low = []   # max-heap via negation
    high = []  # min-heap
    out = []
    for v in items:
        if low and v > -low[0]:
            heapq.heappush(high, v)
        else:
            heapq.heappush(low, -v)
        if len(low) > len(high) + 1:
            heapq.heappush(high, -heapq.heappop(low))
        elif len(high) > len(low):
            heapq.heappush(low, -heapq.heappop(high))
        out.append(-low[0])
    return out


def remove_k_digits(text, k):
    """Smallest number after removing exactly k digits, order kept.

    The text must be ASCII digits; leading zeros of the result are
    stripped, and an all-removed result is "0".
    """
    fail = make_fail("remove_k_digits")
    from app.modules.instinct_doc.p235_concepts_registry import (
        check_str)
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    if not text.isascii() or any(c < "0" or c > "9" for c in text):
        fail("bad_char:text")
    check_int(fail, k, "k")
    if k < 0 or k > len(text):
        fail("out_of_range:k")
    stack = []
    drops = k
    for ch in text:
        while drops and stack and stack[-1] > ch:
            stack.pop()
            drops -= 1
        stack.append(ch)
    if drops:
        stack = stack[:len(stack) - drops]
    out = "".join(stack).lstrip("0")
    return out if out else "0"
