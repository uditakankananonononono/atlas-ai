"""U03 -> J1 adapter, written against the early J1 call shape (keyword-only, exact schema, no extras).
J1 has since landed on main but is still not imported: this adapter only builds J1-shaped dicts and resolves outcomes from
posts, and has not been run against the landed ledger."""
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


# ---- timestamp fix (child): the ledger returns UTC as '...Z'; bind_ids must compare parsed instants, not text ----
def _returned_with(pending, fmt):
    out = []
    for i, j in enumerate(pending["j1_predictions"]):
        d = dict(j, prediction_id=f"{i + 5:064x}")
        d["made_at"] = fmt(datetime.fromisoformat(j["made_at"]))
        d["horizon"] = fmt(datetime.fromisoformat(j["horizon"]))
        out.append(d)
    return out


def _z(d):
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _plus_0530(d):
    return d.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()


def test_ts_bind_ids_accepts_ledger_z_timestamps():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    bound = ad.bind_ids(pending, _returned_with(pending, _z))
    assert [b["j1_id"] for b in bound] == [f"{5:064x}", f"{6:064x}"]
    assert bound[0]["made_at"] == "2026-03-31T00:00:00+00:00"          # bound keeps the adapter's own form


def test_ts_bind_ids_accepts_same_instant_in_another_offset():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    assert len(ad.bind_ids(pending, _returned_with(pending, _plus_0530))) == 2


def test_ts_bind_ids_still_matches_plus_zero_form():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    assert len(ad.bind_ids(pending, _returned_with(pending, lambda d: d.isoformat()))) == 2


def test_ts_a_different_instant_does_not_match():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    ret = _returned_with(pending, _z)
    ret[0]["horizon"] = "2026-04-08T00:00:00Z"
    assert "no returned prediction" in err(lambda: ad.bind_ids(pending, ret))
    ret = _returned_with(pending, _z)
    ret[0]["made_at"] = "2026-03-31T00:00:01Z"
    assert "no returned prediction" in err(lambda: ad.bind_ids(pending, ret))


def test_ts_unparseable_or_naive_returned_timestamp_is_a_refusal_not_a_crash():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    for bad in ("not a time", "2026-04-07T00:00:00", 5, None):
        ret = _returned_with(pending, _z)
        ret[1]["horizon"] = bad
        msg = err(lambda ret=ret: ad.bind_ids(pending, ret))
        assert "returned 1" in msg and "horizon" in msg


def test_ts_text_fields_still_compared_exactly():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    for key, val in (("claim", "other"), ("source", "other"), ("probability", 0.71)):
        ret = _returned_with(pending, _z)
        ret[0][key] = val
        assert "no returned prediction" in err(lambda ret=ret: ad.bind_ids(pending, ret))


# ---- closing pins (auditor-5 named survivors, tests only) ----
def test_pin_source_type_and_length_bounds():
    preds = u03_predictions()
    assert "source" in err(lambda: ad.to_j1_predictions(preds, source=5))
    assert "source" in err(lambda: ad.to_j1_predictions(preds, source="   "))
    assert len(ad.to_j1_predictions(preds, source="s" * 200)["j1_predictions"]) == 2
    assert "source" in err(lambda: ad.to_j1_predictions(preds, source="s" * 201))


def test_pin_probability_bounds_zero_one_and_non_finite():
    p = u03_predictions()
    assert ad.to_j1_predictions([dict(p[0], confidence=0)], source="s")["j1_predictions"][0]["probability"] == 0
    assert ad.to_j1_predictions([dict(p[0], confidence=1)], source="s")["j1_predictions"][0]["probability"] == 1
    for bad in (float("inf"), float("-inf"), float("nan")):
        assert "probability" in err(lambda bad=bad: ad.to_j1_predictions([dict(p[0], confidence=bad)], source="s"))


def test_pin_horizon_days_bounds_one_to_ninety():
    p = u03_predictions()
    assert ad.to_j1_predictions([dict(p[0], horizon_days=1)], source="s")["j1_predictions"][0]["horizon"] == "2026-04-01T00:00:00+00:00"
    assert ad.to_j1_predictions([dict(p[0], horizon_days=90)], source="s")["j1_predictions"][0]["horizon"] == "2026-06-29T00:00:00+00:00"
    assert "horizon_days" in err(lambda: ad.to_j1_predictions([dict(p[0], horizon_days=91)], source="s"))
    assert "horizon_days" in err(lambda: ad.to_j1_predictions([dict(p[0], horizon_days=0)], source="s"))


def test_pin_term_must_be_a_non_blank_string():
    p = u03_predictions()
    for bad in ("", "   ", 5, None):
        assert "'term'" in err(lambda bad=bad: ad.to_j1_predictions([dict(p[0], term=bad)], source="s"))


def test_pin_threshold_posts_type_and_bounds():
    p = u03_predictions()
    for ok in (1, 2, 10 ** 9):
        assert ad.to_j1_predictions([dict(p[0], threshold_posts=ok)], source="s")["j1_predictions"]
    for bad in (0, -1, True, 1.5, "1"):
        assert "'threshold_posts'" in err(lambda bad=bad: ad.to_j1_predictions([dict(p[0], threshold_posts=bad)], source="s"))


def test_pin_claim_text_uses_repr_of_term():
    p = u03_predictions()
    claim = ad.to_j1_predictions([dict(p[0], term="it's")], source="s")["j1_predictions"][0]["claim"]
    assert 'term="it\'s"' in claim
    assert "term=it's" not in claim


def test_pin_to_j1_predictions_shape_refusals():
    assert "prediction 0 must be an object" in err(lambda: ad.to_j1_predictions([42], source="s"))
    assert "predictions" in err(lambda: ad.to_j1_predictions("x", source="s"))


def test_pin_bind_ids_shape_refusals():
    pending = ad.to_j1_predictions(u03_predictions(), source="s")
    returned = [dict(j, prediction_id=f"{i:064x}") for i, j in enumerate(pending["j1_predictions"])]
    assert "pending_result" in err(lambda: ad.bind_ids("x", returned))
    assert "pending_result" in err(lambda: ad.bind_ids({"pending": "x"}, returned))
    assert "returned must be a list" in err(lambda: ad.bind_ids(pending, "x"))
    bad_type = [dict(returned[0], prediction_id=5)] + returned[1:]
    assert "returned 0" in err(lambda: ad.bind_ids(pending, bad_type))
    bad_empty = [dict(returned[0], prediction_id="")] + returned[1:]
    assert "returned 0" in err(lambda: ad.bind_ids(pending, bad_empty))


def test_pin_resolutions_from_posts_shape_refusals():
    assert "bound" in err(lambda: ad.resolutions_from_posts("x", [], resolved_at="2026-04-07T00:00:00+00:00"))
    assert "bound 0 must be an object" in err(
        lambda: ad.resolutions_from_posts([42], [], resolved_at="2026-04-07T00:00:00+00:00"))


def test_pin_pending_echoes_probability_and_j1_probability_is_passthrough():
    preds = u03_predictions(conf=0.13)
    out = ad.to_j1_predictions(preds, source="s")
    assert [j["probability"] for j in out["j1_predictions"]] == [0.13, 0.13]
    assert [e["probability"] for e in out["pending"]] == [p["confidence"] for p in preds]


def test_pin_scoring_value_errors_are_wrapped_as_adapter_error():
    bound = bound_from(u03_predictions())
    dup = later(2, "aurora") + [later(1, "aurora")[0]]                     # duplicate post_id inside scoring
    m = err(lambda: ad.resolutions_from_posts(bound, dup, resolved_at="2026-04-07T00:00:00+00:00"))
    assert "duplicate" in m
