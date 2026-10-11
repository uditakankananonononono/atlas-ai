"""S4.7 abroad-fullride-planner tests. Stdlib only, hermetic.

Pins the U32-stricter filter: full rides only, no additional written tests,
CBSE marks + SAT or IELTS (IELTS "maybe"). Rows are caller-supplied from
public sourced pages; each row carries source_url + fetched_at and freshness
is graded by composing m23 source_freshness (recorded-check age only, never
verification). Coverage is reported, never claimed: target 100 countries,
achieved N. Planner only - never applies, submits or spends.
"""
import pytest

from app.modules.m23_study_abroad.s4_7_abroad_fullride import plan_full_rides

BASE = {"as_of": "2026-10-11", "profile": {"curriculum": "CBSE", "sat": 1520}}


def row(rid, country="Canada", university="U of Toronto", scholarship="Lester B. Pearson",
        url="https://www.utoronto.ca/pearson", fetched="2026-10-01", full_ride=True,
        extra_test=False, cbse=True, sat=True, ielts=True):
    return {"id": rid, "country": country, "university": university, "scholarship": scholarship,
            "source_url": url, "fetched_at": fetched, "full_ride": full_ride,
            "requires_extra_written_test": extra_test, "accepts_cbse": cbse,
            "accepts_sat": sat, "accepts_ielts": ielts}


def refuses(code, payload):
    with pytest.raises(ValueError) as exc:
        plan_full_rides(payload)
    assert str(exc.value) == code


class TestGoldenPath:
    def test_keeps_only_full_ride_no_extra_test_cbse_plus_sat_or_ielts(self):
        r = plan_full_rides(dict(BASE, rows=[
            row("k1"),
            row("x1", full_ride=False),
            row("x2", extra_test=True),
            row("x3", cbse=False),
            row("x4", sat=False, ielts=False),
            row("k2", country="United States", university="MIT", scholarship="need-blind full-need",
                url="https://mitadmissions.org/afford", sat=True, ielts=False)]))
        assert [k["id"] for k in r["kept"]] == ["k1", "k2"]
        reasons = {e["id"]: e["reasons"] for e in r["excluded"]}
        assert reasons == {"x1": ["not_full_ride"], "x2": ["requires_extra_written_test"],
                           "x3": ["cbse_not_accepted"], "x4": ["test_credential_not_accepted"]}

    def test_multiple_exclusion_reasons_ordered(self):
        r = plan_full_rides(dict(BASE, rows=[row("x", full_ride=False, extra_test=True,
                                                 cbse=False, sat=False, ielts=False)]))
        assert r["excluded"] == [{"id": "x", "reasons": ["not_full_ride",
                                                         "requires_extra_written_test",
                                                         "cbse_not_accepted",
                                                         "test_credential_not_accepted"]}]
        assert r["kept"] == []
        assert r["freshness"] == {"counts": {"fresh": 0, "stale": 0, "unknown": 0},
                                  "max_age_days": 180, "limits": ["no kept rows to grade"]}

    def test_coverage_is_computed_not_claimed(self):
        r = plan_full_rides(dict(BASE, rows=[
            row("a", country="United States", university="MIT"),
            row("b", country="United States", university="Yale"),
            row("c", country="Canada"), row("d", country="Germany", university="TU Munich")]))
        cov = r["coverage"]
        assert cov["target_countries"] == 100 and cov["achieved_countries"] == 3
        assert cov["countries"] == ["Canada", "Germany", "United States"]
        assert cov["us_universities_kept"] == 2 and cov["non_us_countries_kept"] == 2
        assert cov["total_rows"] == 4 and cov["total_kept"] == 4

    def test_scope_honesty_block(self):
        r = plan_full_rides(dict(BASE, rows=[row("k")]))
        scope = r["scope"]
        assert set(scope) == {"implemented", "not_implemented", "data_source", "as_of"}
        assert scope["data_source"] == "supplied" and scope["as_of"] == "2026-10-11"
        assert any("never applies" in s for s in scope["not_implemented"])


class TestFreshnessComposition:
    def test_fresh_stale_unknown_graded_by_recorded_check_age(self):
        r = plan_full_rides(dict(BASE, rows=[
            row("fresh", fetched="2026-10-01T12:00:00+00:00"),
            row("stale", fetched="2025-01-01T00:00:00+00:00"),
            row("unknown", fetched="not-a-date")]))
        status = {k["id"]: (k["freshness"]["status"], k["freshness"]["reason"]) for k in r["kept"]}
        assert status["fresh"] == ("fresh", "checked_within_max_age")
        assert status["stale"] == ("stale", "older_than_max_age")
        assert status["unknown"][0] == "unknown"
        assert r["freshness"]["counts"] == {"fresh": 1, "stale": 1, "unknown": 1}

    def test_future_check_is_unknown(self):
        r = plan_full_rides(dict(BASE, rows=[row("fut", fetched="2027-01-01T00:00:00+00:00")]))
        assert r["kept"][0]["freshness"]["status"] == "unknown"
        assert r["kept"][0]["freshness"]["reason"] == "timestamp_future"


class TestProfileGates:
    def test_non_cbse_refused(self):
        refuses("APPLY_REFUSED_PROFILE:curriculum_must_be_CBSE",
                dict(BASE, profile={"curriculum": "IB", "sat": 1520}, rows=[row("k")]))

    def test_sat_only_profile_excludes_ielts_only_rows(self):
        ielts_only = row("ielts-only", sat=False, ielts=True)
        r = plan_full_rides(dict(BASE, rows=[ielts_only, row("sat-ok", ielts=False)]))
        assert [k["id"] for k in r["kept"]] == ["sat-ok"]
        assert r["excluded"] == [{"id": "ielts-only", "reasons": ["test_credential_not_accepted"]}]
        both = plan_full_rides({"as_of": BASE["as_of"],
                                "profile": {"curriculum": "CBSE", "sat": 1520, "ielts": 8.0},
                                "rows": [ielts_only]})
        assert [k["id"] for k in both["kept"]] == ["ielts-only"]

    def test_needs_sat_or_ielts(self):
        refuses("APPLY_REFUSED_PROFILE:cbse_plus_sat_or_ielts_required",
                dict(BASE, profile={"curriculum": "CBSE"}, rows=[row("k")]))
        r = plan_full_rides(dict(BASE, profile={"curriculum": "CBSE", "ielts": 8.0}, rows=[row("k")]))
        assert [k["id"] for k in r["kept"]] == ["k"]

    def test_sat_range(self):
        refuses("APPLY_REFUSED_OUT_OF_RANGE:sat",
                dict(BASE, profile={"curriculum": "CBSE", "sat": 1700}, rows=[row("k")]))
        refuses("APPLY_REFUSED_BAD_TYPE:sat",
                dict(BASE, profile={"curriculum": "CBSE", "sat": True}, rows=[row("k")]))


class TestBoundaryPins:
    def test_exact_bounds_accepted(self):
        payload = dict(BASE, profile={"curriculum": "CBSE", "sat": 400}, rows=[row("lo")])
        assert plan_full_rides(payload)["coverage"]["total_kept"] == 1
        payload["profile"] = {"curriculum": "CBSE", "sat": 1600, "ielts": 9}
        assert plan_full_rides(payload)["coverage"]["total_kept"] == 1
        payload["profile"] = {"curriculum": "CBSE", "ielts": 0}
        assert plan_full_rides(payload)["coverage"]["total_kept"] == 1
        payload["profile"] = {"curriculum": "CBSE", "sat": 1500}
        payload["max_age_days"] = 3650
        assert plan_full_rides(payload)["freshness"]["max_age_days"] == 3650

    def test_exactly_5000_rows_accepted(self):
        r = plan_full_rides(dict(BASE, rows=[row("r%04d" % i, fetched="2026-10-01T00:00:00+00:00")
                                             for i in range(5000)]))
        assert r["coverage"]["total_rows"] == 5000 and r["coverage"]["total_kept"] == 5000
        assert r["freshness"]["counts"] == {"fresh": 5000, "stale": 0, "unknown": 0}

    def test_single_slash_https_refused(self):
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("k", url="https:/single-slash.example.com/x")]))

    def test_kept_sort_is_country_university_id(self):
        r = plan_full_rides(dict(BASE, rows=[
            row("a1", country="Zambia", university="Zed U"),
            row("z1", country="Australia", university="Aussie U"),
            row("m1", country="Australia", university="Monash")]))
        assert [k["id"] for k in r["kept"]] == ["z1", "m1", "a1"]

    def test_us_count_discriminated(self):
        r = plan_full_rides(dict(BASE, rows=[
            row("u", country="United States", university="Yale"),
            row("c1", country="Canada"), row("c2", country="Germany", university="TU Munich")]))
        cov = r["coverage"]
        assert cov["us_universities_kept"] == 1 and cov["non_us_countries_kept"] == 2
        assert cov["achieved_countries"] == 3


class TestRefusals:
    def test_spend_and_submit_refused(self):
        for key in ("purchase", "spend", "pay", "fee_payment"):
            refuses("APPLY_REFUSED_SPEND:s4_7_is_a_planner_no_spend",
                    dict(BASE, rows=[row("k")], **{key: True}))
        for key in ("submit", "apply", "send", "auto_apply"):
            refuses("APPLY_REFUSED_SUBMIT:s4_7_plans_only_never_applies",
                    dict(BASE, rows=[row("k")], **{key: True}))

    def test_non_public_source_refused(self):
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("k", url="http://insecure.example.com/x")]))

    def test_overcap(self):
        refuses("APPLY_REFUSED_OVERCAP:max_5000_rows",
                dict(BASE, rows=[row("r%04d" % i) for i in range(5001)]))

    def test_validation(self):
        refuses("APPLY_REFUSED_BAD_TYPE:payload", "nope")
        refuses("APPLY_REFUSED_UNKNOWN_FIELDS:payload", dict(BASE, rows=[row("k")], mystery=1))
        refuses("APPLY_REFUSED_EMPTY_FIELD:rows", dict(BASE, rows=[]))
        refuses("APPLY_REFUSED_BAD_TYPE:rows", dict(BASE, rows={}))
        refuses("APPLY_REFUSED_DUPLICATE:dup", dict(BASE, rows=[row("dup"), row("dup")]))
        refuses("APPLY_REFUSED_BAD_TYPE:full_ride",
                dict(BASE, rows=[row("k", full_ride=1)]))
        refuses("APPLY_REFUSED_UNKNOWN_FIELDS:row[extra]",
                dict(BASE, rows=[dict(row("k"), extra=1)]))
        refuses("APPLY_REFUSED_EMPTY_FIELD:country",
                dict(BASE, rows=[row("k", country="")]))
        refuses("APPLY_REFUSED_UNSAFE_CHARS:university",
                dict(BASE, rows=[row("k", university="Bad Name")]))
        refuses("APPLY_REFUSED_BAD_TYPE:fetched_at",
                dict(BASE, rows=[row("k", fetched=20240101)]))
        refuses("APPLY_REFUSED_BAD_TYPE:as_of", dict(BASE, as_of=20261011, rows=[row("k")]))
        refuses("APPLY_REFUSED_BAD_DATE:as_of", dict(BASE, as_of="11/10/2026", rows=[row("k")]))


class TestDeterminism:
    def test_same_payload_same_result(self):
        payload = dict(BASE, rows=[row("b", fetched="2025-06-01"), row("a"), row("c", cbse=False)])
        assert plan_full_rides(payload) == plan_full_rides(payload)
        r = plan_full_rides(payload)
        assert [k["id"] for k in r["kept"]] == ["a", "b"]
        assert [e["id"] for e in r["excluded"]] == ["c"]


# ---- repair: non-finite IELTS refused ----
class TestRepairNonFiniteIelts:
    def test_nan_ielts_refused(self):
        refuses("APPLY_REFUSED_OUT_OF_RANGE:ielts",
                dict(BASE, profile={"curriculum": "CBSE", "ielts": float("nan")}, rows=[row("k")]))

    def test_inf_ielts_refused(self):
        for bad in (float("inf"), float("-inf")):
            refuses("APPLY_REFUSED_OUT_OF_RANGE:ielts",
                    dict(BASE, profile={"curriculum": "CBSE", "ielts": bad}, rows=[row("k")]))


# ---- repair: exact-type dicts and no format (Cf) characters ----
class TestRepairExactTypeAndFormatChars:
    def test_dict_subclass_refused(self):
        class D(dict):
            pass
        refuses("APPLY_REFUSED_BAD_TYPE:payload", D(BASE, rows=[row("k")]))
        refuses("APPLY_REFUSED_BAD_TYPE:profile",
                dict(BASE, profile=D(curriculum="CBSE", sat=1520), rows=[row("k")]))
        refuses("APPLY_REFUSED_BAD_TYPE:rows[0]", dict(BASE, rows=[D(row("k"))]))

    def test_format_characters_refused_in_text_fields(self):
        zw = "\u200b"   # zero-width space (Cf)
        for field in ("id", "country", "university", "scholarship"):
            r = row("k")
            refuses("APPLY_REFUSED_UNSAFE_CHARS:%s" % field,
                    dict(BASE, rows=[dict(r, **{field: r[field] + zw})]))


# ---- boundary pins (row cap 5000/5001 pinned above) ----
class TestRowCapAndLimitPins:
    @pytest.mark.parametrize("field", ["country", "university", "scholarship"])
    def test_max_text_200_accepted_201_refused(self, field):
        assert plan_full_rides(dict(BASE, rows=[dict(row("k"), **{field: "a" * 200})]))["coverage"]["total_kept"] == 1
        refuses("APPLY_REFUSED_EMPTY_FIELD:%s" % field,
                dict(BASE, rows=[dict(row("k"), **{field: "a" * 201})]))

    def test_curriculum_cap_32_and_cbse_refusal_flip(self):
        refuses("APPLY_REFUSED_PROFILE:curriculum_must_be_CBSE",
                dict(BASE, profile={"curriculum": "CBSE" + "x" * 28, "sat": 1520}, rows=[row("k")]))  # 32: inside cap
        refuses("APPLY_REFUSED_EMPTY_FIELD:curriculum",
                dict(BASE, profile={"curriculum": "CBSE" + "x" * 29, "sat": 1520}, rows=[row("k")]))  # 33: cap refusal

    def test_unknown_profile_key_refused(self):
        refuses("APPLY_REFUSED_UNKNOWN_FIELDS:profile[mystery]",
                dict(BASE, profile={"curriculum": "CBSE", "sat": 1520, "mystery": 1}, rows=[row("k")]))

    def test_source_url_length_and_host_dot(self):
        long_url = "https://www.example.com/" + "a" * (2048 - len("https://www.example.com/"))
        assert len(long_url) == 2048
        assert plan_full_rides(dict(BASE, rows=[row("k", url=long_url)]))["coverage"]["total_kept"] == 1
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("k", url=long_url + "a")]))
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("k", url="https://nodothere")]))
        assert plan_full_rides(dict(BASE, rows=[row("k", url="https://a.b")]))["coverage"]["total_kept"] == 1

    def test_max_age_days_bounds(self):
        refuses("APPLY_REFUSED_OUT_OF_RANGE:max_age_days", dict(BASE, rows=[row("k")], max_age_days=0))
        assert plan_full_rides(dict(BASE, rows=[row("k")], max_age_days=1))["freshness"]["max_age_days"] == 1
        assert plan_full_rides(dict(BASE, rows=[row("k")], max_age_days=3650))["freshness"]["max_age_days"] == 3650
        refuses("APPLY_REFUSED_OUT_OF_RANGE:max_age_days", dict(BASE, rows=[row("k")], max_age_days=3651))

    @pytest.mark.parametrize("n", [499, 500, 501, 1000])
    def test_chunk_loop_grades_all_kept_rows(self, n):
        rows = [row("c%04d" % i, fetched="2026-10-01T00:00:00+00:00") for i in range(n)]
        r = plan_full_rides(dict(BASE, rows=rows))
        assert r["coverage"]["total_kept"] == n
        assert r["freshness"]["counts"] == {"fresh": n, "stale": 0, "unknown": 0}
        assert all(k["freshness"]["status"] == "fresh" for k in r["kept"])

    def test_date_only_fetched_at_grades_unknown(self):
        r = plan_full_rides(dict(BASE, rows=[row("d", fetched="2026-10-01")]))
        assert r["kept"][0]["freshness"]["status"] == "unknown"
        assert r["kept"][0]["freshness"]["reason"] == "timestamp_invalid"
        assert r["freshness"]["counts"] == {"fresh": 0, "stale": 0, "unknown": 1}


# ---- further boundary and type-gate pins ----
class TestTypeGatePins:
    def test_source_url_documented_prefix_and_dot_semantics(self):
        # documented check: startswith("https://"), length <= 2048, a dot at index 8 or later - nothing more
        assert plan_full_rides(dict(BASE, rows=[row("dot", url="https://.")]))["coverage"]["total_kept"] == 1
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("nodot", url="https://x")]))

    def test_source_url_each_clause_is_load_bearing(self):
        # clause A (scheme) false, length and dot fine
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("a", url="http://example.com/x")]))
        # clause B (length) false at exactly 2049, scheme and dot fine
        long2049 = "https://www.example.com/" + "a" * (2049 - len("https://www.example.com/"))
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("b", url=long2049)]))
        # clause C (host dot) false, scheme and length fine
        refuses("APPLY_REFUSED_NON_PUBLIC:source_url_must_be_public_https",
                dict(BASE, rows=[row("c", url="https://localhost:8443/x" .replace(":", ":", 1)[:2048])]))

    def test_curriculum_cbse_itself_is_accepted(self):
        # kills the != -> == flip at the must-be-CBSE branch: "CBSE" must pass, a look-alike must not
        assert plan_full_rides(dict(BASE, profile={"curriculum": "CBSE", "sat": 1520},
                                     rows=[row("k")]))["coverage"]["total_kept"] == 1
        refuses("APPLY_REFUSED_PROFILE:curriculum_must_be_CBSE",
                dict(BASE, profile={"curriculum": "cbse", "sat": 1520}, rows=[row("k")]))

    def test_payload_exact_type_refusals(self):
        refuses("APPLY_REFUSED_BAD_TYPE:payload", "nope")
        refuses("APPLY_REFUSED_BAD_TYPE:payload", [1])
        refuses("APPLY_REFUSED_BAD_TYPE:payload", None)

        class D(dict):
            pass
        refuses("APPLY_REFUSED_BAD_TYPE:payload", D(BASE, rows=[row("k")]))

    def test_unknown_keys_refused_at_both_levels(self):
        refuses("APPLY_REFUSED_UNKNOWN_FIELDS:payload", dict(BASE, rows=[row("k")], mystery=1))
        refuses("APPLY_REFUSED_UNKNOWN_FIELDS:profile[mystery]",
                dict(BASE, profile={"curriculum": "CBSE", "sat": 1520, "mystery": 1}, rows=[row("k")]))



class TestEdgePins:
    """Edge pins: SAT 399/1601, IELTS type and range gates, row-id cap, fetched_at length,
    as_of T-form, non-US coverage."""

    def test_sat_range_edges_399_and_1601_are_refused(self):
        refuses("APPLY_REFUSED_OUT_OF_RANGE:sat",
                dict(BASE, profile={"curriculum": "CBSE", "sat": 399}, rows=[row("k")]))
        refuses("APPLY_REFUSED_OUT_OF_RANGE:sat",
                dict(BASE, profile={"curriculum": "CBSE", "sat": 1601}, rows=[row("k")]))

    def test_ielts_type_gate_refuses_bool_or_non_number_alone(self):
        refuses("APPLY_REFUSED_BAD_TYPE:ielts",
                dict(BASE, profile={"curriculum": "CBSE", "ielts": True}, rows=[row("k")]))
        refuses("APPLY_REFUSED_BAD_TYPE:ielts",
                dict(BASE, profile={"curriculum": "CBSE", "ielts": "8"}, rows=[row("k")]))

    def test_ielts_range_refuses_negative_and_above_nine(self):
        refuses("APPLY_REFUSED_OUT_OF_RANGE:ielts",
                dict(BASE, profile={"curriculum": "CBSE", "ielts": -0.5}, rows=[row("k")]))
        refuses("APPLY_REFUSED_OUT_OF_RANGE:ielts",
                dict(BASE, profile={"curriculum": "CBSE", "ielts": 10}, rows=[row("k")]))

    def test_row_id_cap_64_accepted_65_refused(self):
        r = plan_full_rides(dict(BASE, rows=[row("i" * 64)]))
        assert [k["id"] for k in r["kept"]] == ["i" * 64]
        refuses("APPLY_REFUSED_EMPTY_FIELD:id", dict(BASE, rows=[row("i" * 65)]))

    def test_fetched_at_length_boundaries(self):
        refuses("APPLY_REFUSED_BAD_TYPE:fetched_at", dict(BASE, rows=[row("k", fetched="")]))
        r1 = plan_full_rides(dict(BASE, rows=[row("k", fetched="2")]))
        assert [k["id"] for k in r1["kept"]] == ["k"]
        r40 = plan_full_rides(dict(BASE, rows=[row("k", fetched="2026-10-01" + "0" * 30)]))
        assert [k["id"] for k in r40["kept"]] == ["k"]
        refuses("APPLY_REFUSED_BAD_TYPE:fetched_at",
                dict(BASE, rows=[row("k", fetched="2026-10-01" + "0" * 31)]))

    def test_as_of_datetime_with_t_branch_is_accepted(self):
        r = plan_full_rides(dict(BASE, as_of="2026-10-11T00:00:00", rows=[row("k")]))
        assert [k["id"] for k in r["kept"]] == ["k"]

    def test_non_us_countries_kept_without_us_rows(self):
        r = plan_full_rides(dict(BASE, rows=[
            row("a"),
            row("b", country="United Kingdom", university="Oxford", url="https://www.ox.ac.uk/aid")]))
        assert r["coverage"]["us_universities_kept"] == 0
        assert r["coverage"]["non_us_countries_kept"] == 2
