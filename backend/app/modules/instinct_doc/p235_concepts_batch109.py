"""P235 concepts batch 109: ten concepts.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries; tighter caps
(MAX_INVOLUTIONS_N, MAX_MERKLE_LEAVES, MAX_TRIE_WORDS,
MAX_WORD_LEN, MAX_APPROX_DEN, MAX_SIG_DIGITS, MAX_RATIO_VAL,
MAX_SEXP_DEPTH, MAX_SEXP_NUM_DIGITS, MAX_NKEY_DIGITS,
MAX_SIGN_WIDTH, MAX_NSPC_N, MAX_BLACKJACK_CARDS) are stated in the docstrings of the functions that
carry them. Every function validates its whole input first:
length caps are checked before the elements they bound are
inspected, then type, range, and shape checks run during the
validation phase, and the computation phase starts only after
validation succeeds. Exact arithmetic uses ints and Fractions
only; sha256 hashing is the documented Merkle combining step.
"""

from fractions import Fraction
from hashlib import sha256
from math import gcd

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_INVOLUTIONS_N = 400
MAX_MERKLE_LEAVES = 2048
MAX_TRIE_WORDS = 1000
MAX_WORD_LEN = 64
MAX_APPROX_DEN = 10**6
MAX_SIG_DIGITS = 18
MAX_RATIO_VAL = 10**18
MAX_SEXP_DEPTH = 100
MAX_SEXP_NUM_DIGITS = 4300
MAX_NKEY_DIGITS = 4300
MAX_SIGN_WIDTH = 64
MAX_NSPC_N = 10**18
MAX_BLACKJACK_CARDS = 11


def involutions_count(n):
    """Number of involutions of an n-element set.

    n is an int from 0 to MAX_INVOLUTIONS_N. An involution is a
    permutation that is its own inverse; the count a(n) follows
    a(0) = a(1) = 1 and a(n) = a(n-1) + (n-1)*a(n-2). Returns
    the exact int. Iterates the recurrence directly; an
    estimated O(n) big-int additions."""
    fail = make_fail("involutions_count")
    check_int(fail, n, "n")
    if n < 0 or n > MAX_INVOLUTIONS_N:
        fail("out_of_range:n")
    prev2, prev1 = 1, 1
    for i in range(2, n + 1):
        prev2, prev1 = prev1, prev1 + (i - 1) * prev2
    return prev2 if n == 0 else prev1


_HEX_DIGITS = frozenset("0123456789abcdef")


def merkle_root(digests):
    """Root of a Merkle tree over sha256 hex digests.

    digests holds 1..MAX_MERKLE_LEAVES strings, each exactly 64
    lowercase hexadecimal characters (a sha256 digest). Parents
    are sha256 of the concatenation of the two child digests as
    raw bytes, rendered lowercase hex. When a level has an odd
    number of nodes the last node is duplicated (the Bitcoin
    convention). A single digest is its own root. Returns the
    64-character lowercase hex root. An estimated O(leaves)
    hashes of 64 bytes each."""
    fail = make_fail("merkle_root")
    check_items(fail, digests, "digests")
    if not digests:
        fail("empty:digests")
    if len(digests) > MAX_MERKLE_LEAVES:
        fail("too_many:digests")
    level = []
    for i, d in enumerate(digests):
        check_str(fail, d, "digests[%d]" % i)
        if len(d) != 64:
            fail("bad_shape:digests[%d]" % i)
        for ch in d:
            if ch not in _HEX_DIGITS:
                fail("bad_char:digests[%d]" % i)
        level.append(bytes.fromhex(d))
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [sha256(level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex()


_LOWER = frozenset("abcdefghijklmnopqrstuvwxyz")


def _check_word(fail, word, name):
    check_str(fail, word, name)
    if not word:
        fail("empty:%s" % name)
    if len(word) > MAX_WORD_LEN:
        fail("too_long:%s" % name)
    for ch in word:
        if ch not in _LOWER:
            fail("bad_char:%s" % name)
    return word


def trie_prefix_count(words, prefix):
    """Count of distinct inserted words that start with prefix.

    words holds 0..MAX_TRIE_WORDS strings of 1..MAX_WORD_LEN
    lowercase ascii letters; duplicates are inserted once.
    prefix holds 0..MAX_WORD_LEN lowercase ascii letters; the
    empty prefix counts every distinct inserted word. Builds a
    trie with per-node subtree counts and reads the count at
    the prefix node. Returns an int, 0 when no inserted word
    starts with prefix. An estimated O(total characters) work."""
    fail = make_fail("trie_prefix_count")
    check_items(fail, words, "words")
    if len(words) > MAX_TRIE_WORDS:
        fail("too_many:words")
    check_str(fail, prefix, "prefix")
    if len(prefix) > MAX_WORD_LEN:
        fail("too_long:prefix")
    for ch in prefix:
        if ch not in _LOWER:
            fail("bad_char:prefix")
    root = [0, {}]
    seen = set()
    for i, w in enumerate(words):
        _check_word(fail, w, "words[%d]" % i)
        if w in seen:
            continue
        seen.add(w)
        node = root
        node[0] += 1
        for ch in w:
            nxt = node[1].get(ch)
            if nxt is None:
                nxt = [0, {}]
                node[1][ch] = nxt
            node = nxt
            node[0] += 1
    node = root
    for ch in prefix:
        nxt = node[1].get(ch)
        if nxt is None:
            return 0
        node = nxt
    return node[0]


def best_rational_approx(num, den, max_den):
    """Closest p/q with 0 <= p and 1 <= q <= max_den to num/den.

    num is an int from 0 to MAX_RATIO_VAL, den an int from 1 to
    MAX_RATIO_VAL, max_den an int from 1 to MAX_APPROX_DEN.
    Walks the Stern-Brocot tree toward the target, consuming
    each run of same-side mediant steps in one batched
    continued-fraction quotient, and compares the final
    bounding neighbors by exact cross-multiplied distance;
    ties go to the smaller q, then the smaller p. An exact hit
    with a reduced denominator within max_den returns the
    reduced target. The result may be (0, 1) when zero is the
    closest allowed fraction. Returns a (p, q) tuple of ints.
    The loop runs once per continued-fraction term of the
    target, independent of the target's magnitude."""
    fail = make_fail("best_rational_approx")
    check_int(fail, num, "num")
    if num < 0 or num > MAX_RATIO_VAL:
        fail("out_of_range:num")
    check_int(fail, den, "den")
    if den < 1 or den > MAX_RATIO_VAL:
        fail("out_of_range:den")
    check_int(fail, max_den, "max_den")
    if max_den < 1 or max_den > MAX_APPROX_DEN:
        fail("out_of_range:max_den")
    if num == 0:
        return (0, 1)
    g = gcd(num, den)
    rn, rd = num // g, den // g
    if rd <= max_den:
        return (rn, rd)
    lo_p, lo_q = 0, 1
    hi_p, hi_q = 1, 0
    while True:
        # Batch the lo-side run: the largest k with lo + k*hi
        # still at or below the target and within the
        # denominator cap. Both guards are exact integer
        # floors; hi_q is zero only while hi is the 1/0 bound,
        # where the cap does not bind.
        gap_lo = num * lo_q - lo_p * den
        gap_hi = hi_p * den - num * hi_q
        k_target = gap_lo // gap_hi
        if hi_q:
            k = min(k_target, (max_den - lo_q) // hi_q)
        else:
            k = k_target
        if k >= 1:
            lo_p += k * hi_p
            lo_q += k * hi_q
            if lo_p * den == num * lo_q:
                return (lo_p, lo_q)
            continue
        # Batch the hi-side run symmetrically; lo_q is at
        # least one here.
        k_target = gap_hi // gap_lo
        k = min(k_target, (max_den - hi_q) // lo_q)
        if k >= 1:
            hi_p += k * lo_p
            hi_q += k * lo_q
            if hi_p * den == num * hi_q:
                return (hi_p, hi_q)
            continue
        break
    # Both neighbors are real fractions at the break: the
    # first mediant is 1/1, so hi is never left at 1/0.
    best, best_dist = (lo_p, lo_q), abs(lo_p * den - num * lo_q)
    cand_dist = abs(hi_p * den - num * hi_q)
    if (cand_dist * best[1], hi_q, hi_p) <             (best_dist * hi_q, best[1], best[0]):
        best = (hi_p, hi_q)
    return best


_TEN = 10


def _round_half_even(frac):
    floor = frac.numerator // frac.denominator
    rem2 = (frac.numerator % frac.denominator) * 2
    if rem2 < frac.denominator:
        return floor
    if rem2 > frac.denominator:
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def round_significant(num, den, digits):
    """Canonical decimal of num/den to `digits` significant figures.

    num is an int from 0 to MAX_RATIO_VAL, den an int from 1 to
    MAX_RATIO_VAL, digits an int from 1 to MAX_SIG_DIGITS.
    Rounds half to even and renders plain decimal notation with
    no exponent; zeros that carry significance are kept, so
    0.0996 to two figures renders "0.10" and 1235 to two
    figures renders "1200". Zero renders "0". Uses exact
    Fraction arithmetic; an estimated O(number of rendered
    digits) work after a bounded exponent search."""
    fail = make_fail("round_significant")
    check_int(fail, num, "num")
    if num < 0 or num > MAX_RATIO_VAL:
        fail("out_of_range:num")
    check_int(fail, den, "den")
    if den < 1 or den > MAX_RATIO_VAL:
        fail("out_of_range:den")
    check_int(fail, digits, "digits")
    if digits < 1 or digits > MAX_SIG_DIGITS:
        fail("out_of_range:digits")
    if num == 0:
        return "0"
    x = Fraction(num, den)
    k = 0
    if x >= 1:
        while x >= _TEN ** (k + 1):
            k += 1
    else:
        while x < _TEN ** k:
            k -= 1
    s = k - digits + 1
    y = x / Fraction(_TEN ** s) if s >= 0 else x * Fraction(
        _TEN ** (-s))
    m = _round_half_even(y)
    if m == 0:
        return "0"
    if m == _TEN ** digits:
        m //= 10
        s += 1
    text = str(m)
    if s >= 0:
        return text + "0" * s
    point = len(text) + s
    if point > 0:
        return text[:point] + "." + text[point:]
    return "0." + "0" * (-point) + text


_WS = frozenset(" \t\n\r")


def sexp_parse(text):
    """Parse a single s-expression into nested lists and atoms.

    text holds 1..MAX_ITEMS characters. Whitespace (space, tab,
    newline, carriage return) separates tokens. An atom is a
    maximal run of characters that are neither whitespace,
    parentheses, nor quote characters; quote characters refuse.
    An atom of optional minus followed by at most
    MAX_SEXP_NUM_DIGITS digits converts with int(); a longer
    digit run refuses, keeping int conversion inside the
    platform digit limit. Any other atom stays a string.
    Parentheses nest
    lists; nesting depth is capped at MAX_SEXP_DEPTH. The text
    must hold exactly one datum: empty text, unbalanced
    parentheses, and trailing content refuse. Returns the
    nested list/int/str structure. An estimated O(len(text))
    work."""
    fail = make_fail("sexp_parse")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    for ch in text:
        if ch in "\"'":
            fail("bad_char:text")
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in _WS:
            i += 1
        elif ch in "()":
            tokens.append(ch)
            i += 1
        else:
            j = i
            while j < n and text[j] not in _WS and \
                    text[j] not in "()":
                j += 1
            tokens.append(text[i:j])
            i = j
    if not tokens:
        fail("empty:text")
    stack = []
    result = []
    done = False
    for tok in tokens:
        if done:
            fail("trailing:text")
        if tok == "(":
            if len(stack) >= MAX_SEXP_DEPTH:
                fail("too_deep:text")
            stack.append([])
        elif tok == ")":
            if not stack:
                fail("unbalanced:text")
            lst = stack.pop()
            if stack:
                stack[-1].append(lst)
            else:
                result = lst
                done = True
        else:
            atom = tok
            body = atom[1:] if atom.startswith("-") else atom
            if body and all(c in "0123456789" for c in body):
                if len(body) > MAX_SEXP_NUM_DIGITS:
                    fail("too_long:atom")
                value = int(atom)
            else:
                value = atom
            if stack:
                stack[-1].append(value)
            else:
                result = value
                done = True
    if stack:
        fail("unbalanced:text")
    if not done:
        fail("empty:text")
    return result


def natural_sort_key(text):
    """Sort key splitting text into digit runs and text runs.

    text holds 0..MAX_ITEMS characters. Each run becomes a
    (kind, value) tuple: (0, int) for a run of ascii digits
    (leading zeros collapse) and (1, str) for a run of other
    characters, so keys built from any texts always compare;
    digit runs sort before text runs. A digit run longer than
    MAX_NKEY_DIGITS digits refuses, keeping int conversion
    inside the platform digit limit. Empty text returns [].
    For example "a12b3" returns
    [(1, "a"), (0, 12), (1, "b"), (0, 3)]. Returns the key
    list; an estimated O(len(text)) work."""
    fail = make_fail("natural_sort_key")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_long:text")
    key = []
    i = 0
    n = len(text)
    while i < n:
        digit = "0" <= text[i] <= "9"
        j = i
        while j < n and ("0" <= text[j] <= "9") == digit:
            j += 1
        chunk = text[i:j]
        if digit:
            if len(chunk) > MAX_NKEY_DIGITS:
                fail("too_long:digit_run")
            key.append((0, int(chunk)))
        else:
            key.append((1, chunk))
        i = j
    return key


def sign_extend_bits(x, width):
    """Interpret the low `width` bits of x as a signed integer.

    x is an int from 0 to 2**width - 1, width an int from 1 to
    MAX_SIGN_WIDTH. The top of the width bits is the sign bit:
    values from 2**(width - 1) up come back negative, as two's
    complement. For example (0b1011, 4) returns -5 and
    (0b0111, 4) returns 7. O(1) big-int work."""
    fail = make_fail("sign_extend_bits")
    check_int(fail, width, "width")
    if width < 1 or width > MAX_SIGN_WIDTH:
        fail("out_of_range:width")
    check_int(fail, x, "x")
    if x < 0 or x >= (1 << width):
        fail("out_of_range:x")
    if x >= (1 << (width - 1)):
        return x - (1 << width)
    return x


def next_same_popcount(n):
    """Smallest integer above n with the same popcount.

    n is an int from 1 to MAX_NSPC_N; zero refuses because no
    positive integer has popcount zero. The result is not
    bounded by MAX_NSPC_N; for n at the cap it stays below
    2**61. Uses the standard two's-complement bit trick. O(1)
    big-int work."""
    fail = make_fail("next_same_popcount")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_NSPC_N:
        fail("out_of_range:n")
    low = n & -n
    raised = n + low
    return (((raised ^ n) >> 2) // low) | raised


_RANKS = frozenset(
    ["2", "3", "4", "5", "6", "7", "8", "9", "10",
     "j", "q", "k", "a"])


def blackjack_hand_value(cards):
    """Best total of a blackjack hand.

    cards holds 1..MAX_BLACKJACK_CARDS rank strings: "2"
    through "10" at face value, "j", "q" and "k" worth ten,
    and "a" worth eleven or one. Every ace starts at eleven
    and downgrades to one while the total exceeds twenty-one.
    Returns the resulting int total: the highest total not
    over twenty-one when one exists, otherwise the smallest
    total (the bust value). An estimated O(cards) work."""
    fail = make_fail("blackjack_hand_value")
    check_items(fail, cards, "cards")
    if not cards:
        fail("empty:cards")
    if len(cards) > MAX_BLACKJACK_CARDS:
        fail("too_many:cards")
    aces = 0
    total = 0
    for i, card in enumerate(cards):
        check_str(fail, card, "cards[%d]" % i)
        if card not in _RANKS:
            fail("bad_rank:cards[%d]" % i)
        if card == "a":
            aces += 1
            total += 11
        elif card in ("j", "q", "k"):
            total += 10
        else:
            total += int(card)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total
