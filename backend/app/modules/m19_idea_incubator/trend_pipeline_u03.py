"""[U03] Trend pipeline: collected posts -> measured trend candidates -> idea candidates -> checkable predictions.

Pure, hermetic, stdlib only: no files, no network, no clock, no model calls.
Everything here is arithmetic over the posts the caller supplies. It measures how often a term appears in
those posts (each post counted once), ranks terms by a stated growth formula, turns the top terms into
templated idea candidates that cite the numbers, makes persistence predictions with a caller-stated
confidence, and later scores those predictions against posts collected afterwards.
It does not collect posts, does not write to the incubator, does not call m06/m19/m20 modules, does not
judge whether a trend is good, and does not predict markets. Not investment advice.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta

SCOPE = "TREND_U03 measured post frequency only"
BOUNDARY = ("Measured term frequency in the supplied posts only. It does not predict markets, prices or business "
            "outcomes, is not investment advice, and no accuracy is promised. Results depend on which posts the "
            "caller collected; sampling bias and bots are not detected. A rising term is a measurement, not a "
            "recommendation.")
FORMULA = "growth_ratio = (recent_posts / recent_days) / ((baseline_posts + 1) / baseline_days)"
METRIC = "posts containing the term (each post counted once)"
CLAIM_CLASS = "trend_persistence"

MAX_POSTS = 20000
MAX_TEXT = 10000
MAX_ID = 200
MAX_PREDICTIONS = 1000

_STOP = frozenset("""the and for are but not you all any can had her was one our out has his how its may new now see two way who did
get use she him let put say too off own yet via per was with that this from they will have been were what when your than then them
there their these those into over also just only some such very about after again because before being below between both could
does doing down during each few further here more most other should same through under until while would""".split())
_WORD = re.compile(r"[a-z0-9]+")


class TrendError(ValueError):
    pass


def _fail(msg, code="TREND_U03"):
    raise TrendError(f"{code}: {msg}")


def _str(v, where, limit):
    if not isinstance(v, str) or not v.strip() or len(v) > limit:
        _fail(f"{where} must be a non-empty string of at most {limit} characters")
    return v


def _when(v, where):
    if not isinstance(v, str):
        _fail(f"{where} must be an ISO-8601 timestamp with an explicit UTC offset")
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        _fail(f"{where} must be an ISO-8601 timestamp with an explicit UTC offset")
    if d.tzinfo is None or d.utcoffset() is None:
        _fail(f"{where} must be an ISO-8601 timestamp with an explicit UTC offset")
    return d


def _int(v, name, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        _fail(f"{name} must be an integer from {lo} to {hi}")
    return v


def _eligible(tok):
    return len(tok) >= 3 and tok not in _STOP and not tok.isdigit()


def _terms(text):
    toks = _WORD.findall(text.lower())
    out = set()
    for i, t in enumerate(toks):
        if not _eligible(t):
            continue
        out.add(t)
        if i + 1 < len(toks) and _eligible(toks[i + 1]):
            out.add(t + " " + toks[i + 1])
    return out


def _post(p, n, label, optional=()):
    if not isinstance(p, dict):
        _fail(f"{label} {n} must be an object")
    for k in ("post_id", "author", "posted_at", "text"):
        if k not in p:
            _fail(f"{label} {n} missing '{k}'")
    for k in p:
        if k not in ("post_id", "author", "posted_at", "text") + tuple(optional):
            _fail(f"{label} {n} has unknown key '{k}'")
    pid = _str(p["post_id"], f"{label} {n} 'post_id'", MAX_ID)
    author = _str(p["author"], f"{label} {n} 'author'", MAX_ID)
    text = _str(p["text"], f"{label} {n} 'text'", MAX_TEXT)
    when = _when(p["posted_at"], f"{label} {n} 'posted_at'")
    for k in optional:
        if k in p:
            _str(p[k], f"{label} {n} '{k}'", 2000)
    return pid, author, text, when


def extract_trends(posts, *, as_of, recent_days=7, baseline_days=28, min_recent_posts=3, min_authors=2, top_n=20):
    if not isinstance(posts, list):
        _fail("posts must be a list")
    if not posts:
        _fail("posts must not be empty")
    if len(posts) > MAX_POSTS:
        _fail(f"too many posts (limit {MAX_POSTS})", "TREND_REFUSED_OVERSIZE")
    t_as_of = _when(as_of, "as_of")
    recent_days = _int(recent_days, "recent_days", 1, 90)
    baseline_days = _int(baseline_days, "baseline_days", 1, 365)
    min_recent_posts = _int(min_recent_posts, "min_recent_posts", 1, 1000)
    min_authors = _int(min_authors, "min_authors", 1, 100)
    top_n = _int(top_n, "top_n", 1, 100)
    recent_start = t_as_of - timedelta(days=recent_days)
    base_start = recent_start - timedelta(days=baseline_days)
    seen = set()
    rec, base = {}, {}
    future_ids, out_of_window, used = [], 0, 0
    for n, p in enumerate(posts):
        pid, author, text, when = _post(p, n, "post", optional=("platform", "source_url"))
        if pid in seen:
            _fail(f"duplicate post_id {pid!r}")
        seen.add(pid)
        if when > t_as_of:
            future_ids.append(pid)
            continue
        if when <= base_start:
            out_of_window += 1
            continue
        used += 1
        bucket = rec if when > recent_start else base
        for term in _terms(text):
            e = bucket.setdefault(term, {"ids": [], "authors": set()})
            e["ids"].append(pid)
            e["authors"].add(author)
    trends = []
    for term, e in rec.items():
        r, authors = len(e["ids"]), len(e["authors"])
        if r < min_recent_posts or authors < min_authors:
            continue
        b = len(base[term]["ids"]) if term in base else 0
        ratio = (r / recent_days) / ((b + 1) / baseline_days)
        trends.append({"term": term, "recent_posts": r, "baseline_posts": b, "recent_authors": authors,
                       "growth_ratio": round(ratio, 6), "recent_days": recent_days, "baseline_days": baseline_days,
                       "formula": FORMULA, "metric": METRIC, "evidence_post_ids": sorted(e["ids"])[:5]})
    trends.sort(key=lambda t: (-t["growth_ratio"], -t["recent_posts"], t["term"]))
    trends = trends[:top_n]
    for i, t in enumerate(trends, 1):
        t["rank"] = i
    return {"scope": SCOPE, "boundary": BOUNDARY, "as_of": as_of, "posts_used": used,
            "status": "TRENDS_MEASURED" if trends else "NO_TRENDS_MEETING_THRESHOLDS",
            "parameters": {"recent_days": recent_days, "baseline_days": baseline_days,
                           "min_recent_posts": min_recent_posts, "min_authors": min_authors, "top_n": top_n},
            "excluded": {"future": len(future_ids), "future_post_ids": sorted(future_ids), "out_of_window": out_of_window},
            "trends": trends}


def _trend_result(result):
    if not isinstance(result, dict) or not isinstance(result.get("trends"), list) or "as_of" not in result:
        _fail("trend result must be the dict returned by extract_trends")
    return result


def ideas_from_trends(result, *, limit):
    result = _trend_result(result)
    limit = _int(limit, "limit", 1, 100)
    ideas = []
    for t in result["trends"][:limit]:
        ideas.append({
            "term": t["term"], "rank": t["rank"],
            "title": f"Investigate rising topic: '{t['term']}'",
            "rationale": (f"{t['recent_posts']} posts by {t['recent_authors']} authors in the last {t['recent_days']} days "
                          f"against {t['baseline_posts']} in the prior {t['baseline_days']} days "
                          f"(growth ratio {t['growth_ratio']}). Measured frequency only; no market or business claim."),
            "origin": "measured_post_frequency", "evidence_post_ids": list(t["evidence_post_ids"]),
            "requires_human_review": True, "written_to_incubator": False})
    return ideas


def make_predictions(result, *, confidence, horizon_days, limit):
    result = _trend_result(result)
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        _fail("confidence must be a finite number from 0 to 1 stated by the caller")
    horizon_days = _int(horizon_days, "horizon_days", 1, 90)
    limit = _int(limit, "limit", 1, 100)
    as_of = result["as_of"]
    preds = []
    for t in result["trends"][:limit]:
        thr = max(1, (t["recent_posts"] * horizon_days) // t["recent_days"])
        preds.append({
            "prediction_id": f"{t['term']}@{as_of}@{horizon_days}d", "term": t["term"], "claim_class": CLAIM_CLASS,
            "claim": f"at least {thr} posts containing '{t['term']}' will be collected in the {horizon_days} days after {as_of}",
            "threshold_posts": thr, "confidence": confidence, "confidence_source": "caller_stated",
            "predicted_at": as_of, "horizon_days": horizon_days})
    return preds


def score_predictions(predictions, later_posts, *, resolved_at):
    if not isinstance(predictions, list) or not predictions or len(predictions) > MAX_PREDICTIONS:
        _fail(f"predictions must be a non-empty list of at most {MAX_PREDICTIONS}")
    checked, seen = [], set()
    for i, p in enumerate(predictions):
        if not isinstance(p, dict):
            _fail(f"prediction {i} must be an object")
        for k in ("prediction_id", "term", "claim_class", "threshold_posts", "confidence", "predicted_at", "horizon_days"):
            if k not in p:
                _fail(f"prediction {i} missing '{k}'")
        pid = _str(p["prediction_id"], f"prediction {i} 'prediction_id'", 400)
        term = _str(p["term"], f"prediction {i} 'term'", 400)
        if p["claim_class"] != CLAIM_CLASS:
            _fail(f"prediction {i} 'claim_class' must be '{CLAIM_CLASS}'")
        thr = _int(p["threshold_posts"], f"prediction {i} 'threshold_posts'", 1, 10**9)
        conf = p["confidence"]
        if type(conf) not in (int, float) or not math.isfinite(conf) or not 0 <= conf <= 1:
            _fail(f"prediction {i} 'confidence' must be a finite number from 0 to 1")
        hz = _int(p["horizon_days"], f"prediction {i} 'horizon_days'", 1, 90)
        t0 = _when(p["predicted_at"], f"prediction {i} 'predicted_at'")
        if pid in seen:
            _fail(f"duplicate prediction_id {pid!r}")
        seen.add(pid)
        checked.append((pid, term, thr, conf, hz, t0))
    if not isinstance(later_posts, list):
        _fail("later_posts must be a list")
    if len(later_posts) > MAX_POSTS:
        _fail(f"too many later posts (limit {MAX_POSTS})", "TREND_REFUSED_OVERSIZE")
    t_res = _when(resolved_at, "resolved_at")
    for i, (_, _, _, _, _, t0) in enumerate(checked):
        if t_res <= t0:
            _fail(f"resolved_at must be after predicted_at (prediction {i})")
    posts = []
    lseen = set()
    for n, p in enumerate(later_posts):
        pid, _author, text, when = _post(p, n, "later post", optional=("platform", "source_url"))
        if pid in lseen:
            _fail(f"duplicate post_id {pid!r}")
        lseen.add(pid)
        posts.append((when, _terms(text)))
    if not posts:
        return {"scope": SCOPE, "boundary": BOUNDARY, "status": "NO_LATER_DATA", "results": []}
    results = []
    for pid, term, thr, conf, hz, t0 in checked:
        end = t0 + timedelta(days=hz)
        row = {"prediction_id": pid, "term": term, "threshold_posts": thr, "observed_posts": None, "outcome": None}
        if t_res < end:
            row["status"] = "UNRESOLVED_TOO_EARLY"
        else:
            window = [terms for when, terms in posts if t0 < when <= end]
            if not window:
                row["status"] = "NO_COLLECTED_POSTS_IN_HORIZON"
            else:
                obs = sum(1 for terms in window if term in terms)
                row.update(status="SCORED", observed_posts=obs, outcome=obs >= thr)
        results.append(row)
    return {"scope": SCOPE, "boundary": BOUNDARY, "status": "SCORING_DONE", "results": results}
