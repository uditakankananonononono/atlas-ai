"""[U03] Count-series trend detection and calibration bins.

Pure, hermetic, stdlib only. Input is rows the caller already has (for example an exported counts file):
{"term", "date" (ISO with offset), "count" (int >= 0), "source"}. Output is arithmetic over those rows.
Not wired to any other module. Measured counts only; not investment advice; does not predict markets.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

SCOPE = "TREND_U03 measured counts only"
BOUNDARY = ("Measured counts in the supplied rows only. It does not predict markets, prices or business outcomes, "
            "is not investment advice, and no accuracy is promised. A rising count is a measurement, not a recommendation.")
FORMULA = "growth_ratio = (recent_count / recent_days) / ((baseline_count + 1) / baseline_days)"
MAX_ROWS = 200000
MIN_FOR_SAMPLE = 20


class TrendError(ValueError):
    pass


def _fail(msg, code="TREND_U03"):
    raise TrendError(f"{code}: {msg}")


def _int(v, name, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        _fail(f"{name} must be an integer from {lo} to {hi}")
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


def _text(v, where, limit=200):
    if not isinstance(v, str) or not v.strip() or len(v) > limit:
        _fail(f"{where} must be a non-empty string of at most {limit} characters")
    return v


def extract_count_trends(series, *, as_of, recent_days=7, baseline_days=28, min_recent_count=5, top_n=20):
    if not isinstance(series, list):
        _fail("series must be a list")
    if not series:
        _fail("series must not be empty")
    if len(series) > MAX_ROWS:
        _fail(f"too many rows (limit {MAX_ROWS})", "TREND_REFUSED_OVERSIZE")
    t_as_of = _when(as_of, "as_of")
    recent_days = _int(recent_days, "recent_days", 1, 90)
    baseline_days = _int(baseline_days, "baseline_days", 1, 365)
    min_recent_count = _int(min_recent_count, "min_recent_count", 1, 10**9)
    top_n = _int(top_n, "top_n", 1, 100)
    recent_start = t_as_of - timedelta(days=recent_days)
    base_start = recent_start - timedelta(days=baseline_days)
    seen = set()
    rec, base = {}, {}
    future = out = 0
    for n, r in enumerate(series):
        if not isinstance(r, dict):
            _fail(f"row {n} must be an object")
        for k in ("term", "date", "count", "source"):
            if k not in r:
                _fail(f"row {n} missing '{k}'")
        for k in r:
            if k not in ("term", "date", "count", "source"):
                _fail(f"row {n} has unknown key '{k}'")
        term = _text(r["term"], f"row {n} 'term'").lower()
        source = _text(r["source"], f"row {n} 'source'")
        when = _when(r["date"], f"row {n} 'date'")
        c = r["count"]
        if type(c) is not int or c < 0 or c > 10**12:
            _fail(f"row {n} 'count' must be an integer from 0 to 10**12")
        key = (term, when, source)
        if key in seen:
            _fail(f"duplicate row for term {term!r}, date and source (row {n})")
        seen.add(key)
        if when > t_as_of:
            future += 1
            continue
        if when <= base_start:
            out += 1
            continue
        bucket = rec if when > recent_start else base
        e = bucket.setdefault(term, {"count": 0, "sources": set()})
        e["count"] += c
        e["sources"].add(source)
    trends = []
    for term, e in rec.items():
        rc = e["count"]
        if rc < min_recent_count:
            continue
        bc = base[term]["count"] if term in base else 0
        trends.append({"term": term, "recent_count": rc, "baseline_count": bc,
                       "growth_ratio": round((rc / recent_days) / ((bc + 1) / baseline_days), 6),
                       "recent_days": recent_days, "baseline_days": baseline_days, "formula": FORMULA,
                       "sources": sorted(e["sources"])})
    trends.sort(key=lambda t: (-t["growth_ratio"], -t["recent_count"], t["term"]))
    trends = trends[:top_n]
    for i, t in enumerate(trends, 1):
        t["rank"] = i
    return {"scope": SCOPE, "boundary": BOUNDARY, "as_of": as_of,
            "status": "TRENDS_MEASURED" if trends else "NO_TRENDS_MEETING_THRESHOLDS",
            "excluded": {"future": future, "out_of_window": out}, "trends": trends}


def calibration_bins(records, *, bins=5):
    if not isinstance(records, list) or not records:
        _fail("records must be a non-empty list")
    bins = _int(bins, "bins", 2, 20)
    acc = [{"n": 0, "hits": 0, "csum": 0.0} for _ in range(bins)]
    for i, r in enumerate(records):
        if not isinstance(r, dict) or "confidence" not in r or "outcome" not in r:
            _fail(f"record {i} must be an object with 'confidence' and 'outcome'")
        c, o = r["confidence"], r["outcome"]
        if type(c) not in (int, float) or not math.isfinite(c) or not 0 <= c <= 1:
            _fail(f"record {i} 'confidence' must be a finite number from 0 to 1")
        if type(o) is not bool:
            _fail(f"record {i} 'outcome' must be true or false")
        b = acc[min(int(c * bins), bins - 1)]
        b["n"] += 1
        b["hits"] += 1 if o else 0
        b["csum"] += c
    out = []
    for i, b in enumerate(acc):
        n = b["n"]
        out.append({"range": [i / bins, (i + 1) / bins], "n": n, "hits": b["hits"],
                    "hit_rate": round(b["hits"] / n, 6) if n else None,
                    "mean_confidence": round(b["csum"] / n, 6) if n else None})
    total = len(records)
    return {"boundary": BOUNDARY, "total": total, "bins": out,
            "caveat": ("fewer than 20 records: bins say nothing reliable about calibration" if total < MIN_FOR_SAMPLE
                       else "bins describe the supplied records only, not future accuracy")}
