"""G117: full-ride corpus + personal plan over real 100+ country routes."""
from __future__ import annotations

import pytest

from app.modules.m23_study_abroad import fullride_corpus, fullride_plan
from app.modules.m23_study_abroad import s4_7_abroad_fullride as s47


def test_corpus_covers_100_plus_countries():
    cov = fullride_corpus.coverage()
    assert cov["countries_covered"] >= 100
    assert cov["rows"] >= 100
    assert cov["verification"].startswith("flags curated")


def test_corpus_rows_match_s47_schema_and_pass_validation():
    rows = fullride_corpus.corpus_rows()
    out = s47.plan_full_rides({"as_of": "2026-10-12",
                               "profile": {"curriculum": "CBSE", "sat": 1520}, "rows": rows})
    # true invariant over the pinned s4_7: every input row lands kept or excluded
    assert len(out["kept"]) + len(out["excluded"]) == len(rows)
    assert out["coverage"]["total_kept"] > 0
    assert out["coverage"]["achieved_countries"] >= 20
    for kept in out["kept"]:
        assert kept["full_ride"] and not kept["requires_extra_written_test"]
        assert kept["accepts_cbse"] and kept["accepts_sat"]


def test_exclusions_carry_real_reasons():
    rows = fullride_corpus.corpus_rows()
    out = s47.plan_full_rides({"as_of": "2026-10-12",
                               "profile": {"curriculum": "CBSE", "sat": 1520}, "rows": rows})
    reasons = {r for e in out["excluded"] for r in e["reasons"]}
    assert "not_full_ride" in reasons
    assert "requires_extra_written_test" in reasons  # MEXT and Russia honestly excluded


def test_ielts_only_profile_still_fits():
    rows = fullride_corpus.corpus_rows()
    out = s47.plan_full_rides({"as_of": "2026-10-12",
                               "profile": {"curriculum": "CBSE", "ielts": 7.5}, "rows": rows})
    assert out["coverage"]["total_kept"] > 0
    for kept in out["kept"]:
        assert kept["accepts_ielts"]


def test_no_test_credential_refuses():
    with pytest.raises(ValueError, match="APPLY_REFUSED_PROFILE"):
        s47.plan_full_rides({"as_of": "2026-10-12",
                             "profile": {"curriculum": "CBSE"}, "rows": fullride_corpus.corpus_rows()})


def test_finished_plan_is_personal_and_complete():
    plan = fullride_plan.build_plan({"curriculum": "CBSE", "sat": 1520}, "2026-10-12")
    assert plan["countries_with_fitting_routes"] >= 20
    us = next(c for c in plan["countries"] if c["country"] == "United States")
    assert us["route_count"] >= 10  # "unlimited colleges in the US" lane
    for country in plan["countries"]:
        for route in country["routes"]:
            assert route["actions"] and route["source_url"].startswith("https://")
            assert any("CBSE" in a for a in route["actions"])
    assert [p["phase"] for p in plan["timeline"]] == ["profile build", "applications",
                                                      "decisions", "visa + enrollment"]
    assert plan["gaps"]
    assert plan["corpus_coverage"]["countries_covered"] >= 100


def test_plan_deterministic():
    a = fullride_plan.build_plan({"curriculum": "CBSE", "sat": 1520}, "2026-10-12")
    b = fullride_plan.build_plan({"curriculum": "CBSE", "sat": 1520}, "2026-10-12")
    assert a == b
