"""P235 concepts, batch 37 (checksums, encodings, DP II, 361-370).

Offline, stdlib only. Exact integer arithmetic; caps refuse before work.
"""
from __future__ import annotations

import re

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_TEXT = 10_000
MAX_MATRIX_DIMS = 200
MAX_KNAPSACK_ITEMS = 100
MAX_CAPACITY = 10_000
MAX_ROD = 500

_JSON_NUMBER = re.compile(
    r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_B32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def _check_text(fail, text, name="text", cap=MAX_TEXT):
    check_str(fail, text, name)
    if len(text) > cap:
        fail("too_many:%s" % name)
    if not text.isascii():
        fail("bad_value:%s:non_ascii" % name)


def adler32_sum(text):
    fail = make_fail("adler32_sum")
    _check_text(fail, text)
    a, b = 1, 0
    for byte in text.encode("utf-8"):
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


def crc16_ccitt_value(text):
    fail = make_fail("crc16_ccitt_value")
    _check_text(fail, text)
    crc = 0xFFFF
    for byte in text.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def base32_encode_text(text):
    fail = make_fail("base32_encode_text")
    check_str(fail, text, "text")
    if len(text.encode("utf-8")) > MAX_TEXT:
        fail("too_many:text")
    data = text.encode("utf-8")
    out = []
    for i in range(0, len(data), 5):
        block = data[i:i + 5]
        bits = 0
        for byte in block:
            bits = (bits << 8) | byte
        pad_bytes = 5 - len(block)
        bits <<= 8 * pad_bytes
        chars = (len(block) * 8 + 4) // 5
        for k in range(chars):
            shift = 40 - 5 * (k + 1)
            out.append(_B32_ALPHABET[(bits >> shift) & 31])
        out.append("=" * (8 - chars))
    return "".join(out)


def base32_decode_text(text):
    fail = make_fail("base32_decode_text")
    _check_text(fail, text)
    if len(text) % 8 != 0:
        fail("bad_value:length")
    pad = len(text) - len(text.rstrip("="))
    if pad not in (0, 1, 3, 4, 6):
        fail("bad_value:padding")
    body = text.rstrip("=")
    for i, ch in enumerate(body):
        if ch not in _B32_ALPHABET:
            fail("bad_value:text[%d]" % i)
    bits = 0
    nbits = 0
    out = bytearray()
    for ch in body:
        bits = (bits << 5) | _B32_ALPHABET.index(ch)
        nbits += 5
        while nbits >= 8:
            nbits -= 8
            out.append((bits >> nbits) & 0xFF)
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        fail("bad_value:not_utf8")


def json_number_check(text):
    fail = make_fail("json_number_check")
    _check_text(fail, text)
    return _JSON_NUMBER.fullmatch(text) is not None


def json_string_escape(text):
    fail = make_fail("json_string_escape")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    short = {"\b": "\\b", "\t": "\\t", "\n": "\\n",
             "\f": "\\f", "\r": "\\r"}
    out = []
    for ch in text:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch in short:
            out.append(short[ch])
        elif code < 0x20:
            out.append("\\u%04x" % code)
        else:
            out.append(ch)
    return "".join(out)


def json_string_unescape(text):
    fail = make_fail("json_string_unescape")
    check_str(fail, text, "text")
    if len(text) > MAX_TEXT:
        fail("too_many:text")
    out = []
    i = 0
    simple = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
              "n": "\n", "r": "\r", "t": "\t"}
    while i < len(text):
        ch = text[i]
        if ch == '"':
            fail("bad_value:raw_quote[%d]" % i)
        if ch == "\\":
            if i + 1 >= len(text):
                fail("bad_value:trailing_backslash")
            esc = text[i + 1]
            if esc in simple:
                out.append(simple[esc])
                i += 2
            elif esc == "u":
                hexd = text[i + 2:i + 6]
                if len(hexd) != 4 or not all(
                        c in "0123456789abcdefABCDEF" for c in hexd):
                    fail("bad_value:escape[%d]" % i)
                code = int(hexd, 16)
                if 0xD800 <= code <= 0xDBFF:
                    pair = text[i + 6:i + 12]
                    if (len(pair) == 6 and pair[0] == "\\"
                            and pair[1] == "u"
                            and all(c in "0123456789abcdefABCDEF"
                                    for c in pair[2:])):
                        low = int(pair[2:], 16)
                        if 0xDC00 <= low <= 0xDFFF:
                            out.append(chr(0x10000
                                           + ((code - 0xD800) << 10)
                                           + (low - 0xDC00)))
                            i += 12
                            continue
                    fail("bad_value:lone_surrogate[%d]" % i)
                if 0xDC00 <= code <= 0xDFFF:
                    fail("bad_value:lone_surrogate[%d]" % i)
                out.append(chr(code))
                i += 6
            else:
                fail("bad_value:escape[%d]" % i)
        elif ord(ch) < 0x20:
            fail("bad_value:control_char[%d]" % i)
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def matrix_chain_cost(dims):
    fail = make_fail("matrix_chain_cost")
    check_items(fail, dims, "dims")
    if len(dims) < 2:
        fail("too_few:dims")
    if len(dims) > MAX_MATRIX_DIMS:
        fail("too_many:dims")
    for i, v in enumerate(dims):
        check_int(fail, v, "dims[%d]" % i)
        if v < 1:
            fail("bad_value:dims[%d]" % i)
    n = len(dims) - 1
    cost = [[0] * n for _ in range(n)]
    for span in range(2, n + 1):
        for i in range(n - span + 1):
            j = i + span - 1
            best = None
            for k in range(i, j):
                total = (cost[i][k] + cost[k + 1][j]
                         + dims[i] * dims[k + 1] * dims[j + 1])
                if best is None or total < best:
                    best = total
            cost[i][j] = best
    return cost[0][n - 1]


def knapsack_01_max(weights, values, capacity):
    fail = make_fail("knapsack_01_max")
    check_items(fail, weights, "weights")
    check_items(fail, values, "values")
    if len(weights) != len(values):
        fail("bad_value:length_mismatch")
    if len(weights) > MAX_KNAPSACK_ITEMS:
        fail("too_many:weights")
    check_int(fail, capacity, "capacity")
    if capacity < 0 or capacity > MAX_CAPACITY:
        fail("bad_value:capacity")
    for i in range(len(weights)):
        check_int(fail, weights[i], "weights[%d]" % i)
        check_int(fail, values[i], "values[%d]" % i)
        if weights[i] < 0 or values[i] < 0:
            fail("bad_value:negative")
    dp = [0] * (capacity + 1)
    for w, v in zip(weights, values):
        for c in range(capacity, w - 1, -1):
            if dp[c - w] + v > dp[c]:
                dp[c] = dp[c - w] + v
    return dp[capacity]


def rod_cut_max(prices):
    fail = make_fail("rod_cut_max")
    check_items(fail, prices, "prices")
    if not prices:
        fail("empty:prices")
    if len(prices) > MAX_ROD:
        fail("too_many:prices")
    for i, v in enumerate(prices):
        check_int(fail, v, "prices[%d]" % i)
        if v < 0:
            fail("bad_value:prices[%d]" % i)
    n = len(prices)
    best = [0] * (n + 1)
    for length in range(1, n + 1):
        best[length] = max(
            prices[cut - 1] + best[length - cut]
            for cut in range(1, length + 1))
    return best[n]
