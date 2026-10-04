"""m22 POST /pipeline/discoveries must not turn 'every source failed' into an empty 201 ('no matches')."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.m22_tools_hub.pipeline_routes import get_discovery_service


class _FakeService:  # LABELED FIXTURE: stands in for the discovery service, no network
    def __init__(self, found, errors):
        self._found, self.last_errors = found, errors

    async def discover(self, query):
        return self._found


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
    assert r.json()["detail"]["source_errors"] == {"pypi": "boom", "npm": "boom2"}


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
    assert json.loads(r.headers["x-atlas-discovery-source-errors"]) == {"npm": "down"}
