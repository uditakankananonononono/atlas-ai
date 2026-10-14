"""P235 concepts batch 83: binary search on the answer.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps. Each
binary-searches a monotone feasibility predicate over a bounded
integer range; max_average_subarray_k halves a dyadic range 50
times with an exact scaled-integer feasibility check, recovers
the exact best window, and rounds half-even to six declared
decimals.
Every predicate scan is O(len(items)), so the heaviest call
(min_time_repair_cars at cap: 10_000 ranks times about 41
halvings of a 10^12 range) stays under a million integer
operations.
"""

from fractions import Fraction
from math import isqrt

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, make_fail)

MAX_VAL = 10_000


def _values(fail, xs, name):
    """Validate a nonempty list of ints in 1..MAX_VAL."""
    check_items(fail, xs, name)
    if not xs:
        fail("empty:%s" % name)
    for i, v in enumerate(xs):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < 1 or v > MAX_VAL:
            fail("out_of_range:%s[%d]" % (name, i))
    return xs


def _param(fail, v, name, lo, hi):
    check_int(fail, v, name)
    if v < lo or v > hi:
        fail("out_of_range:%s" % name)
    return v


def max_average_subarray_k(nums, k):
    """Largest average over any contiguous window of length >= k.

    nums holds positive ints and k is between 1 and len(nums).
    The range [1, MAX_VAL] is halved a fixed 50 times around a
    monotone feasibility check - does any window of length at
    least k average at least the candidate - evaluated exactly in
    scaled integers. The surviving interval is 9999/2^50 wide,
    below the smallest possible gap 1/len(nums)^2 between two
    distinct attainable window averages, so one final exact
    witness pass at the lower bound recovers a best window and
    its exact average is rounded half-even to six decimals."""
    fail = make_fail("max_average_subarray_k")
    _values(fail, nums, "nums")
    _param(fail, k, "k", 1, len(nums))
    prefix = [0]
    for v in nums:
        prefix.append(prefix[-1] + v)

    def witness(limit):
        # exact feasibility in scaled integers; returns the first
        # window [start, end] whose average reaches limit, or None
        num, den = limit.numerator, limit.denominator
        run = 0
        delayed = 0
        floor = 0
        floor_t = -1
        for j, v in enumerate(nums):
            run += den * v - num
            if j >= k - 1:
                if run - floor >= 0:
                    return floor_t + 1, j
                delayed += den * nums[j - k + 1] - num
                if delayed < floor:
                    floor = delayed
                    floor_t = j - k + 1
        return None

    lo, hi = Fraction(1), Fraction(MAX_VAL)
    for _ in range(50):
        mid = (lo + hi) / 2
        if witness(mid) is not None:
            lo = mid
        else:
            hi = mid
    start, end = witness(lo)
    best = Fraction(prefix[end + 1] - prefix[start], end - start + 1)
    scaled = best * 1_000_000
    base, rem = divmod(scaled.numerator, scaled.denominator)
    if 2 * rem > scaled.denominator or (
            2 * rem == scaled.denominator and base % 2 == 1):
        base += 1
    return base / 1_000_000


def ship_capacity_min_days(weights, days):
    """Least ship capacity moving every weight, in order, in days.

    Each day the ship takes a contiguous run of packages whose sum
    stays within capacity. days must be positive; a capacity below
    the heaviest package can never work."""
    fail = make_fail("ship_capacity_min_days")
    _values(fail, weights, "weights")
    _param(fail, days, "days", 1, MAX_ITEMS)

    def needed(cap):
        used, run = 1, 0
        for w in weights:
            if run + w > cap:
                used += 1
                run = w
            else:
                run += w
        return used

    lo, hi = max(weights), sum(weights)
    while lo < hi:
        mid = (lo + hi) // 2
        if needed(mid) <= days:
            hi = mid
        else:
            lo = mid + 1
    return lo


def magnetic_force_max_min(positions, balls):
    """Largest achievable minimum gap between balls on a line.

    positions holds distinct positive coordinates (any order);
    balls balls are placed on distinct positions, maximizing the
    smallest distance between any two placed balls. balls must be
    between 2 and len(positions)."""
    fail = make_fail("magnetic_force_max_min")
    _values(fail, positions, "positions")
    if len(set(positions)) != len(positions):
        fail("bad_value:positions")
    _param(fail, balls, "balls", 2, len(positions))
    spots = sorted(positions)

    def fits(gap):
        placed, last = 1, spots[0]
        for p in spots[1:]:
            if p - last >= gap:
                placed += 1
                last = p
        return placed

    lo, hi = 1, spots[-1] - spots[0]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(mid) >= balls:
            lo = mid
        else:
            hi = mid - 1
    return lo


def min_limit_balls_in_bag(nums, max_ops):
    """Smallest achievable largest bag after at most max_ops splits.

    One operation splits one bag into two nonempty bags; a bag of
    size n needs ceil(n / k) - 1 splits to stay within k. The
    answer is the least k reachable within max_ops operations."""
    fail = make_fail("min_limit_balls_in_bag")
    _values(fail, nums, "nums")
    _param(fail, max_ops, "max_ops", 0, MAX_ITEMS * MAX_VAL)

    def ops_needed(k):
        return sum((v - 1) // k for v in nums)

    lo, hi = 1, max(nums)
    while lo < hi:
        mid = (lo + hi) // 2
        if ops_needed(mid) <= max_ops:
            hi = mid
        else:
            lo = mid + 1
    return lo


def min_days_make_bouquets(bloom_days, bouquets, flowers):
    """Least day on which the requested bouquets can be picked.

    bloom_days[i] is the day position i blooms; a bouquet needs
    flowers adjacent bloomed positions. Returns -1 when the garden
    cannot supply bouquets * flowers blooms at all."""
    fail = make_fail("min_days_make_bouquets")
    _values(fail, bloom_days, "bloom_days")
    _param(fail, bouquets, "bouquets", 1, MAX_ITEMS)
    _param(fail, flowers, "flowers", 1, MAX_ITEMS)
    if bouquets * flowers > len(bloom_days):
        return -1

    def ready(day):
        made = run = 0
        for d in bloom_days:
            run = run + 1 if d <= day else 0
            if run == flowers:
                made += 1
                run = 0
        return made

    lo, hi = min(bloom_days), max(bloom_days)
    while lo < hi:
        mid = (lo + hi) // 2
        if ready(mid) >= bouquets:
            hi = mid
        else:
            lo = mid + 1
    return lo


def min_time_repair_cars(ranks, cars):
    """Least minutes for all mechanics together to repair cars cars.

    A mechanic of rank r repairs one car in r * c * c minutes for
    the c-th car they take, so in t minutes they finish
    floor(sqrt(t / r)) cars."""
    fail = make_fail("min_time_repair_cars")
    _values(fail, ranks, "ranks")
    _param(fail, cars, "cars", 1, MAX_ITEMS)

    def fixable(t):
        return sum(isqrt(t // r) for r in ranks)

    lo, hi = 1, max(ranks) * cars * cars
    while lo < hi:
        mid = (lo + hi) // 2
        if fixable(mid) >= cars:
            hi = mid
        else:
            lo = mid + 1
    return lo


def max_running_time_computers(n_computers, batteries):
    """Longest time all n_computers computers run at once.

    Batteries cannot be recharged or shared at the same instant;
    battery b can back one computer for up to b minutes. Returns 0
    when the total charge cannot run every computer for a minute."""
    fail = make_fail("max_running_time_computers")
    _param(fail, n_computers, "n_computers", 1, MAX_ITEMS)
    _values(fail, batteries, "batteries")

    def feasible(t):
        return sum(min(b, t) for b in batteries) >= n_computers * t

    lo, hi = 0, sum(batteries) // n_computers
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if feasible(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


def min_capability_rob_houses(values, picks):
    """Least capability robbing at least picks non-adjacent houses.

    Capability k means every house taken must be worth at most k;
    the thief never takes two adjacent houses. picks must be at
    most the largest non-adjacent selection, (n + 1) // 2."""
    fail = make_fail("min_capability_rob_houses")
    _values(fail, values, "values")
    _param(fail, picks, "picks", 1, (len(values) + 1) // 2)

    def robbable(k):
        taken = i = 0
        while i < len(values):
            if values[i] <= k:
                taken += 1
                i += 2
            else:
                i += 1
        return taken

    lo, hi = min(values), max(values)
    while lo < hi:
        mid = (lo + hi) // 2
        if robbable(mid) >= picks:
            hi = mid
        else:
            lo = mid + 1
    return lo


def max_candies_per_child(piles, children):
    """Largest equal candy share for every child.

    Piles may be split but never combined; a share of k means each
    child gets k candies from one pile. Returns 0 when the total
    cannot give every child even one candy."""
    fail = make_fail("max_candies_per_child")
    _values(fail, piles, "piles")
    _param(fail, children, "children", 1, MAX_ITEMS * MAX_VAL)

    def served(k):
        return sum(p // k for p in piles)

    lo, hi = 1, max(piles)
    if served(1) < children:
        return 0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if served(mid) >= children:
            lo = mid
        else:
            hi = mid - 1
    return lo


def nth_magical_number(n, a, b):
    """The n-th positive integer divisible by a or b.

    Counts below x are x // a + x // b - x // lcm(a, b), which is
    monotone in x, so the n-th term binary-searches the range."""
    fail = make_fail("nth_magical_number")
    _param(fail, n, "n", 1, MAX_ITEMS)
    _param(fail, a, "a", 1, MAX_VAL)
    _param(fail, b, "b", 1, MAX_VAL)
    from math import gcd
    lcm = a // gcd(a, b) * b

    def count(x):
        return x // a + x // b - x // lcm

    lo, hi = 1, n * min(a, b)
    while lo < hi:
        mid = (lo + hi) // 2
        if count(mid) >= n:
            hi = mid
        else:
            lo = mid + 1
    return lo
