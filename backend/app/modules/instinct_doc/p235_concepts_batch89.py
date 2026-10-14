"""P235 concepts batch 89: disjoint-set union applications.

Eight small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps. Each
solves a different problem whose structure is an implicit
union-find: grouping accounts, checking equation consistency,
finding a first connection time, judging friend requests under
restrictions, optimizing strings by free swaps or by
substitution, counting bricks dropped by erasures, and scoring
similar-sentence pairs; the two weighted-graph entries were
removed and replaced by batch 93 after auditor screens. Node,
edge, text, and cell counts stay within declared caps (grids
within a total-cell cap). The generic union-find uses
union-by-rank with full path-compression finds (near-constant
amortized).
"""


from fractions import Fraction
from math import isfinite

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_VAL = 10_000
MAX_DIM = 100
MAX_WORD = 40
MAX_SENT = 100
MAX_RESTRICTIONS = 300


class _DSU:
    """Union-by-rank disjoint set with full path-compression finds."""

    __slots__ = ("parent", "rank", "count")

    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        self.count -= 1
        return True


def _node_list(fail, edges, name, hi=MAX_ITEMS):
    check_items(fail, edges, name)
    if not edges:
        fail("empty:%s" % name)
    if len(edges) > hi:
        fail("too_many:%s" % name)
    return edges


def accounts_merge_groups(accounts):
    """Merged accounts: any shared email links two accounts.

    accounts holds [name, email, ...] lists. Two accounts belong
    together when they share an email, directly or through other
    accounts. Returns one group per linked cluster as [name,
    sorted-unique-emails...], groups ordered by name then first
    email. An email tied to two different names refuses, since the
    owner would be ambiguous."""
    fail = make_fail("accounts_merge_groups")
    _node_list(fail, accounts, "accounts")
    total = 0
    cleaned = []
    seen_names = {}
    for i, acc in enumerate(accounts):
        if (type(acc) is not list or len(acc) < 2
                or type(acc[0]) is not str or not acc[0]):
            fail("bad_shape:accounts[%d]" % i)
        name = acc[0]
        emails = []
        for j, e in enumerate(acc[1:]):
            if type(e) is not str or "@" not in e or len(e) > MAX_WORD * 2:
                fail("bad_value:accounts[%d][%d]" % (i, j + 1))
            owner = seen_names.setdefault(e, name)
            if owner != name:
                fail("conflict:accounts[%d][%d]" % (i, j + 1))
            emails.append(e)
        total += len(emails)
        if total > MAX_ITEMS:
            fail("too_many:emails")
        cleaned.append((name, emails))
    dsu = _DSU(len(cleaned))
    first = {}
    for i, (_, emails) in enumerate(cleaned):
        for e in emails:
            if e in first:
                dsu.union(i, first[e])
            else:
                first[e] = i
    groups = {}
    for e, i in first.items():
        groups.setdefault(dsu.find(i), []).append(e)
    out = []
    for root, emails in groups.items():
        name = cleaned[root][0]
        out.append([name] + sorted(set(emails)))
    out.sort(key=lambda g: (g[0], g[1]))
    return out


def equations_satisfiable_check(equations):
    """Whether single-letter equalities and inequalities agree.

    equations holds "a==b" or "a!=b" strings over lowercase
    letters. Equalities define equivalence classes; the list is
    satisfiable unless an inequality joins two equivalent letters
    (including a!=a). Result does not depend on equation order."""
    fail = make_fail("equations_satisfiable_check")
    _node_list(fail, equations, "equations")
    parsed = []
    for i, eq in enumerate(equations):
        if (type(eq) is not str or len(eq) != 4
                or eq[1:3] not in ("==", "!=")
                or not ("a" <= eq[0] <= "z" and "a" <= eq[3] <= "z")):
            fail("bad_shape:equations[%d]" % i)
        parsed.append((eq[0], eq[3], eq[1:3] == "=="))
    dsu = _DSU(26)
    for a, b, is_eq in parsed:
        if is_eq:
            dsu.union(ord(a) - 97, ord(b) - 97)
    for a, b, is_eq in parsed:
        if not is_eq and dsu.find(ord(a) - 97) == dsu.find(ord(b) - 97):
            return False
    return True


def earliest_fully_connected_time(n, logs):
    """Earliest timestamp when every node is connected, or -1.

    logs holds [timestamp, a, b] entries over nodes 1..n with
    nondecreasing timestamps; a regressing timestamp refuses.
    Returns the first timestamp at which the graph becomes
    connected, or -1 when the logs never connect it. A single
    node is connected from time 0. Every log is validated before
    any union runs, so a malformed or regressing entry refuses
    even past the connection point."""
    fail = make_fail("earliest_fully_connected_time")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_ITEMS:
        fail("out_of_range:n")
    _node_list(fail, logs, "logs")
    # whole-input validation first: a malformed or regressing log
    # refuses even when it sits past the connection point
    last = None
    for i, log in enumerate(logs):
        if (type(log) is not list or len(log) != 3
                or any(type(v) is not int for v in log)):
            fail("bad_shape:logs[%d]" % i)
        t, a, b = log
        if last is not None and t < last:
            fail("bad_order:logs[%d]" % i)
        last = t
        if not (1 <= a <= n and 1 <= b <= n):
            fail("bad_value:logs[%d]" % i)
    if n == 1:
        return 0
    dsu = _DSU(n + 1)
    dsu.count = n  # ignore the unused slot 0
    for t, a, b in logs:
        if a != b:
            dsu.union(a, b)
        if dsu.count == 1:
            return t
    return -1


def restricted_friend_verdicts(n, restrictions, requests):
    """Accept or refuse each friend request in order.

    restrictions holds [x, y] pairs over users 0..n-1 that must
    never share a friend group; requests holds [u, v] pairs
    processed in order, approved exactly when the merge cannot
    place any restricted pair in one group. At most
    MAX_RESTRICTIONS restrictions, so each request checks every
    restriction's roots and the total work stays within
    restrictions times requests."""
    fail = make_fail("restricted_friend_verdicts")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_ITEMS:
        fail("out_of_range:n")
    check_items(fail, restrictions, "restrictions")
    if len(restrictions) > MAX_RESTRICTIONS:
        fail("too_many:restrictions")
    parsed_r = []
    for i, r in enumerate(restrictions):
        if (type(r) is not list or len(r) != 2
                or any(type(v) is not int for v in r)):
            fail("bad_shape:restrictions[%d]" % i)
        x, y = r
        if not (0 <= x < n and 0 <= y < n) or x == y:
            fail("bad_value:restrictions[%d]" % i)
        parsed_r.append((x, y))
    check_items(fail, requests, "requests")
    if len(requests) > MAX_ITEMS:
        fail("too_many:requests")
    parsed_q = []
    for i, q in enumerate(requests):
        if (type(q) is not list or len(q) != 2
                or any(type(v) is not int for v in q)):
            fail("bad_shape:requests[%d]" % i)
        u, v = q
        if not (0 <= u < n and 0 <= v < n) or u == v:
            fail("bad_value:requests[%d]" % i)
        parsed_q.append((u, v))
    dsu = _DSU(n)
    out = []
    for u, v in parsed_q:
        ru, rv = dsu.find(u), dsu.find(v)
        ok = True
        if ru != rv:
            for x, y in parsed_r:
                rx, ry = dsu.find(x), dsu.find(y)
                if (rx == ru and ry == rv) or (rx == rv and ry == ru):
                    ok = False
                    break
        if ok:
            dsu.union(u, v)
        out.append(ok)
    return out


def smallest_string_with_swaps(text, pairs):
    """Lexicographically smallest string after free swaps.

    pairs lists index pairs into text that may be swapped any
    number of times, so indices linked through pairs permute
    freely. Returns the lexicographically smallest arrangement."""
    fail = make_fail("smallest_string_with_swaps")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    check_items(fail, pairs, "pairs")
    if len(pairs) > MAX_ITEMS:
        fail("too_many:pairs")
    n = len(text)
    dsu = _DSU(n)
    for i, p in enumerate(pairs):
        if (type(p) is not list or len(p) != 2
                or any(type(v) is not int for v in p)):
            fail("bad_shape:pairs[%d]" % i)
        a, b = p
        if not (0 <= a < n and 0 <= b < n):
            fail("bad_value:pairs[%d]" % i)
        dsu.union(a, b)
    slots = {}
    for i in range(n):
        slots.setdefault(dsu.find(i), []).append(i)
    out = list(text)
    for idxs in slots.values():
        chars = sorted(text[i] for i in idxs)
        for i, c in zip(idxs, chars):
            out[i] = c
    return "".join(out)


def lexicographically_smallest_char_map(pairs, text):
    """Map every letter to the smallest letter in its class.

    pairs holds two-letter strings declaring equal lowercase
    characters. Each character of text is replaced by the smallest
    character equivalent to it; equivalence is transitive."""
    fail = make_fail("lexicographically_smallest_char_map")
    check_items(fail, pairs, "pairs")
    if len(pairs) > MAX_ITEMS:
        fail("too_many:pairs")
    dsu = _DSU(26)
    for i, p in enumerate(pairs):
        if (type(p) is not str or len(p) != 2
                or not ("a" <= p[0] <= "z" and "a" <= p[1] <= "z")):
            fail("bad_shape:pairs[%d]" % i)
        dsu.union(ord(p[0]) - 97, ord(p[1]) - 97)
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    smallest = {}
    for c in range(26):
        r = dsu.find(c)
        smallest[r] = min(smallest.get(r, c), c)
    out = []
    for c in text:
        if not "a" <= c <= "z":
            fail("bad_char:text")
        out.append(chr(smallest[dsu.find(ord(c) - 97)] + 97))
    return "".join(out)


def bricks_falling_counts(grid, hits):
    """Bricks that fall after each hit, in hit order.

    grid holds 0/1 cells; a brick stays when it links to the top
    row through other bricks (4-neighbourhood). hits holds
    distinct brick cells erased in order; each answer counts the
    bricks that stood before that hit and are no longer
    roof-linked. Erasures are processed in reverse: every hit
    cell starts erased, hits undo one at a time, and a union-find
    with root sizes tracks the roof-linked count."""
    fail = make_fail("bricks_falling_counts")
    check_items(fail, grid, "grid")
    if not grid:
        fail("empty:grid")
    if len(grid) > MAX_DIM:
        fail("too_many:grid")
    width = None
    for i, row in enumerate(grid):
        check_items(fail, row, "grid[%d]" % i)
        if not row or len(row) > MAX_DIM:
            fail("bad_shape:grid[%d]" % i)
        if width is None:
            width = len(row)
        elif len(row) != width:
            fail("ragged:grid[%d]" % i)
        for v in row:
            if type(v) is not int or v not in (0, 1):
                fail("bad_value:grid[%d]" % i)
    rows, cols = len(grid), width
    if rows * cols > MAX_ITEMS:
        fail("too_many:cells")
    check_items(fail, hits, "hits")
    if len(hits) > MAX_ITEMS:
        fail("too_many:hits")
    seen_hits = set()
    for i, h in enumerate(hits):
        if (type(h) is not list or len(h) != 2
                or any(type(v) is not int for v in h)):
            fail("bad_shape:hits[%d]" % i)
        r, c = h
        if not (0 <= r < rows and 0 <= c < cols):
            fail("out_of_range:hits[%d]" % i)
        if grid[r][c] != 1:
            fail("bad_value:hits[%d]" % i)
        if (r, c) in seen_hits:
            fail("duplicate:hits[%d]" % i)
        seen_hits.add((r, c))

    total = rows * cols
    roof = total
    dsu = _DSU(total + 1)
    size = [1] * (total + 1)

    def unite(a, b):
        ra, rb = dsu.find(a), dsu.find(b)
        if ra == rb:
            return
        dsu.union(ra, rb)
        root = dsu.find(ra)
        size[root] = size[ra] + size[rb]

    erased = [[grid[r][c] == 0 for c in range(cols)]
              for r in range(rows)]
    for r, c in hits:
        erased[r][c] = True

    def activate(r, c):
        me = r * cols + c
        if r == 0:
            unite(me, roof)
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols
                    and not erased[nr][nc]):
                unite(me, nr * cols + nc)

    for r in range(rows):
        for c in range(cols):
            if not erased[r][c]:
                activate(r, c)
    out = [0] * len(hits)
    for t in range(len(hits) - 1, -1, -1):
        r, c = hits[t]
        before = size[dsu.find(roof)]
        erased[r][c] = False
        activate(r, c)
        out[t] = max(0, size[dsu.find(roof)] - before - 1)
    return out


def similar_sentence_groups(pairs, queries):
    """Similarity verdicts for sentence pairs under synonym closure.

    pairs holds [word_a, word_b] synonym links; similarity is the
    transitive closure and a word is similar to itself. queries
    holds [sentence_a, sentence_b] pairs of word lists; a query is
    True when the sentences have equal length and every aligned
    word pair is similar."""
    fail = make_fail("similar_sentence_groups")
    check_items(fail, pairs, "pairs")
    if len(pairs) > MAX_ITEMS:
        fail("too_many:pairs")
    ids = {}
    links = []
    for i, p in enumerate(pairs):
        if (type(p) is not list or len(p) != 2
                or any(type(w) is not str or not w or len(w) > MAX_WORD
                       for w in p)):
            fail("bad_shape:pairs[%d]" % i)
        for w in p:
            if w not in ids:
                ids[w] = len(ids)
        links.append((ids[p[0]], ids[p[1]]))
    check_items(fail, queries, "queries")
    if len(queries) > MAX_ITEMS:
        fail("too_many:queries")
    parsed = []
    for i, q in enumerate(queries):
        if (type(q) is not list or len(q) != 2
                or any(type(s) is not list for s in q)):
            fail("bad_shape:queries[%d]" % i)
        for s in q:
            if len(s) > MAX_SENT:
                fail("too_long:queries[%d]" % i)
            for w in s:
                if type(w) is not str or not w or len(w) > MAX_WORD:
                    fail("bad_value:queries[%d]" % i)
        parsed.append(q)
    dsu = _DSU(len(ids))
    for a, b in links:
        dsu.union(a, b)

    def similar(a, b):
        if a == b:
            return True
        if a not in ids or b not in ids:
            return False
        return dsu.find(ids[a]) == dsu.find(ids[b])

    out = []
    for a, b in parsed:
        out.append(len(a) == len(b)
                   and all(similar(x, y) for x, y in zip(a, b)))
    return out
