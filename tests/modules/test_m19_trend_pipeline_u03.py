"""U03 trend pipeline: collected posts -> measured trend candidates -> idea candidates -> checkable predictions.

Hermetic: stdlib only, no files, no network, no clock. Loads the module by path.
"""
import importlib.util
import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m19_idea_incubator/trend_pipeline_u03.py"


def _load():
    spec = importlib.util.spec_from_file_location("trend_pipeline_u03", _SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["trend_pipeline_u03"] = mod
    spec.loader.exec_module(mod)
    return mod


tp = _load()
AS_OF = "2026-03-31T00:00:00+00:00"
AS_OF_DT = datetime(2026, 3, 31, tzinfo=timezone.utc)


def at(days_before, hours=0):
    return (AS_OF_DT - timedelta(days=days_before, hours=hours)).isoformat()


_n = [0]


def post(text, days_before, author="a1", **kw):
    _n[0] += 1
    d = {"post_id": f"p{_n[0]}", "author": author, "posted_at": at(days_before), "text": text}
    d.update(kw)
    return d


def base_posts():
    _n[0] = 0
    return ([post("aurora", 1, "a1"), post("aurora", 2, "a2"), post("aurora", 3, "a3"), post("aurora", 4, "a1"),
             post("quartz", 1, "a1"), post("quartz", 2, "a2"), post("quartz", 5, "a1"),
             post("quartz", 10, "a1"), post("quartz", 12, "a2"), post("quartz", 20, "a3")])


def extract(posts=None, **kw):
    return tp.extract_trends(posts if posts is not None else base_posts(), as_of=AS_OF, **kw)


def by_term(r):
    return {t["term"]: t for t in r["trends"]}


def refuse(call, text=None):
    with pytest.raises(tp.TrendError) as e:
        call()
    assert str(e.value).startswith(("TREND_U03: ", "TREND_REFUSED_OVERSIZE: "))
    if text:
        assert text in str(e.value)


# ---- trend extraction: measured numbers ------------------------------------
def test_growth_ratio_formula_and_counts():
    r = extract()
    t = by_term(r)
    a, q = t["aurora"], t["quartz"]
    assert (a["recent_posts"], a["baseline_posts"], a["recent_authors"]) == (4, 0, 3)
    assert a["growth_ratio"] == 16.0
    assert (q["recent_posts"], q["baseline_posts"], q["recent_authors"]) == (3, 3, 2)
    assert q["growth_ratio"] == 3.0
    assert a["formula"] == "growth_ratio = (recent_posts / recent_days) / ((baseline_posts + 1) / baseline_days)"
    assert a["metric"] == "posts containing the term (each post counted once)"


def test_ranking_is_by_growth_then_recent_then_term():
    r = extract()
    assert [x["term"] for x in r["trends"][:2]] == ["aurora", "quartz"]
    assert [x["rank"] for x in r["trends"]] == list(range(1, len(r["trends"]) + 1))
    ratios = [x["growth_ratio"] for x in r["trends"]]
    assert ratios == sorted(ratios, reverse=True)


def test_ties_break_on_recent_posts_then_alphabetical():
    _n[0] = 0
    posts = [post("zeta", 1, "a1"), post("zeta", 2, "a2"), post("zeta", 3, "a3"),
             post("beta", 1, "a1"), post("beta", 2, "a2"), post("beta", 3, "a3"),
             post("gamma", 1, "a1"), post("gamma", 2, "a2"), post("gamma", 3, "a3"), post("gamma", 4, "a1")]
    r = tp.extract_trends(posts, as_of=AS_OF, min_recent_posts=3, min_authors=2)
    assert [x["term"] for x in r["trends"]] == ["gamma", "beta", "zeta"]


def test_term_counted_once_per_post():
    _n[0] = 0
    posts = [post("aurora aurora aurora", 1, "a1"), post("aurora", 2, "a2"), post("aurora", 3, "a3")]
    assert by_term(extract(posts))["aurora"]["recent_posts"] == 3


def test_min_recent_posts_threshold_is_inclusive():
    _n[0] = 0
    posts = [post("aurora", 1, "a1"), post("aurora", 2, "a2")]
    assert "aurora" in by_term(extract(posts, min_recent_posts=2))
    assert "aurora" not in by_term(extract(posts, min_recent_posts=3))


def test_min_authors_threshold_is_inclusive_and_blocks_single_account_spam():
    _n[0] = 0
    posts = [post("aurora", 1, "a1"), post("aurora", 2, "a1"), post("aurora", 3, "a1")]
    assert "aurora" not in by_term(extract(posts, min_recent_posts=3, min_authors=2))
    assert "aurora" in by_term(extract(posts, min_recent_posts=3, min_authors=1))


def test_author_identity_is_exact_string():
    _n[0] = 0
    posts = [post("aurora", 1, "A1"), post("aurora", 2, "a1"), post("aurora", 3, "a1")]
    assert by_term(extract(posts, min_recent_posts=3))["aurora"]["recent_authors"] == 2


def test_window_boundaries_recent_is_open_closed():
    _n[0] = 0
    posts = [post("aurora", 0, "a1"),          # exactly as_of: in recent
             post("aurora", 7, "a2"),          # exactly as_of - 7d: baseline, not recent
             post("aurora", 35, "a3")]         # exactly as_of - 35d: outside window
    r = extract(posts, min_recent_posts=1, min_authors=1)
    a = by_term(r)["aurora"]
    assert a["recent_posts"] == 1 and a["baseline_posts"] == 1
    assert r["excluded"]["out_of_window"] == 1


def test_future_posts_are_excluded_and_listed_never_used():
    _n[0] = 0
    posts = [post("aurora", 1, "a1"), post("aurora", 2, "a2"), post("aurora", 3, "a3"),
             {"post_id": "fut", "author": "a9", "posted_at": "2026-03-31T00:00:01+00:00", "text": "aurora"}]
    r = extract(posts, min_recent_posts=3)
    assert by_term(r)["aurora"]["recent_posts"] == 3
    assert r["excluded"]["future"] == 1 and r["excluded"]["future_post_ids"] == ["fut"]


def test_offsets_compared_in_utc():
    _n[0] = 0
    p = {"post_id": "x1", "author": "a1", "posted_at": "2026-03-31T05:00:00+10:00", "text": "aurora"}  # 2026-03-30T19:00Z
    r = extract([p], min_recent_posts=1, min_authors=1)
    assert by_term(r)["aurora"]["recent_posts"] == 1 and r["excluded"]["future"] == 0
    q = {"post_id": "x2", "author": "a1", "posted_at": "2026-03-30T20:00:00-05:00", "text": "aurora"}  # 2026-03-31T01:00Z future
    r = extract([q], min_recent_posts=1, min_authors=1)
    assert r["excluded"]["future"] == 1


def test_stopwords_short_tokens_and_digits_are_not_terms():
    _n[0] = 0
    posts = [post("the and 42 ab aurora", d, a) for d, a in [(1, "a1"), (2, "a2"), (3, "a3")]]
    terms = set(by_term(extract(posts, min_recent_posts=3)))
    assert terms == {"aurora"}


def test_bigrams_of_adjacent_valid_tokens_are_terms_and_not_across_stopwords():
    _n[0] = 0
    posts = [post("silver aurora launch", d, a) for d, a in [(1, "a1"), (2, "a2"), (3, "a3")]]
    terms = set(by_term(extract(posts, min_recent_posts=3)))
    assert {"silver", "aurora", "launch", "silver aurora", "aurora launch"} <= terms
    assert "silver launch" not in terms
    _n[0] = 0
    posts = [post("silver the aurora", d, a) for d, a in [(1, "a1"), (2, "a2"), (3, "a3")]]
    assert "silver aurora" not in set(by_term(extract(posts, min_recent_posts=3)))


def test_tokenization_is_case_insensitive_and_splits_punctuation():
    _n[0] = 0
    posts = [post("Aurora!", 1, "a1"), post("AURORA, now", 2, "a2"), post("#aurora", 3, "a3")]
    assert by_term(extract(posts, min_recent_posts=3))["aurora"]["recent_posts"] == 3


def test_evidence_post_ids_are_sorted_and_capped_at_five():
    _n[0] = 0
    posts = [post("aurora", 1 + (i % 5), f"a{i % 3}") for i in range(8)]
    ids = by_term(extract(posts, min_recent_posts=3))["aurora"]["evidence_post_ids"]
    assert ids == sorted(ids) and len(ids) == 5
    assert set(ids) <= {p["post_id"] for p in posts}


def test_top_n_limits_the_ranked_output():
    r = extract(top_n=1)
    assert len(r["trends"]) == 1 and r["trends"][0]["term"] == "aurora"


def test_custom_window_lengths_change_the_formula_inputs():
    r = extract(recent_days=14, baseline_days=14)
    a = by_term(r)["aurora"]
    assert a["recent_days"] == 14 and a["baseline_days"] == 14
    q = by_term(r)["quartz"]
    assert q["recent_posts"] == 5 and q["baseline_posts"] == 1
    assert q["growth_ratio"] == round((5 / 14) / ((1 + 1) / 14), 6)


def test_no_trends_status_when_nothing_clears_thresholds():
    _n[0] = 0
    r = extract([post("aurora", 1, "a1")])
    assert r["trends"] == [] and r["status"] == "NO_TRENDS_MEETING_THRESHOLDS"
    assert extract()["status"] == "TRENDS_MEASURED"


def test_result_discloses_scope_and_does_not_forecast_or_advise():
    r = extract()
    assert r["scope"] == "TREND_U03 measured post frequency only"
    assert "not investment advice" in r["boundary"] and "does not predict" in r["boundary"]
    assert r["as_of"] == AS_OF and r["posts_used"] == 10


def test_deterministic_and_input_not_mutated():
    p = base_posts()
    snap = repr(p)
    assert extract(p) == extract(p)
    assert repr(p) == snap


# ---- idea candidates ---------------------------------------------------------
def test_ideas_from_trends_are_templated_candidates_citing_the_numbers():
    r = extract()
    ideas = tp.ideas_from_trends(r, limit=2)
    assert [i["term"] for i in ideas] == ["aurora", "quartz"]
    i = ideas[0]
    assert i["title"] == "Investigate rising topic: 'aurora'"
    assert i["origin"] == "measured_post_frequency"
    assert i["requires_human_review"] is True and i["written_to_incubator"] is False
    assert i["evidence_post_ids"] == by_term(r)["aurora"]["evidence_post_ids"]
    assert i["rationale"] == ("4 posts by 3 authors in the last 7 days against 0 in the prior 28 days "
                              "(growth ratio 16.0). Measured frequency only; no market or business claim.")


def test_ideas_limit_and_empty():
    r = extract()
    assert len(tp.ideas_from_trends(r, limit=1)) == 1
    assert tp.ideas_from_trends(r, limit=100) == tp.ideas_from_trends(r, limit=len(r["trends"]))
    _n[0] = 0
    assert tp.ideas_from_trends(extract([post("aurora", 1)]), limit=5) == []
    refuse(lambda: tp.ideas_from_trends(r, limit=0), "limit")
    refuse(lambda: tp.ideas_from_trends({"trends": 1}, limit=1), "trend result")


# ---- predictions ---------------------------------------------------------------
def test_predictions_are_persistence_thresholds_with_caller_confidence():
    r = extract()
    preds = tp.make_predictions(r, confidence=0.6, horizon_days=7, limit=2)
    assert [p["term"] for p in preds] == ["aurora", "quartz"]
    p = preds[0]
    assert p["prediction_id"] == f"aurora@{AS_OF}@7d"
    assert p["claim_class"] == "trend_persistence"
    assert p["threshold_posts"] == 4          # floor(4 / 7 * 7)
    assert p["confidence"] == 0.6 and p["confidence_source"] == "caller_stated"
    assert p["predicted_at"] == AS_OF and p["horizon_days"] == 7
    assert p["claim"] == "at least 4 posts containing 'aurora' will be collected in the 7 days after 2026-03-31T00:00:00+00:00"
    assert preds[1]["threshold_posts"] == 3


def test_threshold_uses_floor_and_horizon_scaling():
    r = extract()
    p = tp.make_predictions(r, confidence=0.5, horizon_days=14, limit=1)[0]
    assert p["threshold_posts"] == 8          # floor(4 / 7 * 14)
    p = tp.make_predictions(r, confidence=0.5, horizon_days=3, limit=1)[0]
    assert p["threshold_posts"] == 1          # floor(4 / 7 * 3) = 1


@pytest.mark.parametrize("bad", [-0.01, 1.01, None, "0.5", True, float("nan"), float("inf")])
def test_prediction_confidence_must_be_caller_supplied_in_unit_interval(bad):
    refuse(lambda: tp.make_predictions(extract(), confidence=bad, horizon_days=7, limit=1), "confidence")


@pytest.mark.parametrize("c", [0, 1, 0.0, 1.0])
def test_confidence_endpoints_accepted(c):
    assert tp.make_predictions(extract(), confidence=c, horizon_days=7, limit=1)[0]["confidence"] == c


@pytest.mark.parametrize("bad", [0, 91, -1, 1.5, "7", None, True])
def test_prediction_horizon_bounds(bad):
    refuse(lambda: tp.make_predictions(extract(), confidence=0.5, horizon_days=bad, limit=1), "horizon_days")


def test_horizon_bounds_inclusive():
    for h in (1, 90):
        assert tp.make_predictions(extract(), confidence=0.5, horizon_days=h, limit=1)[0]["horizon_days"] == h


# ---- scoring against later posts ---------------------------------------------
def later(n_aurora, n_quartz, start_days_after=1):
    _n[0] = 1000
    out = []
    for i in range(n_aurora):
        out.append({"post_id": f"l{start_days_after}_{i}", "author": f"x{i}", "text": "aurora",
                    "posted_at": (AS_OF_DT + timedelta(days=start_days_after, hours=i)).isoformat()})
    for i in range(n_quartz):
        out.append({"post_id": f"q{start_days_after}_{i}", "author": f"y{i}", "text": "quartz",
                    "posted_at": (AS_OF_DT + timedelta(days=start_days_after, hours=i)).isoformat()})
    return out


RESOLVED = (AS_OF_DT + timedelta(days=8)).isoformat()


def score(preds, later_posts, resolved_at=RESOLVED):
    return tp.score_predictions(preds, later_posts, resolved_at=resolved_at)


def test_scoring_hit_and_miss_with_brier_and_records():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=2)
    r = score(preds, later(4, 2))
    a, q = r["results"]
    assert (a["term"], a["observed_posts"], a["threshold_posts"], a["outcome"]) == ("aurora", 4, 4, True)
    assert (q["term"], q["observed_posts"], q["threshold_posts"], q["outcome"]) == ("quartz", 2, 3, False)
    assert r["summary"]["scored"] == 2 and r["summary"]["hits"] == 1 and r["summary"]["hit_rate"] == 0.5
    assert r["summary"]["brier"] == pytest.approx(((0.8 - 1) ** 2 + (0.8 - 0) ** 2) / 2)
    assert r["summary"]["constant_half_brier"] == 0.25


def test_scoring_threshold_is_inclusive():
    preds = tp.make_predictions(extract(), confidence=0.5, horizon_days=7, limit=1)
    assert score(preds, later(3, 0))["results"][0]["outcome"] is False
    assert score(preds, later(4, 0))["results"][0]["outcome"] is True


def test_only_posts_inside_the_horizon_count():
    preds = tp.make_predictions(extract(), confidence=0.5, horizon_days=7, limit=1)
    inside = later(4, 0)
    after_end = later(10, 0, start_days_after=8)       # after predicted_at + 7d
    at_as_of = [{"post_id": "z1", "author": "z", "text": "aurora", "posted_at": AS_OF}]
    r = score(preds, inside + after_end + at_as_of)
    assert r["results"][0]["observed_posts"] == 4
    end_exact = [{"post_id": "e1", "author": "e", "text": "aurora",
                  "posted_at": (AS_OF_DT + timedelta(days=7)).isoformat()}]
    assert score(preds, inside + end_exact)["results"][0]["observed_posts"] == 5


def test_observed_counts_posts_not_occurrences():
    preds = tp.make_predictions(extract(), confidence=0.5, horizon_days=7, limit=1)
    lp = later(1, 0)
    lp[0]["text"] = "aurora aurora aurora aurora"
    assert score(preds, lp)["results"][0]["observed_posts"] == 1


def test_bigram_prediction_matches_adjacent_tokens_only():
    _n[0] = 0
    posts = [post("silver aurora", d, a) for d, a in [(1, "a1"), (2, "a2"), (3, "a3")]]
    preds = [p for p in tp.make_predictions(extract(posts, min_recent_posts=3), confidence=0.5, horizon_days=7, limit=10)
             if p["term"] == "silver aurora"]
    lp = [{"post_id": "b1", "author": "q", "text": "silver aurora", "posted_at": (AS_OF_DT + timedelta(days=1)).isoformat()},
          {"post_id": "b2", "author": "q", "text": "silver the aurora", "posted_at": (AS_OF_DT + timedelta(days=1)).isoformat()}]
    assert score(preds, lp)["results"][0]["observed_posts"] == 1


def test_too_early_to_score_is_not_scored_and_not_counted():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)
    r = score(preds, later(4, 0), resolved_at=(AS_OF_DT + timedelta(days=6)).isoformat())
    assert r["results"][0]["status"] == "UNRESOLVED_TOO_EARLY"
    assert r["summary"]["scored"] == 0 and r["summary"]["brier"] is None and r["summary"]["hit_rate"] is None


def test_resolution_exactly_at_horizon_end_is_scored():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)
    r = score(preds, later(4, 0), resolved_at=(AS_OF_DT + timedelta(days=7)).isoformat())
    assert r["results"][0]["status"] == "SCORED"


def test_no_later_posts_is_not_a_miss():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)
    r = score(preds, [])
    assert r["status"] == "NO_LATER_DATA" and r["results"] == [] and r["summary"]["scored"] == 0


def test_later_posts_only_outside_every_horizon_is_no_data_for_that_prediction():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)
    r = score(preds, later(5, 0, start_days_after=30))
    assert r["results"][0]["status"] == "NO_COLLECTED_POSTS_IN_HORIZON" and r["summary"]["scored"] == 0


def test_calibration_style_records_are_emitted_for_scored_predictions_only():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=2)
    r = score(preds, later(4, 2))
    rec = r["records"][0]
    assert set(rec) == {"prediction_id", "claim_class", "prediction_source", "outcome_source", "confidence", "outcome",
                        "predicted_at", "resolved_at"}
    assert rec["claim_class"] == "trend_persistence" and rec["outcome"] is True and rec["confidence"] == 0.8
    assert rec["predicted_at"] == AS_OF_DT.timestamp() and rec["resolved_at"] == (AS_OF_DT + timedelta(days=8)).timestamp()
    assert rec["prediction_source"] == "caller_supplied_confidence" and rec["outcome_source"] == "later_collected_posts"
    assert len(r["records"]) == 2
    early = score(preds, later(4, 2), resolved_at=(AS_OF_DT + timedelta(days=1)).isoformat())
    assert early["records"] == []


def test_small_sample_caveat_always_stated_below_twenty():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=2)
    r = score(preds, later(4, 2))
    assert "fewer than 20" in r["summary"]["caveat"] and r["summary"]["sample_sufficient"] is False


def test_twenty_scored_predictions_lift_the_small_sample_caveat():
    _n[0] = 0
    posts = []
    for t in range(20):
        word = "term%c" % (97 + t)
        word = "".join(ch for ch in word if ch.isalpha()) + "xyz"
        for d, a in [(1, "a1"), (2, "a2"), (3, "a3")]:
            posts.append(post(word, d, a))
    r = extract(posts, min_recent_posts=3, top_n=100)
    preds = [p for p in tp.make_predictions(r, confidence=0.5, horizon_days=7, limit=100)]
    assert len(preds) >= 20
    lp = [{"post_id": f"L{i}", "author": "q", "text": " ".join(p["term"] for p in preds if " " not in p["term"]),
           "posted_at": (AS_OF_DT + timedelta(days=1, minutes=i)).isoformat()} for i in range(5)]
    res = score(preds[:20], lp)
    assert res["summary"]["scored"] == 20 and res["summary"]["sample_sufficient"] is True
    assert "fewer than 20" not in res["summary"]["caveat"]


def test_boundary_text_in_scoring_result():
    preds = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)
    b = score(preds, later(4, 0))["boundary"]
    assert "not investment advice" in b and "does not predict" in b and "no accuracy is promised" in b


def test_scoring_validates_prediction_shape():
    refuse(lambda: score("x", later(1, 0)), "predictions")
    refuse(lambda: score([], later(1, 0)), "predictions")
    refuse(lambda: score([{"term": "x"}], later(1, 0)), "prediction 0")
    good = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)[0]
    bad = dict(good, confidence=2)
    refuse(lambda: score([bad], later(1, 0)), "prediction 0")
    dup = [good, dict(good)]
    refuse(lambda: score(dup, later(1, 0)), "duplicate prediction_id")


def test_scoring_validates_later_posts_and_resolved_at():
    good = tp.make_predictions(extract(), confidence=0.8, horizon_days=7, limit=1)
    refuse(lambda: score(good, "x"), "later_posts")
    refuse(lambda: score(good, [{"post_id": "1"}]), "later post 0")
    refuse(lambda: score(good, later(1, 0), resolved_at="2026-04-10T00:00:00"), "resolved_at")
    refuse(lambda: score(good, later(1, 0), resolved_at=5), "resolved_at")
    refuse(lambda: score(good, later(1, 0), resolved_at=(AS_OF_DT - timedelta(days=1)).isoformat()), "resolved_at")


# ---- input refusals ------------------------------------------------------------
@pytest.mark.parametrize("bad", [None, "x", {}, (), 5])
def test_posts_must_be_a_list(bad):
    refuse(lambda: tp.extract_trends(bad, as_of=AS_OF), "posts must be a list")


def test_posts_must_not_be_empty_and_have_a_limit():
    refuse(lambda: tp.extract_trends([], as_of=AS_OF), "posts must not be empty")
    _n[0] = 0
    p = post("aurora", 1)
    refuse(lambda: tp.extract_trends([dict(p, post_id=str(i)) for i in range(20001)], as_of=AS_OF), "too many posts")


@pytest.mark.parametrize("bad", [None, 1, "x", ["a"]])
def test_post_must_be_an_object(bad):
    refuse(lambda: tp.extract_trends([bad], as_of=AS_OF), "post 0 must be an object")


@pytest.mark.parametrize("key", ["post_id", "author", "posted_at", "text"])
def test_post_missing_key(key):
    p = base_posts()[0]
    del p[key]
    refuse(lambda: tp.extract_trends([p], as_of=AS_OF), f"post 0 missing '{key}'")


def test_post_unknown_key_refused_but_known_optional_keys_accepted():
    p = base_posts()[0]
    refuse(lambda: tp.extract_trends([dict(p, extra=1)], as_of=AS_OF), "post 0 has unknown key 'extra'")
    tp.extract_trends([dict(p, platform="pinterest", source_url="https://example.test/p/1")], as_of=AS_OF)


@pytest.mark.parametrize("key", ["post_id", "author", "text"])
@pytest.mark.parametrize("bad", ["", "   ", 5, None])
def test_post_text_fields_validated(key, bad):
    p = base_posts()[0]
    p[key] = bad
    refuse(lambda: tp.extract_trends([p], as_of=AS_OF), f"post 0 '{key}'")


def test_text_length_limit_and_id_author_limits():
    p = base_posts()[0]
    refuse(lambda: tp.extract_trends([dict(p, text="a" * 10001)], as_of=AS_OF), "post 0 'text'")
    tp.extract_trends([dict(p, text="a" * 10000)], as_of=AS_OF)
    refuse(lambda: tp.extract_trends([dict(p, author="a" * 201)], as_of=AS_OF), "post 0 'author'")
    tp.extract_trends([dict(p, author="a" * 200)], as_of=AS_OF)
    refuse(lambda: tp.extract_trends([dict(p, post_id="a" * 201)], as_of=AS_OF), "post 0 'post_id'")


def test_duplicate_post_id_refused():
    p = base_posts()[0]
    refuse(lambda: tp.extract_trends([p, dict(p)], as_of=AS_OF), "duplicate post_id")


@pytest.mark.parametrize("bad", ["2026-03-30T00:00:00", "yesterday", "", 5, None, "2026-13-01T00:00:00+00:00"])
def test_posted_at_and_as_of_require_iso_with_offset(bad):
    p = base_posts()[0]
    refuse(lambda: tp.extract_trends([dict(p, posted_at=bad)], as_of=AS_OF), "post 0 'posted_at'")
    refuse(lambda: tp.extract_trends([p], as_of=bad), "as_of")


@pytest.mark.parametrize("name,bad", [("recent_days", 0), ("recent_days", 91), ("baseline_days", 0), ("baseline_days", 366),
                                      ("min_recent_posts", 0), ("min_recent_posts", 1001), ("min_authors", 0),
                                      ("min_authors", 101), ("top_n", 0), ("top_n", 101),
                                      ("recent_days", 1.5), ("top_n", True), ("min_authors", "2")])
def test_parameter_bounds_refused(name, bad):
    refuse(lambda: tp.extract_trends(base_posts(), as_of=AS_OF, **{name: bad}), name)


@pytest.mark.parametrize("name,ok", [("recent_days", 1), ("recent_days", 90), ("baseline_days", 1), ("baseline_days", 365),
                                     ("min_recent_posts", 1), ("min_recent_posts", 1000), ("min_authors", 1),
                                     ("min_authors", 100), ("top_n", 1), ("top_n", 100)])
def test_parameter_bounds_inclusive(name, ok):
    tp.extract_trends(base_posts(), as_of=AS_OF, **{name: ok})


def test_error_is_a_value_error_and_module_is_hermetic():
    assert issubclass(tp.TrendError, ValueError)
    src = _SRC.read_text()
    for banned in ("import socket", "import subprocess", "import requests", "urllib", "open(", "os.environ", "random", "time.time", "datetime.now", "utcnow"):
        assert banned not in src


# ---- Tests added AFTER the first hand-mutant run (survivors m7, m8, m9, m12, m23, m26) ----
def test_late_tie_on_growth_orders_by_recent_posts_before_term():
    _n[0] = 0
    posts = [post("yankee", 1 + (i % 3), f"u{i % 3}") for i in range(8)]
    posts += [post("yankee", 10, "u9")]
    posts += [post("xray", 1 + (i % 3), f"v{i % 3}") for i in range(4)]
    r = extract(posts)
    t = by_term(r)
    assert t["yankee"]["growth_ratio"] == t["xray"]["growth_ratio"] == 16.0
    assert [x["term"] for x in r["trends"]][:2] == ["yankee", "xray"]


def test_late_growth_ratio_is_rounded_to_six_places():
    _n[0] = 0
    posts = [post("aurora", d, f"a{d}") for d in (1, 2, 3)]
    r = extract(posts, baseline_days=29)
    assert by_term(r)["aurora"]["growth_ratio"] == 12.428571


def test_late_evidence_ids_are_capped_at_five():
    _n[0] = 0
    posts = [post("aurora", 1 + (i % 3), f"a{i % 3}") for i in range(8)]
    ev = by_term(extract(posts))["aurora"]["evidence_post_ids"]
    assert len(ev) == 5 and ev == sorted(ev)


def test_late_digit_only_tokens_are_not_terms():
    _n[0] = 0
    posts = [post("aurora 2024", d, f"a{d}") for d in (1, 2, 3)]
    terms = by_term(extract(posts))
    assert "2024" not in terms and "aurora 2024" not in terms and "aurora" in terms


def test_late_sample_not_sufficient_below_twenty_scored():
    preds = []
    for i in range(19):
        preds.append({"prediction_id": f"aurora@{i}", "term": "aurora", "claim_class": "trend_persistence",
                      "threshold_posts": 1, "confidence": 0.5, "predicted_at": AS_OF, "horizon_days": 7})
    s = score(preds, later(2, 0))["summary"]
    assert s["scored"] == 19 and s["sample_sufficient"] is False and "fewer than 20" in s["caveat"]


def test_late_duplicate_later_post_id_refused():
    preds = tp.make_predictions(extract(), confidence=0.5, horizon_days=7, limit=1)
    lp = later(2, 0)
    lp[1]["post_id"] = lp[0]["post_id"]
    with pytest.raises(tp.TrendError) as e:
        score(preds, lp)
    assert "duplicate post_id" in str(e.value)


# ---- S2.3 follow-up (G4): oversize refusals carry the TREND_REFUSED_OVERSIZE code ----
def test_s23_oversize_refusals_use_refused_oversize_code():
    p = {"post_id": "x", "author": "a", "posted_at": AS_OF, "text": "aurora"}
    with pytest.raises(tp.TrendError) as e:
        tp.extract_trends([dict(p, post_id=str(i)) for i in range(20001)], as_of=AS_OF)
    assert str(e.value).startswith("TREND_REFUSED_OVERSIZE: ") and "too many posts" in str(e.value)
    preds = tp.make_predictions(extract(), confidence=0.5, horizon_days=7, limit=1)
    lp = [dict(p, post_id=str(i)) for i in range(20001)]
    with pytest.raises(tp.TrendError) as e2:
        tp.score_predictions(preds, lp, resolved_at="2026-04-20T00:00:00+00:00")
    assert str(e2.value).startswith("TREND_REFUSED_OVERSIZE: ")
