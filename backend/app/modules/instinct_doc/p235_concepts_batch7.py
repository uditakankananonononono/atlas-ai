"""P235 concepts, batch 7 (strings/encoding, 61-70). Offline, stdlib only."""
from __future__ import annotations

import re

from app.modules.instinct_doc.p235_concepts_registry import (
    check_int, check_str, make_fail)

_MAX_TEXT = 100_000  # explicit literal, pinned by test
_MAX_INDENT = 1_024
_MAX_OUTPUT = 200_000


def _text(fail, value, name="text"):
    check_str(fail, value, name)
    if len(value) > _MAX_TEXT:
        fail("too_many:" + name)
    return value


def utf8_byte_length(text):
    fail = make_fail("utf8_byte_length")
    return len(_text(fail, text).encode("utf-8"))


def ascii_only_check(text):
    fail = make_fail("ascii_only_check")
    return _text(fail, text).isascii()


def line_count(text):
    fail = make_fail("line_count")
    text = _text(fail, text)
    if text == "":
        return 0
    return len(text.splitlines())


def word_wrap_width(text, width):
    fail = make_fail("word_wrap_width")
    text = _text(fail, text)
    check_int(fail, width, "width")
    if width < 1:
        fail("bad_value:width")
    lines = []
    current = ""
    for word in text.split():
        if len(word) > width:
            fail("bad_value:word_exceeds_width:%s" % word[:32])
        candidate = (current + " " + word).strip()
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def indent_lines(text, spaces):
    fail = make_fail("indent_lines")
    text = _text(fail, text)
    check_int(fail, spaces, "spaces")
    if spaces < 0:
        fail("bad_value:spaces")
    if spaces > _MAX_INDENT:
        fail("too_many:spaces")
    if text == "":
        return ""
    if len(text) + (text.count("\n") + 1) * spaces > _MAX_OUTPUT:
        fail("too_many:output")
    pad = " " * spaces
    return "\n".join(pad + line for line in text.split("\n"))


def dedent_block(text):
    fail = make_fail("dedent_block")
    text = _text(fail, text)
    lines = text.split("\n")
    indents = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    if not indents:
        return text
    cut = min(indents)
    return "\n".join(line[cut:] if line.strip() else line for line in lines)


def reverse_words(text):
    fail = make_fail("reverse_words")
    return " ".join(reversed(_text(fail, text).split()))


def swap_case(text):
    fail = make_fail("swap_case")
    text = _text(fail, text)
    return "".join(ch.lower() if ch.isupper() else ch.upper() for ch in text)


def count_substring_overlapping(text, needle):
    fail = make_fail("count_substring_overlapping")
    text = _text(fail, text)
    check_str(fail, needle, "needle")
    if needle == "":
        fail("empty:needle")
    return sum(1 for i in range(len(text) - len(needle) + 1)
               if text[i:i + len(needle)] == needle)


_ROMAN_VALUES = (("M", 1000), ("CM", 900), ("D", 500), ("CD", 400),
                 ("C", 100), ("XC", 90), ("L", 50), ("XL", 40),
                 ("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1))
_ROMAN_RE = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")


def roman_numeral_parse(numeral):
    fail = make_fail("roman_numeral_parse")
    check_str(fail, numeral, "numeral")
    if not numeral or not _ROMAN_RE.fullmatch(numeral):
        fail("bad_value:numeral")
    total = 0
    rest = numeral
    for token, value in _ROMAN_VALUES:
        while rest.startswith(token):
            total += value
            rest = rest[len(token):]
    return total
