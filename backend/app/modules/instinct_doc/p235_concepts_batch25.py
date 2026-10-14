"""P235 concepts batch 25 (concepts 241-250, format validators/transforms) -
ten new small deterministic format concepts. 241-250 of the doc's 1000
(anchor P235|L184). ASCII-strict parsing; inputs bounded; oracles pinned.
"""
from __future__ import annotations

import re

MAX_WORD_LEN = 1_000

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_str, make_fail

_IPV4 = re.compile(r"^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\."
                   r"([0-9]{1,3})$")
_MAC = re.compile(r"^[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}(?:\1[0-9A-Fa-f]"
                  r"{2}){4}$")
_UUID = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
                   r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")
_HEX_COLOR = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
_DIGITS = re.compile(r"^[0-9]+$")


def _checked(fail, text, name):
    check_str(fail, text, name)
    if len(text) > MAX_ITEMS:
        fail("too_many:" + name)
    if not text.isascii():
        fail("bad_value:" + name)
    return text


def ipv4_check(text):
    """Dotted-quad shape: four octets 0-255, no leading zeros."""
    fail = make_fail("ipv4_check")
    _checked(fail, text, "text")
    m = _IPV4.fullmatch(text)
    if not m:
        return False
    for group in m.groups():
        if len(group) > 1 and group[0] == "0":
            return False
        if int(group) > 255:
            return False
    return True


def mac_address_check(text):
    fail = make_fail("mac_address_check")
    _checked(fail, text, "text")
    return _MAC.fullmatch(text) is not None


def uuid_shape_check(text):
    fail = make_fail("uuid_shape_check")
    _checked(fail, text, "text")
    return _UUID.fullmatch(text) is not None


def hex_color_check(text):
    fail = make_fail("hex_color_check")
    _checked(fail, text, "text")
    return _HEX_COLOR.fullmatch(text) is not None


def email_shape_check(text):
    """Minimal honest shape: one @, nonempty local part, dotted domain.
    Not a deliverability check."""
    fail = make_fail("email_shape_check")
    _checked(fail, text, "text")
    if text.count("@") != 1:
        return False
    local, _, domain = text.partition("@")
    if not local or not domain:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False
    return _EMAIL.fullmatch(text) is not None


def isbn13_check(text):
    fail = make_fail("isbn13_check")
    _checked(fail, text, "text")
    if not _DIGITS.fullmatch(text) or len(text) != 13:
        return False
    total = sum((1 if i % 2 == 0 else 3) * (ord(ch) - 48)
                for i, ch in enumerate(text))
    return total % 10 == 0


def mask_digits_keep_last(text, keep):
    """Replace every digit with * except the last `keep` digits of the
    whole text; non-digit characters pass through untouched."""
    fail = make_fail("mask_digits_keep_last")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    check_int(fail, keep, "keep")
    if keep < 0:
        fail("bad_value:keep")
    digits = sum(1 for ch in text if ch.isascii() and ch.isdigit())
    seen = 0
    out = []
    for ch in text:
        if ch.isascii() and ch.isdigit():
            seen += 1
            out.append(ch if digits - seen < keep else "*")
        else:
            out.append(ch)
    return "".join(out)


def redact_words(text, words):
    """Replace whole whitespace-separated tokens equal to a listed word
    (case-sensitive) with [REDACTED]. Whitespace runs (spaces, tabs,
    newlines) are preserved exactly; each listed word is capped."""
    fail = make_fail("redact_words")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    if type(words) is not list or len(words) > 1_000:
        fail("bad_value:words")
    targets = set()
    for i, w in enumerate(words):
        check_str(fail, w, "words[%d]" % i)
        if not w or w != w.strip() or any(c.isspace() for c in w):
            fail("bad_value:words[%d]" % i)
        if len(w) > MAX_WORD_LEN:
            fail("too_big:words[%d]" % i)
        targets.add(w)
    parts = re.split(r"(\s+)", text)
    return "".join("[REDACTED]" if tok in targets else tok
                   for tok in parts)


def collapse_whitespace_runs(text):
    """Collapse every run of whitespace to a single space and strip the
    ends; equivalent to " ".join(text.split())."""
    fail = make_fail("collapse_whitespace_runs")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    return " ".join(text.split())


def palindrome_sentence_check(text):
    """Case-insensitive palindrome over ASCII letters and digits only;
    all other characters are ignored."""
    fail = make_fail("palindrome_sentence_check")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    kept = [ch.lower() for ch in text
            if ch.isascii() and (ch.isalpha() or ch.isdigit())]
    return kept == kept[::-1]
