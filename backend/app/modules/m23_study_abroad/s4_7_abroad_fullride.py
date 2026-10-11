"""S4.7 abroad-fullride-planner (scoped, pure, no I/O).

Filters caller-supplied country/university/scholarship rows down to full-ride
offers for international undergrads that need no additional written tests and
accept CBSE secondary-school marks plus SAT or IELTS ("IELTs(maybe)"). Rows
come from public sourced pages only: every row carries a public https
source_url and a fetched_at check date; freshness is graded by composing
``source_freshness.assess_facts`` (recorded-check age only - never
verification, official status, or reachability). Coverage is computed, never
claimed: target 100 countries ("applying abroad for upto 100 countries"),
achieved N. This planner never applies, submits, sends or spends
(``APPLY_REFUSED_SUBMIT`` / ``APPLY_REFUSED_SPEND``); fee waivers are S4.3,
application prefill is S4.5.

Deterministic: output depends only on the payload; ``as_of`` is the freshness
"now", so no clock is read.
"""
from __future__ import annotations

import math
import unicodedata
from datetime import datetime, timezone
from typing import Any

from app.modules.m23_study_abroad.source_freshness import assess_facts

MAX_ROWS = 5000
MAX_TEXT = 200
TARGET_COUNTRIES = 100
_SPEND_KEYS = ("purchase", "spend", "pay", "fee_payment")
_SUBMIT_KEYS = ("submit", "apply", "send", "auto_apply")
_PAYLOAD_FIELDS = {"as_of", "profile", "rows", "max_age_days"} | set(_SPEND_KEYS) | set(_SUBMIT_KEYS)
_PROFILE_FIELDS = {"curriculum", "sat", "ielts"}
_ROW_FIELDS = {"id", "country", "university", "scholarship", "source_url", "fetched_at",
               "full_ride", "requires_extra_written_test", "accepts_cbse",
               "accepts_sat", "accepts_ielts"}
_BOOL_FLAGS = ("full_ride", "requires_extra_written_test", "accepts_cbse",
               "accepts_sat", "accepts_ielts")


def _refuse(detail):
    raise ValueError(detail)


def _strict_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _text(value, name, limit=MAX_TEXT):
    if not isinstance(value, str):
        _refuse("APPLY_REFUSED_BAD_TYPE:%s" % name)
    if value != value.strip() or not (1 <= len(value) <= limit):
        _refuse("APPLY_REFUSED_EMPTY_FIELD:%s" % name)
    if any(unicodedata.category(ch) in ("Cc", "Cf") or ch in (" ", " ", " ") for ch in value):
        _refuse("APPLY_REFUSED_UNSAFE_CHARS:%s" % name)
    return value


def _parse_date(value, name):
    if not isinstance(value, str):
        _refuse("APPLY_REFUSED_BAD_TYPE:%s" % name)
    try:
        if "T" in value:
            return datetime.fromisoformat(value)
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        _refuse("APPLY_REFUSED_BAD_DATE:%s" % name)


def _validate_profile(profile):
    if type(profile) is not dict:
        _refuse("APPLY_REFUSED_BAD_TYPE:profile")
    unknown = sorted(set(profile) - _PROFILE_FIELDS)
    if unknown:
        _refuse("APPLY_REFUSED_UNKNOWN_FIELDS:profile[%s]" % ",".join(unknown))
    if "curriculum" not in profile:
        _refuse("APPLY_REFUSED_EMPTY_FIELD:curriculum")
    curriculum = _text(profile["curriculum"], "curriculum", 32)
    if curriculum != "CBSE":
        _refuse("APPLY_REFUSED_PROFILE:curriculum_must_be_CBSE")
    sat = profile.get("sat")
    if sat is not None:
        if not _strict_int(sat):
            _refuse("APPLY_REFUSED_BAD_TYPE:sat")
        if sat < 400 or sat > 1600:
            _refuse("APPLY_REFUSED_OUT_OF_RANGE:sat")
    ielts = profile.get("ielts")
    if ielts is not None:
        if isinstance(ielts, bool) or not isinstance(ielts, (int, float)):
            _refuse("APPLY_REFUSED_BAD_TYPE:ielts")
        if isinstance(ielts, float) and not math.isfinite(ielts):
            _refuse("APPLY_REFUSED_OUT_OF_RANGE:ielts")
        if ielts < 0 or ielts > 9:
            _refuse("APPLY_REFUSED_OUT_OF_RANGE:ielts")
    if sat is None and ielts is None:
        _refuse("APPLY_REFUSED_PROFILE:cbse_plus_sat_or_ielts_required")


def _validate_row(raw, index, seen):
    if type(raw) is not dict:
        _refuse("APPLY_REFUSED_BAD_TYPE:rows[%d]" % index)
    unknown = sorted(set(raw) - _ROW_FIELDS)
    if unknown:
        _refuse("APPLY_REFUSED_UNKNOWN_FIELDS:row[%s]" % ",".join(unknown))
    for field in _ROW_FIELDS:
        if field not in raw:
            _refuse("APPLY_REFUSED_EMPTY_FIELD:%s" % field)
    row_id = _text(raw["id"], "id", 64)
    if row_id in seen:
        _refuse("APPLY_REFUSED_DUPLICATE:%s" % row_id)
    seen.add(row_id)
    country = _text(raw["country"], "country")
    university = _text(raw["university"], "university")
    scholarship = _text(raw["scholarship"], "scholarship")
    url = raw["source_url"]
    if not isinstance(url, str):
        _refuse("APPLY_REFUSED_BAD_TYPE:source_url")
    if not (url.startswith("https://") and len(url) <= 2048 and "." in url[8:]):
        _refuse("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https")
    fetched = raw["fetched_at"]
    if not isinstance(fetched, str) or not (1 <= len(fetched) <= 40):
        _refuse("APPLY_REFUSED_BAD_TYPE:fetched_at")
    for flag in _BOOL_FLAGS:
        if not isinstance(raw[flag], bool):
            _refuse("APPLY_REFUSED_BAD_TYPE:%s" % flag)
    return {"id": row_id, "country": country, "university": university,
            "scholarship": scholarship, "source_url": url, "fetched_at": raw["fetched_at"],
            **{flag: raw[flag] for flag in _BOOL_FLAGS}}


def _exclusion_reasons(r, has_sat, has_ielts):
    reasons = []
    if not r["full_ride"]:
        reasons.append("not_full_ride")
    if r["requires_extra_written_test"]:
        reasons.append("requires_extra_written_test")
    if not r["accepts_cbse"]:
        reasons.append("cbse_not_accepted")
    credential_match = (has_sat and r["accepts_sat"]) or (has_ielts and r["accepts_ielts"])
    if not credential_match:
        reasons.append("test_credential_not_accepted")
    return reasons


def plan_full_rides(payload):
    """Filter sourced rows to full-ride, no-extra-written-test, CBSE+SAT/IELTS.

    Returns kept rows (each with a source-freshness grade), excluded rows with
    reason codes, a computed coverage block and a scope honesty block.
    Refusals raise ``ValueError`` with stable ``APPLY_REFUSED_*`` strings (see
    docs/contracts/c35.s4-7-abroad-fullride-planner.md).
    """
    if type(payload) is not dict:
        _refuse("APPLY_REFUSED_BAD_TYPE:payload")
    unknown = sorted(set(payload) - _PAYLOAD_FIELDS)
    if unknown:
        _refuse("APPLY_REFUSED_UNKNOWN_FIELDS:payload")
    for key in _SPEND_KEYS:
        if payload.get(key):
            _refuse("APPLY_REFUSED_SPEND:s4_7_is_a_planner_no_spend")
    for key in _SUBMIT_KEYS:
        if payload.get(key):
            _refuse("APPLY_REFUSED_SUBMIT:s4_7_plans_only_never_applies")
    for field in ("as_of", "profile", "rows"):
        if field not in payload:
            _refuse("APPLY_REFUSED_EMPTY_FIELD:%s" % field)
    as_of = _parse_date(payload["as_of"], "as_of")
    _validate_profile(payload["profile"])
    has_sat = payload["profile"].get("sat") is not None
    has_ielts = payload["profile"].get("ielts") is not None
    max_age_days = payload.get("max_age_days", 180)
    if not _strict_int(max_age_days):
        _refuse("APPLY_REFUSED_BAD_TYPE:max_age_days")
    if max_age_days < 1 or max_age_days > 3650:
        _refuse("APPLY_REFUSED_OUT_OF_RANGE:max_age_days")
    rows = payload["rows"]
    if not isinstance(rows, list):
        _refuse("APPLY_REFUSED_BAD_TYPE:rows")
    if not rows:
        _refuse("APPLY_REFUSED_EMPTY_FIELD:rows")
    if len(rows) > MAX_ROWS:
        _refuse("APPLY_REFUSED_OVERCAP:max_5000_rows")

    seen = set()
    records = [_validate_row(raw, i, seen) for i, raw in enumerate(rows)]
    kept, excluded = [], []
    for rec in records:
        reasons = _exclusion_reasons(rec, has_sat, has_ielts)
        if reasons:
            excluded.append({"id": rec["id"], "reasons": reasons})
        else:
            kept.append(rec)
    kept.sort(key=lambda r: (r["country"], r["university"], r["id"]))
    excluded.sort(key=lambda e: e["id"])

    now = as_of.replace(tzinfo=timezone.utc)
    if kept:
        records = [{"fact_id": r["id"], "subject": r["university"],
                    "field": "full_ride_eligibility",
                    "value": "declared_full_ride_no_extra_written_test_cbse_sat_ielts",
                    "source_url": r["source_url"], "checked_at": r["fetched_at"]} for r in kept]
        # assess_facts caps one call at 500 records; grade in chunks and merge.
        freshness_by_id, counts, limits = {}, {"fresh": 0, "stale": 0, "unknown": 0}, []
        for start in range(0, len(records), 500):
            facts = assess_facts(records[start:start + 500], now=now, max_age_days=max_age_days)
            for f in facts["facts"]:
                freshness_by_id[f["fact_id"]] = {k: f[k] for k in ("status", "reason", "age_days")}
            for status in counts:
                counts[status] += facts["counts"][status]
            limits = facts["limits"]
        freshness_block = {"counts": counts, "max_age_days": max_age_days, "limits": limits}
    else:
        freshness_by_id = {}
        freshness_block = {"counts": {"fresh": 0, "stale": 0, "unknown": 0},
                           "max_age_days": max_age_days,
                           "limits": ["no kept rows to grade"]}
    kept_out = [dict(r, freshness=freshness_by_id[r["id"]]) for r in kept]

    countries = sorted({r["country"] for r in kept})
    us_kept = sum(1 for r in kept if r["country"] == "United States")
    return {
        "kept": kept_out,
        "excluded": excluded,
        "coverage": {
            "target_countries": TARGET_COUNTRIES,
            "achieved_countries": len(countries),
            "countries": countries,
            "us_universities_kept": us_kept,
            "non_us_countries_kept": len(countries) - (1 if us_kept else 0),
            "total_rows": len(records),
            "total_kept": len(kept),
        },
        "freshness": freshness_block,
        "scope": {
            "implemented": ("full-ride filter for international undergrads: no additional "
                            "written tests, CBSE marks plus a matching declared test "
                            "credential (SAT, or IELTS when declared in the profile); "
                            "per-row public https source and recorded-check freshness; "
                            "computed country coverage against the 100-country target"),
            "not_implemented": [
                "no fetching - rows are caller-supplied from public sourced pages",
                "never applies, submits or sends - application prefill is S4.5",
                "no fee waivers or spend - fee waivers are S4.3",
                "freshness is recorded-check age only, never source verification",
            ],
            "data_source": "supplied",
            "as_of": payload["as_of"],
        },
    }
