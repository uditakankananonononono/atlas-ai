"""P235 concepts batch 92: replacement concepts from auditor screens.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries and grids at MAX_ITEMS
cells. Backtracking, cubic interval DP, quadratic scans, and the
tower simulation
carry tighter declared caps (MAX_BEAUTIFUL_N,
MAX_TOWER_ROWS, MAX_BALLOON_N, MAX_SCRAMBLE_LEN,
MAX_JUSTIFY_INPUT, MAX_JUSTIFY_OUTPUT) stated in their
docstrings. Exact arithmetic uses ints and
Fractions only.
"""

from fractions import Fraction
from heapq import heapify, heappop, heappush

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_VAL = 1_000_000
MAX_PP_WORDS = 300
MAX_PP_LEN = 50
MAX_LOG_ENTRY_LEN = 64
MAX_LOG_ID_DIGITS = 5
MAX_LOG_TS_DIGITS = 10
MAX_BEAUTIFUL_N = 15
MAX_TOWER_ROWS = 2_000
MAX_BALLOON_N = 150
MAX_SCRAMBLE_LEN = 30
MAX_JUSTIFY_INPUT = 10_000
MAX_JUSTIFY_OUTPUT = 100_000

def _int_list(fail, xs, name, lo, hi):
    check_items(fail, xs, name)
    if not xs:
        fail("empty:%s" % name)
    for i, v in enumerate(xs):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < lo or v > hi:
            fail("out_of_range:%s[%d]" % (name, i))
    return xs

def skyline_outline(buildings):
    """Key points of the skyline formed by axis-aligned buildings.

    Each building is [left, right, height] with left < right and
    positive height; the outline reports [x, height] at every x
    where the maximum visible height changes, ending at height 0
    after the rightmost edge, with consecutive equal heights
    collapsed. Events are swept with a heap of live (height,
    right) pairs expired lazily, an estimated O(n log n) work."""
    fail = make_fail("skyline_outline")
    check_items(fail, buildings, "buildings")
    if not buildings:
        fail("empty:buildings")
    events = {}
    for i, row in enumerate(buildings):
        if type(row) is not list or len(row) != 3:
            fail("bad_shape:buildings[%d]" % i)
        for j, v in enumerate(row):
            check_int(fail, v, "buildings[%d][%d]" % (i, j))
        left, right, height = row
        if left < 0 or left > MAX_VAL:
            fail("out_of_range:buildings[%d][0]" % i)
        if right <= left or right > MAX_VAL:
            fail("out_of_range:buildings[%d][1]" % i)
        if height < 1 or height > MAX_VAL:
            fail("out_of_range:buildings[%d][2]" % i)
        events.setdefault(left, []).append((height, right))
        events.setdefault(right, [])
    live = []
    out = []
    prev = 0
    for x in sorted(events):
        for height, right in events[x]:
            heappush(live, (-height, right))
        while live and live[0][1] <= x:
            heappop(live)
        top = -live[0][0] if live else 0
        if top != prev:
            out.append([x, top])
            prev = top
    return out

def champagne_tower_fill(poured, row, glass):
    """Exact fill level of one glass in a champagne tower.

    poured units enter glass (0, 0); every glass keeps at most
    one unit and splits any overflow equally between the two
    glasses below. The result is the Fraction held by the glass
    at (row, glass). Rows are simulated one at a time; the
    declared cap MAX_TOWER_ROWS keeps the triangular work at an
    estimated few million Fraction operations; the worst case at the caps measured about 3 seconds."""
    fail = make_fail("champagne_tower_fill")
    check_int(fail, poured, "poured")
    if poured < 0 or poured > MAX_VAL:
        fail("out_of_range:poured")
    check_int(fail, row, "row")
    if row < 0 or row > MAX_TOWER_ROWS:
        fail("out_of_range:row")
    check_int(fail, glass, "glass")
    if glass < 0 or glass > row:
        fail("out_of_range:glass")
    current = [Fraction(poured)]
    for _ in range(row):
        nxt = [Fraction(0)] * (len(current) + 1)
        for i, v in enumerate(current):
            if v > 1:
                over = (v - 1) / 2
                nxt[i] += over
                nxt[i + 1] += over
        current = nxt
    return min(current[glass], Fraction(1))

def car_fleet_arrivals(target, positions, speeds):
    """Number of car fleets that arrive at the target mile.

    Cars start at distinct positions below target with positive
    speeds; a faster car that catches a slower one merges into
    its fleet and then travels at the slower speed. Cars are
    processed in descending position order and a new fleet forms
    exactly when a car's own arrival time exceeds every fleet
    time ahead of it."""
    fail = make_fail("car_fleet_arrivals")
    check_int(fail, target, "target")
    if target < 1 or target > MAX_VAL:
        fail("out_of_range:target")
    positions = _int_list(fail, positions, "positions", 0, MAX_VAL)
    speeds = _int_list(fail, speeds, "speeds", 1, MAX_VAL)
    if len(speeds) != len(positions):
        fail("bad_shape:speeds")
    seen = set()
    for i, p in enumerate(positions):
        if p >= target:
            fail("out_of_range:positions[%d]" % i)
        if p in seen:
            fail("duplicate:positions[%d]" % i)
        seen.add(p)
    order = sorted(range(len(positions)),
                   key=lambda i: -positions[i])
    fleets = 0
    slowest = Fraction(-1)
    for i in order:
        arrive = Fraction(target - positions[i], speeds[i])
        if arrive > slowest:
            fleets += 1
            slowest = arrive
    return fleets

def exclusive_time_functions(logs, n):
    """Exclusive runtime of every function from a call log.

    logs holds "id:start:timestamp" and "id:end:timestamp" entries
    for a single-threaded run of n functions numbered 0 to n - 1.
    An end at timestamp t means the function ran through t
    inclusive. A function's exclusive time is its total span minus
    the spans of the calls nested inside it, computed with an
    explicit stack in an estimated O(len(logs)) work. Entries must
    be well formed, ordered by non-decreasing timestamp, and
    balanced with stack discipline: an end must match the call on
    top of the stack, and a start inside a tick a just-ended call
    still occupies refuses as an overlap. n is
    capped at MAX_ITEMS functions and logs at MAX_ITEMS entries,
    both checked before any entry is parsed. Every entry is
    capped at MAX_LOG_ENTRY_LEN characters before it is split,
    and the id and timestamp digit runs at MAX_LOG_ID_DIGITS and
    MAX_LOG_TS_DIGITS digits before they are scanned or
    converted."""
    fail = make_fail("exclusive_time_functions")
    check_items(fail, logs, "logs")
    if not logs:
        fail("empty:logs")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_ITEMS:
        fail("out_of_range:n")
    parsed = []
    for i, entry in enumerate(logs):
        check_str(fail, entry, "logs[%d]" % i)
        if len(entry) > MAX_LOG_ENTRY_LEN:
            fail("too_long:logs[%d]" % i)
        parts = entry.split(":")
        if len(parts) != 3:
            fail("bad_form:logs[%d]" % i)
        fid_s, op, ts_s = parts
        if op not in ("start", "end"):
            fail("bad_op:logs[%d]" % i)
        if not fid_s or not fid_s.isascii() or not fid_s.isdigit():
            fail("bad_id:logs[%d]" % i)
        if len(fid_s) > MAX_LOG_ID_DIGITS:
            fail("too_long:logs[%d]" % i)
        if not ts_s or not ts_s.isascii() or not ts_s.isdigit():
            fail("bad_time:logs[%d]" % i)
        if len(ts_s) > MAX_LOG_TS_DIGITS:
            fail("too_long:logs[%d]" % i)
        fid = int(fid_s)
        ts = int(ts_s)
        if fid >= n:
            fail("out_of_range:logs[%d]" % i)
        if ts > MAX_VAL:
            fail("out_of_range:logs[%d]" % i)
        parsed.append((fid, op, ts))
    totals = [0] * n
    stack = []
    prev = 0
    last_ts = -1
    for i, (fid, op, ts) in enumerate(parsed):
        if ts < last_ts:
            fail("out_of_order:logs[%d]" % i)
        last_ts = ts
        if op == "start":
            if ts < prev:
                fail("overlap:logs[%d]" % i)
            if stack:
                totals[stack[-1]] += ts - prev
            stack.append(fid)
            prev = ts
        else:
            if not stack or stack[-1] != fid:
                fail("unbalanced:logs[%d]" % i)
            stack.pop()
            totals[fid] += ts - prev + 1
            prev = ts + 1
    if stack:
        fail("unbalanced:logs")
    return totals


def palindrome_pairs_list(words):
    """Index pairs whose concatenation reads the same reversed.

    Returns the sorted list of [i, j] pairs, i != j, where
    words[i] + words[j] is a palindrome. For every word it tries
    every split point: a palindromic prefix pairs the reversed
    suffix on the left, and a palindromic suffix pairs the
    reversed prefix on the right, using a word-to-index map, an
    estimated O(total characters times max word length) work.
    words must hold distinct non-empty strings, capped at
    MAX_PP_WORDS entries and MAX_PP_LEN characters each, checked
    before any palindrome test runs."""
    fail = make_fail("palindrome_pairs_list")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_PP_WORDS:
        fail("too_many:words")
    seen = set()
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if not w:
            fail("empty:words[%d]" % i)
        if len(w) > MAX_PP_LEN:
            fail("too_long:words[%d]" % i)
        if w in seen:
            fail("duplicate:words[%d]" % i)
        seen.add(w)
    index = {w: i for i, w in enumerate(words)}
    pairs = set()
    for i, w in enumerate(words):
        for cut in range(len(w) + 1):
            head, tail = w[:cut], w[cut:]
            if head == head[::-1]:
                j = index.get(tail[::-1])
                if j is not None and j != i:
                    pairs.add((j, i))
            if tail == tail[::-1]:
                j = index.get(head[::-1])
                if j is not None and j != i and cut < len(w):
                    pairs.add((i, j))
    return [list(p) for p in sorted(pairs)]


def beautiful_arrangement_count(n):
    """Count of permutations of 1..n that are beautiful.

    A permutation is beautiful when for every 1-based position i
    the value perm[i] divides i or i divides perm[i]. The search
    places values backtracking with the divisibility test at
    every level; n is capped at MAX_BEAUTIFUL_N, which keeps the
    pruned search small."""
    fail = make_fail("beautiful_arrangement_count")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_BEAUTIFUL_N:
        fail("out_of_range:n")
    divisors = [[] for _ in range(n + 1)]
    for v in range(1, n + 1):
        for i in range(1, n + 1):
            if v % i == 0 or i % v == 0:
                divisors[i].append(v)
    used = [False] * (n + 1)

    def place(i):
        if i > n:
            return 1
        total = 0
        for v in divisors[i]:
            if not used[v]:
                used[v] = True
                total += place(i + 1)
                used[v] = False
        return total

    return place(1)


def queue_reconstruction_height(people):
    """Queue order reconstructed from height and taller-ahead counts.

    Each person is [height, ahead] where ahead counts people of
    equal or greater height standing in front. The greedy places
    people from tallest to shortest, inserting each at index
    ahead; an ahead value beyond the current queue length cannot
    be honored and refuses. The reconstructed order is then
    validated against every ahead count with a Fenwick index
    (an estimated O(n log n)) and an inconsistent input
    refuses."""
    fail = make_fail("queue_reconstruction_height")
    check_items(fail, people, "people")
    if not people:
        fail("empty:people")
    parsed = []
    for i, row in enumerate(people):
        if type(row) is not list or len(row) != 2:
            fail("bad_shape:people[%d]" % i)
        check_int(fail, row[0], "people[%d][0]" % i)
        check_int(fail, row[1], "people[%d][1]" % i)
        if row[0] < 1 or row[0] > MAX_VAL:
            fail("out_of_range:people[%d][0]" % i)
        if row[1] < 0 or row[1] > len(people):
            fail("out_of_range:people[%d][1]" % i)
        parsed.append((row[0], row[1]))
    order = sorted(parsed, key=lambda p: (-p[0], p[1]))
    out = []
    for height, ahead in order:
        if ahead > len(out):
            fail("bad_form:people")
        out.insert(ahead, [height, ahead])
    heights = sorted({h for h, _ in out})
    comp = {h: i + 1 for i, h in enumerate(heights)}
    bit = [0] * (len(heights) + 1)
    for idx, (height, ahead) in enumerate(out):
        less = 0
        i = comp[height] - 1
        while i > 0:
            less += bit[i]
            i -= i & -i
        if idx - less != ahead:
            fail("inconsistent:people")
        i = comp[height]
        while i < len(bit):
            bit[i] += 1
            i += i & -i
    return out


def k_core_numbers(adj):
    """Core number of every node by repeated min-degree peeling.

    adj is the adjacency list of an undirected simple graph: no self
    loops, no duplicate neighbors, and j is in adj[i] exactly when i
    is in adj[j]. A k-core is a maximal induced subgraph of minimum
    degree k; a node's core number is the highest k whose k-core
    contains it. Peeling a minimum-degree node and assigning the
    running maximum of its degree at removal time yields every core
    number, an estimated O((n + e) log n) work with a lazy heap.
    The graph is capped at MAX_ITEMS nodes."""
    fail = make_fail("k_core_numbers")
    check_items(fail, adj, "adj")
    if not adj:
        fail("empty:adj")
    n = len(adj)
    for i, outs in enumerate(adj):
        check_items(fail, outs, "adj[%d]" % i)
        seen = set()
        for j, v in enumerate(outs):
            check_int(fail, v, "adj[%d][%d]" % (i, j))
            if v < 0 or v >= n:
                fail("out_of_range:adj[%d][%d]" % (i, j))
            if v == i:
                fail("self_loop:adj[%d]" % i)
            if v in seen:
                fail("duplicate:adj[%d]" % i)
            seen.add(v)
    for i, outs in enumerate(adj):
        for v in outs:
            if i not in adj[v]:
                fail("asymmetric:adj[%d]" % i)
    deg = [len(outs) for outs in adj]
    heap = [(deg[i], i) for i in range(n)]
    heapify(heap)
    alive = [True] * n
    core = [0] * n
    best = 0
    while heap:
        d, u = heappop(heap)
        if not alive[u] or d != deg[u]:
            continue
        alive[u] = False
        if d > best:
            best = d
        core[u] = best
        for v in adj[u]:
            if alive[v]:
                deg[v] -= 1
                heappush(heap, (deg[v], v))
    return core


def burst_balloons_max(values):
    """Maximum coins from bursting every balloon in order of choice.

    Bursting balloon i pays values[left] * values[i] *
    values[right] where left and right are the nearest unburst
    neighbors; implicit 1s sit beyond both ends. The interval DP
    solves each span by choosing its last burst, an estimated
    O(n^3) work, so values is capped at MAX_BALLOON_N entries; an
    empty list yields 0."""
    fail = make_fail("burst_balloons_max")
    check_items(fail, values, "values")
    if len(values) > MAX_BALLOON_N:
        fail("too_many:values")
    nums = [1]
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        if v < 1 or v > MAX_VAL:
            fail("out_of_range:values[%d]" % i)
        nums.append(v)
    nums.append(1)
    n = len(nums)
    dp = [[0] * n for _ in range(n)]
    for span in range(2, n):
        for left in range(n - span):
            right = left + span
            best = 0
            for mid in range(left + 1, right):
                gain = (nums[left] * nums[mid] * nums[right]
                        + dp[left][mid] + dp[mid][right])
                if gain > best:
                    best = gain
            dp[left][right] = best
    return dp[0][n - 1]


def scramble_string_check(s1, s2):
    """Whether s1 can be scrambled into s2.

    Scrambling recursively swaps the two children of any node in
    a binary split tree over the string, so s2 is reachable when
    some split point makes the two halves scramble-match in
    order or swapped. Strings longer than MAX_SCRAMBLE_LEN
    refuse, keeping the memoized recursion bounded; unequal
    lengths are not a scramble and return False after both
    strings are fully validated."""
    fail = make_fail("scramble_string_check")
    for name, value in (("s1", s1), ("s2", s2)):
        check_str(fail, value, name)
        if len(value) > MAX_SCRAMBLE_LEN:
            fail("too_many:%s" % name)
    if len(s1) != len(s2):
        return False
    memo = {}

    def walk(a, b):
        key = (a, b)
        if key in memo:
            return memo[key]
        if a == b:
            memo[key] = True
            return True
        if sorted(a) != sorted(b):
            memo[key] = False
            return False
        n = len(a)
        for cut in range(1, n):
            if (walk(a[:cut], b[:cut]) and walk(a[cut:], b[cut:])):
                memo[key] = True
                return True
            if (walk(a[:cut], b[n - cut:]) and walk(a[cut:], b[:n - cut])):
                memo[key] = True
                return True
        memo[key] = False
        return False

    return walk(s1, s2)
