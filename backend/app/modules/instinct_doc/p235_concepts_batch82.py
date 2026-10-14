"""P235 concepts batch 82: codecs, encodings and validators.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
"""

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TEXT = 10_000
MAX_WINDOW = 4_096

_UNRESERVED = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
               "abcdefghijklmnopqrstuvwxyz"
               "0123456789-._~")
_HEX = "0123456789ABCDEF"


def iban_check(code):
    """True when a compact IBAN passes the ISO 13616 mod-97 check.

    The code must be 15..34 characters: two uppercase letters, two
    digits, then an alphanumeric BBAN. Spaces are refused, not
    stripped."""
    fail = make_fail("iban_check")
    check_str(fail, code, "code")
    if not code:
        fail("bad_value:code")
    if len(code) < 15 or len(code) > 34:
        fail("bad_length:code")
    if not (code[0].isascii() and code[0].isalpha()
            and code[1].isascii() and code[1].isalpha()):
        fail("bad_value:country")
    if not code[0].isupper() or not code[1].isupper():
        fail("bad_value:country")
    if not (code[2].isascii() and code[2].isdigit()
            and code[3].isascii() and code[3].isdigit()):
        fail("bad_value:checkdigits")
    for c in code[4:]:
        if not (c.isascii() and (c.isdigit() or c.isupper())):
            fail("bad_char:bban")
    digits = []
    for c in code[4:] + code[:4]:
        if c.isdigit():
            digits.append(c)
        else:
            digits.append(str(ord(c) - 55))
    rem = 0
    for d in "".join(digits):
        rem = (rem * 10 + ord(d) - 48) % 97
    return rem == 1


def percent_encode(text):
    """RFC 3986 percent-encoding: unreserved characters pass
    through, everything else is encoded as its UTF-8 bytes."""
    fail = make_fail("percent_encode")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    out = []
    for c in text:
        if c in _UNRESERVED:
            out.append(c)
        else:
            for byte in c.encode("utf-8"):
                out.append("%" + _HEX[byte >> 4] + _HEX[byte & 15])
    return "".join(out)


def percent_decode(text):
    """Strict inverse of RFC 3986 percent-encoding.

    Every '%' must be followed by two hexadecimal digits, and the
    decoded bytes must be valid UTF-8."""
    fail = make_fail("percent_decode")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > 3 * MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if not (" " <= c <= "~"):
            fail("bad_char:text")
    data = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "%":
            if i + 2 >= len(text) or text[i + 1] not in _HEX + "abcdef" \
                    or text[i + 2] not in _HEX + "abcdef":
                fail("bad_value:percent")
            data.append(int(text[i + 1:i + 3], 16))
            i += 3
        else:
            data.extend(text[i].encode("ascii"))
            i += 1
    try:
        return bytes(data).decode("utf-8", "strict")
    except UnicodeDecodeError:
        fail("bad_value:utf8")


def _qp_check_text(fail, text):
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if c in ("\t", "\n"):
            continue
        if not (" " <= c <= "~"):
            fail("bad_char:text")


def quoted_printable_encode(text):
    """MIME quoted-printable encoding of ASCII text.

    Printable characters pass through except '=', which becomes
    '=3D'; spaces and tabs are encoded only at the end of a line;
    newlines pass through. No soft line wrapping is applied."""
    fail = make_fail("quoted_printable_encode")
    _qp_check_text(fail, text)
    out = []
    lines = text.split("\n")
    for li, line in enumerate(lines):
        for i, c in enumerate(line):
            trailing = i == len(line) - 1
            if c == "=":
                out.append("=3D")
            elif c in " \t" and trailing:
                out.append("=20" if c == " " else "=09")
            elif "!" <= c <= "~" and c != "=":
                out.append(c)
            elif c in " \t":
                out.append(c)
            else:
                out.append("=" + _HEX[ord(c) >> 4] + _HEX[ord(c) & 15])
        if li < len(lines) - 1:
            out.append("\n")
    return "".join(out)


def quoted_printable_decode(text):
    """Strict MIME quoted-printable decoding back to ASCII text.

    '=XX' sequences decode bytes (hex letters uppercase only);
    '=<newline>' and '=<CR><newline>' are soft breaks; any other
    use of '=' is a refusal. Decoded bytes must stay ASCII."""
    fail = make_fail("quoted_printable_decode")
    _qp_check_text(fail, text.replace("\r\n", "\n"))
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c != "=":
            out.append(c)
            i += 1
            continue
        if text.startswith("=\r\n", i):
            i += 3
            continue
        if text.startswith("=\n", i):
            i += 2
            continue
        if (i + 2 < len(text) and text[i + 1] in _HEX
                and text[i + 2] in _HEX):
            value = int(text[i + 1:i + 3], 16)
            if value > 126 or (value < 32 and value != 9):
                fail("bad_value:ascii")
            out.append(chr(value))
            i += 3
            continue
        fail("bad_value:escape")
    return "".join(out)


def html_escape_text(text):
    """Escapes &, <, >, double and single quotes as HTML entities."""
    fail = make_fail("html_escape_text")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if c in "\t\n\r" or " " <= c <= "~":
            continue
        fail("bad_char:text")
    out = []
    for c in text:
        if c == "&":
            out.append("&amp;")
        elif c == "<":
            out.append("&lt;")
        elif c == ">":
            out.append("&gt;")
        elif c == '"':
            out.append("&quot;")
        elif c == "'":
            out.append("&#x27;")
        else:
            out.append(c)
    return "".join(out)


def html_unescape_text(text):
    """Strictly decodes HTML entities back to ASCII text.

    Handles the five named entities plus &#...; and &#x...;
    numeric references. A malformed, out-of-range, surrogate, or
    non-ASCII-producing reference is a refusal."""
    fail = make_fail("html_unescape_text")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > 6 * MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if c in "\t\n\r" or " " <= c <= "~":
            continue
        fail("bad_char:text")
    named = {"&amp;": "&", "&lt;": "<", "&gt;": ">",
             "&quot;": '"', "&#x27;": "'", "&#39;": "'"}
    out = []
    i = 0
    while i < len(text):
        if text[i] != "&":
            out.append(text[i])
            i += 1
            continue
        end = text.find(";", i)
        if end == -1 or end - i > 10:
            fail("bad_value:entity")
        entity = text[i:end + 1]
        if entity in named:
            out.append(named[entity])
        elif entity.startswith("&#x") and len(entity) > 4:
            digits = entity[3:-1]
            if any(c not in _HEX + "abcdef" for c in digits):
                fail("bad_value:entity")
            value = int(digits, 16)
            if value > 126 or (value < 32 and value not in (9, 10, 13)):
                fail("bad_value:nonascii")
            out.append(chr(value))
        elif entity.startswith("&#") and len(entity) > 3:
            digits = entity[2:-1]
            if any(c not in "0123456789" for c in digits):
                fail("bad_value:entity")
            value = int(digits)
            if value > 126 or (value < 32 and value not in (9, 10, 13)):
                fail("bad_value:nonascii")
            out.append(chr(value))
        else:
            fail("bad_value:entity")
        i = end + 1
    return "".join(out)


def utf8_encode_bytes(text):
    """Encodes text as its UTF-8 byte sequence, returned as a list
    of ints. Lone surrogates are refused."""
    fail = make_fail("utf8_encode_bytes")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if "\ud800" <= c <= "\udfff":
            fail("bad_value:surrogate")
    return list(text.encode("utf-8"))


def utf8_decode_bytes(data):
    """Strictly decodes a UTF-8 byte sequence given as a list of
    ints. Truncated sequences, stray continuation bytes, overlong
    forms, surrogates, and values above U+10FFFF are all refusals."""
    fail = make_fail("utf8_decode_bytes")
    check_items(fail, data, "data")
    if not data:
        fail("empty:data")
    for i, v in enumerate(data):
        check_int(fail, v, "data[%d]" % i)
        if v < 0 or v > 255:
            fail("out_of_range:data[%d]" % i)
    try:
        return bytes(data).decode("utf-8", "strict")
    except UnicodeDecodeError:
        fail("bad_value:utf8")


def lz77_encode_naive(text):
    """Greedy LZ77 compression to (offset, length, next) triplets.

    At each position the longest match inside the already emitted
    text (up to a 4096-byte window, overlap allowed) is taken; ties
    prefer the smallest offset. Each triplet is [offset, length,
    next_char]; a position with no match emits [0, 0, char]."""
    fail = make_fail("lz77_encode_naive")
    check_str(fail, text, "text")
    if not text:
        fail("empty:text")
    if len(text) > MAX_TEXT:
        fail("too_long:text")
    for c in text:
        if not (" " <= c <= "~"):
            fail("bad_char:text")
    out = []
    pos = 0
    while pos < len(text):
        best_off = 0
        best_len = 0
        start = max(0, pos - MAX_WINDOW)
        for cand in range(pos - 1, start - 1, -1):
            length = 0
            while (pos + length < len(text)
                    and text[cand + length] == text[pos + length]):
                length += 1
            if length > best_len:
                best_len = length
                best_off = pos - cand
        if pos + best_len < len(text):
            out.append([best_off, best_len, text[pos + best_len]])
            pos += best_len + 1
        else:
            out.append([best_off, best_len, ""])
            pos += best_len
    return out
