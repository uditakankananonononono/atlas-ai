"""Reachability of the m20 routes that answer without a bound service.

The m20 spec router is mounted the way app.main mounts every registry spec
(prefix /api/v1, require_tenant dependency) and exercised with production
RS256 test identities. The probes are empty-input probes: they prove the route
path resolves for an authenticated tenant, not that any engine output is right.
"""
import re

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.context import require_tenant
from app.modules.m20_general_cognitive_worker import routes, spec

PREFIX = "/api/v1/api/modules/20"
NOT_BOUND_MARK = "not bound for authenticated tenant"

REACHABLE = {
    ('post', '/api/v1/api/modules/20/meta/decisions/regret'): 422,
    ('post', '/api/v1/api/modules/20/meta/decisions/opportunity-cost'): 422,
    ('post', '/api/v1/api/modules/20/meta/decisions/sunk-cost'): 422,
    ('post', '/api/v1/api/modules/20/meta/systems/loops'): 200,
    ('post', '/api/v1/api/modules/20/legal/support'): 422,
    ('get', '/api/v1/api/modules/20/education/capabilities'): 200,
    ('post', '/api/v1/api/modules/20/education/{capability}'): 422,
    ('get', '/api/v1/api/modules/20/social-research-1710-1759/capabilities'): 200,
    ('post', '/api/v1/api/modules/20/social-research-1710-1759/{method}'): 422,
    ('get', '/api/v1/api/modules/20/political-social-1760-1809/capabilities'): 200,
    ('post', '/api/v1/api/modules/20/political-social-1760-1809/{row_id}'): 422,
    ('post', '/api/v1/api/modules/20/engineering/1510-1559/analyze'): 422,
    ('get', '/api/v1/api/modules/20/learning-reasoning-810-859/capabilities'): 200,
    ('post', '/api/v1/api/modules/20/learning-reasoning-810-859/{method}'): 422,
    ('get', '/api/v1/api/modules/20/cognitive-1960-2009/methods'): 200,
    ('post', '/api/v1/api/modules/20/cognitive-1960-2009/analyze'): 422,
    ('post', '/api/v1/api/modules/20/humanities/1810-1859/analyze'): 422,
    ('get', '/api/v1/api/modules/20/cognitive-learning-860-909/capabilities'): 200,
    ('post', '/api/v1/api/modules/20/cognitive-learning-860-909/{row_id}'): 422,
    ('post', '/api/v1/api/modules/20/platform-engineering/585-634/analyze'): 422,
    ('get', '/api/v1/api/modules/20/optimization-story-235-280/capabilities'): 200,
    ('post', '/api/v1/api/modules/20/optimization-story-235-280/{method}'): 422,
    ('get', '/api/v1/api/modules/20/negotiation-behavior-85-109/methods'): 200,
    ('post', '/api/v1/api/modules/20/negotiation-behavior-85-109/analyze'): 422,
    ('post', '/api/v1/api/modules/20/software-practice/685-709/analyze'): 422,
    ('post', '/api/v1/api/modules/20/legacy-modernization/694/modernize'): 422,
    ('get', '/api/v1/api/modules/20/technical-spec-133-165/methods'): 200,
    ('post', '/api/v1/api/modules/20/technical-spec-133-165/analyze'): 422,
    ('get', '/api/v1/api/modules/20/technical-spec/199-229/requirements'): 200,
    ('post', '/api/v1/api/modules/20/technical-spec/199-229/{row}'): 422,
    ('get', '/api/v1/api/modules/20/atomic-concepts-93-115/methods'): 200,
    ('post', '/api/v1/api/modules/20/atomic-concepts-93-115/analyze'): 422,
    ('post', '/api/v1/api/modules/20/atomic-concepts-70-92'): 422,
    ('get', '/api/v1/api/modules/20/atomic-concepts/139-160'): 200,
    ('post', '/api/v1/api/modules/20/atomic-concepts/139-160/{atomic_row_id}'): 422,
    ('post', '/api/v1/api/modules/20/specialized-domain/analyze'): 422,
    ('post', '/api/v1/api/modules/20/legal-1260-1309/support'): 422,
    ('post', '/api/v1/api/modules/20/execution-truth-ledger'): 200,
    ('post', '/api/v1/api/modules/20/agi-runtime/world/evidence'): 422,
    ('get', '/api/v1/api/modules/20/agi-runtime/world/hypotheses'): 422,
    ('post', '/api/v1/api/modules/20/agi-runtime/world/snapshots'): 201,
    ('get', '/api/v1/api/modules/20/agi-runtime/world/snapshots/verify'): 200,
    ('post', '/api/v1/api/modules/20/agi-runtime/goals/proposals'): 422,
    ('post', '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/request-activation'): 404,
    ('post', '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/activate'): 422,
    ('post', '/api/v1/api/modules/20/agi-runtime/evaluations/cross-domain'): 422,
    ('post', '/api/v1/api/modules/20/genetic-algorithms/solve'): 422,
    ('post', '/api/v1/api/modules/20/genetic-algorithms/solve-quadratic'): 422,
    ('post', '/api/v1/api/modules/20/propositional-reasoning/entail'): 422,
    ('post', '/api/v1/api/modules/20/particle-swarm/solve'): 422,
    ('post', '/api/v1/api/modules/20/differential-evolution/solve'): 422,
    ('post', '/api/v1/api/modules/20/genetic-programming/solve'): 422,
    ('post', '/api/v1/api/modules/20/artificial-life/simulate'): 422,
    ('post', '/api/v1/api/modules/20/api-documentation/openapi'): 422,
    ('post', '/api/v1/api/modules/20/architecture-decisions/705/record'): 422,
    ('post', '/api/v1/api/modules/20/code-comments/706/audit'): 422,
    ('post', '/api/v1/api/modules/20/naming-conventions/707/check'): 422,
    ('post', '/api/v1/api/modules/20/code-formatting/708/inspect'): 422,
    ('post', '/api/v1/api/modules/20/engineering/statistical_process_control1536/run'): 422,
    ('post', '/api/v1/api/modules/20/engineering/process_capability1537/run'): 422,
    ('post', '/api/v1/api/modules/20/engineering/measurement_systems_analysis1538/run'): 422,
    ('post', '/api/v1/api/modules/20/engineering/design_of_experiments1539/run'): 422,
    ('post', '/api/v1/api/modules/20/engineering/taguchi_methods1540/run'): 422,
    ('post', '/api/v1/api/modules/20/engineering/response_surface_methodology1541/run'): 422,
    ('post', '/api/v1/api/modules/20/engineering/robust_design1542/run'): 422,
    ('post', '/api/v1/api/modules/20/bdd-scenarios/686/execute'): 422,
    ('post', '/api/v1/api/modules/20/test-driven-development/687/check'): 422,
    ('post', '/api/v1/api/modules/20/acceptance-test-driven-development/688/bookkeeping'): 422,
    ('post', '/api/v1/api/modules/20/refactoring/689/rename-local'): 422,
    ('post', '/api/v1/api/modules/20/code-review/690/review'): 422,
    ('post', '/api/v1/api/modules/20/pair-programming/691/diagnostics'): 422,
    ('post', '/api/v1/api/modules/20/mob-programming/692/plan'): 422,
    ('post', '/api/v1/api/modules/20/mob-programming/692/audit'): 422,
    ('post', '/api/v1/api/modules/20/technical-debt/693/schedule'): 422,
}
NOT_BOUND = {
    'GCW service not bound for authenticated tenant': 107,
    'GCW runtime not bound for authenticated tenant': 34,
    'twin registry not bound for authenticated tenant': 4,
    'transfer learner not bound for authenticated tenant': 2,
    'predictor not bound for authenticated tenant': 2,
    'registry not bound for authenticated tenant': 3,
    'model not bound for authenticated tenant': 5,
    'investigator not bound for authenticated tenant': 4,
}
TOTAL_ROUTES = 235


@pytest.fixture()
def env(monkeypatch, oidc_auth_headers):
    monkeypatch.delenv("ATLAS_DEV_NO_AUTH", raising=False)
    monkeypatch.setenv("ATLAS_ENV", "production")
    monkeypatch.delenv("ATLAS_GCW_AUTOBIND", raising=False)
    monkeypatch.setattr(routes, "_services", {})
    monkeypatch.setattr(routes, "_service", None)
    from app.modules.m20_general_cognitive_worker import agi_routes
    monkeypatch.setattr(agi_routes, "_services", {})
    app = FastAPI()
    app.include_router(spec.router, prefix="/api/v1", dependencies=[Depends(require_tenant)])
    return app, TestClient(app, raise_server_exceptions=False), oidc_auth_headers("tenant-a")


def ops(app):
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method in ("get", "post", "put", "delete", "patch"):
                yield method, path


def call(client, method, path, headers=None):
    url = re.sub(r"\{[^}]+\}", "x", path)
    return client.request(method.upper(), url, headers=headers or {}, json=None if method == "get" else {})


def detail(r):
    try:
        return str(r.json().get("detail"))
    except Exception:
        return ""


def test_route_inventory_is_pinned(env):
    app, _, _ = env
    got = list(ops(app))
    assert len(got) == TOTAL_ROUTES
    assert len(set(got)) == len(got)
    assert all(p.startswith(PREFIX + "/") for _, p in got)


def test_every_route_refuses_unauthenticated_with_401(env):
    app, c, _ = env
    bad = [(m, p, call(c, m, p).status_code) for m, p in ops(app)]
    assert [x for x in bad if x[2] != 401] == []


def test_authenticated_probe_matches_pinned_reachable_set_and_not_bound_counts(env):
    app, c, h = env
    reach, not_bound = {}, {}
    for m, p in ops(app):
        r = call(c, m, p, h)
        if r.status_code == 503 and NOT_BOUND_MARK in detail(r):
            not_bound[detail(r)] = not_bound.get(detail(r), 0) + 1
        else:
            reach[(m, p)] = r.status_code
    assert reach == REACHABLE
    assert not_bound == NOT_BOUND
    assert all(s in (200, 201, 404, 422) for s in reach.values())


def test_reachable_routes_do_not_depend_on_binding_or_autobind(env, monkeypatch):
    app, c, h = env
    monkeypatch.setenv("ATLAS_GCW_AUTOBIND", "1")
    for (m, p), status in REACHABLE.items():
        assert call(c, m, p, h).status_code == status, (m, p)
    assert routes._services == {}


def test_capability_listings_are_live_and_nonempty(env):
    _, c, h = env
    for fam in ("education", "social-research-1710-1759", "political-social-1760-1809", "learning-reasoning-810-859",
                "cognitive-learning-860-909", "optimization-story-235-280"):
        r = c.get(f"{PREFIX}/{fam}/capabilities", headers=h)
        assert r.status_code == 200 and r.json(), fam
    for fam in ("cognitive-1960-2009", "negotiation-behavior-85-109", "technical-spec-133-165", "atomic-concepts-93-115"):
        r = c.get(f"{PREFIX}/{fam}/methods", headers=h)
        assert r.status_code == 200 and r.json(), fam
    assert len(c.get(f"{PREFIX}/negotiation-behavior-85-109/methods", headers=h).json()) == 25


def test_negotiation_every_method_reachable_and_valid_calls_return_200(env):
    from app.modules.m20_general_cognitive_worker.negotiation_behavior_0085_0109 import ROWS
    _, c, h = env
    url = f"{PREFIX}/negotiation-behavior-85-109/analyze"
    statuses = {m: c.post(url, headers=h, json={"method": m, "data": {}}).status_code for m in ROWS}
    assert set(statuses.values()) == {200, 422}
    assert sorted(m for m, s in statuses.items() if s == 200) == ["credible_threat_construction", "reciprocity_triggers"]
    r = c.post(url, headers=h, json={"method": "zopa_mapping", "data": {"seller_reservation": 5, "buyer_reservation": 10}})
    assert r.status_code == 200 and r.json()["feature_row"] == 93
    assert c.post(url, headers=h, json={"method": "bad"}).status_code == 422
    assert c.post(url, json={"method": "zopa_mapping", "data": {}}).status_code == 401


def test_software_practice_every_method_reachable_and_valid_call_returns_200(env):
    import typing
    from app.modules.m20_general_cognitive_worker.software_practice_routes_685_709 import Method
    _, c, h = env
    url = f"{PREFIX}/software-practice/685-709/analyze"
    methods = typing.get_args(Method)
    assert len(methods) == 25
    for m in methods:
        r = c.post(url, headers=h, json={"method": m, "data": {}})
        assert r.status_code == 422 and "missing required fields" in detail(r), m
    r = c.post(url, headers=h, json={"method": "semantic_versioning",
                                     "data": {"current_version": "1.2.3", "changes": [{"breaking": True}]}})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["next_version"] == "2.0.0"
    assert c.post(url, headers=h, json={"method": "nope", "data": {}}).status_code == 422
    assert c.post(url, json={"method": "semantic_versioning", "data": {}}).status_code == 401


def test_mount_matches_registry_when_importable():
    try:
        from app.modules.registry import IMPLEMENTED_SPECS
    except ImportError as e:
        pytest.skip(f"registry needs optional packages absent here: {e.name}")
    assert [s for s in IMPLEMENTED_SPECS if s.id == 20] == [spec]
