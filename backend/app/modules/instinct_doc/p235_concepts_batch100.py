"""P235 concepts batch 100: five concepts.

Five small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries; tighter caps
(MAX_RC4_KEY, MAX_MAZE_CELLS, MAX_CRYPT_TERMS,
MAX_CRYPT_LENGTH, MAX_BLOOM_SIZE, MAX_BLOOM_HASHES, MAX_STR)
are stated in the docstrings of the functions that carry them.
Every function validates its whole input first: length caps are
checked before the elements they bound are inspected, then
type, range, and shape checks run during the validation phase,
and the computation phase starts only after validation
succeeds. Exact arithmetic uses ints and Fractions only; the
maze generator draws randomness from a local SplitMix64
generator seeded by the caller, never from global state.
"""

from fractions import Fraction

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_RC4_KEY = 256
MAX_MAZE_CELLS = 4096
MAX_CRYPT_TERMS = 8
MAX_CRYPT_LENGTH = 12
MAX_BLOOM_SIZE = 4096
MAX_BLOOM_HASHES = 64
MAX_STR = 1024
MAX_VAL = 10**9
_MASK64 = (1 << 64) - 1


def rc4_keystream(key, n):
    """First n bytes of the RC4 keystream for the given key.

    key is a list of 1 to MAX_RC4_KEY ints, each 0 to 255. n is
    a non-negative int capped at MAX_ITEMS. Runs the standard
    key-scheduling algorithm (256 indexed swaps over the
    identity permutation) followed by n steps of the
    pseudo-random generation algorithm and returns the emitted
    bytes as a list of ints 0 to 255. Deterministic; exactly
    256 KSA swaps plus n PRGA steps."""
    fail = make_fail("rc4_keystream")
    check_items(fail, key, "key")
    if not key:
        fail("empty:key")
    if len(key) > MAX_RC4_KEY:
        fail("too_many:key")
    for i, v in enumerate(key):
        check_int(fail, v, "key[%d]" % i)
        if v < 0 or v > 255:
            fail("out_of_range:key[%d]" % i)
    check_int(fail, n, "n")
    if n < 0 or n > MAX_ITEMS:
        fail("out_of_range:n")
    s = list(range(256))
    j = 0
    klen = len(key)
    for i in range(256):
        j = (j + s[i] + key[i % klen]) & 255
        s[i], s[j] = s[j], s[i]
    out = []
    i = j = 0
    for _ in range(n):
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        out.append(s[(s[i] + s[j]) & 255])
    return out


def token_bucket_trace(capacity, refill_num, refill_den, events):
    """Accept/reject trace of a token-bucket rate limiter.

    The bucket holds up to capacity tokens (an int 1..MAX_VAL)
    and starts full at tick 0; it refills at exactly
    refill_num / refill_den tokens per tick (refill_num an int
    0..MAX_VAL, refill_den an int 1..MAX_VAL), capped at
    capacity. events holds [tick, cost] rows with
    non-decreasing ticks 0..MAX_VAL and costs 1..capacity,
    capped at MAX_ITEMS rows. Each event first refills for the
    elapsed ticks since the previous event, then is accepted
    (1) when the bucket holds at least cost tokens, paying
    cost, else rejected (0) paying nothing. Returns the list
    of 1/0 verdicts. Exact Fraction arithmetic throughout."""
    fail = make_fail("token_bucket_trace")
    check_int(fail, capacity, "capacity")
    if capacity < 1 or capacity > MAX_VAL:
        fail("out_of_range:capacity")
    check_int(fail, refill_num, "refill_num")
    if refill_num < 0 or refill_num > MAX_VAL:
        fail("out_of_range:refill_num")
    check_int(fail, refill_den, "refill_den")
    if refill_den < 1 or refill_den > MAX_VAL:
        fail("out_of_range:refill_den")
    check_items(fail, events, "events")
    prev = 0
    for i, e in enumerate(events):
        check_items(fail, e, "events[%d]" % i)
        if len(e) != 2:
            fail("bad_shape:events[%d]" % i)
        check_int(fail, e[0], "events[%d][0]" % i)
        check_int(fail, e[1], "events[%d][1]" % i)
        tick, cost = e
        if tick < 0 or tick > MAX_VAL:
            fail("out_of_range:events[%d][0]" % i)
        if tick < prev:
            fail("unordered:events[%d]" % i)
        if cost < 1 or cost > capacity:
            fail("out_of_range:events[%d][1]" % i)
        prev = tick
    rate = Fraction(refill_num, refill_den)
    cap = Fraction(capacity)
    bucket = cap
    prev = 0
    out = []
    for tick, cost in events:
        bucket = min(cap, bucket + (tick - prev) * rate)
        prev = tick
        if bucket >= cost:
            bucket -= cost
            out.append(1)
        else:
            out.append(0)
    return out


def maze_gen_backtracker(rows, cols, seed):
    """Perfect maze on a rows-by-cols grid, depth-first carved.

    rows and cols are positive ints whose product is capped at
    MAX_MAZE_CELLS; seed is an int 0 to 2**64 - 1 driving a
    local SplitMix64 generator (no global or shared random
    state). An iterative backtracker starts at cell (0, 0) and
    repeatedly moves to an unvisited neighbor chosen by the
    generator, backtracking when stuck, producing a spanning
    tree of the grid. Returns rows lists of cell bitmasks with
    bit 1 = north passage open, 2 = east, 4 = south, 8 = west.
    Deterministic for a fixed seed."""
    fail = make_fail("maze_gen_backtracker")
    check_int(fail, rows, "rows")
    if rows < 1 or rows > MAX_MAZE_CELLS:
        fail("out_of_range:rows")
    check_int(fail, cols, "cols")
    if cols < 1 or cols > MAX_MAZE_CELLS:
        fail("out_of_range:cols")
    if rows * cols > MAX_MAZE_CELLS:
        fail("too_many:rows,cols")
    check_int(fail, seed, "seed")
    if seed < 0 or seed > _MASK64:
        fail("out_of_range:seed")
    state = [seed & _MASK64]

    def rnd():
        state[0] = (state[0] + 0x9E3779B97F4A7C15) & _MASK64
        z = state[0]
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return z ^ (z >> 31)

    cells = rows * cols
    grid = [[0] * cols for _ in range(rows)]
    visited = [False] * cells
    # neighbor deltas: (dr, dc, this-bit, other-bit)
    dirs = ((-1, 0, 1, 4), (0, 1, 2, 8), (1, 0, 4, 1), (0, -1, 8, 2))
    stack = [(0, 0)]
    visited[0] = True
    while stack:
        r, c = stack[-1]
        options = []
        for dr, dc, bit, obit in dirs:
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols
                    and not visited[nr * cols + nc]):
                options.append((nr, nc, bit, obit))
        if not options:
            stack.pop()
            continue
        nr, nc, bit, obit = options[rnd() % len(options)]
        grid[r][c] |= bit
        grid[nr][nc] |= obit
        visited[nr * cols + nc] = True
        stack.append((nr, nc))
    return grid


def cryptarithmetic_solve(terms, result):
    """Digit assignment making the sum of terms equal result.

    Each of the 2..MAX_CRYPT_TERMS terms and the result is a
    nonempty string of uppercase A-Z letters, at most
    MAX_CRYPT_LENGTH characters; distinct letters across every
    word are capped at 10 and the first letter of any word
    never takes the digit 0. Letters are assigned digits in the
    order they first appear scanning columns right to left
    (within a column, terms top to bottom, then the result),
    trying digits 0..9 in ascending order with column-carries
    checked as soon as a column is fully assigned; the first
    complete assignment in that order is returned as sorted
    [letter, digit] pairs, or None when no assignment exists."""
    fail = make_fail("cryptarithmetic_solve")
    check_items(fail, terms, "terms")
    if len(terms) < 2:
        fail("too_few:terms")
    if len(terms) > MAX_CRYPT_TERMS:
        fail("too_many:terms")
    check_str(fail, result, "result")
    words = []
    for i, w in enumerate(terms):
        check_str(fail, w, "terms[%d]" % i)
        words.append(w)
    words.append(result)
    for i, w in enumerate(words):
        name = "terms[%d]" % i if i < len(terms) else "result"
        if not w:
            fail("empty:%s" % name)
        if len(w) > MAX_CRYPT_LENGTH:
            fail("too_long:%s" % name)
        for j, ch in enumerate(w):
            if ch < "A" or ch > "Z":
                fail("bad_char:%s[%d]" % (name, j))
    leading = {w[0] for w in words}
    order = []
    seen = set()
    width = max(len(w) for w in words)
    for col in range(1, width + 1):
        for w in words:
            if len(w) >= col:
                ch = w[-col]
                if ch not in seen:
                    seen.add(ch)
                    order.append(ch)
    if len(order) > 10:
        fail("too_many:letters")
    assign = {}
    used = [False] * 10

    def search(idx):
        # called only with idx < len(order); the complete-
        # assignment case returns from inside the digit loop
        letter = order[idx]
        for d in range(10):
            if used[d] or (d == 0 and letter in leading):
                continue
            assign[letter] = d
            used[d] = True
            # verify the longest fully-assigned column prefix
            carry = 0
            ok = True
            col = 0
            for col in range(1, width + 1):
                involved = [w[-col] for w in words if len(w) >= col]
                if any(ch not in assign for ch in involved):
                    break
                total = carry
                for w in words[:-1]:
                    if len(w) >= col:
                        total += assign[w[-col]]
                want = (assign[result[-col]]
                        if len(result) >= col else 0)
                if total % 10 != want:
                    ok = False
                    break
                carry = total // 10
            if ok:
                if idx + 1 == len(order):
                    if col == width and carry == 0:
                        return dict(assign)
                else:
                    got = search(idx + 1)
                    if got is not None:
                        return got
            del assign[letter]
            used[d] = False
        return None

    found = search(0)
    if found is None:
        return None
    return [[ch, found[ch]] for ch in sorted(found)]


def bloom_filter_check(items, queries, size, hashes):
    """Bloom-filter membership verdicts for the queries.

    items and queries are lists of strings (each capped at
    MAX_STR characters), size is the filter width 1..
    MAX_BLOOM_SIZE bits and hashes the probe count 1..
    MAX_BLOOM_HASHES. Each string is hashed by 64-bit FNV-1a
    over its UTF-8 bytes (h1) and over the reversed bytes (h2);
    probe i lands at (h1 + i * h2) mod size. Every item's bits
    are set, then each query answers 1 when all its probe bits
    are set (maybe-present) and 0 otherwise (definitely
    absent). Deterministic; no false negatives."""
    fail = make_fail("bloom_filter_check")
    check_int(fail, size, "size")
    if size < 1 or size > MAX_BLOOM_SIZE:
        fail("out_of_range:size")
    check_int(fail, hashes, "hashes")
    if hashes < 1 or hashes > MAX_BLOOM_HASHES:
        fail("out_of_range:hashes")
    check_items(fail, items, "items")
    check_items(fail, queries, "queries")
    for tag, group in (("items", items), ("queries", queries)):
        for i, v in enumerate(group):
            check_str(fail, v, "%s[%d]" % (tag, i))
            if len(v) > MAX_STR:
                fail("too_long:%s[%d]" % (tag, i))
            try:
                v.encode("utf-8")
            except UnicodeEncodeError:
                fail("bad_char:%s[%d]" % (tag, i))

    def fnv(data):
        h = 14695981039346656037
        for b in data:
            h = ((h ^ b) * 1099511628211) & _MASK64
        return h

    def probes(v):
        raw = v.encode("utf-8")
        h1 = fnv(raw)
        h2 = fnv(raw[::-1])
        return [((h1 + i * h2) % size) for i in range(hashes)]

    bits = bytearray(size)
    for v in items:
        for p in probes(v):
            bits[p] = 1
    out = []
    for v in queries:
        out.append(1 if all(bits[p] for p in probes(v)) else 0)
    return out
