"""P235 concepts batch 90: string indexes, transforms, matching
and validation.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Every string input is capped at MAX_ITEMS characters, with one
exception: bwt_decode accepts MAX_ITEMS + 1 because its input
carries the encoder's extra sentinel. The heaviest builds
are the suffix array doubling (at cap: about 14 rounds sorting
10_000 keys) and the suffix automaton scan (at most 2 * MAX_ITEMS
states, one pass over a 10_000-character string), each an
estimated few million primitive operations.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_items, check_str, make_fail)

_BWT_SENTINEL = "\x00"


def _text(fail, s, name):
    check_str(fail, s, name)
    if len(s) > MAX_ITEMS:
        fail("too_many:%s" % name)
    return s


def _suffix_array(s):
    n = len(s)
    if n == 0:
        return []
    sa = sorted(range(n), key=s.__getitem__)
    rank = [0] * n
    classes = 0
    for k in range(1, n):
        if s[sa[k]] != s[sa[k - 1]]:
            classes += 1
        rank[sa[k]] = classes
    width = 1
    while classes < n - 1:
        def key(i, rank=rank, width=width):
            return (rank[i],
                    rank[i + width] if i + width < n else -1)
        sa.sort(key=key)
        new = [0] * n
        classes = 0
        for k in range(1, n):
            if key(sa[k]) != key(sa[k - 1]):
                classes += 1
            new[sa[k]] = classes
        rank = new
        width *= 2
    return sa


def suffix_array_build(s):
    """Start indices of the suffixes of s in lexicographic order.

    Doubling construction: each round re-ranks suffixes by their
    first 2w characters from the ranks of the two w-halves, so an
    estimated O(n log^2 n) comparisons build the order."""
    fail = make_fail("suffix_array_build")
    _text(fail, s, "s")
    return _suffix_array(s)


def bwt_encode(s):
    """Burrows-Wheeler transform of s with a NUL terminator.

    s must be non-empty and must not contain "\\x00"; the output
    is the last column of the sorted rotations of s + "\\x00", one
    character longer than s, built from the suffix array."""
    fail = make_fail("bwt_encode")
    _text(fail, s, "s")
    if not s:
        fail("empty:s")
    for i, ch in enumerate(s):
        if ch == _BWT_SENTINEL:
            fail("bad_char:s[%d]" % i)
    t = s + _BWT_SENTINEL
    return "".join(t[i - 1] for i in _suffix_array(t))


def bwt_decode(t):
    """Invert bwt_encode. t must be non-empty and hold exactly one
    "\\x00" sentinel. It may be one character longer than
    MAX_ITEMS because bwt_encode appends the sentinel to an input
    of up to MAX_ITEMS characters, so the round trip holds at the
    maximum accepted size. The LF-mapping pairs each last-column
    character with its equal occurrence in the sorted first column;
    the walk from the sentinel must visit every row exactly once
    (the valid BWT images are exactly the inputs whose LF orbit is
    a single full cycle) or the input is refused as malformed."""
    fail = make_fail("bwt_decode")
    check_str(fail, t, "t")
    if len(t) > MAX_ITEMS + 1:
        fail("too_many:t")
    if not t:
        fail("empty:t")
    nul = [i for i, ch in enumerate(t) if ch == _BWT_SENTINEL]
    if len(nul) != 1:
        fail("bad_char:t")
    n = len(t)
    seen = {}
    rank = []
    for ch in t:
        rank.append(seen.get(ch, 0))
        seen[ch] = rank[-1] + 1
    first = sorted(t)
    pos = {}
    seen = {}
    for j, ch in enumerate(first):
        pos[(ch, seen.get(ch, 0))] = j
        seen[ch] = seen.get(ch, 0) + 1
    nxt = [pos[(ch, rank[i])] for i, ch in enumerate(t)]
    row = nul[0]
    chars = []
    seen = [False] * n
    for _ in range(n):
        if seen[row]:
            fail("bad_form:t")
        seen[row] = True
        chars.append(t[row])
        row = nxt[row]
    text = "".join(reversed(chars))
    return text[:-1]


def matching_statistics_lengths(s, t):
    """For each position i of s, the length of the longest prefix
    of s[i:] that occurs as a substring of t.

    This is not the z-function: z matches every position against
    the prefix of its own string, while matching statistics match
    against any substring of a second string. A suffix automaton
    of t accepts exactly the substrings of t. The scan runs on
    the reversed strings: a forward pass emits longest matches
    ending at each position, so reversing both sides turns them
    into longest matches starting at each position, an estimated
    O(len(s) + len(t)) steps. Empty t yields all zeros."""
    fail = make_fail("matching_statistics_lengths")
    _text(fail, s, "s")
    _text(fail, t, "t")

    def automaton(text):
        link = [-1]
        length = [0]
        trans = [{}]
        last = 0
        for ch in text:
            cur = len(length)
            length.append(length[last] + 1)
            link.append(0)
            trans.append({})
            p = last
            while p != -1 and ch not in trans[p]:
                trans[p][ch] = cur
                p = link[p]
            if p == -1:
                link[cur] = 0
            else:
                q = trans[p][ch]
                if length[p] + 1 == length[q]:
                    link[cur] = q
                else:
                    clone = len(length)
                    length.append(length[p] + 1)
                    link.append(link[q])
                    trans.append(dict(trans[q]))
                    while p != -1 and trans[p].get(ch) == q:
                        trans[p][ch] = clone
                        p = link[p]
                    link[q] = clone
                    link[cur] = clone
            last = cur
        return link, length, trans

    def ending_matches(text, link, length, trans):
        out = []
        state = 0
        run = 0
        for ch in text:
            while state and ch not in trans[state]:
                state = link[state]
                run = length[state]
            if ch in trans[state]:
                state = trans[state][ch]
                run += 1
            else:
                run = 0
            out.append(run)
        return out

    link, length, trans = automaton(t[::-1])
    return ending_matches(s[::-1], link, length, trans)[::-1]


def smallest_distinct_subsequence(s):
    """Lexicographically smallest subsequence of s that contains
    every distinct character of s exactly once.

    Greedy monotone stack: scan left to right, drop a stacked
    character when it is larger than the new one and still occurs
    later in s, and skip characters already stacked. The result
    keeps exactly one copy of each distinct character; an empty s
    yields an empty result. Two linear passes over at most
    MAX_ITEMS characters (the last-occurrence map, then the stack
    scan)."""
    fail = make_fail("smallest_distinct_subsequence")
    _text(fail, s, "s")
    last = {}
    for i, ch in enumerate(s):
        last[ch] = i
    stack = []
    in_stack = set()
    for i, ch in enumerate(s):
        if ch in in_stack:
            continue
        while stack and stack[-1] > ch and last[stack[-1]] > i:
            in_stack.discard(stack.pop())
        stack.append(ch)
        in_stack.add(ch)
    return "".join(stack)


def manacher_palindrome_radii(s):
    """Odd and even palindrome radii at every center of s.

    d1[i] is the radius of the largest palindrome centered on
    character i (a single character has radius 1); d2[i] is the
    radius of the largest palindrome centered between i - 1 and i.
    Both passes reuse the rightmost known palindrome boundary."""
    fail = make_fail("manacher_palindrome_radii")
    _text(fail, s, "s")
    n = len(s)
    d1 = [0] * n
    left, right = 0, -1
    for i in range(n):
        r = 1 if i > right else min(d1[left + right - i],
                                    right - i + 1)
        while i - r >= 0 and i + r < n and s[i - r] == s[i + r]:
            r += 1
        d1[i] = r
        if i + r - 1 > right:
            left, right = i - r + 1, i + r - 1
    d2 = [0] * n
    left, right = 0, -1
    for i in range(n):
        r = 0 if i > right else min(d2[left + right - i + 1],
                                    right - i + 1)
        while i - r - 1 >= 0 and i + r < n and s[i - r - 1] == s[i + r]:
            r += 1
        d2[i] = r
        if i + r - 1 > right:
            left, right = i - r, i + r - 1
    return d1, d2


def lyndon_factorization(s):
    """The unique factorization of s into a non-increasing sequence
    of Lyndon words (Duval's algorithm). A Lyndon word is strictly
    smaller than each of its nontrivial rotations."""
    fail = make_fail("lyndon_factorization")
    _text(fail, s, "s")
    n = len(s)
    out = []
    i = 0
    while i < n:
        j = i + 1
        k = i
        while j < n and s[k] <= s[j]:
            if s[k] < s[j]:
                k = i
            else:
                k += 1
            j += 1
        while i <= k:
            out.append(s[i:i + j - k])
            i += j - k
    return out


def distinct_palindrome_count(s):
    """Number of distinct non-empty palindromic substrings of s.

    A palindromic tree is grown character by character; each new
    node is one newly seen palindrome, so the answer is the number
    of nodes beyond the two roots. The tree holds at most
    len(s) + 2 nodes."""
    fail = make_fail("distinct_palindrome_count")
    _text(fail, s, "s")
    nodes = [[-1, 0, {}], [0, 0, {}]]
    last = 1
    for pos, ch in enumerate(s):
        cur = last
        while True:
            length = nodes[cur][0]
            if pos - length - 1 >= 0 and s[pos - length - 1] == ch:
                break
            cur = nodes[cur][1]
        if ch in nodes[cur][2]:
            last = nodes[cur][2][ch]
            continue
        new_len = nodes[cur][0] + 2
        if new_len == 1:
            link = 1
        else:
            probe = nodes[cur][1]
            while True:
                length = nodes[probe][0]
                if pos - length - 1 >= 0 \
                        and s[pos - length - 1] == ch:
                    break
                probe = nodes[probe][1]
            link = nodes[probe][2][ch]
        nodes[cur][2][ch] = len(nodes)
        nodes.append([new_len, link, {}])
        last = len(nodes) - 1
    return len(nodes) - 2


def lz78_encode_pairs(s):
    """LZ78 dictionary encoding of s as (phrase_index, char) pairs.

    The dictionary starts empty with index 0 meaning the empty
    phrase. Each emitted pair names the longest already-seen phrase
    that prefixes the remaining input plus one new character; that
    combination becomes the next dictionary phrase, numbered from
    1 in emission order. A trailing pair with an empty character
    closes a final all-dictionary phrase. The dictionary is a trie,
    so the scan is an estimated O(len(s)) lookups."""
    fail = make_fail("lz78_encode_pairs")
    _text(fail, s, "s")
    children = [{}]
    out = []
    cur = 0
    for ch in s:
        nxt = children[cur].get(ch)
        if nxt is None:
            children[cur][ch] = len(children)
            children.append({})
            out.append((cur, ch))
            cur = 0
        else:
            cur = nxt
    if cur:
        out.append((cur, ""))
    return out


def repeated_string_match_min(a, b):
    """Smallest k >= 1 such that b is a substring of a repeated k
    times, or -1 when no repetition of a can contain b.

    a and b must be non-empty. Any occurrence that exists fits
    inside ceil(len(b) / len(a)) + 2 repeats: a cover of len(b)
    consecutive characters needs at most ceil(len(b) / len(a))
    blocks once aligned, plus one block of slack on each side. Only
    that bounded haystack is searched."""
    fail = make_fail("repeated_string_match_min")
    _text(fail, a, "a")
    _text(fail, b, "b")
    if not a:
        fail("empty:a")
    if not b:
        fail("empty:b")
    span = -(-len(b) // len(a)) + 2
    hay = a * span
    at = hay.find(b)
    if at == -1:
        return -1
    return -(-(at + len(b)) // len(a))
