"""P235 concepts, batch 41 (text transforms, conversions, 401-410).

Offline, stdlib only. Exact arithmetic; caps refuse before work.
"""
from __future__ import annotations

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TEXT = 10_000

MAX_VERSION_PARTS = 100
MAX_VERSION_DIGITS = 18
MAX_WORD_LEN = 100
MAX_BASE_VALUE_LEN = 1_000
MAX_DENOMINATOR = 100_000
MAX_SAY_N = 30
MAX_WORDS = 10_000

_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def compare_version_strings(a, b):
    """Compare dotted numeric versions; -1, 0, or 1."""
    fail = make_fail("compare_version_strings")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_TEXT or len(b) > MAX_TEXT:
        fail("too_many:input")

    def parts(v, name):
        if v == "":
            fail("empty:%s" % name)
        raw = v.split(".")
        if len(raw) > MAX_VERSION_PARTS:
            fail("too_many:%s" % name)
        out = []
        for p in raw:
            if p == "" or not p.isascii() or not p.isdigit():
                fail("bad_value:%s" % name)
            if len(p) > MAX_VERSION_DIGITS:
                fail("too_many:%s:component" % name)
            out.append(int(p))
        return out

    pa = parts(a, "a")
    pb = parts(b, "b")
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def simplify_path_unix(path):
    """Normalize an absolute unix path; '..' pops, '.' and '' drop."""
    fail = make_fail("simplify_path_unix")
    check_str(fail, path, "path")
    if not path.startswith("/"):
        fail("bad_value:relative")
    if len(path) > MAX_TEXT:
        fail("too_many:path")
    stack = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
            continue
        stack.append(part)
    return "/" + "/".join(stack)


def min_window_substring(text, chars):
    """Smallest window of text holding every char of chars; '' if none."""
    fail = make_fail("min_window_substring")
    check_str(fail, text, "text")
    check_str(fail, chars, "chars")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    if len(chars) > MAX_TEXT:
        fail("too_many:chars")
    if chars == "":
        fail("empty:chars")
    if len(chars) > len(text):
        return ""
    need = {}
    for ch in chars:
        need[ch] = need.get(ch, 0) + 1
    missing = len(chars)
    best = None
    left = 0
    for right, ch in enumerate(text):
        if ch in need:
            need[ch] -= 1
            if need[ch] >= 0:
                missing -= 1
        while missing == 0:
            if best is None or right - left + 1 < best[1] - best[0]:
                best = (left, right + 1)
            drop = text[left]
            if drop in need:
                if need[drop] >= 0:
                    missing += 1
                need[drop] += 1
            left += 1
    if best is None:
        return ""
    return text[best[0]:best[1]]


def group_anagrams_list(words):
    """Groups of exact anagrams, ordered by first appearance."""
    fail = make_fail("group_anagrams_list")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_WORDS:
        fail("too_many:words")
    groups = {}
    order = []
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if w == "":
            fail("empty:words[%d]" % i)
        if len(w) > MAX_WORD_LEN:
            fail("too_many:words[%d]" % i)
        key = "".join(sorted(w))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(w)
    return [groups[k] for k in order]


def largest_number_concat(values):
    """Largest concatenation of the nonnegative integers, as a string."""
    fail = make_fail("largest_number_concat")
    check_items(fail, values, "values")
    if not values:
        fail("empty:values")
    if len(values) > MAX_ITEMS:
        fail("too_many:values")
    strs = []
    for i, v in enumerate(values):
        check_int(fail, v, "values[%d]" % i)
        if v < 0:
            fail("bad_value:values[%d]" % i)
        strs.append(str(v))
    from functools import cmp_to_key
    strs.sort(key=cmp_to_key(lambda x, y: -1 if x + y > y + x
                             else (1 if x + y < y + x else 0)))
    out = "".join(strs)
    if out.startswith("0"):
        return "0"
    return out


def base_convert_digits(value, from_base, to_base):
    """Convert a digit string between bases 2..36 (0-9a-z charset)."""
    fail = make_fail("base_convert_digits")
    check_str(fail, value, "value")
    check_int(fail, from_base, "from_base")
    check_int(fail, to_base, "to_base")
    if not (2 <= from_base <= 36) or not (2 <= to_base <= 36):
        fail("bad_value:base")
    if value == "":
        fail("empty:value")
    if len(value) > MAX_BASE_VALUE_LEN:
        fail("too_many:value")
    if not value.isascii():
        fail("bad_value:value")
    text = value.lower()
    n = 0
    for pos, ch in enumerate(text):
        d = _DIGITS.find(ch)
        if d < 0 or d >= from_base:
            fail("bad_value:value[%d]" % pos)
        n = n * from_base + d
    if n == 0:
        return "0"
    out = []
    while n:
        out.append(_DIGITS[n % to_base])
        n //= to_base
    return "".join(reversed(out))


def fraction_decimal_cycle(numerator, denominator):
    """Exact decimal expansion; the repeating part in parentheses."""
    fail = make_fail("fraction_decimal_cycle")
    check_int(fail, numerator, "numerator")
    check_int(fail, denominator, "denominator")
    if numerator < 0:
        fail("bad_value:numerator")
    if denominator < 1 or denominator > MAX_DENOMINATOR:
        fail("bad_value:denominator")
    whole = numerator // denominator
    rem = numerator % denominator
    if rem == 0:
        return str(whole)
    seen = {}
    digits = []
    pos = 0
    while rem != 0:
        if rem in seen:
            start = seen[rem]
            head = "".join(digits[:start])
            cycle = "".join(digits[start:])
            return "%d.%s(%s)" % (whole, head, cycle)
        seen[rem] = pos
        pos += 1
        rem *= 10
        digits.append(str(rem // denominator))
        rem %= denominator
    return "%d.%s" % (whole, "".join(digits))


def count_and_say_term(n):
    """The n-th term of the look-and-say sequence, 1-indexed."""
    fail = make_fail("count_and_say_term")
    check_int(fail, n, "n")
    if n < 1 or n > MAX_SAY_N:
        fail("bad_value:n")
    term = "1"
    for _ in range(n - 1):
        out = []
        i = 0
        while i < len(term):
            j = i
            while j < len(term) and term[j] == term[i]:
                j += 1
            out.append(str(j - i))
            out.append(term[i])
            i = j
        term = "".join(out)
    return term


def capitalize_sentences(text):
    """Uppercase the first ASCII letter of each sentence.

    A sentence starts at the text start and after every ., !, or ?.
    Leading non-letters (quotes, digits, brackets, whitespace) are
    skipped: the search ends at the first letter, which is uppercased
    when ASCII, or at the next terminator.
    """
    fail = make_fail("capitalize_sentences")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    out = []
    searching = True
    for ch in text:
        if searching:
            if ch.isascii() and ch.isalpha():
                out.append(ch.upper())
                searching = False
                continue
            if ch.isalpha():
                # a non-ASCII letter ends the search but has no
                # ASCII uppercase
                out.append(ch)
                searching = False
                continue
            out.append(ch)
            if ch in ".!?":
                searching = True
            continue
        out.append(ch)
        if ch in ".!?":
            searching = True
    return "".join(out)



def isomorphic_strings_check(a, b):
    """True when a maps to b by a consistent char bijection."""
    fail = make_fail("isomorphic_strings_check")
    check_str(fail, a, "a")
    check_str(fail, b, "b")
    if len(a) > MAX_TEXT or len(b) > MAX_TEXT:
        fail("too_many:text")
    if len(a) != len(b):
        return False
    fwd = {}
    back = {}
    for ca, cb in zip(a, b):
        if ca in fwd:
            if fwd[ca] != cb:
                return False
        else:
            if cb in back:
                return False
            fwd[ca] = cb
            back[cb] = ca
    return True
