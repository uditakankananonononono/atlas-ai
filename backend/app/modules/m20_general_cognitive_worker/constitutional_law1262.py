"""Row 1262 Constitutional Law: declared bookkeeping over caller-supplied data only.

Organizes caller-supplied state-action, right, scrutiny-level, governmental-interest and
tailoring entries, each tagged sourced fact, assertion or analysis. It is jurisdiction, as-of
and provenance-bound. It never reaches a legal conclusion, never files, serves or contacts
anyone, and never verifies supplied assertions or authority references.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from urllib.parse import urlparse

PREFIX = "CONSTI1262:"
BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify "
            "jurisdiction, currency, citations, facts, duties, deadlines and strategy before use.")
MAX_TEXT = 500
MAX_ITEMS = 20
ELEMENTS = ("state_action", "right", "scrutiny_level", "governmental_interest", "tailoring")
KINDS = ("sourced_fact", "assertion", "analysis")
_TOP = {"jurisdiction", "as_of", "authorities", "elements"}
_AUTH = {"id", "citation", "jurisdiction", "source_url"}
_ELEM_REQ = {"element", "kind", "text"}
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)
MAX_KEYS = 64


class ConstitutionalRefusal(ValueError):
    """Fixed-constant refusal; the message never echoes caller input."""


def _refuse(code: str):
    raise ConstitutionalRefusal(PREFIX + code)


def _hidden(s: str) -> bool:
    # Refuse the full Cc, Cf, Zl and Zp categories (covers DEL, U+00AD, U+200B-200F,
    # U+202A-202E, U+2060-2064, U+2066-2069, U+FEFF). Zs is accepted. Cs is not refused (disclosed residual).
    return any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in s)


def _text(value, field: str = "") -> str:
    if type(value) is not str:
        _refuse("TYPE")
    if len(value) > MAX_TEXT:  # raw length first, before strip or scan
        _refuse("TEXT_LONG")
    if _hidden(value):  # screen the raw text, before strip, so edge LF/TAB/NEL/Zl/Zp are refused
        _refuse("TEXT_HIDDEN")
    s = value.strip()
    if not s:
        _refuse("TEXT_EMPTY")
    return s


def _dict(value, keys: set) -> None:
    if type(value) is not dict:
        _refuse("SHAPE")
    if len(value) > MAX_KEYS:  # key count before any set construction or iteration
        _refuse("COUNT_MAX")
    for k in value:  # strict str keys, after the count and before any set construction
        if type(k) is not str:
            _refuse("KEYS")


def _list(value) -> list:
    if type(value) is not list:
        _refuse("SHAPE")
    if len(value) > MAX_ITEMS:  # count cap before any item is parsed
        _refuse("COUNT_MAX")
    if not value:
        _refuse("COUNT_MIN")
    return value


def _date(value) -> str:
    if type(value) is not str:
        _refuse("TYPE")
    if len(value) != 10:  # exact raw length before regex, strip or parse
        _refuse("DATE")
    s = value
    if not _DATE.fullmatch(s):
        _refuse("DATE")
    try:
        date.fromisoformat(s)
    except ValueError:
        _refuse("DATE")
    return s


def _authority(raw) -> dict:
    _dict(raw, _AUTH)
    if set(raw) != _AUTH:
        _refuse("KEYS")
    out = {k: _text(raw[k]) for k in ("id", "citation", "jurisdiction", "source_url")}
    p = urlparse(out["source_url"])
    if p.scheme not in ("http", "https") or not p.netloc:
        _refuse("URL")
    return out


def map_constitutional_scrutiny(data) -> dict:
    """Return a declared bookkeeping map. Decides nothing; legal_conclusion is always None."""
    _dict(data, _TOP)
    if set(data) != _TOP:
        _refuse("KEYS")
    jurisdiction = _text(data["jurisdiction"])
    as_of = _date(data["as_of"])
    raw_auths = _list(data["authorities"])
    raw_elems = _list(data["elements"])
    auths = [_authority(a) for a in raw_auths]
    ids = [a["id"] for a in auths]
    if len(set(ids)) != len(ids):
        _refuse("DUP")
    known = set(ids)
    grouped = {name: [] for name in ELEMENTS}
    for raw in raw_elems:
        _dict(raw, _ELEM_REQ)
        if not (_ELEM_REQ <= set(raw) <= _ELEM_REQ | {"source_id"}):
            _refuse("KEYS")
        element = _text(raw["element"])
        kind = _text(raw["kind"])
        if element not in ELEMENTS or kind not in KINDS:
            _refuse("ENUM")
        text = _text(raw["text"])
        source_id = _text(raw["source_id"]) if "source_id" in raw else None
        if source_id is None and kind == "sourced_fact":
            _refuse("SOURCE_REQUIRED")
        if source_id is not None and source_id not in known:
            _refuse("SOURCE_UNKNOWN")
        grouped[element].append({"kind": kind, "text": text, "source_id": source_id,
                                 "source_linked": source_id is not None})
    return {
        "status": "constitutional_bookkeeping_only",
        "jurisdiction": jurisdiction,
        "as_of": as_of,
        "elements": {n: {"count": len(grouped[n]), "entries": grouped[n]} for n in ELEMENTS},
        "missing_elements": [n for n in ELEMENTS if not grouped[n]],
        "jurisdiction_mismatch_source_ids": [a["id"] for a in auths if a["jurisdiction"] != jurisdiction],
        "authorities": auths,
        "legal_conclusion": None,
        "authority_independently_verified": False,
        "filing_or_external_effect": False,
        "boundary": BOUNDARY,
    }
