"""M22 delta: fyyd + Software Heritage collectors and the source health report.

Fixtures under fixtures_m22_extra/ are verbatim captures of the live endpoints
(2026-10-11). The network is never touched: every collector takes an injected
fetch. Modules load without importing the package __init__ (which needs the web
stack) when that stack is not installed; sources.py itself is stdlib only.
"""
import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "backend" / "app" / "modules" / "m22_tools_hub"
FIX = Path(__file__).parent / "fixtures_m22_extra"


def _load(name):
    full = "app.modules.m22_tools_hub." + name
    try:
        return importlib.import_module(full)
    except ModuleNotFoundError as exc:
        if exc.name in {"fastapi", "pydantic", "starlette"}:
            # package __init__ needs the web stack: register a bare namespace package
            sys.path.insert(0, str(ROOT / "backend"))
            pkg = types.ModuleType("app.modules.m22_tools_hub")
            pkg.__path__ = [str(PKG_DIR)]
            for parent in ("app", "app.modules"):
                if parent not in sys.modules:
                    importlib.import_module(parent)
            sys.modules["app.modules.m22_tools_hub"] = pkg
            return importlib.import_module(full)
        raise


sources = _load("sources")
extra = _load("sources_extra")
health = _load("source_health")
SourceError = sources.SourceError

FYYD = json.loads((FIX / "fyyd.json").read_text())
SWH = json.loads((FIX / "swh.json").read_text())


def run(coro):
    return asyncio.run(coro)


async def drain(collector, query="python"):
    return [x async for x in collector.collect(query)]


# ----------------------------------------------------------------- fyyd

def test_fyyd_parse_maps_real_capture():
    items = list(extra.parse_fyyd(FYYD))
    assert [i["name"] for i in items] == ["The Real Python Podcast", "Python Bytes", "Talk Python To Me"]
    first = items[0]
    assert first["url"] == "https://realpython.com/podcasts/rpp/"
    assert first["kind"] == "podcast"
    ev = first["evidence"][0]
    assert ev["source"] == "fyyd"
    assert ev["feed_url"] == "https://realpython.com/podcasts/rpp/feed"
    assert ev["episode_count"] == 315
    assert ev["lastpub"] == "2026-10-09T14:00:00+02:00"
    assert first["permissions"] == []
    assert first["summary"] and len(first["summary"]) <= sources.MAX_SUMMARY_CHARS


def test_fyyd_url_falls_back_to_fyyd_page_then_skips_untitled():
    payload = {"status": 1, "data": [
        {"title": "A", "htmlURL": "", "url_fyyd": "https://fyyd.de/podcast/a/0"},
        {"title": "", "htmlURL": "https://x.example/"},
        {"htmlURL": "https://y.example/"},
    ]}
    items = list(extra.parse_fyyd(payload))
    assert [i["url"] for i in items] == ["https://fyyd.de/podcast/a/0"]


def test_fyyd_caps_at_20_and_20_21_boundary():
    mk = lambda n: {"status": 1, "data": [{"title": f"t{i}", "htmlURL": f"https://e/{i}"} for i in range(n)]}
    assert len(list(extra.parse_fyyd(mk(20)))) == 20
    assert len(list(extra.parse_fyyd(mk(21)))) == 20


def test_fyyd_non_ok_status_raises_exact_message():
    with pytest.raises(SourceError, match=r"^fyyd returned status 0: boom$"):
        list(extra.parse_fyyd({"status": 0, "msg": "boom", "data": []}))


@pytest.mark.parametrize("payload", [[], None, "x", {"status": 1}, {"status": 1, "data": None}])
def test_fyyd_malformed_payload_yields_nothing(payload):
    assert list(extra.parse_fyyd(payload)) == []


def test_fyyd_maintenance_tracks_lastpub_recency():
    fresh = {"status": 1, "data": [{"title": "f", "htmlURL": "https://f/", "lastpub": "2099-01-01T00:00:00+00:00"}]}
    old = {"status": 1, "data": [{"title": "o", "htmlURL": "https://o/", "lastpub": "2001-01-01T00:00:00+00:00"}]}
    none = {"status": 1, "data": [{"title": "n", "htmlURL": "https://n/"}]}
    assert list(extra.parse_fyyd(fresh))[0]["maintenance"] == 0.8
    assert list(extra.parse_fyyd(old))[0]["maintenance"] == 0.2
    assert list(extra.parse_fyyd(none))[0]["maintenance"] == 0.5


def test_fyyd_collector_url_and_end_to_end():
    seen = []

    def fetch(url):
        seen.append(url)
        return json.dumps(FYYD).encode()

    col = extra.fyyd_collector(fetch=fetch)
    assert col.name == "fyyd" and col.kind == "podcast"
    got = run(drain(col, "python tools"))
    assert seen == ["https://api.fyyd.de/0.2/search/podcast?title=python+tools&count=20"]
    assert len(got) == 3


# ------------------------------------------------------ Software Heritage

def test_origin_name_forges_collapse_to_owner_repo_so_dedup_collides():
    assert extra.origin_name("https://github.com/DzRepo/Python-Insights") == "DzRepo/Python-Insights"
    assert extra.origin_name("https://gitlab.com/g/sub/proj.git") == "g/sub/proj"
    assert extra.origin_name("https://codeberg.org/o/r/") == "o/r"
    assert extra.origin_name("https://git.example.org/a/b") == "git.example.org/a/b"
    assert extra.origin_name("https://github.com/only") == "github.com/only"


def test_swh_parse_real_capture():
    items = list(extra.parse_softwareheritage(SWH))
    assert [i["name"] for i in items] == [
        "DzRepo/Python-Insights", "LuciaOriana123/Python-Prep", "sinpsarkar/Python---Assignment7"]
    one = items[0]
    assert one["url"] == "https://github.com/DzRepo/Python-Insights"
    assert one["kind"] == "repository"
    assert "Software Heritage" in one["summary"]
    ev = one["evidence"][0]
    assert ev["source"] == "softwareheritage"
    assert ev["visit_types"] == ["git"] and ev["nb_visits"] == 2
    assert ev["last_eventful_visit_date"] == "2021-06-05T04:13:00.26595Z"
    assert one["maintenance"] == 0.2  # archived 2021 activity is old
    assert "snapshot_id" in ev


def test_swh_keeps_only_origins_with_visits():
    payload = [
        {"url": "https://github.com/a/b", "has_visits": False, "visit_types": []},
        {"url": "https://github.com/c/d", "has_visits": True, "visit_types": ["git"], "nb_visits": 1},
    ]
    assert [i["name"] for i in extra.parse_softwareheritage(payload)] == ["c/d"]


def test_swh_skips_blank_url_and_non_list():
    assert list(extra.parse_softwareheritage([{"url": "", "has_visits": True}])) == []
    assert list(extra.parse_softwareheritage({"detail": "x"})) == []


def test_swh_caps_at_20():
    mk = lambda n: [{"url": f"https://github.com/o/r{i}", "has_visits": True} for i in range(n)]
    assert len(list(extra.parse_softwareheritage(mk(20)))) == 20
    assert len(list(extra.parse_softwareheritage(mk(21)))) == 20


def _resp(status=200, body=None, **headers):
    h = {k.replace("_", "-").lower(): str(v) for k, v in headers.items()}
    return status, h, json.dumps(SWH if body is None else body).encode()


def test_swh_collector_url_quotes_query_as_path_component():
    seen = []

    def fetch(url):
        seen.append(url)
        return _resp()

    col = extra.SoftwareHeritageCollector(fetch=fetch, clock=lambda: 0.0)
    got = run(drain(col, "a b/c"))
    assert seen == ["https://archive.softwareheritage.org/api/1/origin/search/a%20b%2Fc/?limit=20&with_visit=true"]
    assert len(got) == 3 and all(g["kind"] == "repository" for g in got)


def test_swh_rejects_empty_query_without_fetching():
    calls = []
    col = extra.SoftwareHeritageCollector(fetch=lambda u: calls.append(u) or _resp(), clock=lambda: 0.0)
    with pytest.raises(SourceError, match=r"^softwareheritage needs a non-empty query$"):
        run(drain(col, "   "))
    assert calls == []


def test_swh_429_raises_with_retry_after():
    col = extra.SoftwareHeritageCollector(fetch=lambda u: _resp(429, [], retry_after=30), clock=lambda: 0.0)
    with pytest.raises(SourceError, match=r"^softwareheritage rate limit hit \(HTTP 429\); retry after 30s$"):
        run(drain(col))


def test_swh_other_http_error_and_non_json():
    col = extra.SoftwareHeritageCollector(fetch=lambda u: _resp(500, []), clock=lambda: 0.0)
    with pytest.raises(SourceError, match=r"^softwareheritage returned HTTP 500$"):
        run(drain(col))
    bad = extra.SoftwareHeritageCollector(fetch=lambda u: (200, {}, b"<html>"), clock=lambda: 0.0)
    with pytest.raises(SourceError, match=r"^softwareheritage returned non-JSON content"):
        run(drain(bad))


def test_swh_respects_exhausted_window_until_reset():
    now = {"t": 1000.0}
    calls = []

    def fetch(url):
        calls.append(url)
        return _resp(200, None, x_ratelimit_limit=10, x_ratelimit_remaining=0, x_ratelimit_reset=1060)

    col = extra.SoftwareHeritageCollector(fetch=fetch, clock=lambda: now["t"])
    run(drain(col))
    assert len(calls) == 1
    with pytest.raises(SourceError, match=r"^softwareheritage rate window exhausted; resets in 60s$"):
        run(drain(col))
    assert len(calls) == 1  # no request was spent while exhausted
    now["t"] = 1060.0  # N: reset instant -> allowed again (boundary)
    run(drain(col))
    assert len(calls) == 2


def test_swh_remaining_one_is_still_allowed():
    calls = []

    def fetch(url):
        calls.append(url)
        return _resp(200, None, x_ratelimit_remaining=1, x_ratelimit_reset=9999)

    col = extra.SoftwareHeritageCollector(fetch=fetch, clock=lambda: 0.0)
    run(drain(col))
    run(drain(col))
    assert len(calls) == 2


def test_extra_source_collectors_names_and_kinds():
    cols = extra.extra_source_collectors()
    assert [(c.name, c.kind) for c in cols] == [("fyyd", "podcast"), ("softwareheritage", "repository")]


# ------------------------------------------------------------- health

class FakeCol:
    def __init__(self, name, items=None, exc=None, delay=0.0, kind="blog"):
        self.name, self.kind, self._items, self._exc, self._delay = name, kind, items or [], exc, delay

    async def collect(self, query):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc:
            raise self._exc
        for i in self._items:
            yield i


def _item(date_key=None, date=None, n="x"):
    ev = {"source": "s"}
    if date_key:
        ev[date_key] = date
    return {"name": n, "url": "https://e/" + n, "evidence": [ev]}


def test_freshness_picks_newest_across_known_keys():
    ev = [{"updated_at": "2020-01-01T00:00:00Z"}, {"lastpub": "2026-10-09T14:00:00+02:00"},
          {"last_eventful_visit_date": "2021-06-05T04:13:00.26595Z"}, {"published_at": "garbage"}]
    got = health.freshness_of(ev)
    assert got.isoformat().startswith("2026-10-09T12:00:00")
    assert health.freshness_of([{"stars": 3}]) is None
    assert health.freshness_of([]) is None


def test_probe_reports_ok_empty_error_with_latency_and_counts():
    ticks = iter([10.0, 10.25, 20.0, 20.5, 30.0, 31.0])
    clock = lambda: next(ticks)
    ok = run(health.probe_source(FakeCol("a", [_item("updated_at", "2026-10-01T00:00:00Z")]), "q", clock=clock))
    empty = run(health.probe_source(FakeCol("b"), "q", clock=clock))
    err = run(health.probe_source(FakeCol("c", exc=SourceError("down")), "q", clock=clock))
    assert (ok["status"], ok["count"], ok["latency_ms"]) == ("ok", 1, 250.0)
    assert ok["newest"] == "2026-10-01T00:00:00+00:00"
    assert (empty["status"], empty["count"], empty["latency_ms"]) == ("empty", 0, 500.0)
    assert (err["status"], err["error"], err["latency_ms"]) == ("error", "down", 1000.0)
    assert err["count"] == 0 and err["newest"] is None


def test_probe_flags_stale_by_age_boundary():
    now = health.datetime(2026, 10, 11, tzinfo=health.timezone.utc)
    mk = lambda d: FakeCol("s", [_item("updated_at", d)])
    at = run(health.probe_source(mk("2025-10-11T00:00:00Z"), "q", now=now, max_age_days=365))
    over = run(health.probe_source(mk("2025-10-10T23:59:59Z"), "q", now=now, max_age_days=365))
    assert at["stale"] is False and over["stale"] is True
    nodate = run(health.probe_source(FakeCol("n", [_item()]), "q", now=now))
    assert nodate["stale"] is None  # unknown, not claimed fresh or stale


def test_probe_times_out_as_error():
    r = run(health.probe_source(FakeCol("slow", [_item()], delay=0.5), "q", timeout=0.05))
    assert r["status"] == "error" and r["error"] == "timed out after 0.05s"


def test_report_aggregates_and_isolates_failures():
    cols = [FakeCol("a", [_item("updated_at", "2026-10-01T00:00:00Z")]), FakeCol("b"),
            FakeCol("c", exc=RuntimeError("boom"))]
    rep = run(health.health_report(cols, "q"))
    assert [s["source"] for s in rep["sources"]] == ["a", "b", "c"]
    assert rep["summary"] == {"ok": 1, "empty": 1, "error": 1, "total": 3}
    assert rep["query"] == "q" and rep["generated_at"]
    assert rep["sources"][2]["error"] == "boom"
    json.dumps(rep)  # JSON-serialisable


def test_probe_caps_counted_items_at_20():
    r = run(health.probe_source(FakeCol("many", [_item(n=str(i)) for i in range(25)]), "q"))
    assert r["count"] == 20


# ---------------------------------------------------- review additions

def test_swh_recency_prefers_eventful_date_over_last_visit():
    payload = [{"url": "https://github.com/o/r", "has_visits": True, "visit_types": ["git"],
                "last_visit_date": "2099-01-01T00:00:00+00:00",
                "last_eventful_visit_date": "2001-01-01T00:00:00+00:00"}]
    assert list(extra.parse_softwareheritage(payload))[0]["maintenance"] == 0.2
    only_visit = [{"url": "https://github.com/o/r", "has_visits": True, "last_visit_date": "2099-01-01T00:00:00+00:00"}]
    assert list(extra.parse_softwareheritage(only_visit))[0]["maintenance"] == 0.8


def test_fyyd_titled_item_without_any_url_is_skipped():
    payload = {"status": 1, "data": [{"title": "No url", "htmlURL": "", "url_fyyd": ""}]}
    assert list(extra.parse_fyyd(payload)) == []


def test_parse_ts_handles_five_digit_fraction_and_rejects_garbage():
    got = extra.parse_ts("2021-06-05T04:13:00.26595Z")
    assert got is not None and got.microsecond == 265950 and got.utcoffset().total_seconds() == 0
    assert extra.parse_ts("2026-10-09T14:00:00+02:00").hour == 12
    assert extra.parse_ts("2026-10-09T14:00:00").tzinfo is not None  # naive -> UTC
    assert extra.parse_ts("garbage") is None and extra.parse_ts("") is None and extra.parse_ts(None) is None


def test_all_collectors_has_no_duplicate_names_even_if_wiring_applied(monkeypatch):
    names = [c.name for c in health.all_collectors()]
    assert len(names) == len(set(names))
    assert names[-2:] == ["fyyd", "softwareheritage"]
    base = sources.default_source_collectors
    monkeypatch.setattr(sources, "default_source_collectors", lambda: base() + extra.extra_source_collectors())
    again = [c.name for c in health.all_collectors()]
    assert len(again) == len(set(again)) and again.count("fyyd") == 1
