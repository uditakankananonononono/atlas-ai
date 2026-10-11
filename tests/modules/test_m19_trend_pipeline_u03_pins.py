"""Boundary pins for trend_pipeline_u03 (tests only). Each pin targets a mutant the first test file left alive.
Loads the module by path. These pass on the unmutated source; they are meant to FAIL under the listed mutants."""
import importlib.util
import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m19_idea_incubator/trend_pipeline_u03.py"
spec = importlib.util.spec_from_file_location("trend_pipeline_u03_pins", _SRC)
tp = importlib.util.module_from_spec(spec)
sys.modules["trend_pipeline_u03_pins"] = tp
spec.loader.exec_module(tp)

AS_OF = "2026-03-31T00:00:00+00:00"
DT = datetime(2026, 3, 31, tzinfo=timezone.utc)


def at(days_before):
    return (DT - timedelta(days=days_before)).isoformat()


def P(i, text, days_before=1, author=None, **kw):
    d = {"post_id": f"p{i}", "author": author or f"a{i}", "posted_at": at(days_before), "text": text}
    d.update(kw)
    return d


def terms(posts, **kw):
    return {t["term"]: t for t in tp.extract_trends(posts, as_of=AS_OF, **kw)["trends"]}


def refused(fn, needle=None):
    with pytest.raises(tp.TrendError) as e:
        fn()
    if needle:
        assert needle in str(e.value)


def pred(**kw):
    d = {"prediction_id": "x@1", "term": "aurora", "claim_class": "trend_persistence", "threshold_posts": 1,
         "confidence": 0.5, "predicted_at": AS_OF, "horizon_days": 7}
    d.update(kw)
    return d


LATER = [{"post_id": "l1", "author": "z", "text": "aurora", "posted_at": (DT + timedelta(days=1)).isoformat()}]
RES = (DT + timedelta(days=1)).isoformat()


def score(preds, later=LATER, resolved_at=RES):
    return tp.score_predictions(preds, later, resolved_at=resolved_at)


def trend_result():
    return tp.extract_trends([P(i, "aurora", 1 + i % 3) for i in range(3)], as_of=AS_OF)


# ---- size caps -------------------------------------------------------------
def test_max_posts_boundary_accepts_exactly_20000():
    posts = [{"post_id": f"p{i}", "author": "a", "posted_at": at(1), "text": "x"} for i in range(20000)]
    assert tp.extract_trends(posts, as_of=AS_OF)["posts_used"] == 20000
    refused(lambda: tp.extract_trends(posts + [dict(posts[0], post_id="extra")], as_of=AS_OF), "too many posts")


def test_max_later_posts_boundary_accepts_exactly_20000():
    later = [{"post_id": f"l{i}", "author": "a", "text": "x", "posted_at": (DT + timedelta(days=1)).isoformat()} for i in range(20000)]
    assert score([pred()], later)["status"] == "SCORING_DONE"
    refused(lambda: score([pred()], later + [dict(later[0], post_id="extra")]), "too many later posts")


def test_max_predictions_boundary_accepts_exactly_1000():
    preds = [pred(prediction_id=f"x@{i}") for i in range(1000)]
    assert len(score(preds)["results"]) == 1000
    refused(lambda: score(preds + [pred(prediction_id="x@extra")]), "predictions")


# ---- tokenizer -------------------------------------------------------------
def test_three_letter_tokens_are_terms_and_two_letter_tokens_are_not():
    t = terms([P(i, "gpu ai") for i in range(3)])
    assert "gpu" in t and "ai" not in t


def test_bigram_uses_the_following_token_and_never_reads_past_the_end():
    t = terms([P(i, "aurora borealis the") for i in range(3)])
    assert "aurora borealis" in t
    t2 = terms([P(i, "aurora borealis") for i in range(3)])      # last token: must not index past the end
    assert "aurora borealis" in t2 and "aurora" in t2


# ---- optional field length ---------------------------------------------------
@pytest.mark.parametrize("key", ["platform", "source_url"])
def test_optional_field_length_limit_is_2000(key):
    ok = [P(0, "aurora", **{key: "p" * 2000})]
    assert tp.extract_trends(ok, as_of=AS_OF)["posts_used"] == 1
    refused(lambda: tp.extract_trends([P(0, "aurora", **{key: "p" * 2001})], as_of=AS_OF), f"'{key}'")


# ---- defaults and keyword-only signatures --------------------------------------
def test_default_min_recent_posts_is_three():
    assert terms([P(i, "aurora") for i in range(2)]) == {}
    assert "aurora" in terms([P(i, "aurora") for i in range(3)])


def test_default_min_authors_is_two():
    assert terms([P(i, "aurora", author="same") for i in range(3)]) == {}
    assert "aurora" in terms([P(i, "aurora", author="a" + str(i % 2)) for i in range(3)])


def test_default_top_n_is_twenty():
    posts = []
    for k in range(25):
        for j in range(3):
            posts.append(P(k * 3 + j, f"term{k:02d}x", author=f"a{j}"))
    assert len(tp.extract_trends(posts, as_of=AS_OF)["trends"]) == 20


def test_public_functions_are_keyword_only_after_their_data_arguments():
    posts = [P(i, "aurora") for i in range(3)]
    with pytest.raises(TypeError):
        tp.extract_trends(posts, AS_OF)
    r = trend_result()
    with pytest.raises(TypeError):
        tp.ideas_from_trends(r, 1)
    with pytest.raises(TypeError):
        tp.make_predictions(r, 0.5, 7, 1)
    with pytest.raises(TypeError):
        tp.score_predictions([pred()], LATER, RES)


# ---- limits on ideas and predictions ----------------------------------------------
def test_ideas_limit_bounds_1_to_100():
    r = trend_result()
    assert len(tp.ideas_from_trends(r, limit=1)) == 1 and isinstance(tp.ideas_from_trends(r, limit=100), list)
    refused(lambda: tp.ideas_from_trends(r, limit=101), "limit")
    refused(lambda: tp.ideas_from_trends(r, limit=0), "limit")


def test_prediction_limit_bounds_1_to_100():
    r = trend_result()
    assert len(tp.make_predictions(r, confidence=0.5, horizon_days=7, limit=1)) == 1
    assert isinstance(tp.make_predictions(r, confidence=0.5, horizon_days=7, limit=100), list)
    refused(lambda: tp.make_predictions(r, confidence=0.5, horizon_days=7, limit=101), "limit")
    refused(lambda: tp.make_predictions(r, confidence=0.5, horizon_days=7, limit=0), "limit")


def test_prediction_threshold_never_drops_below_one():
    r = trend_result()          # 3 posts in 7 days; 3 * 1 // 7 == 0
    assert tp.make_predictions(r, confidence=0.5, horizon_days=1, limit=1)[0]["threshold_posts"] == 1


# ---- trend-result shape ------------------------------------------------------------
@pytest.mark.parametrize("bad", ["x", 5, None, [], {}, {"trends": []}, {"as_of": AS_OF}, {"as_of": AS_OF, "trends": "no"},
                                 {"as_of": AS_OF, "trends": None}])
def test_trend_result_shape_is_refused_not_crashed(bad):
    refused(lambda: tp.ideas_from_trends(bad, limit=1), "trend result")
    refused(lambda: tp.make_predictions(bad, confidence=0.5, horizon_days=7, limit=1), "trend result")


def test_empty_trend_result_with_as_of_is_accepted():
    assert tp.ideas_from_trends({"as_of": AS_OF, "trends": []}, limit=1) == []


# ---- scoring input bounds ---------------------------------------------------------------
def test_prediction_id_and_term_length_limit_is_400():
    assert score([pred(prediction_id="p" * 400)])["status"] == "SCORING_DONE"
    refused(lambda: score([pred(prediction_id="p" * 401)]), "'prediction_id'")
    assert score([pred(term="t" * 400)])["status"] == "SCORING_DONE"
    refused(lambda: score([pred(term="t" * 401)]), "'term'")


def test_threshold_posts_bounds():
    assert score([pred(threshold_posts=1)])["status"] == "SCORING_DONE"
    assert score([pred(threshold_posts=10 ** 9)])["status"] == "SCORING_DONE"
    refused(lambda: score([pred(threshold_posts=0)]), "'threshold_posts'")
    refused(lambda: score([pred(threshold_posts=10 ** 9 + 1)]), "'threshold_posts'")


def test_confidence_bounds_and_types_in_scoring():
    for ok in (0, 1, 0.0, 1.0, 0.5):
        assert score([pred(confidence=ok)])["status"] == "SCORING_DONE"
    for bad in (-0.001, 1.001, math.nan, math.inf, -math.inf, True, False, "0.5", None):
        refused(lambda bad=bad: score([pred(confidence=bad)]), "'confidence'")


def test_horizon_days_bounds_in_scoring():
    for ok in (1, 90):
        assert score([pred(horizon_days=ok)])["status"] == "SCORING_DONE"
    for bad in (0, 91, True, 1.5):
        refused(lambda bad=bad: score([pred(horizon_days=bad)]), "'horizon_days'")


def test_resolved_at_equal_to_predicted_at_is_refused():
    refused(lambda: score([pred()], resolved_at=AS_OF), "resolved_at")
    assert score([pred()], resolved_at=(DT + timedelta(seconds=1)).isoformat())["status"] == "SCORING_DONE"


def test_naive_and_offset_less_timestamps_are_refused():
    refused(lambda: tp.extract_trends([P(0, "aurora")], as_of="2026-03-31T00:00:00"), "as_of")
    refused(lambda: tp.extract_trends([dict(P(0, "aurora"), posted_at="2026-03-30T00:00:00")], as_of=AS_OF), "posted_at")


# ---- closing pins (auditor-5 named survivors, tests only) ----------------------
def test_pin_bigrams_never_skip_an_ineligible_token():
    t = terms([P(i, "cat ab dog") for i in range(3)])
    assert "cat" in t and "dog" in t and "ab" not in t
    assert "cat dog" not in t and "cat ab" not in t


def test_pin_evidence_post_ids_are_sorted_and_capped_at_five():
    ids = ["p9", "p3", "p7", "p1", "p8", "p2"]
    posts = [{"post_id": pid, "author": f"a{i % 2}", "posted_at": at(1), "text": "aurora"} for i, pid in enumerate(ids)]
    t = terms(posts)
    assert t["aurora"]["evidence_post_ids"] == ["p1", "p2", "p3", "p7", "p8"]


def test_pin_future_post_ids_are_sorted():
    future = [dict(P(i, "aurora"), post_id=pid, posted_at=(DT + timedelta(days=1)).isoformat())
              for i, pid in enumerate(["z2", "m1", "a9"])]
    r = tp.extract_trends([P(9, "aurora")] + future, as_of=AS_OF)
    assert r["excluded"]["future"] == 3
    assert r["excluded"]["future_post_ids"] == ["a9", "m1", "z2"]


def test_pin_as_of_is_echoed_raw_not_normalized():
    r = tp.extract_trends([P(i, "aurora") for i in range(3)], as_of="2026-03-31T05:30:00+05:30")  # same instant as AS_OF
    assert r["as_of"] == "2026-03-31T05:30:00+05:30"
    assert r["posts_used"] == 3
    # a Z-suffixed input re-serializes to +00:00 under isoformat(), so a plain
    # re-serialization mutant cannot survive this echo check (auditor-5 100)
    z = tp.extract_trends([P(i, "aurora") for i in range(3)], as_of="2026-03-31T00:00:00Z")
    assert z["as_of"] == "2026-03-31T00:00:00Z"


def test_pin_top_n_is_echoed_in_parameters():
    r = tp.extract_trends([P(i, "aurora") for i in range(3)], as_of=AS_OF, top_n=7)
    assert r["parameters"]["top_n"] == 7


def test_pin_non_dict_prediction_is_a_trend_error_not_a_type_error():
    with pytest.raises(tp.TrendError) as e:
        score([42])
    assert "prediction 0 must be an object" in str(e.value)


def test_pin_score_predictions_refuses_a_foreign_claim_class():
    refused(lambda: score([pred(claim_class="other")]), "'claim_class'")
