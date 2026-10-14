"""P235 concepts, batch 3 (text). Offline, stdlib only."""
from __future__ import annotations

import re
import unicodedata

from app.modules.instinct_doc.p235_concepts_registry import (
    check_int, check_items, check_str, make_fail)

_MAX_TEXT = 100_000


def _text(fail, value, name):
    check_str(fail, value, name)
    if len(value) > _MAX_TEXT:
        fail("too_many:" + name)
    return value


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CAMEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


def token_histogram(text):
    fail = make_fail("token_histogram")
    _text(fail, text, "text")
    counts = {}
    for tok in _TOKEN_RE.findall(text.lower()):
        counts[tok] = counts.get(tok, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def longest_common_prefix(strings):
    fail = make_fail("longest_common_prefix")
    check_items(fail, strings, "strings")
    if not strings:
        fail("empty:strings")
    for i, s in enumerate(strings):
        _text(fail, s, "strings[%d]" % i)
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
    return prefix


def palindrome_check(text):
    fail = make_fail("palindrome_check")
    _text(fail, text, "text")
    cleaned = [ch.lower() for ch in text if ch.isalnum()]
    return cleaned == cleaned[::-1]


def anagram_check_casefold(a, b):
    fail = make_fail("anagram_check_casefold")
    _text(fail, a, "a")
    _text(fail, b, "b")
    return sorted(a.casefold()) == sorted(b.casefold())


def camel_to_snake(name):
    fail = make_fail("camel_to_snake")
    _text(fail, name, "name")
    if not _CAMEL_RE.fullmatch(name):
        fail("bad_value:name")
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def truncate_words(text, max_words):
    fail = make_fail("truncate_words")
    _text(fail, text, "text")
    check_int(fail, max_words, "max_words")
    if max_words < 1:
        fail("bad_value:max_words")
    words = text.split()
    return " ".join(words[:max_words])


def strip_diacritics(text):
    fail = make_fail("strip_diacritics")
    _text(fail, text, "text")
    return "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))


def sentence_split_naive(text):
    fail = make_fail("sentence_split_naive")
    _text(fail, text, "text")
    parts = re.split(r"[.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def title_case_small_words(text, small_words):
    fail = make_fail("title_case_small_words")
    _text(fail, text, "text")
    check_items(fail, small_words, "small_words")
    smalls = set()
    for i, w in enumerate(small_words):
        check_str(fail, w, "small_words[%d]" % i)
        if not w.strip():
            fail("empty:small_words[%d]" % i)
        smalls.add(w.strip().lower())
    words = text.split()
    out = []
    for i, w in enumerate(words):
        if i != 0 and i != len(words) - 1 and w.lower() in smalls:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def csv_field_escape(field):
    fail = make_fail("csv_field_escape")
    _text(fail, field, "field")
    if any(c in field for c in (",", '"', "\n", "\r")):
        return '"' + field.replace('"', '""') + '"'
    return field
