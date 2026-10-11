"""U03 S2.3 follow-up: count-series trend detection. Hermetic, loads module by path."""
import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m19_idea_incubator/trend_counts_u03.py"


def _load():
    spec = importlib.util.spec_from_file_location("trend_counts_u03", _SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["trend_counts_u03"] = mod
    spec.loader.exec_module(mod)
    return mod


tc = _load()
AS_OF = "2026-03-31T00:00:00+00:00"
DT = datetime(2026, 3, 31, tzinfo=timezone.utc)


def row(term, days_before, count, source="export"):
    return {"term": term, "date": (DT - timedelta(days=days_before)).isoformat(), "count": count, "source": source}


def run(rows, **kw):
    return tc.extract_count_trends(rows, as_of=AS_OF, **kw)


def err(fn):
    with pytest.raises(tc.TrendError) as e:
        fn()
    assert str(e.value).startswith("TREND_U03: ") or str(e.value).startswith("TREND_REFUSED_OVERSIZE: ")
    return str(e.value)


def test_growth_from_counts_uses_stated_formula():
    r = run([row("aurora", 1, 6), row("aurora", 3, 4), row("aurora", 10, 1), row("aurora", 20, 1)], min_recent_count=5)
    t = r["trends"][0]
    assert (t["term"], t["recent_count"], t["baseline_count"]) == ("aurora", 10, 2)
    assert t["growth_ratio"] == round((10 / 7) / (3 / 28), 6)
    assert t["rank"] == 1 and r["status"] == "TRENDS_MEASURED"
    assert "not investment advice" in r["boundary"] and "does not predict" in r["boundary"]


def test_window_edges():
    r = run([row("a", 7, 100), row("a", 0, 5), row("a", 35, 100), row("a", 8, 1)], min_recent_count=1)
    t = r["trends"][0]
    assert t["recent_count"] == 5          # 7 days before is baseline (start exclusive)
    assert t["baseline_count"] == 101      # 7d and 8d rows; 35d is at the window start, excluded
    assert r["excluded"]["out_of_window"] == 1


def test_future_rows_excluded_and_counted():
    r = run([row("a", 1, 5), row("a", -1, 50)], min_recent_count=1)
    assert r["trends"][0]["recent_count"] == 5 and r["excluded"]["future"] == 1


def test_threshold_and_ranking_and_ties():
    r = run([row("zeta", 1, 7), row("alpha", 1, 7), row("big", 1, 20), row("big", 10, 2), row("tiny", 1, 2)], min_recent_count=5)
    assert [t["term"] for t in r["trends"]] == ["alpha", "zeta", "big"]
    assert "tiny" not in [t["term"] for t in r["trends"]]


def test_top_n_and_no_trends_status():
    rows = [row(f"t{i}", 1, 5 + i) for i in range(5)]
    assert len(run(rows, top_n=2)["trends"]) == 2
    r = run([row("a", 1, 1)], min_recent_count=5)
    assert r["status"] == "NO_TRENDS_MEETING_THRESHOLDS" and r["trends"] == []


def test_sources_listed():
    r = run([row("a", 1, 3, "rss"), row("a", 2, 3, "reddit")], min_recent_count=1)
    assert r["trends"][0]["sources"] == ["reddit", "rss"]


def test_validation():
    assert "series must be a list" in err(lambda: run("x"))
    assert "series must not be empty" in err(lambda: run([]))
    assert "row 0 missing 'count'" in err(lambda: run([{"term": "a", "date": AS_OF, "source": "s"}]))
    assert "unknown key 'x'" in err(lambda: run([dict(row("a", 1, 1), x=1)]))
    assert "'count'" in err(lambda: run([row("a", 1, -1)]))
    assert "'count'" in err(lambda: run([row("a", 1, True)]))
    assert "'count'" in err(lambda: run([row("a", 1, 1.5)]))
    assert "'date'" in err(lambda: run([dict(row("a", 1, 1), date="2026-03-30")]))
    assert "'term'" in err(lambda: run([row("", 1, 1)]))
    assert "row 0 must be an object" in err(lambda: run([5]))
    assert "as_of" in err(lambda: tc.extract_count_trends([row("a", 1, 1)], as_of="2026-03-31"))
    assert "recent_days" in err(lambda: run([row("a", 1, 1)], recent_days=0))
    assert "min_recent_count" in err(lambda: run([row("a", 1, 1)], min_recent_count=True))
    assert "duplicate" in err(lambda: run([row("a", 1, 1), row("a", 1, 2)]))


def test_oversize_has_refused_code():
    rows = [row("a", 1, 1, f"s{i}") for i in range(200001)]
    m = err(lambda: run(rows))
    assert m.startswith("TREND_REFUSED_OVERSIZE: ")




def test_hermetic_source():
    src = _SRC.read_text()
    for banned in ("import socket", "import subprocess", "import requests", "urllib", "open(", "os.environ", "random", "time.time", "datetime.now", "utcnow"):
        assert banned not in src


# ---- Tests added AFTER the first S2.3 mutant run (survivors m5, m6, m18) ----
def test_late_count_equal_to_threshold_is_kept():
    assert [t["term"] for t in run([row("a", 1, 5)], min_recent_count=5)["trends"]] == ["a"]


def test_late_tie_on_growth_orders_by_recent_count_before_term():
    r = run([row("xray", 1, 7), row("yankee", 1, 14), row("yankee", 10, 1)], min_recent_count=1)
    t = {x["term"]: x for x in r["trends"]}
    assert t["xray"]["growth_ratio"] == t["yankee"]["growth_ratio"] == 28.0
    assert [x["term"] for x in r["trends"]] == ["yankee", "xray"]


def test_late_terms_are_lowercased_and_merged():
    r = run([row("Aurora", 1, 3), row("aurora", 2, 4, "other")], min_recent_count=1)
    assert [(t["term"], t["recent_count"]) for t in r["trends"]] == [("aurora", 7)]


def test_late_sources_sorted_with_many_sources():
    # m10 was NOT deterministic (set order varies by hash seed); six sources make an accidental pass 1 in 720
    names = ["s_f", "s_a", "s_e", "s_b", "s_d", "s_c"]
    r = run([row("a", 1 + i % 3, 1, n) for i, n in enumerate(names)], min_recent_count=1)
    assert r["trends"][0]["sources"] == sorted(names)
