"""[U03] Adapter between U03 trend predictions and the forecast-ledger call shape.

Prepared against an early interface note; the J1 ledger has since landed on main with the same keyword-only call shape (checked by reading the landed source, never by running against it).

Additive and pure. It builds dictionaries with the exact keys claim, probability, horizon, source, made_at,
binds the ids the ledger hands back to the U03 term and threshold, and works out which predictions can be
resolved from later collected posts. It does NOT score, keep a ledger, or import any ledger module: scoring is
done by the one scorer elsewhere. Resolutions are only produced when the horizon has passed and posts were
collected inside it; otherwise the prediction stays unresolved and is never turned into a miss.
Not investment advice.
"""
from __future__ import annotations

import importlib.util
import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

_NAME = "trend_pipeline_u03"


def _pipeline():
    mod = sys.modules.get(_NAME)
    if mod is None:
        spec = importlib.util.spec_from_file_location(_NAME, pathlib.Path(__file__).with_name("trend_pipeline_u03.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_NAME] = mod
        spec.loader.exec_module(mod)
    return mod


_tp = _pipeline()
_KEYS = ("claim", "probability", "horizon", "source", "made_at")
SCORING = "scoring is done by the single forecast scorer elsewhere; not computed here"
LIMITS = ("Outcomes are only as complete as the collection of later posts supplied; U03 cannot tell whether that collection was complete.",
          "The forecast scorer does not verify outcome truth or completeness.",
          "Counts are posts containing the term in the supplied posts only; sampling bias and bots are not detected.")


class AdapterError(ValueError):
    pass


def _fail(msg):
    raise AdapterError("TREND_U03: " + msg)


def _utc(v, where):
    try:
        d = _tp._when(v, where)
    except ValueError as e:
        raise AdapterError(str(e)) from None
    return d.astimezone(timezone.utc)


def _iso(d):
    return d.isoformat()


def to_j1_predictions(predictions, *, source):
    if not isinstance(predictions, list) or not predictions:
        _fail("predictions must be a non-empty list")
    if not isinstance(source, str) or not source.strip() or len(source) > 200:
        _fail("source must be a non-empty string of at most 200 characters")
    out, pending = [], []
    for i, p in enumerate(predictions):
        if not isinstance(p, dict):
            _fail(f"prediction {i} must be an object")
        for k in ("prediction_id", "term", "threshold_posts", "confidence", "predicted_at", "horizon_days"):
            if k not in p:
                _fail(f"prediction {i} missing '{k}'")
        prob = p["confidence"]
        if type(prob) not in (int, float) or not math.isfinite(prob) or not 0 <= prob <= 1:
            _fail(f"prediction {i} probability must be a finite number from 0 to 1 (not a bool)")
        days = p["horizon_days"]
        if type(days) is not int or not 1 <= days <= 90:
            _fail(f"prediction {i} horizon_days must be an integer from 1 to 90")
        term, thr = p["term"], p["threshold_posts"]
        if not isinstance(term, str) or not term.strip():
            _fail(f"prediction {i} 'term' must be a non-empty string")
        if type(thr) is not int or thr < 1:
            _fail(f"prediction {i} 'threshold_posts' must be a positive integer")
        made = _utc(p["predicted_at"], f"prediction {i} made_at")
        horizon = made + timedelta(days=days)
        claim = (f"U03 term={term!r} threshold_posts={thr}: at least {thr} collected posts containing '{term}' "
                 f"in the window (made_at, horizon]")
        j = {"claim": claim, "probability": prob, "horizon": _iso(horizon), "source": source, "made_at": _iso(made)}
        out.append(j)
        pending.append({"u03_prediction_id": p["prediction_id"], "term": term, "threshold_posts": thr,
                        "horizon_days": days, **j})
    return {"j1_predictions": out, "pending": pending}


def bind_ids(pending_result, returned):
    if not isinstance(pending_result, dict) or not isinstance(pending_result.get("pending"), list):
        _fail("pending_result must be the dict returned by to_j1_predictions")
    if not isinstance(returned, list):
        _fail("returned must be a list")
    for i, r in enumerate(returned):
        if not isinstance(r, dict) or not isinstance(r.get("prediction_id"), str) or not r["prediction_id"]:
            _fail(f"returned {i} must carry a non-empty prediction_id")
    when = []
    for i, r in enumerate(returned):
        pair = {}
        for k in ("made_at", "horizon"):
            v = r.get(k)
            if not isinstance(v, str):
                _fail(f"returned {i} {k} must be timezone-aware ISO text")
            try:
                d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                _fail(f"returned {i} {k} must be timezone-aware ISO text")
            if d.tzinfo is None or d.utcoffset() is None:
                _fail(f"returned {i} {k} must be timezone-aware ISO text")
            pair[k] = d.astimezone(timezone.utc)
        when.append(pair)
    bound = []
    for i, e in enumerate(pending_result["pending"]):
        mine = {k: _utc(e[k], f"pending {i} {k}") for k in ("made_at", "horizon")}
        hits = [r for r, w in zip(returned, when)
                if all(r.get(k) == e[k] for k in ("claim", "probability", "source"))
                and w["made_at"] == mine["made_at"] and w["horizon"] == mine["horizon"]]
        if not hits:
            _fail(f"no returned prediction matches pending {i}")
        if len(hits) > 1:
            _fail(f"ambiguous: {len(hits)} returned predictions match pending {i}")
        bound.append({"j1_id": hits[0]["prediction_id"], "u03_prediction_id": e["u03_prediction_id"], "term": e["term"],
                      "threshold_posts": e["threshold_posts"], "horizon_days": e["horizon_days"],
                      "made_at": e["made_at"], "horizon": e["horizon"], "probability": e["probability"]})
    return bound


def resolutions_from_posts(bound, later_posts, *, resolved_at):
    if not isinstance(bound, list) or not bound:
        _fail("bound must be a non-empty list from bind_ids")
    preds = []
    for i, b in enumerate(bound):
        if not isinstance(b, dict):
            _fail(f"bound {i} must be an object")
        for k in ("j1_id", "term", "threshold_posts", "probability", "made_at", "horizon_days"):
            if k not in b:
                _fail(f"bound {i} missing '{k}'")
        preds.append({"prediction_id": b["j1_id"], "term": b["term"], "claim_class": _tp.CLAIM_CLASS,
                      "threshold_posts": b["threshold_posts"], "confidence": b["probability"],
                      "predicted_at": b["made_at"], "horizon_days": b["horizon_days"]})
    res_utc = _utc(resolved_at, "resolved_at")
    try:
        r = _tp.score_predictions(preds, later_posts, resolved_at=_iso(res_utc))
    except ValueError as e:
        raise AdapterError(str(e)) from None
    resolutions, unresolved = [], []
    if r["status"] == "NO_LATER_DATA":
        unresolved = [{"j1_id": b["j1_id"], "reason": "NO_LATER_DATA"} for b in bound]
    else:
        for row in r["results"]:
            if row["status"] == "SCORED":
                resolutions.append({"prediction_id": row["prediction_id"], "outcome": row["outcome"],
                                    "resolved_at": _iso(res_utc)})
            else:
                unresolved.append({"j1_id": row["prediction_id"], "reason": row["status"]})
    return {"resolutions": resolutions, "unresolved": unresolved, "limits": list(LIMITS), "boundary": _tp.BOUNDARY,
            "scoring": SCORING}
