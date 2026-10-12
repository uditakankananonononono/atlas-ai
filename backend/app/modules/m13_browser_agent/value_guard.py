"""Fail-closed guard against writing ID-shaped values into web forms (SSN, Aadhaar, card numbers).

Shared by the M01 prefill planner, ApplicationFlow.stage and the low-level Service.fill so a caller
that skips planning gets the same protection. Shape-based, not semantic: it cannot know a value is a
real SSN, only that it is shaped like one.

Normalization: NFKC (fullwidth -> ASCII), other-script digits -> ASCII digits, zero-width/format
characters removed. The digit count is taken after stripping ALL non-digit
characters (separators AND letters), i.e. the whole value is one run: "123a45a6789" counts as 9 digits.

Rules:
- any key: a dashed SSN pattern (NNN-NN-NNNN) is refused.
- non-phone keys: a value whose total digit count is exactly 9 or 12 or more is refused.
- phone key: the value must look like a phone number (only digits, spaces, dots, hyphens,
  parentheses, optional leading '+'), with 7 to 15 digits in total, not 9, and 12-15 digits only
  with a leading '+'.

Documented residuals (verbatim, by design):
- 10 and 11 digit runs are ACCEPTED under non-phone keys (they are ordinary phone/ID-less numbers
  and cannot be told from one).
- Fail-closed false positives are accepted: any free text whose digits total 9 or 12+ (e.g. a street
  address '123 Main St Apt 4B 94110'), and ZIP+4 (9 digits), a 9-digit run in a URL or date range,
  and legitimate 9-digit phone numbers are refused; the owner types those.
- A '+'-prefixed 12-15 digit ID-shaped number under the phone key is indistinguishable from an
  international phone number and is accepted.
"""
from __future__ import annotations

import re
import unicodedata

_SSN_DASHED = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_RUN = re.compile(r"[0-9](?:[^0-9]*[0-9])*")  # strip-all: letters do not break a run
_PHONE_SHAPE = re.compile(r"^\+?[0-9\s().\-]{7,24}$")
_PHONE_KEY = re.compile(r"phone|mobile|\btel\b|telephone|\bcell\b", re.I)
ID_LEN_MIN = 12


def normalize(value: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKC", value):
        cat = unicodedata.category(ch)
        if cat in {"Cf", "Cc"} and ch not in "\n\t":
            continue
        if ch.isdigit() and not ch.isascii():
            try:
                ch = str(unicodedata.digit(ch))
            except ValueError:
                pass
        out.append(ch)
    return "".join(out)


def is_phone_key(key: str) -> bool:
    return bool(_PHONE_KEY.search(key.replace("_", " ")))


def _runs(value: str) -> list[int]:
    return [sum(c.isdigit() for c in m.group(0)) for m in _RUN.finditer(value)]


def forbidden_value(key: str, value: str) -> bool:
    """True when the value is ID-shaped for this key. See module docstring for the exact rules."""
    v = normalize(value)
    if _SSN_DASHED.search(v):
        return True
    if not is_phone_key(key):
        return any(n == 9 or n >= ID_LEN_MIN for n in _runs(v))
    v = v.strip()
    if not _PHONE_SHAPE.match(v):
        return True
    n = sum(c.isdigit() for c in v)
    if not 7 <= n <= 15 or n == 9:
        return True
    return n >= ID_LEN_MIN and not v.startswith("+")


def assert_no_forbidden_values(data: dict) -> None:
    for key, value in data.items():
        if isinstance(value, str) and forbidden_value(str(key), value):
            raise ValueError("value for '%s' is ID-shaped (SSN/ID/card-like); the owner types it, Atlas never fills it" % key)
