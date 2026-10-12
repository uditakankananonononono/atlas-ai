"""G117: evidence-gated full-ride corpus + personal plan (B8 re-audit of 2026-10-12)."""
from __future__ import annotations

import pytest

from app.modules.m23_study_abroad import fullride_corpus as fc
from app.modules.m23_study_abroad import fullride_plan
from app.modules.m23_study_abroad import s4_7_abroad_fullride as s47

PROFILE = {"curriculum": "CBSE", "sat": 1520}


def test_corpus_covers_100_plus_countries():
    cov = fc.coverage()
    assert cov["rows"] == 126
    assert cov["countries_covered"] >= 100
    assert cov["verified_at"] == "2026-10-12"


def test_verified_count_is_honest_and_small():
    cov = fc.coverage()
    assert cov["verified_routes"] == 14  # 12 verified + 2 evidence-backed corrections
    assert cov["verified_full_ride_no_extra_test_routes"] == 11
    assert cov["verified_full_ride_no_extra_test_countries"] == 2
    assert cov["fitting_countries"] == ["Canada", "United States"]
    assert cov["not_established_rows"] == 126 - 14


def test_flags_come_from_evidence_only():
    for row in fc.corpus_rows():
        ev = fc.EVIDENCE.get(row["university"])
        if ev is None:
            assert not any([row["full_ride"], row["accepts_cbse"], row["accepts_sat"],
                            row["accepts_ielts"]]), row
        else:
            assert row["full_ride"] is ev["full_ride"]
            assert row["requires_extra_written_test"] is ev["requires_extra_written_test"]
            assert ev["basis"] and ev["checked_url"].startswith("https://")


def test_auditor_corrections_are_encoded():
    ev = fc.EVIDENCE
    assert ev["Hungarian Government"]["full_ride"] is False
    assert "does not fully cover all costs of living" in ev["Hungarian Government"]["basis"]
    assert ev["Chinese Government (CSC)"]["requires_extra_written_test"] is True
    assert "CSCA" in ev["Chinese Government (CSC)"]["basis"]
    kz = [r for r in fc.corpus_rows() if r["country"] == "Kazakhstan"]
    assert len(kz) == 1 and "Bolashak is the citizen outbound" in kz[0]["scholarship"]
    assert kz[0]["full_ride"] is False
    assert ev["University of Oxford"]["requires_extra_written_test"] is True  # admissions tests


def test_s47_keeps_only_evidence_verified_fitting_routes():
    out = s47.plan_full_rides({"as_of": "2026-10-12", "profile": PROFILE,
                               "rows": fc.corpus_rows()})
    assert len(out["kept"]) == 11
    assert out["coverage"]["us_universities_kept"] == 10
    assert {k["country"] for k in out["kept"]} == {"United States", "Canada"}
    for kept in out["kept"]:
        assert kept["university"] in fc.EVIDENCE
    assert len(out["kept"]) + len(out["excluded"]) == 126


def test_excluded_carry_reasons_including_test_flag():
    out = s47.plan_full_rides({"as_of": "2026-10-12", "profile": PROFILE,
                               "rows": fc.corpus_rows()})
    by_id = {r["university"]: e for r, e in
             [(next(r for r in fc.corpus_rows() if r["id"] == e["id"]), e)
              for e in out["excluded"]]}
    assert "requires_extra_written_test" in by_id["Chinese Government (CSC)"]["reasons"]
    assert "requires_extra_written_test" in by_id["University of Oxford"]["reasons"]
    assert "not_full_ride" in by_id["Hungarian Government"]["reasons"]


def test_finished_plan_reflects_verified_routes_only():
    plan = fullride_plan.build_plan(PROFILE, "2026-10-12")
    assert plan["countries_with_fitting_routes"] == 2
    assert plan["total_fitting_routes"] == 11
    us = next(c for c in plan["countries"] if c["country"] == "United States")
    assert us["route_count"] == 10
    for country in plan["countries"]:
        for route in country["routes"]:
            assert route["actions"] and route["source_url"].startswith("https://")
    assert plan["corpus_coverage"]["verified_routes"] == 14


def test_no_test_credential_refuses_and_plan_deterministic():
    with pytest.raises(ValueError, match="APPLY_REFUSED_PROFILE"):
        s47.plan_full_rides({"as_of": "2026-10-12",
                             "profile": {"curriculum": "CBSE"}, "rows": fc.corpus_rows()})
    a = fullride_plan.build_plan(PROFILE, "2026-10-12")
    b = fullride_plan.build_plan(PROFILE, "2026-10-12")
    assert a == b
