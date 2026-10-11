r"""Row 1260 Sentencing Guidelines: bounded declared legal-support bookkeeping.

Maps caller-supplied guideline edition, offense characteristics, adjustments
and departures into a separated, provenance-bound bookkeeping receipt. The
edition is a declared label (never verified); every entry is tagged by the
caller as sourced_fact, assertion or analysis, and the receipt separates and
counts those classes. The unit NEVER computes a sentence, a guideline range,
an offense level, a criminal-history category, or any other outcome; it never
files, serves or contacts anyone; it never verifies supplied assertions,
editions, citations or source references. Standard library only.

Validation order: exact container types (type(x) is list/dict/str) BEFORE len(); keys at both levels must be exact str (subclass keys are refused); as_of takes its raw length cap BEFORE the ISO regex; basis is exact str with a raw 12-char cap BEFORE membership;
count caps BEFORE any iteration; for every string, length cap first, then a
Unicode check (no Unicode control (Cc), format (Cf) or line/paragraph
separator (Zl/Zp) characters; space separators (Zs) accepted), then aggregate
accounting. Disclosed residual: unpaired surrogates (Cs) are not refused. Strict nested key allowlists with
key-count caps. The incoming object is never copied: the receipt and the
provenance hash are built only from validated values in fresh containers.
Refusal reasons are generic and name schema fields only - never a caller key,
value, edition, or entry text.

Delta vs the existing mechanism: the shared cluster engine
backend/app/modules/m20_general_cognitive_worker/legal_support_1260_1309.py
carries row 1260 as a _SPECS entry (line 17 at main a294723b) executed by
analyze_legal_feature (line 96), which returns
status="supplied_legal_review_template_only" with named_capability_executed=
False - a generic template artifact with no row-specific mapping. This unit
executes the row-1260 mechanism itself: validated per-entry bookkeeping of
edition + offense characteristics + adjustments + departures with
sourced_fact/assertion/analysis separation, exact row-tagged refusal codes
(SENTEN1260:), and explicit never-computed flags for sentence and range.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

MAX_EDITION_LEN = 64
MAX_ITEMS = 64
MAX_TEXT_LEN = 256
MAX_SOURCE_REF_LEN = 256
MAX_JURISDICTION_LEN = 128
MAX_PROVENANCE_LEN = 256
MAX_AGGREGATE_STRING_LEAVES = 200000
MAX_BASIS_LEN = 12  # longest basis is "sourced_fact"

_PREFIX = "SENTEN1260:"
_TOP_KEYS = ("guideline_edition", "offense_characteristics", "adjustments",
             "departures", "jurisdiction", "as_of", "provenance")
_ITEM_KEYS = ("text", "basis", "source_ref")
_ITEM_LISTS = ("offense_characteristics", "adjustments", "departures")
_BASES = ("sourced_fact", "assertion", "analysis")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}$")

_UNICODE_MSG = ("contains a disallowed character: no Unicode control (Cc), "
                "format (Cf) or line/paragraph separator (Zl/Zp) characters")

LEGAL_BOUNDARY = ("Legal work product for review, not legal advice. Licensed counsel "
                  "must verify jurisdiction, currency, citations, facts, duties, "
                  "deadlines and strategy before use.")


class SentencingGuidelinesRefusal(ValueError):
    """The request was refused; .code is machine readable, str() is the exact reason."""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def _refuse(kind: str, message: str) -> None:
    code = _PREFIX + kind
    raise SentencingGuidelinesRefusal(code, code + ": " + message)


def _invalid(message: str) -> None:
    _refuse("invalid_input", message)


def _limit(message: str) -> None:
    _refuse("resource_limit", message)


class _Aggregate:
    """Running budget over every validated string leaf of the input."""

    def __init__(self) -> None:
        self.total = 0

    def add(self, text: str, field_class: str) -> None:
        self.total += len(text)
        if self.total > MAX_AGGREGATE_STRING_LEAVES:
            _refuse("oversize",
                    f"aggregate string leaves exceed limit {MAX_AGGREGATE_STRING_LEAVES} "
                    f"(field class: {field_class})")


def _unicode_check(value: str, owner: str) -> None:
    for ch in value:
        if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp"):
            _invalid(f"{owner} {_UNICODE_MSG}")


def _text(value: str, owner: str, limit: int, agg: _Aggregate, field_class: str) -> str:
    """Length cap first, then Unicode check, then aggregate accounting."""
    if len(value) > limit:
        _limit(f"{owner} is {len(value)} characters, limit is {limit}")
    _unicode_check(value, owner)
    agg.add(value, field_class)
    return value


def _unknown_key(parent: str) -> None:
    # The reason names the parent schema field only; a key is unbounded caller
    # input and must never reach the refusal text.
    _refuse("unknown_key", f"unknown key at {parent}")


def _validate_item(raw: Any, owner: str, agg: _Aggregate) -> dict:
    if type(raw) is not dict:  # exact type
        _invalid(f"{owner} must be an object")
    if len(raw) > len(_ITEM_KEYS):  # count cap before the allowlist scan
        _unknown_key(owner)
    for key in raw:
        if type(key) is not str:  # exact str keys only
            _invalid(f"{owner} keys must be strings")
        if key not in _ITEM_KEYS:
            _unknown_key(owner)
    text = raw.get("text")
    if type(text) is not str or not text:  # exact str
        _invalid(f"{owner}.text requires a non-empty string")
    checked = {"text": _text(text, f"{owner}.text", MAX_TEXT_LEN, agg, owner)}
    basis = raw.get("basis")
    if type(basis) is not str:  # exact str
        _invalid(f"{owner}.basis must be one of sourced_fact, assertion, analysis")
    if len(basis) > MAX_BASIS_LEN:  # raw cap BEFORE membership
        _limit(f"{owner}.basis is {len(basis)} characters, limit is {MAX_BASIS_LEN}")
    if basis not in _BASES:
        _invalid(f"{owner}.basis must be one of sourced_fact, assertion, analysis")
    checked["basis"] = basis
    if "source_ref" in raw:
        ref = raw["source_ref"]
        if type(ref) is not str:  # exact str
            _invalid(f"{owner}.source_ref must be a string when provided")
        checked["source_ref"] = _text(ref, f"{owner}.source_ref", MAX_SOURCE_REF_LEN, agg, owner)
    return checked


def _validate(data: Any) -> tuple[str, dict[str, list], str | None, str | None, str | None]:
    if type(data) is not dict:  # exact type: subclasses refused before len
        _invalid("input must be an object")
    if len(data) > len(_TOP_KEYS):  # count cap before the allowlist scan
        _unknown_key("input")
    for key in data:
        if type(key) is not str:  # exact str keys only
            _invalid("input keys must be strings")
        if key not in _TOP_KEYS:
            _unknown_key("input")
    agg = _Aggregate()
    edition = data.get("guideline_edition")
    if type(edition) is not str or not edition:  # exact str
        _invalid("guideline_edition requires a non-empty string")
    _text(edition, "guideline_edition", MAX_EDITION_LEN, agg, "guideline_edition")
    lists: dict[str, list] = {}
    for name in _ITEM_LISTS:
        raw_list = data.get(name, [])
        if type(raw_list) is not list:  # exact type
            _invalid(f"{name} must be a list of entry objects")
        if len(raw_list) > MAX_ITEMS:  # count cap before any iteration
            _limit(f"{name} count {len(raw_list)} exceeds limit {MAX_ITEMS}")
        entries = []
        for index, raw in enumerate(raw_list):
            entries.append(_validate_item(raw, f"{name}[{index}]", agg))
        lists[name] = entries
    jurisdiction = data.get("jurisdiction")
    if jurisdiction is not None:
        if type(jurisdiction) is not str:  # exact str
            _invalid("jurisdiction must be a string when provided")
        _text(jurisdiction, "jurisdiction", MAX_JURISDICTION_LEN, agg, "jurisdiction")
    as_of = data.get("as_of")
    if as_of is not None:
        if type(as_of) is not str:  # exact str
            _invalid("as_of must be an ISO date string")
        if len(as_of) > 10:  # raw length cap BEFORE the regex
            _limit(f"as_of is {len(as_of)} characters, limit is 10")
        if not _ISO_DATE.fullmatch(as_of):
            _invalid("as_of must be an ISO date string")
        _text(as_of, "as_of", 10, agg, "as_of")
    provenance = data.get("provenance")
    if provenance is not None:
        if type(provenance) is not str:  # exact str
            _invalid("provenance must be a string when provided")
        _text(provenance, "provenance", MAX_PROVENANCE_LEN, agg, "provenance")
    return edition, lists, jurisdiction, as_of, provenance


def map_guideline_inputs(data: Any) -> dict[str, Any]:
    """Return the separated bookkeeping map of the supplied guideline inputs.

    The incoming object is validated read-only: exact container types first,
    then count caps, and only then per-item iteration. Nothing copies the
    caller's object. The receipt and the provenance hash are built only from
    validated values in fresh containers, so mutating the caller's data after
    the call cannot change the receipt, mutating the receipt cannot reach the
    caller's data, and two calls over the same input return byte-identical
    receipts. No sentence, range, offense level or criminal-history category
    is computed; the edition and every entry are caller declarations and are
    not verified.
    """
    edition, lists, jurisdiction, as_of, provenance = _validate(data)
    separation = {"sourced_facts": 0, "assertions": 0, "analysis": 0}
    trace = []
    canonical_obj: dict[str, Any] = {"guideline_edition": edition}
    for name in _ITEM_LISTS:
        for index, entry in enumerate(lists[name]):
            key = {"sourced_fact": "sourced_facts", "assertion": "assertions",
                   "analysis": "analysis"}[entry["basis"]]
            separation[key] += 1
            trace.append({"list": name, "input_index": index})
        if name in data:
            canonical_obj[name] = [dict(e) for e in lists[name]]
    for opt in ("jurisdiction", "as_of", "provenance"):
        if opt in data:
            canonical_obj[opt] = {"jurisdiction": jurisdiction, "as_of": as_of,
                                  "provenance": provenance}[opt]
    canonical = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    return {
        "row": 1260,
        "capability": "Sentencing Guidelines",
        "scope": "supplied_guideline_input_mapping",
        "status": "mapping_complete",
        "guideline_edition": edition,
        "jurisdiction": jurisdiction,
        "as_of": as_of,
        "provenance_label": provenance,
        "guideline_map": {name: [dict(e) for e in lists[name]] for name in _ITEM_LISTS},
        "separation": separation,
        "input_trace": trace,
        "provenance": {
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "hash_scope": "validated_fields",
            "edition_verified": False,
            "assertions_verified": False,
            "sources_verified": False,
        },
        "flags": {
            "sentence_computed": False,
            "guideline_range_computed": False,
            "legal_advice": False,
            "filing_or_contact": False,
        },
        "boundary": {
            "not_legal_advice": True,
            "requires_licensed_counsel": True,
            "text": LEGAL_BOUNDARY,
        },
        "human_review_required": True,
    }
