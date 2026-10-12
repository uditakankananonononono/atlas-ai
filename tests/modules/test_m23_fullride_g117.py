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
    """A nonempty shared quote is never treated as proof of a different flag:
    each True credential/testing flag carries its own basis + URL."""
    for uni, ev in fc.EVIDENCE.items():
        assert ev["basis"] and ev["checked_url"].startswith("https://")
        for flag in ("accepts_cbse", "accepts_sat", "accepts_ielts"):
            fb = fc.flag_basis(uni, flag)
            if ev[flag]:
                assert fb and fb["basis"] and fb["url"].startswith("https://"), (uni, flag)
            else:
                # False = not established in this pass: no basis claimed
                assert fb is None, (uni, flag)
        if ev["requires_extra_written_test"] is False:
            fb = fc.flag_basis(uni, "requires_extra_written_test")
            if uni in FITTING or uni == "Yale University" or uni == "Brown University":
                assert fb and fb["basis"] and fb["url"], (uni, flag)


def test_flag_basis_matches_what_the_quote_establishes():
    """Spot-check that basis text names the exact flag it proves."""
    assert "national leaving exam" in fc.flag_basis("Harvard University", "accepts_cbse")["basis"]
    assert "CBSE X/AISSCE X" in fc.flag_basis("Rice University", "accepts_cbse")["basis"]
    assert "Std X/Std XII in India" in fc.flag_basis("Princeton University", "accepts_cbse")["basis"]
    assert "a preference for a specific curriculum" in fc.flag_basis("Stanford University", "accepts_cbse")["basis"]
    assert "IELTS" in fc.flag_basis("Rice University", "accepts_ielts")["basis"]
    assert "IELTS Academic" in fc.flag_basis("Princeton University", "accepts_ielts")["basis"]
    assert "IELTS" in fc.flag_basis("Yale University", "accepts_ielts")["basis"]
    assert "IELTS" in fc.flag_basis("Harvard University", "accepts_ielts")["basis"]


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
    assert "requires_extra_written_test" in by_uni["Chinese Government (CSC)"]
    assert "requires_extra_written_test" in by_uni["University of Oxford"]
    assert "not_full_ride" in by_uni["Hungarian Government"]
    assert "cbse_not_accepted" in by_uni["Massachusetts Institute of Technology"]
    assert "cbse_not_accepted" in by_uni["Yale University"]


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


def test_no_test_credential_refuses_and_plan_deterministic():
    with pytest.raises(ValueError, match="APPLY_REFUSED_PROFILE"):
        s47.plan_full_rides({"as_of": "2026-10-12",
                             "profile": {"curriculum": "CBSE"}, "rows": fc.corpus_rows()})
    assert fullride_plan.build_plan(PROFILE, "2026-10-12") == fullride_plan.build_plan(PROFILE, "2026-10-12")
