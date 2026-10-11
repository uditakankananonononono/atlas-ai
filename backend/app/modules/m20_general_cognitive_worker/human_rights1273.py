"""Row 1273 Human Rights: caller-declared classification bookkeeping, nothing more.

The ledger row has no description; its requirement title is the whole spec. The existing
shared engine (legal_support_1260_1309.py, SPECS row 1273 line 30, analyze_legal_feature)
only passes caller `row_inputs` through. This module adds a closed-vocabulary record of
what the CALLER declares about each item (right_kind, duty_bearer, derogation, exhaustion, remedy_declared, monitoring_source) and flags unknown values,
unresolved source ids, and authority jurisdiction/date mismatches. It never reaches a
legal conclusion, never verifies authority, never files, serves or contacts anyone.
Stdlib only, deterministic, input never mutated.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

PREFIX = "HRIG1273"
MAX_ITEMS, MAX_AUTHORITIES, MAX_SOURCE_IDS, MAX_TEXT, MAX_KEYS = 16, 32, 8, 256, 16
_REFUSED_CATEGORIES = ('Cc', 'Cf', 'Zl', 'Zp')  # Zs accepted; Cs (surrogates) not newly refused, see contract
BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, "
            "currency, citations, facts, duties, deadlines and strategy before use.")

VOCAB = {
    "right_kind": ("civil_political", "economic_social", "collective", "other", "unknown"),
    "duty_bearer": ("state", "state_agent", "private_actor_asserted", "international_organization", "unknown"),
    "derogation": ("none_declared", "declared_derogation", "non_derogable_asserted", "disputed", "unknown"),
    "exhaustion": ("exhausted", "partial", "not_exhausted", "futility_asserted", "unknown"),
    "remedy_declared": ("compensation", "restitution", "injunction", "declaratory", "none_declared", "unknown"),
    "monitoring_source": ("treaty_body", "special_rapporteur", "regional_court", "domestic_court", "none_declared", "unknown"),
}
_CLASSIFY_FIELDS = ("right_kind", "duty_bearer", "derogation", "exhaustion", "remedy_declared", "monitoring_source")
_CONCLUSION_KEYS = ("decide", "constitutional", "conclusion")
_EFFECT_KEYS = ("file", "serve", "contact", "send", "spend")
_MAX_DATE = 10
_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def _err(reason):
    return ValueError(PREFIX + ":" + reason)


def _guard(d):
    for k in _CONCLUSION_KEYS:
        if d.get(k):
            raise _err("CONCLUSION_REFUSED")
    for k in _EFFECT_KEYS:
        if d.get(k):
            raise _err("EXTERNAL_EFFECT_REFUSED")


def _text(v, name):
    if type(v) is not str:
        raise _err("BAD_TYPE:" + name)
    if len(v) > MAX_TEXT:  # raw length first, before strip or any Unicode check
        raise _err("TEXT_TOO_LONG:" + name)
    if not v.strip():
        raise _err("EMPTY:" + name)
    if any(unicodedata.category(c) in _REFUSED_CATEGORIES for c in v):
        raise _err("CONTROL_CHARS:" + name)
    return v


def _date(v, name):
    if type(v) is not str:  # 1. exact type
        raise _err("BAD_TYPE:" + name)
    if len(v) != _MAX_DATE:  # 2. exact raw length, before any format or Unicode work
        raise _err("BAD_DATE:" + name)
    if not _ISO.match(v):  # 3. ASCII YYYY-MM-DD shape, then calendar
        raise _err("BAD_DATE:" + name)
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise _err("BAD_DATE:" + name) from None


def _shape(d, allowed, required, kind):
    if type(d) is not dict:
        raise _err("BAD_TYPE:" + kind)
    if len(d) > MAX_KEYS:  # count before any iteration
        raise _err("TOO_MANY:keys")
    for k in d:  # key types before any key lookup (guard) or membership test
        if type(k) is not str:
            raise _err("BAD_TYPE:key")
    _guard(d)
    for k in d:
        if k not in allowed:
            raise _err("UNKNOWN_KEY")
    for k in required:
        if k not in d:
            raise _err("MISSING:" + k)


def _list(v, name, cap):
    if type(v) is not list:
        raise _err("BAD_TYPE:" + name)
    if not v:
        raise _err("EMPTY:" + name)
    if len(v) > cap:
        raise _err("TOO_MANY:" + name)
    return v


def organize(payload):
    """Record caller-declared Human Rights fields; decide nothing."""
    top = ("jurisdiction", "as_of", "authorities", "items")
    _shape(payload, top, top, "payload")
    jurisdiction = _text(payload["jurisdiction"], "jurisdiction")
    as_of = _date(payload["as_of"], "as_of")
    auth_keys = ("id", "citation_text", "jurisdiction", "effective_date")
    flags, ids = [], set()
    for a in _list(payload["authorities"], "authorities", MAX_AUTHORITIES):
        _shape(a, auth_keys, auth_keys, "authority")
        aid = _text(a["id"], "authority_id")
        if aid in ids:
            raise _err("DUPLICATE:authority_id")
        ids.add(aid)
        _text(a["citation_text"], "citation_text")
        ajur = _text(a["jurisdiction"], "jurisdiction")
        eff = _date(a["effective_date"], "effective_date")
        flags.append({"id": aid, "jurisdiction_mismatch": ajur != jurisdiction,
                      "effective_after_as_of": eff > as_of, "independently_verified": False})
    item_keys = ("id",) + _CLASSIFY_FIELDS + ("source_ids",)
    out, seen = [], set()
    for it in _list(payload["items"], "items", MAX_ITEMS):
        _shape(it, item_keys, item_keys, "item")
        iid = _text(it["id"], "item_id")
        if iid in seen:
            raise _err("DUPLICATE:item_id")
        seen.add(iid)
        vals = {}
        for f in _CLASSIFY_FIELDS:
            v = it[f]
            if type(v) is not str:
                raise _err("BAD_TYPE:" + f)
            if len(v) > MAX_TEXT:  # raw cap before membership
                raise _err("TEXT_TOO_LONG:" + f)
            if v not in VOCAB[f]:
                raise _err("UNKNOWN_VALUE:" + f)
            vals[f] = v
        refs = _list(it["source_ids"], "source_ids", MAX_SOURCE_IDS)
        for r in refs:
            _text(r, "source_id")  # strict str, raw cap, blank and Unicode screen (echoed on success)
        missing = []
        for r in refs:
            if r not in ids and r not in missing:
                missing.append(r)
        unclassified = [f for f in _CLASSIFY_FIELDS if vals[f] == "unknown"]
        out.append(dict({"id": iid}, **vals, unclassified_fields=unclassified, missing_source_ids=missing))
    blocked = sum(1 for c in out if c["unclassified_fields"] or c["missing_source_ids"])
    authority_problem = any(f["jurisdiction_mismatch"] or f["effective_after_as_of"] for f in flags)
    return {
        "row": 1273, "status": "caller_declared_human_rights_bookkeeping_only",
        "jurisdiction": jurisdiction, "as_of": payload["as_of"],
        "classified": out, "authority_flags": flags,
        "counts": {"items": len(out), "unclassified": sum(1 for c in out if c["unclassified_fields"]),
                   "blocked_items": blocked},
        "review_state": "blocked" if blocked or authority_problem else "counsel_review_required",
        "rights_violation_determined": False, "legal_conclusion": None, "filing_or_external_effect": False,
        "authorities_independently_verified": False, "requires_licensed_counsel": True, "disclaimer": BOUNDARY,
    }
