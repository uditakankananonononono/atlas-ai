"""P235 concepts batch 79: array and string algorithms VI.

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


def stock_max_profit_twice(prices):
    """Best profit with at most two non-overlapping transactions."""
    fail = make_fail("stock_max_profit_twice")
    _int_list(fail, prices, "prices")
    for i, v in enumerate(prices):
        if v < 0 or v > MAX_N:
            fail("out_of_range:prices[%d]" % i)
    buy1 = buy2 = -MAX_N * MAX_ITEMS - 1
    sell1 = sell2 = 0
    for p in prices:
        buy1 = max(buy1, -p)
        sell1 = max(sell1, buy1 + p)
        buy2 = max(buy2, sell1 - p)
        sell2 = max(sell2, buy2 + p)
    return sell2


def min_cost_climbing_stairs(cost):
    """Cheapest toll to pass the top, stepping one or two.

    The climb may start at step 0 or step 1; needs at least two
    steps.
    """
    fail = make_fail("min_cost_climbing_stairs")
    _int_list(fail, cost, "cost")
    if len(cost) < 2:
        fail("too_few:cost")
    for i, v in enumerate(cost):
        if v < 0 or v > MAX_N:
            fail("out_of_range:cost[%d]" % i)
    back2, back1 = cost[0], cost[1]
    for v in cost[2:]:
        back2, back1 = back1, v + min(back1, back2)
    return min(back1, back2)


def delete_and_earn(items):
    """Most points where taking v deletes every v-1 and v+1.

    Each value scores v times its count.
    """
    fail = make_fail("delete_and_earn")
    _int_list(fail, items)
    for i, v in enumerate(items):
        if v < 1 or v > MAX_N:
            fail("out_of_range:items[%d]" % i)
    points = {}
    for v in items:
        points[v] = points.get(v, 0) + v
    take = skip = 0
    prev = None
    for v in sorted(points):
        if prev == v - 1:
            take, skip = skip + points[v], max(take, skip)
        else:
            take, skip = max(take, skip) + points[v], max(take, skip)
        prev = v
    return max(take, skip)


def minimum_swaps_sort(items):
    """Fewest swaps of any two positions to sort the list ascending.

    Values must be distinct.
    """
    fail = make_fail("minimum_swaps_sort")
    _int_list(fail, items)
    if len(set(items)) != len(items):
        fail("bad_value:items")
    rank = {v: i for i, v in enumerate(sorted(items))}
    seen = [False] * len(items)
    swaps = 0
    for i in range(len(items)):
        if seen[i]:
            continue
        cycle = 0
        j = i
        while not seen[j]:
            seen[j] = True
            j = rank[items[j]]
            cycle += 1
        swaps += cycle - 1
    return swaps


def reorganize_string_arrange(text):
    """Rearrangement with no two equal neighbors, "" if impossible.

    Only lowercase ASCII a-z is accepted. The result is
    deterministic: a most-frequent-first greedy, ties broken by
    letter, never repeating the just-used letter. Empty text gives
    empty text.
    """
    fail = make_fail("reorganize_string_arrange")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    if any(not ("a" <= c <= "z") for c in text):
        fail("bad_char:text")
    import heapq
    counts = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    if counts and max(counts.values()) > (len(text) + 1) // 2:
        return ""
    heap = [(-c, ch) for ch, c in counts.items()]
    heapq.heapify(heap)
    out = []
    prev = None
    while heap:
        negc, ch = heapq.heappop(heap)
        out.append(ch)
        if prev is not None:
            heapq.heappush(heap, prev)
        prev = (negc + 1, ch) if negc + 1 < 0 else None
    return "".join(out)


def min_swaps_parens_balance(text):
    """Fewest swaps of any two positions to balance the brackets.

    Only ( and ) are accepted; the length must be even and the two
    kinds must be equally many.
    """
    fail = make_fail("min_swaps_parens_balance")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    if any(c not in "()" for c in text):
        fail("bad_char:text")
    if len(text) % 2 or text.count("(") != text.count(")"):
        fail("bad_value:text")
    unbalanced = 0
    swaps = 0
    for ch in text:
        if ch == "(":
            unbalanced += 1
        else:
            unbalanced -= 1
        if unbalanced == -1:
            swaps += 1
            unbalanced = 1
    return swaps


def min_taps_garden(n, ranges):
    """Fewest taps watering the whole garden interval [0, n].

    Tap i covers [i - ranges[i], i + ranges[i]]; ranges holds n + 1
    entries. Returns -1 when full coverage is impossible.
    """
    fail = make_fail("min_taps_garden")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_N:
        fail("out_of_range:n")
    _int_list(fail, ranges, "ranges")
    if len(ranges) != n + 1:
        fail("bad_length:ranges")
    for i, v in enumerate(ranges):
        if v < 0 or v > n:
            fail("out_of_range:ranges[%d]" % i)
    reach = [0] * (n + 1)
    for i, v in enumerate(ranges):
        lo = max(0, i - v)
        if i + v > reach[lo]:
            reach[lo] = i + v
    taps = 0
    end = 0
    far = 0
    for i in range(n + 1):
        if i > far:
            return -1
        if i > end:
            taps += 1
            end = far
        if reach[i] > far:
            far = reach[i]
    return taps


def min_refuel_stops(target, start_fuel, stations):
    """Fewest refuels to reach target, best stations first.

    stations holds [position, fuel] pairs, positions distinct,
    increasing, and below target. Returns -1 when the target is
    unreachable.
    """
    fail = make_fail("min_refuel_stops")
    check_int(fail, target, "target")
    check_int(fail, start_fuel, "start_fuel")
    if target < 1 or target > MAX_N * 100:
        fail("out_of_range:target")
    if start_fuel < 0 or start_fuel > MAX_N * 100:
        fail("out_of_range:start_fuel")
    check_items(fail, stations, "stations")
    if len(stations) > MAX_ITEMS:
        fail("too_many:stations")
    prev = 0
    for i, st in enumerate(stations):
        if type(st) is not list or len(st) != 2:
            fail("bad_shape:stations[%d]" % i)
        check_int(fail, st[0], "stations[%d][0]" % i)
        check_int(fail, st[1], "stations[%d][1]" % i)
        if st[0] <= prev or st[0] >= target:
            fail("bad_value:stations[%d]" % i)
        if st[1] < 1 or st[1] > MAX_N:
            fail("out_of_range:stations[%d]" % i)
        prev = st[0]
    import heapq
    tank = start_fuel
    stops = 0
    pool = []
    i = 0
    while tank < target:
        while i < len(stations) and stations[i][0] <= tank:
            heapq.heappush(pool, -stations[i][1])
            i += 1
        if not pool:
            return -1
        tank += -heapq.heappop(pool)
        stops += 1
    return stops


def max_erasure_value(items):
    """Largest sum of a contiguous window of distinct values.

    Every value must be a positive int.
    """
    fail = make_fail("max_erasure_value")
    _int_list(fail, items)
    for i, v in enumerate(items):
        if v < 1 or v > MAX_N:
            fail("out_of_range:items[%d]" % i)
    seen = set()
    left = 0
    total = 0
    best = 0
    for v in items:
        while v in seen:
            seen.remove(items[left])
            total -= items[left]
            left += 1
        seen.add(v)
        total += v
        if total > best:
            best = total
    return best


def longest_unique_substring_length(text):
    """Longest substring without a repeated character.

    Only ASCII is accepted.
    """
    fail = make_fail("longest_unique_substring_length")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    if not text.isascii():
        fail("bad_char:text")
    last = {}
    left = 0
    best = 0
    for i, ch in enumerate(text):
        if ch in last and last[ch] >= left:
            left = last[ch] + 1
        last[ch] = i
        if i - left + 1 > best:
            best = i - left + 1
    return best
