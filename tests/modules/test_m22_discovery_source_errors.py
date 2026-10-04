"""m22 POST /pipeline/discoveries must not turn 'every source failed' into an empty 201 ('no matches')."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.m22_tools_hub.pipeline_routes import get_discovery_service


class _FakeService:  # LABELED FIXTURE: stands in for the discovery service, no network
    def __init__(self, found, errors):
        self._found, self.last_errors = found, errors

    async def discover_report(self, query):
        n = len(self.last_errors)
        return {"ranked": self._found, "errors": dict(self.last_errors), "sources_attempted": n + 1,
                "sources_ok": 0 if (self.last_errors and not self._found) else 1, "sources_failed": n}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_DATABASE_URL", f"sqlite:///{tmp_path}/m22.db")
    monkeypatch.setenv("ATLAS_AUTO_CREATE_SCHEMA", "1")
    from app.modules.m22_tools_hub import pipeline_routes
    monkeypatch.setattr(pipeline_routes, "_pipelines", {})
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_discovery_service, None)


H = {"x-atlas-tenant": "m22-err-tenant"}


def test_all_sources_failed_is_502_with_source_errors_not_empty_201(client):
    app.dependency_overrides[get_discovery_service] = lambda: _FakeService([], {"pypi": "boom", "npm": "boom2"})
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "x"}, headers=H)
    assert r.status_code == 502
    assert r.json()["detail"]["source_errors"] == {"pypi": "source_failed", "npm": "source_failed"}


def test_no_errors_and_no_results_is_a_genuine_empty_201(client):
    app.dependency_overrides[get_discovery_service] = lambda: _FakeService([], {})
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "x"}, headers=H)
    assert r.status_code == 201 and r.json() == []
    assert "x-atlas-discovery-source-errors" not in r.headers


def test_partial_failure_keeps_list_body_and_reports_errors_in_header(client):
    from app.modules.m22_tools_hub.service import Candidate
    import inspect
    sig = inspect.signature(Candidate)
    kwargs = {k: v for k, v in dict(name="fixture-tool", kind="package", source="pypi", url="https://example.invalid/x",
                                     summary="LABELED FIXTURE").items() if k in sig.parameters}
    cand = Candidate(**kwargs)
    app.dependency_overrides[get_discovery_service] = lambda: _FakeService([cand], {"npm": "down"})
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "x"}, headers=H)
    assert r.status_code == 201 and isinstance(r.json(), list)
    assert json.loads(r.headers["x-atlas-discovery-source-errors"])["shown"] == {"npm": "source_failed"}


def test_source_errors_never_expose_urls_ips_queries_or_secrets_and_are_bounded(client):
    leaky = {f"s{i}": "<urlopen error https://user:SECRETTOKEN@host.example/search?q=private-query 10.0.0.5>" for i in range(40)}
    app.dependency_overrides[get_discovery_service] = lambda: _FakeService([], leaky)
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "private-query"}, headers=H)
    body = r.text
    for secret in ("SECRETTOKEN", "private-query", "10.0.0.5", "host.example", "https://"):
        assert secret not in body
    assert len(r.json()["detail"]["source_errors"]) <= 12


def test_concurrent_discoveries_do_not_see_each_others_errors():
    """Real Service, LABELED FIXTURE collectors: overlapping calls each get only their own failures."""
    import asyncio
    from app.modules.m22_tools_hub.service import Service

    class Failing:  # LABELED FIXTURE
        kind = "tool"
        def __init__(self, name): self.name = name
        async def collect(self, query):
            await asyncio.sleep(0.05)
            raise OSError(f"{self.name} down")
            yield  # pragma: no cover

    svc_a = Service.__new__(Service)
    async def run():
        svc = Service(approval_store=None, collectors=[Failing("src-a"), Failing("src-b")])
        async def one(kinds_name):
            svc.collectors = svc.collectors  # same shared service object
            return await svc.discover_with_errors(kinds_name)
        (ra, ea), (rb, eb) = await asyncio.gather(one("q1"), one("q2"))
        return ea, eb
    ea, eb = asyncio.run(run())
    assert set(ea) == {"src-a", "src-b"} and set(eb) == {"src-a", "src-b"}
    assert "src-a down" in ea["src-a"] and "src-b down" in eb["src-b"]
    # call-local dicts, not the same object
    assert ea is not eb


# ---- end-to-end through the route with the REAL Service and LABELED FIXTURE collectors (no network) ----
import asyncio  # noqa: E402


class _Failing:  # LABELED FIXTURE
    kind = "tool"

    def __init__(self, name, msg="boom"):
        self.name, self.msg = name, msg

    async def collect(self, query):
        raise OSError(self.msg)
        yield  # pragma: no cover


class _Empty:  # LABELED FIXTURE: a source that answers genuinely with nothing
    kind = "tool"

    def __init__(self, name):
        self.name = name

    async def collect(self, query):
        return
        yield  # pragma: no cover


def _real(collectors):
    from app.modules.m22_tools_hub.service import Service
    return Service(approval_store=None, collectors=collectors)


def test_real_service_all_failed_is_502_with_counts_and_commits_no_snapshot_or_history(client):
    svc = _real([_Failing("a"), _Failing("b")])
    svc._query_snapshots["q"] = {"k": "previously-found-tool"}  # a real earlier result that a failed run must not erase
    app.dependency_overrides[get_discovery_service] = lambda: svc
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "q"}, headers=H)
    assert r.status_code == 502
    d = r.json()["detail"]
    assert (d["sources_attempted"], d["sources_ok"], d["sources_failed"]) == (2, 0, 2)
    assert svc._query_snapshots["q"] == {"k": "previously-found-tool"}  # not overwritten with an empty snapshot
    assert svc.query_history == []
    assert svc.last_diffs["q"]["incomplete"] is True and "removed" not in svc.last_diffs["q"]


def test_real_service_partial_with_genuine_empty_is_201_not_no_source_answered(client):
    svc = _real([_Empty("ok-src"), _Failing("bad-src")])
    app.dependency_overrides[get_discovery_service] = lambda: svc
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "q"}, headers=H)
    assert r.status_code == 201 and r.json() == []
    hdr = json.loads(r.headers["x-atlas-discovery-source-errors"])
    assert (hdr["sources_ok"], hdr["sources_failed"]) == (1, 1) and hdr["shown"] == {"bad-src": "source_failed"}
    assert svc.query_history == []  # incomplete run is not committed as a real empty result


def test_real_service_complete_run_still_commits_snapshot_and_history(client):
    svc = _real([_Empty("ok-1"), _Empty("ok-2")])
    app.dependency_overrides[get_discovery_service] = lambda: svc
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "q"}, headers=H)
    assert r.status_code == 201 and r.json() == []
    assert "x-atlas-discovery-source-errors" not in r.headers
    assert svc._query_snapshots["q"] == {} and svc.query_history[-1]["count"] == 0


def test_real_service_oversize_errors_header_is_valid_bounded_json_and_redacted(client, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    cols = [_Failing(f"s{i}", "https://user:SECRETTOKEN@h.example/x?q=private-query 10.0.0.5") for i in range(40)]
    cols.append(_Empty("ok"))
    svc = _real(cols)
    app.dependency_overrides[get_discovery_service] = lambda: svc
    r = client.post("/api/v1/tools-hub/pipeline/discoveries", json={"query": "private-query"}, headers=H)
    assert r.status_code == 201
    raw = r.headers["x-atlas-discovery-source-errors"]
    hdr = json.loads(raw)  # valid JSON, not a sliced string
    assert len(raw) < 1000 and len(hdr["shown"]) == 5 and hdr["omitted"] == 35 and hdr["sources_failed"] == 40
    for secret in ("SECRETTOKEN", "private-query", "10.0.0.5", "h.example"):
        assert secret not in raw
        assert secret not in caplog.text  # nor in server logs


# ---- tenant scoping of the in-memory discovery service ----
def test_discovery_service_state_is_per_tenant_and_collectors_are_shared(monkeypatch):
    from app.modules.m22_tools_hub import routes as rt
    monkeypatch.setattr(rt, "_services", {})
    monkeypatch.setattr(rt, "_shared_collectors", [_Empty("shared-public-source")])
    a, b = rt.service_for_tenant("tenant-a"), rt.service_for_tenant("tenant-b")
    assert a is not b and rt.service_for_tenant("tenant-a") is a
    a.query_history.append({"query": "tenant-a-private-query"})
    a._query_snapshots["x"] = {"k": "a-only"}
    a.candidates["id"] = object()
    assert b.query_history == [] and b._query_snapshots == {} and b.candidates == {}
    assert a.collectors[0] is b.collectors[0]  # public-data collectors shared by design


def test_discovery_service_cap_fails_closed_without_evicting(monkeypatch):
    from fastapi import HTTPException
    from app.modules.m22_tools_hub import routes as rt
    monkeypatch.setattr(rt, "_services", {})
    monkeypatch.setattr(rt, "_shared_collectors", [])
    monkeypatch.setattr(rt, "MAX_TENANT_SERVICES", 2)
    t1, t2 = rt.service_for_tenant("t1"), rt.service_for_tenant("t2")
    with pytest.raises(HTTPException) as e:
        rt.service_for_tenant("t3")
    assert e.value.status_code == 503 and set(rt._services) == {"t1", "t2"}
    assert rt.service_for_tenant("t1") is t1


def test_discovery_history_endpoint_does_not_leak_across_tenants_through_http(monkeypatch):
    from app.modules.m22_tools_hub import routes as rt
    monkeypatch.setattr(rt, "_services", {})
    monkeypatch.setattr(rt, "_shared_collectors", [])
    c = TestClient(app, raise_server_exceptions=False)
    rt.service_for_tenant("hist-a").query_history.append({"query": "only-for-a"})
    ra = c.get("/api/v1/tools-hub/queries", headers={"x-atlas-tenant": "hist-a"}).json()
    rb = c.get("/api/v1/tools-hub/queries", headers={"x-atlas-tenant": "hist-b"}).json()
    assert ra["queries"] == [{"query": "only-for-a"}] and rb["queries"] == []


def test_service_working_caches_are_bounded_after_writes_and_evictions_are_reported():
    svc = _real([_Empty("x")])
    svc.MAX_CACHED_CANDIDATES, svc.MAX_QUERY_SNAPSHOTS = 3, 2
    for i in range(5):
        svc.candidates[f"c{i}"] = object()
        svc._query_snapshots[f"q{i}"] = {}
        svc.last_diffs[f"q{i}"] = {}
    svc._bound_caches()
    assert list(svc.candidates) == ["c2", "c3", "c4"]  # exactly the cap, not cap+1
    assert len(svc._query_snapshots) == 2 and len(svc.last_diffs) == 2
    st = svc.cache_stats()
    assert st["evicted_total"] == 2 + 3 + 3 and st["baseline_resets_total"] == 3
    assert st["candidates"] == 3 and st["candidates_cap"] == 3


def test_installed_and_proposed_candidates_are_never_evicted_and_portfolio_still_works():
    from types import SimpleNamespace
    svc = _real([_Empty("x")])
    svc.MAX_CACHED_CANDIDATES = 2
    for i in range(6):
        svc.candidates[f"c{i}"] = SimpleNamespace(id=f"c{i}")
    svc.installed["c0"] = {"proposal": None, "evidence": {}, "installed_at": "t"}
    svc.proposals["p1"] = SimpleNamespace(candidate_id="c1")
    svc._bound_caches()
    assert "c0" in svc.candidates and "c1" in svc.candidates  # retained although oldest
    assert [x["candidate"].id for x in svc.portfolio()] == ["c0"]  # no KeyError
    assert svc.cache_stats()["protected_candidates"] == 2 and len(svc.candidates) == 2
    assert svc.cache_evicted == 4


def test_snapshot_eviction_is_reported_as_baseline_reset_on_next_run_not_silent_first_run():
    svc = _real([_Empty("x")])
    svc.MAX_QUERY_SNAPSHOTS = 1

    async def go():
        await svc.discover_report("q1")
        await svc.discover_report("q2")  # evicts q1's snapshot -> baseline reset
        return await svc.discover_report("q1")
    rep = asyncio.run(go())
    assert svc.last_diffs["q1"]["first_run"] is True and svc.last_diffs["q1"]["baseline_reset"] is True
    assert rep["cache"]["baseline_resets_total"] >= 1


def test_cache_stats_are_visible_through_the_queries_api(monkeypatch):
    from app.modules.m22_tools_hub import routes as rt
    monkeypatch.setattr(rt, "_services", {})
    monkeypatch.setattr(rt, "_shared_collectors", [])
    rt.service_for_tenant("stat-t").cache_evicted = 7
    c = TestClient(app, raise_server_exceptions=False)
    body = c.get("/api/v1/tools-hub/queries", headers={"x-atlas-tenant": "stat-t"}).json()
    assert body["cache"]["evicted_total"] == 7


def test_baseline_reset_flag_is_one_shot_across_two_complete_runs():
    svc = _real([_Empty("x")])
    svc.MAX_QUERY_SNAPSHOTS = 1

    async def go():
        await svc.discover_report("q1")
        await svc.discover_report("q2")   # evicts q1's baseline
        await svc.discover_report("q1")   # run 1 after eviction
        first = dict(svc.last_diffs["q1"])
        await svc.discover_report("q1")   # run 2: baseline now exists again
        return first, dict(svc.last_diffs["q1"])
    first, second = asyncio.run(go())
    assert first["first_run"] is True and first["baseline_reset"] is True
    assert second["first_run"] is False and second["baseline_reset"] is False


def test_reset_flag_tracking_overflow_is_counted_not_silent():
    svc = _real([_Empty("x")])
    svc.MAX_QUERY_SNAPSHOTS = 1
    for i in range(1005):
        svc._query_snapshots[f"q{i}"] = {}
        svc._bound_caches()
    assert svc.cache_stats()["baseline_reset_flags_overflowed"] == 1004 - 1000


def test_discovery_report_labels_candidates_as_whole_cache_and_gives_query_scoped_names():
    svc = _real([_Empty("x")])
    svc._query_snapshots["q"] = {"k": "name-for-q"}
    rep = svc.discovery_report("q")
    assert "NOT filtered" in rep["candidates_scope"] and rep["query_snapshot_names"] == ["name-for-q"]
