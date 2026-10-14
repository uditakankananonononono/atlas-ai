"""P235 concepts, batch 15 (strings/parsing, 141-150). Offline, stdlib only."""
from __future__ import annotations

import base64
import binascii

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_items, check_str, make_fail)

_MAX_TEXT = MAX_ITEMS
MAX_B64_BYTES = 7_500
_MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.",
}


def _capped_text(fail, text, name="text"):
    check_str(fail, text, name)
    if len(text) > _MAX_TEXT:
        fail("too_many:text")
    return text


def csv_row_split(text):
    fail = make_fail("csv_row_split")
    _capped_text(fail, text, "csv")
    fields = []
    field = []
    i = 0
    n = len(text)
    in_quotes = False
    quoted_field = False
    while i < n:
        ch = text[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                field.append(ch)
        elif ch == '"':
            if field or quoted_field:
                fail("bad_value:csv")
            in_quotes = True
            quoted_field = True
        elif ch == ",":
            fields.append("".join(field))
            field = []
            quoted_field = False
        else:
            if quoted_field:
                fail("bad_value:csv")
            field.append(ch)
        i += 1
    if in_quotes:
        fail("bad_value:csv")
    fields.append("".join(field))
    return fields


def snake_to_camel(text):
    fail = make_fail("snake_to_camel")
    _capped_text(fail, text)
    if not text:
        fail("bad_value:text")
    parts = text.split("_")
    if any(not p for p in parts):
        fail("bad_value:text")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def initials_of(text):
    fail = make_fail("initials_of")
    _capped_text(fail, text)
    words = text.split()
    if not words:
        fail("bad_value:text")
    return "".join(w[0].upper() for w in words)


def longest_word(text):
    fail = make_fail("longest_word")
    _capped_text(fail, text)
    best = ""
    for word in text.split():
        if len(word) > len(best):
            best = word
    return best


def word_count(text):
    fail = make_fail("word_count")
    _capped_text(fail, text)
    return len(text.split())


def strip_html_tags(text):
    """Remove angle-bracket spans. This is NOT an HTML sanitizer: it
    matches '<' to the next '>' and drops the span, nothing more."""
    fail = make_fail("strip_html_tags")
    _capped_text(fail, text, "html")
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "<":
            close = text.find(">", i + 1)
            if close == -1:
                fail("bad_value:html")
            i = close + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def url_query_parse(text):
    """Split a query string into key/value pairs. Keys and values are
    literal: no percent-decoding and no plus-as-space decoding."""
    fail = make_fail("url_query_parse")
    _capped_text(fail, text, "query")
    if not text:
        return {}
    pairs = text.split("&")
    if len(pairs) > MAX_ITEMS:
        fail("too_many:pairs")
    out = {}
    for seg in pairs:
        if "=" not in seg:
            fail("bad_value:query")
        key, _, value = seg.partition("=")
        if not key:
            fail("bad_value:query")
        if key in out:
            fail("duplicate:key")
        out[key] = value
    return out


def base64_encode_text(text):
    fail = make_fail("base64_encode_text")
    check_str(fail, text, "text")
    raw = text.encode("utf-8")
    if len(raw) > MAX_B64_BYTES:
        fail("too_many:bytes")
    return base64.b64encode(raw).decode("ascii")


def base64_decode_text(text):
    fail = make_fail("base64_decode_text")
    _capped_text(fail, text, "b64")
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
        return raw.decode("utf-8")
    except (UnicodeEncodeError, binascii.Error, ValueError):
        fail("bad_value:b64")


def morse_encode(text):
    fail = make_fail("morse_encode")
    _capped_text(fail, text)
    if not text:
        fail("bad_value:text")
    words = text.upper().split(" ")
    out = []
    for word in words:
        letters = []
        for ch in word:
            if ch not in _MORSE:
                fail("bad_value:text")
            letters.append(_MORSE[ch])
        out.append(" ".join(letters))
    return " / ".join(out)
