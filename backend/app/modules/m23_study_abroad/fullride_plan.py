"""G117 / m23.fullride_plan - finished personal 100-country full-ride plan.

Composes fullride_corpus (the real 100+ country route corpus) with
s4_7_abroad_fullride (the constraint filter) into a finished, personal plan:
kept routes grouped by country with per-route actions, a milestone timeline
backwards from application season, profile gaps, and the excluded set with
reason codes. Deterministic, stdlib only; never applies or submits.
"""
from __future__ import annotations

import re

from app.modules.c30 import policy
from app.modules.m23_study_abroad import fullride_corpus, s4_7_abroad_fullride

PREFIX = "APPLY"


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _route_actions(row, profile):
    actions = ["read the official page and confirm current cycle rules",
               "prepare transcripts: CBSE Class X-XII marksheets (predicted if pending)"]
    if profile.get("sat") is None and profile.get("ielts") is None:
        actions.insert(0, "register for the SAT (or IELTS) - a test credential is required")
    if row["accepts_sat"] and profile.get("sat") is not None:
        actions.append("send SAT score via College Board when the portal opens")
    if "need" in row["scholarship"].casefold() or "aid" in row["scholarship"].casefold():
        actions.append("prepare financial-aid documents (income proofs, CSS/alternate forms)")
    actions.append("draft essays and activity list; owner reviews every word before use")
    return actions


def _timeline(as_of_year):
    """Months are named, not fabricated dates: standard application-season phases."""
    return [
        {"phase": "profile build", "window": "now - June %d" % as_of_year,
         "work": ["SAT attempt(s)", "activity consolidation", "research the kept-country rules"]},
        {"phase": "applications", "window": "August - January %d/%d" % (as_of_year, as_of_year + 1),
         "work": ["portals open; owner reviews and submits each application herself",
                  "aid documents filed alongside"]},
        {"phase": "decisions", "window": "March - April %d" % (as_of_year + 1),
         "work": ["compare aid letters line by line", "appeal weak offers with updated marks"]},
        {"phase": "visa + enrollment", "window": "May - August %d" % (as_of_year + 1),
         "work": ["accept one offer", "visa documentation from the admit country's official list"]},
    ]


def build_plan(profile, as_of):
    """The finished personal plan over the curated corpus."""
    if type(profile) is not dict or set(profile) - {"curriculum", "sat", "ielts"}:
        _refuse("BAD_TYPE", "profile")
    as_of_text = policy.clean_text(as_of, PREFIX, "as_of", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of_text):
        _refuse("BAD_TYPE", "as_of")
    rows = fullride_corpus.corpus_rows(as_of_text)
    filtered = s4_7_abroad_fullride.plan_full_rides(
        {"as_of": as_of_text, "profile": profile, "rows": rows})
    by_country = {}
    for row in filtered["kept"]:
        entry = by_country.setdefault(row["country"], {"country": row["country"], "routes": []})
        entry["routes"].append({
            "university": row["university"], "scholarship": row["scholarship"],
            "source_url": row["source_url"], "freshness": row["freshness"],
            "actions": _route_actions(row, profile)})
    for entry in by_country.values():
        entry["route_count"] = len(entry["routes"])
    countries = sorted(by_country.values(), key=lambda e: (-e["route_count"], e["country"]))
    gaps = []
    if profile.get("sat") is None:
        gaps.append("no SAT score in profile - every kept route assumes SAT or IELTS")
    if profile.get("ielts") is None:
        gaps.append("no IELTS in profile - fine where SAT suffices, but some portals prefer an English test")
    gaps.append("essays, activity list and recommendation letters are built per route before season")
    year = int(as_of_text[:4])
    return {
        "as_of": as_of_text,
        "profile": dict(profile),
        "countries_with_fitting_routes": len(countries),
        "total_fitting_routes": filtered["coverage"]["total_kept"],
        "countries": countries,
        "excluded": filtered["excluded"],
        "corpus_coverage": fullride_corpus.coverage(as_of_text),
        "timeline": _timeline(year),
        "gaps": gaps,
        "scope": policy.scope(
            ["finished personal plan over the curated 100+ country corpus",
             "per-route action lists from the profile's actual credentials",
             "season timeline, gaps, and the excluded set with reason codes"],
            ["per-row live re-verification of program flags (stated in corpus scope)",
             "applying or submitting - owner-gated forever"],
            "curated corpus + supplied profile", as_of_text),
    }
