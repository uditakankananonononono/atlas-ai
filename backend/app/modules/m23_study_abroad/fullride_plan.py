"""G117 / m23.fullride_plan - finished personal 100-country full-ride plan.

Composes fullride_corpus (the 100+ country route corpus) with
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

# Route-specific English-proficiency facts from the corpus evidence record.
# English proficiency is a SEPARATE credential from the SAT/ACT: for Harvard,
# Stanford and Yale the official pages state English-proficiency exams cannot
# meet the standardized-testing requirement. It is never presented as an
# alternative admission exam.
_ENGLISH_NOTES = {
    "Harvard University":
        "English proficiency: optional at Harvard - IELTS/TOEFL scores may be "
        "submitted, but English-proficiency exams cannot meet the "
        "standardized-testing requirement",
    "Yale University":
        "English proficiency: required at Yale for non-native speakers without "
        "2+ years of English-medium schooling (TOEFL/IELTS/Cambridge/DET/"
        "InitialView) - a separate credential, never a substitute for the SAT/ACT",
    "Princeton University":
        "English proficiency: required at Princeton when English is not the "
        "language of instruction (TOEFL/IELTS Academic/DET/PTE) - separate from "
        "the SAT/ACT",
    "Stanford University":
        "English proficiency: not required at Stanford; any English-proficiency "
        "exam may be self-reported - never a substitute for the SAT/ACT",
    "Rice University":
        "English proficiency: demonstration required at Rice - check the current "
        "minimum-score table on the official page (TOEFL reporting moved to the "
        "5.0 scale for tests after January 21, 2026) and whether a language "
        "waiver applies; separate from the SAT/ACT",
}


def _refuse(reason, field=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, reason, ":" + field if field else ""))


def _route_actions(row, profile):
    actions = ["read the official page and confirm current cycle rules",
               "prepare transcripts: CBSE Class X-XII marksheets (predicted if pending)"]
    if profile.get("sat") is None:
        if row["university"] == "Princeton University":
            actions.insert(0, "register for the SAT or ACT - at Princeton it is optional "
                              "for the 2026-27 cycle (fall 2027 entry) and required from "
                              "2027-28 (fall 2028 entry); every other kept route requires "
                              "a standardized-test credential; English-proficiency exams "
                              "(IELTS/TOEFL) never substitute for it")
        else:
            actions.insert(0, "register for the SAT or ACT - a standardized-test credential "
                              "is required at this route (Princeton is the exception: "
                              "optional for its 2026-27 cycle); English-proficiency exams "
                              "(IELTS/TOEFL) are a separate credential and never "
                              "substitute for it")
    if row["university"] == "Princeton University":
        actions.append("Princeton testing cycle: SAT/ACT optional for 2026-27 (fall 2027 "
                       "entry); required from 2027-28 (fall 2028 entry)")
    if row["accepts_sat"] and profile.get("sat") is not None:
        actions.append("send SAT score via College Board when the portal opens")
    english = _ENGLISH_NOTES.get(row["university"])
    if english:
        actions.append(english)
    award = fullride_corpus.award_type(row["university"])
    if award == "meets_full_demonstrated_need":
        actions.append("need-based coverage: the award equals assessed need - confirm the "
                       "family's assessed contribution before treating this as zero-cost")
        actions.append("prepare financial-aid documents (income proofs, CSS/alternate forms)")
    elif award == "full_cost_award":
        actions.append("merit full-cost award: check nomination and separate-application "
                       "requirements on the official page")
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
    rows_by_id = {r["id"]: r for r in rows}
    # The pinned planner's reason codes conflate unknown with ruled-out; the
    # corpus evidence record translates them at this boundary.
    excluded = [{"id": e["id"],
                 "reasons": fullride_corpus.translate_reasons(
                     rows_by_id[e["id"]]["university"], e["reasons"])}
                for e in filtered["excluded"]]
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
        gaps.append("no SAT score in profile - kept routes require a standardized-test "
                    "credential (SAT or ACT), with one cycle exception: Princeton is "
                    "test-optional for 2026-27 (fall 2027 entry) and requires it from "
                    "2027-28 (fall 2028 entry); English-proficiency exams (IELTS/TOEFL) "
                    "are a separate credential and never substitute for it")
    if profile.get("ielts") is None:
        gaps.append("no English-proficiency score in profile - required at Yale, "
                    "Princeton and Rice when schooling is not English-medium; optional "
                    "at Harvard and Stanford; a separate credential from the SAT/ACT")
    gaps.append("essays, activity list and recommendation letters are built per route before season")
    if any(fullride_corpus.award_type(r["university"]) == "meets_full_demonstrated_need"
           for c in countries for r in c["routes"]):
        gaps.append("need-based routes cover assessed need, not a fixed full ride - a "
                    "profile without assessed financial need is not covered to zero cost")
    year = int(as_of_text[:4])
    return {
        "as_of": as_of_text,
        "profile": dict(profile),
        "countries_with_fitting_routes": len(countries),
        "total_fitting_routes": filtered["coverage"]["total_kept"],
        "countries": countries,
        "excluded": excluded,
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
