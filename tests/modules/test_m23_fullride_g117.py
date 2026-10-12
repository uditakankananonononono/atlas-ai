"""G117: evidence-gated full-ride corpus + personal plan (each True flag carries
its own official-page basis quote; False means not established in this pass)."""
from __future__ import annotations

import pytest

from app.modules.m23_study_abroad import fullride_corpus as fc
from app.modules.m23_study_abroad import fullride_plan
from app.modules.m23_study_abroad import s4_7_abroad_fullride as s47

PROFILE = {"curriculum": "CBSE", "sat": 1520}
FITTING = {"Harvard University", "Princeton University",
           "Stanford University", "Rice University"}
FLAGS = ("full_ride", "requires_extra_written_test", "accepts_cbse",
         "accepts_sat", "accepts_ielts")


def test_corpus_covers_100_plus_countries():
    cov = fc.coverage()
    assert cov["rows"] == 126
    assert cov["countries_covered"] >= 100


def test_verified_and_fitting_counts_are_honest():
    cov = fc.coverage()
    assert cov["verified_routes"] == 14
    assert cov["verified_full_ride_no_extra_test_routes"] == 4
    assert cov["verified_full_ride_no_extra_test_countries"] == 1
    assert cov["fitting_countries"] == ["United States"]
    assert cov["fitting_by_award_type"] == {"meets_full_demonstrated_need": 4,
                                            "full_cost_award": 0}
    assert "not established" in cov["verification"]
    assert "never rejected" in cov["verification"]


def test_every_true_flag_has_its_own_basis_quote():
    """No fallback: EVERY True flag across all 5 flag fields, on every evidence
    row, must physically carry its own nonempty basis entry with a URL. A
    nonempty shared string never masquerades as a flag record."""
    for uni, ev in fc.EVIDENCE.items():
        for flag in FLAGS:
            fb = fc.flag_basis(uni, flag)
            if ev[flag] is True:
                assert fb is not None, (uni, flag)
                assert fb["basis"].strip() and fb["url"].startswith("https://"), (uni, flag)
            else:
                # False flags may carry a published-process basis (e.g. a verified
                # no-extra-test page) but never require one
                if fb is not None:
                    assert fb["basis"].strip() and fb["url"].startswith("https://")


def test_full_ride_projection_is_explicit_per_row():
    for uni, ev in fc.EVIDENCE.items():
        fb = fc.flag_basis(uni, "full_ride")
        if ev["full_ride"]:
            assert fb is not None and fb["basis"] == ev["basis"]
            assert fb["url"] == ev["checked_url"]
        else:
            assert fb is None, uni


def test_quotes_are_verbatim_and_inference_is_labeled():
    """Basis strings hold source text only; any reading we add sits in the
    labeled inference field, never blended into the quote."""
    harvard_cbse = fc.flag_basis("Harvard University", "accepts_cbse")
    assert harvard_cbse["basis"].endswith("national leaving exam predictions or results")
    assert "CBSE" not in harvard_cbse["basis"]
    assert "CBSE" in harvard_cbse["inference"]
    stanford_cbse = fc.flag_basis("Stanford University", "accepts_cbse")
    assert stanford_cbse["basis"] == ("We do not have a preference for a specific "
                                      "curriculum (A-Level, IB, AP, National, etc.)")
    assert "CBSE" in stanford_cbse["inference"]
    stanford_ielts = fc.flag_basis("Stanford University", "accepts_ielts")
    assert "IELTS" not in stanford_ielts["basis"]
    assert "IELTS" in stanford_ielts["inference"]
    for uni, ev in fc.EVIDENCE.items():
        for rec in ev.get("flag_basis", {}).values():
            if "inference" in rec:
                assert rec["inference"] not in rec["basis"]


def test_flag_basis_matches_what_the_quote_establishes():
    """Spot-check that basis text names the exact flag it proves."""
    assert "national leaving exam" in fc.flag_basis("Harvard University", "accepts_cbse")["basis"]
    assert "CBSE X/AISSCE X" in fc.flag_basis("Rice University", "accepts_cbse")["basis"]
    assert "Std X/Std XII in India" in fc.flag_basis("Princeton University", "accepts_cbse")["basis"]
    assert "IELTS" in fc.flag_basis("Rice University", "accepts_ielts")["basis"]
    assert "IELTS Academic" in fc.flag_basis("Princeton University", "accepts_ielts")["basis"]
    assert "IELTS" in fc.flag_basis("Yale University", "accepts_ielts")["basis"]
    assert "IELTS" in fc.flag_basis("Harvard University", "accepts_ielts")["basis"]
    assert "2027-28" in fc.flag_basis("Princeton University", "accepts_sat")["basis"]
    assert "remains test optional" in fc.flag_basis("Princeton University", "accepts_sat")["basis"]
    oxford = fc.flag_basis("University of Oxford", "requires_extra_written_test")
    assert oxford and "admissions tests" in oxford["basis"]
    china = fc.flag_basis("Chinese Government (CSC)", "requires_extra_written_test")
    assert china and "CSCA" in china["basis"]


def test_flag_status_distinguishes_negative_from_not_established():
    assert fc.flag_status("Hungarian Government", "full_ride") == "established_negative"
    assert fc.flag_status("Hungarian Government", "accepts_cbse") == "not_established"
    assert fc.flag_status("Yale University", "accepts_cbse") == "not_established"
    assert fc.flag_status("Rice University", "accepts_cbse") == "evidenced_true"


def test_yale_not_fitting_until_cbse_basis_exists():
    """Yale evidences SAT + IELTS but no CBSE-acceptance quote this pass, so it
    is excluded - 'not established' is never coerced to True."""
    row = next(r for r in fc.corpus_rows() if r["university"] == "Yale University")
    assert row["accepts_sat"] and row["accepts_ielts"] and not row["accepts_cbse"]
    out = s47.plan_full_rides({"as_of": "2026-10-12", "profile": PROFILE,
                               "rows": fc.corpus_rows()})
    assert "Yale University" not in {k["university"] for k in out["kept"]}


def test_rows_mirror_evidence_only():
    for row in fc.corpus_rows():
        ev = fc.EVIDENCE.get(row["university"])
        if ev is None:
            assert not any(row[f] for f in FLAGS), row
        else:
            for flag in FLAGS:
                assert row[flag] is ev[flag]
            assert row["fetched_at"] == "2026-10-12"


def test_award_type_schema_distinguishes_need_based_from_full_cost():
    for uni in FITTING:
        assert fc.award_type(uni) == "meets_full_demonstrated_need"
    assert fc.award_type("Berea College") == "full_cost_award"
    assert fc.award_type("University of Toronto") == "full_cost_award"
    assert "qualifies for financial assistance" in fc.EVIDENCE["Stanford University"]["basis"]
    assert "$100,000 family income and below" in fc.EVIDENCE["Harvard University"]["basis"]
    assert "school nomination" in fc.EVIDENCE["University of Toronto"]["basis"]


def test_corrections_are_encoded():
    ev = fc.EVIDENCE
    assert ev["Hungarian Government"]["full_ride"] is False
    assert "does not fully cover all costs of living" in ev["Hungarian Government"]["basis"]
    assert ev["Chinese Government (CSC)"]["requires_extra_written_test"] is True
    assert "CSCA" in ev["Chinese Government (CSC)"]["basis"]
    kz = [r for r in fc.corpus_rows() if r["country"] == "Kazakhstan"]
    assert "Bolashak is the citizen outbound" in kz[0]["scholarship"]
    assert ev["University of Oxford"]["requires_extra_written_test"] is True


def test_s47_keeps_only_routes_with_full_flag_evidence():
    out = s47.plan_full_rides({"as_of": "2026-10-12", "profile": PROFILE,
                               "rows": fc.corpus_rows()})
    assert {k["university"] for k in out["kept"]} == FITTING
    assert len(out["kept"]) + len(out["excluded"]) == 126
    by_uni = {r["university"]: e["reasons"]
              for e in out["excluded"]
              for r in fc.corpus_rows() if r["id"] == e["id"]}
    # pinned planner codes (flat; conflation is translated at the consumer boundary)
    assert "requires_extra_written_test" in by_uni["Chinese Government (CSC)"]
    assert "requires_extra_written_test" in by_uni["University of Oxford"]
    assert "not_full_ride" in by_uni["Hungarian Government"]
    assert "cbse_not_accepted" in by_uni["Massachusetts Institute of Technology"]


def test_plan_boundary_translates_reason_codes():
    """The consumer translates the pinned flat codes: established-negative only
    where the official page contradicts the flag, otherwise not-established."""
    plan = fullride_plan.build_plan(PROFILE, "2026-10-12")
    by_uni = {r["university"]: e["reasons"]
              for e in plan["excluded"]
              for r in fc.corpus_rows() if r["id"] == e["id"]}
    assert "full_ride_established_negative" in by_uni["Hungarian Government"]
    assert "not_full_ride" not in by_uni["Hungarian Government"]
    assert "cbse_not_established" in by_uni["Yale University"]
    assert "cbse_not_established" in by_uni["Massachusetts Institute of Technology"]
    assert "cbse_not_accepted" not in by_uni["Yale University"]
    assert "requires_extra_written_test" in by_uni["University of Oxford"]
    assert fc.translate_reasons("Hungarian Government", ["not_full_ride"]) == [
        "full_ride_established_negative"]
    assert fc.translate_reasons("Yale University", ["cbse_not_accepted"]) == [
        "cbse_not_established"]


def test_plan_text_is_award_type_honest():
    plan = fullride_plan.build_plan(PROFILE, "2026-10-12")
    assert plan["countries_with_fitting_routes"] == 1
    assert plan["total_fitting_routes"] == 4
    us = plan["countries"][0]
    for route in us["routes"]:
        assert any("need-based coverage" in a for a in route["actions"])
        assert any("financial-aid documents" in a for a in route["actions"])
    assert any("need-based routes cover assessed need, not a fixed full ride" in g
               for g in plan["gaps"])
    assert plan["corpus_coverage"]["fitting_by_award_type"]["meets_full_demonstrated_need"] == 4


def test_plan_never_presents_ielts_as_an_admission_exam():
    """Standardized-test credential and English-proficiency credential are
    separate in actions and gaps; IELTS is never offered as an SAT substitute."""
    plan = fullride_plan.build_plan(PROFILE, "2026-10-12")
    texts = [a for c in plan["countries"] for r in c["routes"] for a in r["actions"]]
    texts += plan["gaps"]
    assert not any("(or IELTS)" in t for t in texts)
    assert not any("assumes SAT or IELTS" in t for t in texts)
    for c in plan["countries"]:
        for r in c["routes"]:
            assert any(a.startswith("English proficiency:") for a in r["actions"]), r
    princeton = next(r for c in plan["countries"] for r in c["routes"]
                     if r["university"] == "Princeton University")
    assert any("optional for 2026-27 (fall 2027 entry)" in a and
               "required from 2027-28 (fall 2028 entry)" in a
               for a in princeton["actions"])


def test_plan_without_sat_requires_standardized_credential_not_english():
    plan = fullride_plan.build_plan({"curriculum": "CBSE", "ielts": 8}, "2026-10-12")
    texts = plan["gaps"] + [a for c in plan["countries"]
                            for r in c["routes"] for a in r["actions"]]
    assert any("register for the SAT or ACT" in g and "never substitute" in g
               for g in texts)
    # the generic required wording never contradicts Princeton's cycle line
    assert not any("required for every kept route" in g for g in texts)
    princeton = next(r for c in plan["countries"] for r in c["routes"]
                     if r["university"] == "Princeton University")
    assert any("optional" in a and "2026-27" in a for a in princeton["actions"])
    assert any("test-optional for 2026-27" in g for g in plan["gaps"])


def test_rice_english_note_carries_no_hardcoded_thresholds():
    """Thresholds move (TOEFL 5.0 scale from January 2026): the note references
    the current official table instead of freezing numbers."""
    note = fullride_plan._ENGLISH_NOTES["Rice University"]
    assert "TOEFL 100" not in note and "IELTS 7" not in note and "Duolingo 130" not in note
    assert "official page" in note and "waiver" in note


def test_no_test_credential_refuses_and_plan_deterministic():
    with pytest.raises(ValueError, match="APPLY_REFUSED_PROFILE"):
        s47.plan_full_rides({"as_of": "2026-10-12",
                             "profile": {"curriculum": "CBSE"}, "rows": fc.corpus_rows()})
    assert fullride_plan.build_plan(PROFILE, "2026-10-12") == fullride_plan.build_plan(PROFILE, "2026-10-12")
