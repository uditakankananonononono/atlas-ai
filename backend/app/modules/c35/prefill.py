"""S4.5 / c35.prefill - application prefill-and-tracker.

Source excerpt (verbatim): "Apply super strategically to all opportunities
on the internet" (pin delegated, not independently recovered from a user
channel; provenance per the delegation, not verified here).

Builds prefill packets from a SUPPLIED profile, a deadline calendar and an
effort/EV ranking over SUPPLIED opportunities. "All opportunities on the
internet" is substituted by the supplied set. Never submits (X6): any
submit/password/login key refuses. Ranking is computed only from
caller-supplied numbers: score = (value * p_win) / effort_hours; no
invented probabilities. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import math
import re
from datetime import date

from app.modules.c30 import policy

PREFIX = "APPLY"
MAX_OPPORTUNITIES = 512
MAX_FIELDS = 64
MAX_PROFILE_KEYS = 128
# exact normalized names treated as long-form prose: never auto-filled
ESSAY_FIELDS = frozenset({
    "essay", "personal_statement", "statement", "statement_of_purpose",
    "cover_letter", "motivation", "motivation_letter", "sop",
})
# any key or requested field carrying one of these tokens is a
# submit/credential pathway; refused before any processing
BLOCKED_TOKENS = ("submit", "password", "login")

_CANONICAL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _bad(name):
    raise ValueError("%s_REFUSED_BAD_TYPE:%s" % (PREFIX, name))


def _is_number(v):
    return not isinstance(v, bool) and isinstance(v, (int, float))


def _finite_number(v):
    """Type-safe finiteness: math.isfinite raises OverflowError on ints too
    large to convert to float; those refuse as bad input, never crash."""
    if not _is_number(v):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:
        return False


def _scan_blocked(mapping, fields):
    for key in mapping:
        if any(tok in str(key).strip().lower() for tok in BLOCKED_TOKENS):
            raise ValueError("%s_REFUSED_SUBMIT" % PREFIX)
    for f in fields:
        if any(tok in f.strip().lower() for tok in BLOCKED_TOKENS):
            raise ValueError("%s_REFUSED_SUBMIT" % PREFIX)


def _parse_date(value, name):
    """Canonical YYYY-MM-DD only. fromisoformat alone accepts basic
    (20261101) and ISO-week forms; mixed forms would sort lexicographically,
    not by actual time."""
    if isinstance(value, bool) or not isinstance(value, str):
        _bad(name)
    if not _CANONICAL_DATE.match(value):
        _bad(name)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _bad(name)


def run(request):
    """Build prefill packets, tracker rows, ranking and calendar.

    Raises ValueError('APPLY_REFUSED_<REASON>') on refusal; returns a plain
    deterministic dict on success.
    """
    if isinstance(request, bool) or not isinstance(request, dict):
        _bad("request")
    profile = request.get("profile")
    if isinstance(profile, bool) or not isinstance(profile, dict) or not profile:
        raise ValueError("%s_REFUSED_NOPROFILE" % PREFIX)
    if len(profile) > MAX_PROFILE_KEYS:
        raise ValueError("%s_REFUSED_OVERSIZE:profile" % PREFIX)
    clean_profile = {}
    for k, v in profile.items():
        key = policy.clean_text(k, PREFIX, "profile_key", 128)
        if isinstance(v, str):
            clean_profile[key] = policy.clean_text(v, PREFIX, "profile_value", 2000)
        elif _is_number(v):
            if not _finite_number(v):
                _bad("profile_value")
            clean_profile[key] = round(v, 6)
        else:
            _bad("profile_value")
    _scan_blocked(request, ())
    _scan_blocked(profile, ())
    as_of = _parse_date(request.get("as_of"), "as_of")
    as_of_text = policy.clean_text(request.get("as_of"), PREFIX, "as_of", 32)

    opps = request.get("opportunities")
    if isinstance(opps, bool) or not isinstance(opps, (list, tuple)):
        _bad("opportunities")
    if not opps:
        raise ValueError("%s_REFUSED_EMPTY:opportunities" % PREFIX)
    if len(opps) > MAX_OPPORTUNITIES:
        raise ValueError("%s_REFUSED_OVERSIZE:opportunities" % PREFIX)

    packets, tracker, ranked, unranked, calendar = [], [], [], [], []
    for row in opps:
        if isinstance(row, bool) or not isinstance(row, dict):
            _bad("opportunity")
        raw_fields = row.get("fields", [])
        if isinstance(raw_fields, bool) or not isinstance(raw_fields, (list, tuple)):
            _bad("fields")
        if len(raw_fields) > MAX_FIELDS:
            raise ValueError("%s_REFUSED_OVERSIZE:fields" % PREFIX)
        fields = [policy.clean_text(f, PREFIX, "field", 128) for f in raw_fields]
        _scan_blocked(row, fields)
        oid = policy.clean_text(row.get("id"), PREFIX, "id", 128)
        title = policy.clean_text(row.get("title"), PREFIX, "title", 256)
        deadline = _parse_date(row.get("deadline"), "deadline")
        deadline_text = policy.clean_text(row.get("deadline"), PREFIX, "deadline", 32)

        filled, missing, drafts = {}, [], []
        for f in fields:
            if f.strip().lower() in ESSAY_FIELDS:
                drafts.append(f)
            elif f in clean_profile:
                filled[f] = clean_profile[f]
            else:
                missing.append(f)
        packets.append({"id": oid, "title": title, "filled": filled,
                        "missing_fields": missing, "draft_required": drafts})

        days_left = (deadline - as_of).days
        if days_left < 0:
            status = "expired"
        elif missing:
            status = "needs_input"
        elif filled:
            status = "prefilled"
        else:
            status = "not_started"
        tracker.append({"id": oid, "title": title, "deadline": deadline_text,
                        "days_left": days_left, "status": status})
        calendar.append({"id": oid, "title": title, "deadline": deadline_text,
                         "days_left": days_left})

        present = [k for k in ("value", "p_win", "effort_hours") if k in row]
        if len(present) < 3:
            absent = next(k for k in ("value", "p_win", "effort_hours") if k not in row)
            unranked.append({"id": oid, "reason": "missing %s" % absent})
            continue
        value, p_win, effort = row["value"], row["p_win"], row["effort_hours"]
        if not _finite_number(value):
            _bad("value")
        if not _finite_number(p_win) or not 0 <= p_win <= 1:
            _bad("p_win")
        if not _finite_number(effort) or effort <= 0:
            _bad("effort_hours")
        try:
            score = round((value * p_win) / effort, 6)
            finite = math.isfinite(score)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("%s_REFUSED_NONFINITE:score" % PREFIX)
        ranked.append({"id": oid, "deadline": deadline_text, "score": score})

    ranked.sort(key=lambda r: (-r["score"], r["deadline"], r["id"]))
    calendar.sort(key=lambda c: (c["deadline"], c["id"]))
    return {
        "packets": packets,
        "tracker": tracker,
        "ranking": {"ranked": ranked, "unranked": unranked},
        "calendar": calendar,
        "scope": policy.scope(
            implemented=["prefill packets from supplied profile",
                         "tracker statuses {not_started, prefilled, needs_input, expired}",
                         "ranking by computed (value * p_win) / effort_hours",
                         "deadline calendar with days_left"],
            not_implemented=["true win probability - ranking is only as good as the supplied numbers",
                             "submission of any application - never submits (X6)",
                             "startup-grant matcher - separate later unit",
                             "opportunities beyond the supplied set - 'all opportunities on the internet' is substituted by the supplied set"],
            data_source="supplied-input",
            as_of=as_of_text,
        ),
    }
