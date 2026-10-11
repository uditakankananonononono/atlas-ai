"""U03 -> J1 adapter, written against the early J1 call shape (keyword-only, exact schema, no extras).
J1 itself is not imported: it is not on main. This adapter only builds J1-shaped dicts and resolves outcomes from posts."""
import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_DIR = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m19_idea_incubator"


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, _DIR / fname)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


tp = _load("trend_pipeline_u03", "trend_pipeline_u03.py")
ad = _load("u03_j1_adapter", "u03_j1_adapter.py")
AS_OF = "2026-03-31T05:30:00+05:30"            # 2026-03-31T00:00:00+00:00 in UTC
AS_OF_UTC = datetime(2026, 3, 31, tzinfo=timezone.utc)
J1_KEYS = {"claim", "probability", "horizon", "source", "made_at"}


def post(i, text, days_before, author=None):
    return {"post_id": f"p{i}", "author": author or f"a{i % 3}", "text": text,
            "posted_at": (AS_OF_UTC - timedelta(days=days_before)).isoformat()}


def u03_predictions(conf=0.7, horizon=7, limit=2):
    posts = [post(i, "aurora", 1 + i % 3) for i in range(8)] + [post(20 + i, "quartz", 1 + i % 3) for i in range(4)]
    return tp.make_predictions(tp.extract_trends(posts, as_of=AS_OF), confidence=conf, horizon_days=horizon, limit=limit)


def later(n, term="aurora", day=1, prefix="l"):
    return [{"post_id": f"{prefix}{day}_{i}", "author": f"x{i}", "text": term,
             "posted_at": (AS_OF_UTC + timedelta(days=day, hours=i)).isoformat()} for i in range(n)]


def bound_from(preds):
    pending = ad.to_j1_predictions(preds, source="u03 measured post frequency")
    returned = [dict(p, prediction_id=f"{i:064x}") for i, p in enumerate(pending["j1_predictions"])]
    return ad.bind_ids(pending, returned)


def err(fn):
    with pytest.raises(ad.AdapterError) as e:
        fn()
    assert str(e.value).startswith("TREND_U03: ")
    return str(e.value)


def test_j1_predictions_have_exact_schema_and_utc():
    preds = u03_predictions()
    out = ad.to_j1_predictions(preds, source="src")
    assert len(out["j1_predictions"]) == len(preds) == 2
    for p, j in zip(preds, out["j1_predictions"]):
        assert set(j) == J1_KEYS
        assert j["probability"] == 0.7 and j["source"] == "src"
        assert j["made_at"] == "2026-03-31T00:00:00+00:00"
        assert j["horizon"] == "2026-04-07T00:00:00+00:00"
        assert p["term"] in j["claim"] and f"threshold_posts={p['threshold_posts']}" in j["claim"]


def test_claim_text_is_unambiguous_and_distinct_per_term():
    claims = [j["claim"] for j in ad.to_j1_predictions(u03_predictions(), source="s")["j1_predictions"]]
    assert len(set(claims)) == 2
    assert all("(made_at, horizon]" in c for c in claims)


def test_side_map_has_old_id_term_and_threshold_but_no_j1_ids_yet():
    preds = u03_predictions()
    out = ad.to_j1_predictions(preds, source="s")
    assert [e["u03_prediction_id"] for e in out["pending"]] == [p["prediction_id"] for p in preds]
    assert [(e["term"], e["threshold_posts"], e["horizon_days"]) for e in out["pending"]] == \
        [(p["term"], p["threshold_posts"], 7) for p in preds]


def test_probability_validation():
    p = u03_predictions()
    for bad in (True, float("nan"), 1.5, "0.5", None):
        q = [dict(p[0], confidence=bad)]
        assert "probability" in err(lambda q=q: ad.to_j1_predictions(q, source="s"))


def test_source_and_input_validation():
    p = u03_predictions()
    assert "source" in err(lambda: ad.to_j1_predictions(p, source=""))
    assert "predictions" in err(lambda: ad.to_j1_predictions([], source="s"))
    assert "prediction 0 missing 'term'" in err(lambda: ad.to_j1_predictions([{k: v for k, v in p[0].items() if k != "term"}], source="s"))
    assert "made_at" in err(lambda: ad.to_j1_predictions([dict(p[0], predicted_at="2026-03-31")], source="s"))
    assert "horizon_days" in err(lambda: ad.to_j1_predictions([dict(p[0], horizon_days=True)], source="s"))
    assert "horizon_days" in err(lambda: ad.to_j1_predictions([dict(p[0], horizon_days=0)], source="s"))


def test_bind_ids_matches_by_exact_content_and_refuses_mismatch():
    preds = u03_predictions()
    pending = ad.to_j1_predictions(preds, source="s")
    returned = [dict(j, prediction_id="a" * 64) for j in pending["j1_predictions"]]
    returned[1]["prediction_id"] = "b" * 64
    bound = ad.bind_ids(pending, list(reversed(returned)))
    assert [b["j1_id"] for b in bound] == ["a" * 64, "b" * 64]
    assert "no returned prediction" in err(lambda: ad.bind_ids(pending, returned[:1]))
    tampered = [dict(r) for r in returned]
    tampered[0]["probability"] = 0.1
    assert "no returned prediction" in err(lambda: ad.bind_ids(pending, tampered))
    dup = [dict(returned[0]), dict(returned[0], prediction_id="c" * 64), returned[1]]
    assert "ambiguous" in err(lambda: ad.bind_ids(pending, dup))
    assert "prediction_id" in err(lambda: ad.bind_ids(pending, [{k: v for k, v in r.items() if k != "prediction_id"} for r in returned]))


def test_resolutions_scored_hit_and_miss_use_j1_ids():
    bound = bound_from(u03_predictions())
    res = ad.resolutions_from_posts(bound, later(10, "aurora") + later(1, "quartz", prefix="q"), resolved_at="2026-04-07T00:00:00+00:00")
    assert [set(r) for r in res["resolutions"]] == [{"prediction_id", "outcome", "resolved_at"}] * 2
    by = {r["prediction_id"]: r for r in res["resolutions"]}
    aur = [b for b in bound if b["term"] == "aurora"][0]
    qua = [b for b in bound if b["term"] == "quartz"][0]
    assert by[aur["j1_id"]]["outcome"] is True and by[qua["j1_id"]]["outcome"] is False
    assert all(r["resolved_at"] == "2026-04-07T00:00:00+00:00" for r in res["resolutions"])
    assert res["unresolved"] == []


def test_too_early_and_empty_horizon_never_become_false():
    bound = bound_from(u03_predictions())
    early = ad.resolutions_from_posts(bound, later(10), resolved_at="2026-04-06T00:00:00+00:00")
    assert early["resolutions"] == [] and {u["reason"] for u in early["unresolved"]} == {"UNRESOLVED_TOO_EARLY"}
    none = ad.resolutions_from_posts(bound, later(3, day=20), resolved_at="2026-05-30T00:00:00+00:00")
    assert none["resolutions"] == [] and {u["reason"] for u in none["unresolved"]} == {"NO_COLLECTED_POSTS_IN_HORIZON"}
    nodata = ad.resolutions_from_posts(bound, [], resolved_at="2026-05-30T00:00:00+00:00")
    assert nodata["resolutions"] == [] and {u["reason"] for u in nodata["unresolved"]} == {"NO_LATER_DATA"}


def test_partial_resolution_lists_the_rest_as_unresolved():
    # test corrected after first run: with posts inside the horizon, a short count is a miss, so the partial case
    # needs a prediction whose horizon (14d) has not passed at resolved_at (day 7)
    short = u03_predictions(horizon=7, limit=2)[0]
    long_ = u03_predictions(horizon=14, limit=2)[1]
    bound = bound_from([short, long_])
    res = ad.resolutions_from_posts(bound, later(10, "aurora"), resolved_at="2026-04-07T00:00:00+00:00")
    assert len(res["resolutions"]) == 1 and len(res["unresolved"]) == 1
    assert res["unresolved"][0] == {"j1_id": bound[1]["j1_id"], "reason": "UNRESOLVED_TOO_EARLY"}
    assert res["resolutions"][0]["prediction_id"] == bound[0]["j1_id"]


def test_short_count_inside_a_collected_horizon_is_a_miss_not_unresolved():
    bound = bound_from(u03_predictions())
    res = ad.resolutions_from_posts(bound, later(10, "aurora"), resolved_at="2026-04-07T00:00:00+00:00")
    q = [b for b in bound if b["term"] == "quartz"][0]
    assert {r["prediction_id"]: r["outcome"] for r in res["resolutions"]}[q["j1_id"]] is False


def test_resolved_at_offset_is_normalized_to_utc_and_must_be_at_or_after_horizon():
    bound = bound_from(u03_predictions(limit=1))
    res = ad.resolutions_from_posts(bound, later(10), resolved_at="2026-04-07T05:30:00+05:30")
    assert res["resolutions"][0]["resolved_at"] == "2026-04-07T00:00:00+00:00"
    assert "resolved_at" in err(lambda: ad.resolutions_from_posts(bound, later(10), resolved_at="2026-04-07"))


def test_window_counts_end_inclusive_start_exclusive():
    bound = bound_from(u03_predictions(limit=1))
    thr = bound[0]["threshold_posts"]
    edge = [{"post_id": "e", "author": "e", "text": "aurora", "posted_at": "2026-04-07T00:00:00+00:00"},
            {"post_id": "s", "author": "s", "text": "aurora", "posted_at": AS_OF_UTC.isoformat()}]
    filler = later(thr - 1, "aurora")
    res = ad.resolutions_from_posts(bound, edge + filler, resolved_at="2026-04-08T00:00:00+00:00")
    assert res["resolutions"][0]["outcome"] is True       # end-inclusive post counts, start post does not
    res2 = ad.resolutions_from_posts(bound, edge[1:] + filler, resolved_at="2026-04-08T00:00:00+00:00")
    assert res2["resolutions"][0]["outcome"] is False


def test_limits_and_boundary_are_stated():
    bound = bound_from(u03_predictions())
    res = ad.resolutions_from_posts(bound, later(10), resolved_at="2026-04-07T00:00:00+00:00")
    text = " ".join(res["limits"])
    assert "collection" in text and "complete" in text and "does not verify" in text
    assert "not investment advice" in res["boundary"]
    assert "scorer" in res["scoring"] and "not computed here" in res["scoring"]
    assert "brier" not in res and "hit_rate" not in res


def test_bound_input_validation():
    assert "bound" in err(lambda: ad.resolutions_from_posts([], later(1), resolved_at="2026-04-07T00:00:00+00:00"))
    assert "j1_id" in err(lambda: ad.resolutions_from_posts([{"term": "a"}], later(1), resolved_at="2026-04-07T00:00:00+00:00"))


def test_hermetic_source_and_no_j1_import():
    src = (_DIR / "u03_j1_adapter.py").read_text()
    for banned in ("import socket", "import subprocess", "import requests", "urllib", "open(", "os.environ", "random",
                   "time.time", "datetime.now", "utcnow", "j1_forecast", "ForecastLedger", "m20_general"):
        assert banned not in src
