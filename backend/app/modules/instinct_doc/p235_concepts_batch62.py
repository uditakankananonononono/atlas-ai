"""P235 concepts batch 62: string transforms and checks.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. ASCII only.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TEXT = 10_000
MAX_WORD = 100

_VOWELS = set("aeiouAEIOU")
_ROWS = [set("qwertyuiop"), set("asdfghjkl"), set("zxcvbnm")]


def _ascii_text(fail, text, name="text", allow_empty=False):
    check_str(fail, text, name)
    if not text and not allow_empty:
        fail("empty:%s" % name)
    if len(text) > MAX_TEXT:
        fail("too_many:%s" % name)
    if not text.isascii():
        fail("bad_value:%s" % name)


def is_pangram_ascii(text):
    """Whether ASCII text contains every letter a-z at least once.

    Case-insensitive; non-letters are ignored.
    """
    fail = make_fail("is_pangram_ascii")
    _ascii_text(fail, text)
    seen = set()
    for ch in text.lower():
        if "a" <= ch <= "z":
            seen.add(ch)
    return len(seen) == 26


def reverse_vowels_of_string(text):
    """ASCII text with the vowel characters swapped mirror-wise."""
    fail = make_fail("reverse_vowels_of_string")
    _ascii_text(fail, text)
    chars = list(text)
    i = 0
    j = len(chars) - 1
    while i < j:
        if chars[i] not in _VOWELS:
            i += 1
        elif chars[j] not in _VOWELS:
            j -= 1
        else:
            chars[i], chars[j] = chars[j], chars[i]
            i += 1
            j -= 1
    return "".join(chars)


def detect_capital_use(word):
    """Whether a word's casing is valid.

    Valid means all uppercase, all lowercase, or a single leading
    uppercase followed by lowercase.
    """
    fail = make_fail("detect_capital_use")
    _ascii_text(fail, word, "word")
    if not word.isalpha():
        fail("bad_value:word")
    if word.isupper() or word.islower():
        return True
    return word[0].isupper() and word[1:].islower()


def gcd_of_strings(a, b):
    """Longest string that concatenated copies of tile both a and b.

    Returns "" when no such string exists.
    """
    fail = make_fail("gcd_of_strings")
    _ascii_text(fail, a, "a")
    _ascii_text(fail, b, "b")
    if a + b != b + a:
        return ""
    from math import gcd
    return a[:gcd(len(a), len(b))]


def longest_substring_k_distinct(text, k):
    """Length of the longest window of ASCII text with <= k distinct.

    k must be at least 1.
    """
    fail = make_fail("longest_substring_k_distinct")
    _ascii_text(fail, text, allow_empty=True)
    check_int(fail, k, "k")
    if k < 1:
        fail("bad_value:k")
    counts = {}
    left = 0
    best = 0
    for right, ch in enumerate(text):
        counts[ch] = counts.get(ch, 0) + 1
        while len(counts) > k:
            counts[text[left]] -= 1
            if counts[text[left]] == 0:
                del counts[text[left]]
            left += 1
        if right - left + 1 > best:
            best = right - left + 1
    return best


def decode_ways_count(digits):
    """Number of A=1..Z=26 decodings of a digit string.

    A leading zero, or any zero that cannot pair, gives 0.
    """
    fail = make_fail("decode_ways_count")
    _ascii_text(fail, digits, "digits")
    if not digits.isascii() or not all("0" <= c <= "9"
                                       for c in digits):
        fail("bad_value:digits")
    prev2 = 1
    prev1 = 0 if digits[0] == "0" else 1
    for i in range(1, len(digits)):
        cur = 0
        if digits[i] != "0":
            cur += prev1
        if digits[i - 1] != "0" and int(digits[i - 1:i + 1]) <= 26:
            cur += prev2
        prev2, prev1 = prev1, cur
    return prev1


def goat_latin_words(text):
    """Goat-latin render of space-separated ASCII words.

    A vowel-initial word gains "ma"; any other word moves its first
    letter to the end and gains "ma". The i-th word (1-based) then
    gains i copies of "a".
    """
    fail = make_fail("goat_latin_words")
    _ascii_text(fail, text)
    words = text.split(" ")
    for i, w in enumerate(words):
        if not w or not w.isalpha():
            fail("bad_value:words[%d]" % i)
    out = []
    for i, w in enumerate(words):
        if w[0] in _VOWELS:
            stem = w
        else:
            stem = w[1:] + w[0]
        out.append(stem + "ma" + "a" * (i + 1))
    return " ".join(out)


def license_key_format(key, k):
    """Uppercase alphanumerics of key regrouped into k-wide groups.

    Dashes in the input are ignored; the first group may be
    shorter. Refuses input with no alphanumeric characters.
    """
    fail = make_fail("license_key_format")
    _ascii_text(fail, key, "key")
    check_int(fail, k, "k")
    if k < 1:
        fail("bad_value:k")
    chars = []
    for i, ch in enumerate(key):
        if ch == "-":
            continue
        if not ch.isalnum():
            fail("bad_value:key[%d]" % i)
        chars.append(ch.upper())
    if not chars:
        fail("empty:key")
    first = len(chars) % k
    groups = []
    if first:
        groups.append("".join(chars[:first]))
    for i in range(first, len(chars), k):
        groups.append("".join(chars[i:i + k]))
    return "-".join(groups)


def keyboard_row_words(words):
    """Words typeable on a single QWERTY letter row, order kept.

    Refuses words longer than MAX_WORD (100) before any scanning.
    """
    fail = make_fail("keyboard_row_words")
    check_items(fail, words, "words")
    if not words:
        fail("empty:words")
    if len(words) > MAX_ITEMS:
        fail("too_many:words")
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if len(w) > MAX_WORD:
            fail("too_long:words[%d]" % i)
        if not w or not w.isascii() or not w.isalpha():
            fail("bad_value:words[%d]" % i)
    out = []
    for w in words:
        letters = set(w.lower())
        if any(letters <= row for row in _ROWS):
            out.append(w)
    return out


def jewels_and_stones_count(jewels, stones):
    """How many characters of stones also appear in jewels.

    Matching is case-sensitive; both must be non-empty ASCII.
    """
    fail = make_fail("jewels_and_stones_count")
    _ascii_text(fail, jewels, "jewels")
    _ascii_text(fail, stones, "stones")
    kinds = set(jewels)
    return sum(1 for ch in stones if ch in kinds)
