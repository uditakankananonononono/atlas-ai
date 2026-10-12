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
    monkeypatch.delenv("ATLAS_AGI_RUNTIME_AUTOBIND", raising=False)
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


# Additive snapshot on 6be4678: preserve the R2 historical pins above.
# Counts below were re-derived by probing the mounted operation inventory.
ADDITIONAL_REACHABLE = {('post', '/api/v1/api/modules/20/axial-fea/1512/solve'): 422,
 ('post', '/api/v1/api/modules/20/cad-modeling/1511/evaluate'): 422,
 ('post', '/api/v1/api/modules/20/design-for-six-sigma/1530/run'): 422,
 ('post', '/api/v1/api/modules/20/flow-balance/1513/evaluate'): 422,
 ('post', '/api/v1/api/modules/20/mechanical-design/1510/evaluate'): 422,
 ('post', '/api/v1/api/modules/20/quality-assurance/1535/evaluate'): 422}
CURRENT_INVENTORY = (('get', '/api/v1/api/modules/20/agi-runtime/world/hypotheses'),
 ('get', '/api/v1/api/modules/20/agi-runtime/world/snapshots/verify'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/calibration'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/events'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/memory/episodes'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/memory/facts'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/methods'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/retrospectives'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/compare'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/history'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/supervision'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/decision'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/evidence'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/mcts'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tools'),
 ('get', '/api/v1/api/modules/20/atomic-concepts-93-115/methods'),
 ('get', '/api/v1/api/modules/20/atomic-concepts/139-160'),
 ('get', '/api/v1/api/modules/20/bayesian-models'),
 ('get', '/api/v1/api/modules/20/cognitive-1960-2009/methods'),
 ('get', '/api/v1/api/modules/20/cognitive-learning-860-909/capabilities'),
 ('get', '/api/v1/api/modules/20/curiosity-investigator/queue'),
 ('get', '/api/v1/api/modules/20/digital-twins/{name}'),
 ('get', '/api/v1/api/modules/20/education/capabilities'),
 ('get', '/api/v1/api/modules/20/health'),
 ('get', '/api/v1/api/modules/20/learning-reasoning-810-859/capabilities'),
 ('get', '/api/v1/api/modules/20/memory/episodes'),
 ('get', '/api/v1/api/modules/20/memory/facts'),
 ('get', '/api/v1/api/modules/20/meta/calibration/curve'),
 ('get', '/api/v1/api/modules/20/meta/epistemic-calendar/due'),
 ('get', '/api/v1/api/modules/20/meta/insights/stale'),
 ('get', '/api/v1/api/modules/20/meta/knowledge-decay/forecast'),
 ('get', '/api/v1/api/modules/20/meta/world-models'),
 ('get', '/api/v1/api/modules/20/negotiation-behavior-85-109/methods'),
 ('get', '/api/v1/api/modules/20/optimization-story-235-280/capabilities'),
 ('get', '/api/v1/api/modules/20/political-social-1760-1809/capabilities'),
 ('get', '/api/v1/api/modules/20/skills'),
 ('get', '/api/v1/api/modules/20/social-research-1710-1759/capabilities'),
 ('get', '/api/v1/api/modules/20/standup'),
 ('get', '/api/v1/api/modules/20/tasks'),
 ('get', '/api/v1/api/modules/20/tasks/{task_id}'),
 ('get', '/api/v1/api/modules/20/technical-spec-133-165/methods'),
 ('get', '/api/v1/api/modules/20/technical-spec/199-229/requirements'),
 ('get', '/api/v1/api/modules/20/tools'),
 ('get', '/api/v1/api/modules/20/traces'),
 ('patch',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/risks/{risk_id}'),
 ('patch',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/schedule'),
 ('post',
  '/api/v1/api/modules/20/acceptance-test-driven-development/688/bookkeeping'),
 ('post', '/api/v1/api/modules/20/agi-runtime/evaluations/cross-domain'),
 ('post', '/api/v1/api/modules/20/agi-runtime/goals/proposals'),
 ('post', '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/activate'),
 ('post',
  '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/request-activation'),
 ('post', '/api/v1/api/modules/20/agi-runtime/world/evidence'),
 ('post', '/api/v1/api/modules/20/agi-runtime/world/snapshots'),
 ('post', '/api/v1/api/modules/20/api-documentation/openapi'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/memory/facts'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/memory/recall'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/methods/{name}/activate'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/revise'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/sandbox/run'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/step'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tasks'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/close'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/context'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/preflight'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/step'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/steps/{node_id}/retry'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tools/select'),
 ('post', '/api/v1/api/modules/20/architecture-decisions/705/record'),
 ('post', '/api/v1/api/modules/20/artificial-life/simulate'),
 ('post', '/api/v1/api/modules/20/atomic-concepts-70-92'),
 ('post', '/api/v1/api/modules/20/atomic-concepts-93-115/analyze'),
 ('post', '/api/v1/api/modules/20/atomic-concepts/139-160/{atomic_row_id}'),
 ('post', '/api/v1/api/modules/20/axial-fea/1512/solve'),
 ('post', '/api/v1/api/modules/20/bayesian-models/configure'),
 ('post', '/api/v1/api/modules/20/bayesian-models/evidence'),
 ('post', '/api/v1/api/modules/20/bdd-scenarios/686/execute'),
 ('post', '/api/v1/api/modules/20/cad-modeling/1511/evaluate'),
 ('post', '/api/v1/api/modules/20/calibration-predictor/ingest'),
 ('post', '/api/v1/api/modules/20/calibration-predictor/predict'),
 ('post', '/api/v1/api/modules/20/code-comments/706/audit'),
 ('post', '/api/v1/api/modules/20/code-formatting/708/inspect'),
 ('post', '/api/v1/api/modules/20/code-review/690/review'),
 ('post', '/api/v1/api/modules/20/cognitive-1960-2009/analyze'),
 ('post', '/api/v1/api/modules/20/cognitive-learning-860-909/{row_id}'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/authorize'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/enqueue'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/run'),
 ('post', '/api/v1/api/modules/20/decay-survival/evaluate'),
 ('post', '/api/v1/api/modules/20/decay-survival/forecast'),
 ('post', '/api/v1/api/modules/20/decay-survival/ingest'),
 ('post', '/api/v1/api/modules/20/decay-survival/refresh'),
 ('post', '/api/v1/api/modules/20/decay-survival/track'),
 ('post', '/api/v1/api/modules/20/design-for-six-sigma/1530/run'),
 ('post', '/api/v1/api/modules/20/differential-evolution/solve'),
 ('post', '/api/v1/api/modules/20/digital-twins'),
 ('post', '/api/v1/api/modules/20/digital-twins/{name}/assimilate'),
 ('post', '/api/v1/api/modules/20/digital-twins/{name}/forecast'),
 ('post', '/api/v1/api/modules/20/education/{capability}'),
 ('post', '/api/v1/api/modules/20/engineering/1510-1559/analyze'),
 ('post', '/api/v1/api/modules/20/engineering/design_of_experiments1539/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/measurement_systems_analysis1538/run'),
 ('post', '/api/v1/api/modules/20/engineering/process_capability1537/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/response_surface_methodology1541/run'),
 ('post', '/api/v1/api/modules/20/engineering/robust_design1542/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/statistical_process_control1536/run'),
 ('post', '/api/v1/api/modules/20/engineering/taguchi_methods1540/run'),
 ('post', '/api/v1/api/modules/20/execution-truth-ledger'),
 ('post', '/api/v1/api/modules/20/flow-balance/1513/evaluate'),
 ('post', '/api/v1/api/modules/20/genetic-algorithms/solve'),
 ('post', '/api/v1/api/modules/20/genetic-algorithms/solve-quadratic'),
 ('post', '/api/v1/api/modules/20/genetic-programming/solve'),
 ('post', '/api/v1/api/modules/20/goals'),
 ('post', '/api/v1/api/modules/20/humanities/1810-1859/analyze'),
 ('post', '/api/v1/api/modules/20/ingest/email'),
 ('post', '/api/v1/api/modules/20/ingest/text'),
 ('post', '/api/v1/api/modules/20/learning-reasoning-810-859/{method}'),
 ('post', '/api/v1/api/modules/20/legacy-modernization/694/modernize'),
 ('post', '/api/v1/api/modules/20/legal-1260-1309/support'),
 ('post', '/api/v1/api/modules/20/legal/support'),
 ('post', '/api/v1/api/modules/20/mechanical-design/1510/evaluate'),
 ('post', '/api/v1/api/modules/20/memory/facts'),
 ('post', '/api/v1/api/modules/20/meta-transfer/learn'),
 ('post', '/api/v1/api/modules/20/meta-transfer/transfer'),
 ('post', '/api/v1/api/modules/20/meta/abstraction/rollup'),
 ('post', '/api/v1/api/modules/20/meta/antifragility/assess'),
 ('post', '/api/v1/api/modules/20/meta/asymmetry/evaluate'),
 ('post', '/api/v1/api/modules/20/meta/auction'),
 ('post', '/api/v1/api/modules/20/meta/base-rate/integrate'),
 ('post', '/api/v1/api/modules/20/meta/bayes/update'),
 ('post', '/api/v1/api/modules/20/meta/bias-scan'),
 ('post', '/api/v1/api/modules/20/meta/calibration/claims'),
 ('post', '/api/v1/api/modules/20/meta/calibration/claims/{claim_id}/resolve'),
 ('post', '/api/v1/api/modules/20/meta/causal/assess'),
 ('post', '/api/v1/api/modules/20/meta/constraints/analyze'),
 ('post', '/api/v1/api/modules/20/meta/context-switch'),
 ('post', '/api/v1/api/modules/20/meta/counterfactuals'),
 ('post', '/api/v1/api/modules/20/meta/critical-path'),
 ('post', '/api/v1/api/modules/20/meta/curiosity/explore'),
 ('post', '/api/v1/api/modules/20/meta/curiosity/gaps'),
 ('post', '/api/v1/api/modules/20/meta/decision-tree'),
 ('post', '/api/v1/api/modules/20/meta/decisions/opportunity-cost'),
 ('post', '/api/v1/api/modules/20/meta/decisions/regret'),
 ('post', '/api/v1/api/modules/20/meta/decisions/routine'),
 ('post', '/api/v1/api/modules/20/meta/decisions/sunk-cost'),
 ('post', '/api/v1/api/modules/20/meta/devils-advocate'),
 ('post', '/api/v1/api/modules/20/meta/disruption'),
 ('post', '/api/v1/api/modules/20/meta/epistemic-calendar/beliefs'),
 ('post', '/api/v1/api/modules/20/meta/ergodicity'),
 ('post', '/api/v1/api/modules/20/meta/ev/compute'),
 ('post', '/api/v1/api/modules/20/meta/flow/assess'),
 ('post', '/api/v1/api/modules/20/meta/flow/structure'),
 ('post', '/api/v1/api/modules/20/meta/flywheels'),
 ('post', '/api/v1/api/modules/20/meta/game'),
 ('post', '/api/v1/api/modules/20/meta/goals/check-conflicts'),
 ('post', '/api/v1/api/modules/20/meta/hypotheses'),
 ('post', '/api/v1/api/modules/20/meta/hypotheses/evidence'),
 ('post', '/api/v1/api/modules/20/meta/ideation/generate'),
 ('post', '/api/v1/api/modules/20/meta/improvement/proposals'),
 ('post',
  '/api/v1/api/modules/20/meta/improvement/proposals/{proposal_id}/apply'),
 ('post', '/api/v1/api/modules/20/meta/insights'),
 ('post', '/api/v1/api/modules/20/meta/insights/{insight_id}/develop'),
 ('post', '/api/v1/api/modules/20/meta/intuition'),
 ('post', '/api/v1/api/modules/20/meta/jtbd'),
 ('post', '/api/v1/api/modules/20/meta/kelly/size'),
 ('post', '/api/v1/api/modules/20/meta/littles-law'),
 ('post', '/api/v1/api/modules/20/meta/load-allocation'),
 ('post', '/api/v1/api/modules/20/meta/mechanism/check-incentives'),
 ('post', '/api/v1/api/modules/20/meta/mechanism/vcg'),
 ('post', '/api/v1/api/modules/20/meta/meta-learning/transfer'),
 ('post', '/api/v1/api/modules/20/meta/moats'),
 ('post', '/api/v1/api/modules/20/meta/monte-carlo'),
 ('post', '/api/v1/api/modules/20/meta/nash'),
 ('post', '/api/v1/api/modules/20/meta/network-effects'),
 ('post', '/api/v1/api/modules/20/meta/nonlinear/classify'),
 ('post', '/api/v1/api/modules/20/meta/nonlinear/extrapolate'),
 ('post', '/api/v1/api/modules/20/meta/optimism/adjust'),
 ('post', '/api/v1/api/modules/20/meta/optimism/records'),
 ('post', '/api/v1/api/modules/20/meta/optionality/assess'),
 ('post', '/api/v1/api/modules/20/meta/outside-view'),
 ('post', '/api/v1/api/modules/20/meta/pareto'),
 ('post', '/api/v1/api/modules/20/meta/perspectives'),
 ('post', '/api/v1/api/modules/20/meta/planning-fallacy/correct'),
 ('post', '/api/v1/api/modules/20/meta/planning-fallacy/records'),
 ('post', '/api/v1/api/modules/20/meta/planning-horizon'),
 ('post', '/api/v1/api/modules/20/meta/premortem'),
 ('post', '/api/v1/api/modules/20/meta/premortem/register'),
 ('post', '/api/v1/api/modules/20/meta/principal-agent'),
 ('post', '/api/v1/api/modules/20/meta/queue'),
 ('post', '/api/v1/api/modules/20/meta/real-options'),
 ('post', '/api/v1/api/modules/20/meta/red-team'),
 ('post', '/api/v1/api/modules/20/meta/reference-class/cases'),
 ('post', '/api/v1/api/modules/20/meta/reference-class/forecast'),
 ('post', '/api/v1/api/modules/20/meta/reframe'),
 ('post', '/api/v1/api/modules/20/meta/reversibility/assess'),
 ('post', '/api/v1/api/modules/20/meta/risk-of-ruin'),
 ('post', '/api/v1/api/modules/20/meta/scenarios'),
 ('post', '/api/v1/api/modules/20/meta/second-order'),
 ('post', '/api/v1/api/modules/20/meta/sensitivity'),
 ('post', '/api/v1/api/modules/20/meta/serendipity/plan'),
 ('post', '/api/v1/api/modules/20/meta/signaling'),
 ('post', '/api/v1/api/modules/20/meta/simulations'),
 ('post', '/api/v1/api/modules/20/meta/simulations/{record_id}/resolve'),
 ('post', '/api/v1/api/modules/20/meta/steelman'),
 ('post', '/api/v1/api/modules/20/meta/systems/leverage'),
 ('post', '/api/v1/api/modules/20/meta/systems/loops'),
 ('post', '/api/v1/api/modules/20/meta/temporal/compare'),
 ('post', '/api/v1/api/modules/20/meta/tipping-point'),
 ('post', '/api/v1/api/modules/20/meta/toc/observe'),
 ('post', '/api/v1/api/modules/20/meta/tornado'),
 ('post', '/api/v1/api/modules/20/meta/value-chain'),
 ('post', '/api/v1/api/modules/20/meta/world-models'),
 ('post', '/api/v1/api/modules/20/meta/world-models/{name}/evidence'),
 ('post', '/api/v1/api/modules/20/meta/world-models/{name}/revise'),
 ('post', '/api/v1/api/modules/20/mob-programming/692/audit'),
 ('post', '/api/v1/api/modules/20/mob-programming/692/plan'),
 ('post', '/api/v1/api/modules/20/naming-conventions/707/check'),
 ('post', '/api/v1/api/modules/20/negotiation-behavior-85-109/analyze'),
 ('post', '/api/v1/api/modules/20/optimization-story-235-280/{method}'),
 ('post', '/api/v1/api/modules/20/pair-programming/691/diagnostics'),
 ('post', '/api/v1/api/modules/20/particle-swarm/solve'),
 ('post', '/api/v1/api/modules/20/platform-engineering/585-634/analyze'),
 ('post', '/api/v1/api/modules/20/political-social-1760-1809/{row_id}'),
 ('post', '/api/v1/api/modules/20/propositional-reasoning/entail'),
 ('post', '/api/v1/api/modules/20/quality-assurance/1535/evaluate'),
 ('post', '/api/v1/api/modules/20/refactoring/689/rename-local'),
 ('post', '/api/v1/api/modules/20/social-research-1710-1759/{method}'),
 ('post', '/api/v1/api/modules/20/software-practice/685-709/analyze'),
 ('post', '/api/v1/api/modules/20/specialized-domain/analyze'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/resume'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/retrospective'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/ruminate'),
 ('post', '/api/v1/api/modules/20/technical-debt/693/schedule'),
 ('post', '/api/v1/api/modules/20/technical-spec-133-165/analyze'),
 ('post', '/api/v1/api/modules/20/technical-spec/199-229/{row}'),
 ('post', '/api/v1/api/modules/20/test-driven-development/687/check'),
 ('put', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/plan'))
CURRENT_NOT_BOUND = {'GCW runtime not bound for authenticated tenant': 34, 'registry not bound for authenticated tenant': 3, 'investigator not bound for authenticated tenant': 4, 'twin registry not bound for authenticated tenant': 4, 'GCW service not bound for authenticated tenant': 107, 'predictor not bound for authenticated tenant': 2, 'model not bound for authenticated tenant': 5, 'transfer learner not bound for authenticated tenant': 2}
CURRENT_TOTAL_ROUTES = 241

HISTORICAL_R2_REACHABLE = dict(REACHABLE)
HISTORICAL_R2_TOTAL_ROUTES = TOTAL_ROUTES
REACHABLE = {**HISTORICAL_R2_REACHABLE, **ADDITIONAL_REACHABLE}
TOTAL_ROUTES = CURRENT_TOTAL_ROUTES


def test_additive_current_exact_operation_inventory(env):
    app, _, _ = env
    assert tuple(sorted(ops(app))) == CURRENT_INVENTORY
    assert HISTORICAL_R2_TOTAL_ROUTES == 235
    assert len(ADDITIONAL_REACHABLE) == 6
    assert len(REACHABLE) == 80
    assert CURRENT_TOTAL_ROUTES == 241
    assert CURRENT_NOT_BOUND == NOT_BOUND
    assert sum(CURRENT_NOT_BOUND.values()) == 161
    assert CURRENT_TOTAL_ROUTES == len(REACHABLE) + sum(CURRENT_NOT_BOUND.values())
    assert set(ADDITIONAL_REACHABLE).isdisjoint(HISTORICAL_R2_REACHABLE)


def test_additive_new_mounts_401_and_owner_bound_422(env):
    _, client, headers = env
    for (method, path), status in ADDITIONAL_REACHABLE.items():
        assert call(client, method, path).status_code == 401
        response = call(client, method, path, headers)
        assert response.status_code == status == 422, (path, response.text)


# Append-only batch2 refresh derived on public666a329.
BATCH2_REACHABLE = {('post', '/api/v1/api/modules/20/documentation-generation/703/generate'): 422,
 ('post', '/api/v1/api/modules/20/feature-flags/697/evaluate'): 422,
 ('post', '/api/v1/api/modules/20/release-notes/702/plan'): 422,
 ('post', '/api/v1/api/modules/20/semantic-versioning/700/analyze'): 422,
 ('post', '/api/v1/api/modules/20/trunk-based-development/698/analyze'): 422}
BATCH2_INVENTORY = (('get', '/api/v1/api/modules/20/agi-runtime/world/hypotheses'),
 ('get', '/api/v1/api/modules/20/agi-runtime/world/snapshots/verify'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/calibration'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/events'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/memory/episodes'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/memory/facts'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/methods'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/retrospectives'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/compare'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/history'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/supervision'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/decision'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/evidence'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/mcts'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tools'),
 ('get', '/api/v1/api/modules/20/atomic-concepts-93-115/methods'),
 ('get', '/api/v1/api/modules/20/atomic-concepts/139-160'),
 ('get', '/api/v1/api/modules/20/bayesian-models'),
 ('get', '/api/v1/api/modules/20/cognitive-1960-2009/methods'),
 ('get', '/api/v1/api/modules/20/cognitive-learning-860-909/capabilities'),
 ('get', '/api/v1/api/modules/20/curiosity-investigator/queue'),
 ('get', '/api/v1/api/modules/20/digital-twins/{name}'),
 ('get', '/api/v1/api/modules/20/education/capabilities'),
 ('get', '/api/v1/api/modules/20/health'),
 ('get', '/api/v1/api/modules/20/learning-reasoning-810-859/capabilities'),
 ('get', '/api/v1/api/modules/20/memory/episodes'),
 ('get', '/api/v1/api/modules/20/memory/facts'),
 ('get', '/api/v1/api/modules/20/meta/calibration/curve'),
 ('get', '/api/v1/api/modules/20/meta/epistemic-calendar/due'),
 ('get', '/api/v1/api/modules/20/meta/insights/stale'),
 ('get', '/api/v1/api/modules/20/meta/knowledge-decay/forecast'),
 ('get', '/api/v1/api/modules/20/meta/world-models'),
 ('get', '/api/v1/api/modules/20/negotiation-behavior-85-109/methods'),
 ('get', '/api/v1/api/modules/20/optimization-story-235-280/capabilities'),
 ('get', '/api/v1/api/modules/20/political-social-1760-1809/capabilities'),
 ('get', '/api/v1/api/modules/20/skills'),
 ('get', '/api/v1/api/modules/20/social-research-1710-1759/capabilities'),
 ('get', '/api/v1/api/modules/20/standup'),
 ('get', '/api/v1/api/modules/20/tasks'),
 ('get', '/api/v1/api/modules/20/tasks/{task_id}'),
 ('get', '/api/v1/api/modules/20/technical-spec-133-165/methods'),
 ('get', '/api/v1/api/modules/20/technical-spec/199-229/requirements'),
 ('get', '/api/v1/api/modules/20/tools'),
 ('get', '/api/v1/api/modules/20/traces'),
 ('patch',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/risks/{risk_id}'),
 ('patch',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/schedule'),
 ('post',
  '/api/v1/api/modules/20/acceptance-test-driven-development/688/bookkeeping'),
 ('post', '/api/v1/api/modules/20/agi-runtime/evaluations/cross-domain'),
 ('post', '/api/v1/api/modules/20/agi-runtime/goals/proposals'),
 ('post', '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/activate'),
 ('post',
  '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/request-activation'),
 ('post', '/api/v1/api/modules/20/agi-runtime/world/evidence'),
 ('post', '/api/v1/api/modules/20/agi-runtime/world/snapshots'),
 ('post', '/api/v1/api/modules/20/api-documentation/openapi'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/memory/facts'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/memory/recall'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/methods/{name}/activate'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/revise'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/sandbox/run'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/step'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tasks'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/close'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/context'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/preflight'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/step'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/steps/{node_id}/retry'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tools/select'),
 ('post', '/api/v1/api/modules/20/architecture-decisions/705/record'),
 ('post', '/api/v1/api/modules/20/artificial-life/simulate'),
 ('post', '/api/v1/api/modules/20/atomic-concepts-70-92'),
 ('post', '/api/v1/api/modules/20/atomic-concepts-93-115/analyze'),
 ('post', '/api/v1/api/modules/20/atomic-concepts/139-160/{atomic_row_id}'),
 ('post', '/api/v1/api/modules/20/axial-fea/1512/solve'),
 ('post', '/api/v1/api/modules/20/bayesian-models/configure'),
 ('post', '/api/v1/api/modules/20/bayesian-models/evidence'),
 ('post', '/api/v1/api/modules/20/bdd-scenarios/686/execute'),
 ('post', '/api/v1/api/modules/20/cad-modeling/1511/evaluate'),
 ('post', '/api/v1/api/modules/20/calibration-predictor/ingest'),
 ('post', '/api/v1/api/modules/20/calibration-predictor/predict'),
 ('post', '/api/v1/api/modules/20/code-comments/706/audit'),
 ('post', '/api/v1/api/modules/20/code-formatting/708/inspect'),
 ('post', '/api/v1/api/modules/20/code-review/690/review'),
 ('post', '/api/v1/api/modules/20/cognitive-1960-2009/analyze'),
 ('post', '/api/v1/api/modules/20/cognitive-learning-860-909/{row_id}'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/authorize'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/enqueue'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/run'),
 ('post', '/api/v1/api/modules/20/decay-survival/evaluate'),
 ('post', '/api/v1/api/modules/20/decay-survival/forecast'),
 ('post', '/api/v1/api/modules/20/decay-survival/ingest'),
 ('post', '/api/v1/api/modules/20/decay-survival/refresh'),
 ('post', '/api/v1/api/modules/20/decay-survival/track'),
 ('post', '/api/v1/api/modules/20/design-for-six-sigma/1530/run'),
 ('post', '/api/v1/api/modules/20/differential-evolution/solve'),
 ('post', '/api/v1/api/modules/20/digital-twins'),
 ('post', '/api/v1/api/modules/20/digital-twins/{name}/assimilate'),
 ('post', '/api/v1/api/modules/20/digital-twins/{name}/forecast'),
 ('post', '/api/v1/api/modules/20/documentation-generation/703/generate'),
 ('post', '/api/v1/api/modules/20/education/{capability}'),
 ('post', '/api/v1/api/modules/20/engineering/1510-1559/analyze'),
 ('post', '/api/v1/api/modules/20/engineering/design_of_experiments1539/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/measurement_systems_analysis1538/run'),
 ('post', '/api/v1/api/modules/20/engineering/process_capability1537/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/response_surface_methodology1541/run'),
 ('post', '/api/v1/api/modules/20/engineering/robust_design1542/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/statistical_process_control1536/run'),
 ('post', '/api/v1/api/modules/20/engineering/taguchi_methods1540/run'),
 ('post', '/api/v1/api/modules/20/execution-truth-ledger'),
 ('post', '/api/v1/api/modules/20/feature-flags/697/evaluate'),
 ('post', '/api/v1/api/modules/20/flow-balance/1513/evaluate'),
 ('post', '/api/v1/api/modules/20/genetic-algorithms/solve'),
 ('post', '/api/v1/api/modules/20/genetic-algorithms/solve-quadratic'),
 ('post', '/api/v1/api/modules/20/genetic-programming/solve'),
 ('post', '/api/v1/api/modules/20/goals'),
 ('post', '/api/v1/api/modules/20/humanities/1810-1859/analyze'),
 ('post', '/api/v1/api/modules/20/ingest/email'),
 ('post', '/api/v1/api/modules/20/ingest/text'),
 ('post', '/api/v1/api/modules/20/learning-reasoning-810-859/{method}'),
 ('post', '/api/v1/api/modules/20/legacy-modernization/694/modernize'),
 ('post', '/api/v1/api/modules/20/legal-1260-1309/support'),
 ('post', '/api/v1/api/modules/20/legal/support'),
 ('post', '/api/v1/api/modules/20/mechanical-design/1510/evaluate'),
 ('post', '/api/v1/api/modules/20/memory/facts'),
 ('post', '/api/v1/api/modules/20/meta-transfer/learn'),
 ('post', '/api/v1/api/modules/20/meta-transfer/transfer'),
 ('post', '/api/v1/api/modules/20/meta/abstraction/rollup'),
 ('post', '/api/v1/api/modules/20/meta/antifragility/assess'),
 ('post', '/api/v1/api/modules/20/meta/asymmetry/evaluate'),
 ('post', '/api/v1/api/modules/20/meta/auction'),
 ('post', '/api/v1/api/modules/20/meta/base-rate/integrate'),
 ('post', '/api/v1/api/modules/20/meta/bayes/update'),
 ('post', '/api/v1/api/modules/20/meta/bias-scan'),
 ('post', '/api/v1/api/modules/20/meta/calibration/claims'),
 ('post', '/api/v1/api/modules/20/meta/calibration/claims/{claim_id}/resolve'),
 ('post', '/api/v1/api/modules/20/meta/causal/assess'),
 ('post', '/api/v1/api/modules/20/meta/constraints/analyze'),
 ('post', '/api/v1/api/modules/20/meta/context-switch'),
 ('post', '/api/v1/api/modules/20/meta/counterfactuals'),
 ('post', '/api/v1/api/modules/20/meta/critical-path'),
 ('post', '/api/v1/api/modules/20/meta/curiosity/explore'),
 ('post', '/api/v1/api/modules/20/meta/curiosity/gaps'),
 ('post', '/api/v1/api/modules/20/meta/decision-tree'),
 ('post', '/api/v1/api/modules/20/meta/decisions/opportunity-cost'),
 ('post', '/api/v1/api/modules/20/meta/decisions/regret'),
 ('post', '/api/v1/api/modules/20/meta/decisions/routine'),
 ('post', '/api/v1/api/modules/20/meta/decisions/sunk-cost'),
 ('post', '/api/v1/api/modules/20/meta/devils-advocate'),
 ('post', '/api/v1/api/modules/20/meta/disruption'),
 ('post', '/api/v1/api/modules/20/meta/epistemic-calendar/beliefs'),
 ('post', '/api/v1/api/modules/20/meta/ergodicity'),
 ('post', '/api/v1/api/modules/20/meta/ev/compute'),
 ('post', '/api/v1/api/modules/20/meta/flow/assess'),
 ('post', '/api/v1/api/modules/20/meta/flow/structure'),
 ('post', '/api/v1/api/modules/20/meta/flywheels'),
 ('post', '/api/v1/api/modules/20/meta/game'),
 ('post', '/api/v1/api/modules/20/meta/goals/check-conflicts'),
 ('post', '/api/v1/api/modules/20/meta/hypotheses'),
 ('post', '/api/v1/api/modules/20/meta/hypotheses/evidence'),
 ('post', '/api/v1/api/modules/20/meta/ideation/generate'),
 ('post', '/api/v1/api/modules/20/meta/improvement/proposals'),
 ('post',
  '/api/v1/api/modules/20/meta/improvement/proposals/{proposal_id}/apply'),
 ('post', '/api/v1/api/modules/20/meta/insights'),
 ('post', '/api/v1/api/modules/20/meta/insights/{insight_id}/develop'),
 ('post', '/api/v1/api/modules/20/meta/intuition'),
 ('post', '/api/v1/api/modules/20/meta/jtbd'),
 ('post', '/api/v1/api/modules/20/meta/kelly/size'),
 ('post', '/api/v1/api/modules/20/meta/littles-law'),
 ('post', '/api/v1/api/modules/20/meta/load-allocation'),
 ('post', '/api/v1/api/modules/20/meta/mechanism/check-incentives'),
 ('post', '/api/v1/api/modules/20/meta/mechanism/vcg'),
 ('post', '/api/v1/api/modules/20/meta/meta-learning/transfer'),
 ('post', '/api/v1/api/modules/20/meta/moats'),
 ('post', '/api/v1/api/modules/20/meta/monte-carlo'),
 ('post', '/api/v1/api/modules/20/meta/nash'),
 ('post', '/api/v1/api/modules/20/meta/network-effects'),
 ('post', '/api/v1/api/modules/20/meta/nonlinear/classify'),
 ('post', '/api/v1/api/modules/20/meta/nonlinear/extrapolate'),
 ('post', '/api/v1/api/modules/20/meta/optimism/adjust'),
 ('post', '/api/v1/api/modules/20/meta/optimism/records'),
 ('post', '/api/v1/api/modules/20/meta/optionality/assess'),
 ('post', '/api/v1/api/modules/20/meta/outside-view'),
 ('post', '/api/v1/api/modules/20/meta/pareto'),
 ('post', '/api/v1/api/modules/20/meta/perspectives'),
 ('post', '/api/v1/api/modules/20/meta/planning-fallacy/correct'),
 ('post', '/api/v1/api/modules/20/meta/planning-fallacy/records'),
 ('post', '/api/v1/api/modules/20/meta/planning-horizon'),
 ('post', '/api/v1/api/modules/20/meta/premortem'),
 ('post', '/api/v1/api/modules/20/meta/premortem/register'),
 ('post', '/api/v1/api/modules/20/meta/principal-agent'),
 ('post', '/api/v1/api/modules/20/meta/queue'),
 ('post', '/api/v1/api/modules/20/meta/real-options'),
 ('post', '/api/v1/api/modules/20/meta/red-team'),
 ('post', '/api/v1/api/modules/20/meta/reference-class/cases'),
 ('post', '/api/v1/api/modules/20/meta/reference-class/forecast'),
 ('post', '/api/v1/api/modules/20/meta/reframe'),
 ('post', '/api/v1/api/modules/20/meta/reversibility/assess'),
 ('post', '/api/v1/api/modules/20/meta/risk-of-ruin'),
 ('post', '/api/v1/api/modules/20/meta/scenarios'),
 ('post', '/api/v1/api/modules/20/meta/second-order'),
 ('post', '/api/v1/api/modules/20/meta/sensitivity'),
 ('post', '/api/v1/api/modules/20/meta/serendipity/plan'),
 ('post', '/api/v1/api/modules/20/meta/signaling'),
 ('post', '/api/v1/api/modules/20/meta/simulations'),
 ('post', '/api/v1/api/modules/20/meta/simulations/{record_id}/resolve'),
 ('post', '/api/v1/api/modules/20/meta/steelman'),
 ('post', '/api/v1/api/modules/20/meta/systems/leverage'),
 ('post', '/api/v1/api/modules/20/meta/systems/loops'),
 ('post', '/api/v1/api/modules/20/meta/temporal/compare'),
 ('post', '/api/v1/api/modules/20/meta/tipping-point'),
 ('post', '/api/v1/api/modules/20/meta/toc/observe'),
 ('post', '/api/v1/api/modules/20/meta/tornado'),
 ('post', '/api/v1/api/modules/20/meta/value-chain'),
 ('post', '/api/v1/api/modules/20/meta/world-models'),
 ('post', '/api/v1/api/modules/20/meta/world-models/{name}/evidence'),
 ('post', '/api/v1/api/modules/20/meta/world-models/{name}/revise'),
 ('post', '/api/v1/api/modules/20/mob-programming/692/audit'),
 ('post', '/api/v1/api/modules/20/mob-programming/692/plan'),
 ('post', '/api/v1/api/modules/20/naming-conventions/707/check'),
 ('post', '/api/v1/api/modules/20/negotiation-behavior-85-109/analyze'),
 ('post', '/api/v1/api/modules/20/optimization-story-235-280/{method}'),
 ('post', '/api/v1/api/modules/20/pair-programming/691/diagnostics'),
 ('post', '/api/v1/api/modules/20/particle-swarm/solve'),
 ('post', '/api/v1/api/modules/20/platform-engineering/585-634/analyze'),
 ('post', '/api/v1/api/modules/20/political-social-1760-1809/{row_id}'),
 ('post', '/api/v1/api/modules/20/propositional-reasoning/entail'),
 ('post', '/api/v1/api/modules/20/quality-assurance/1535/evaluate'),
 ('post', '/api/v1/api/modules/20/refactoring/689/rename-local'),
 ('post', '/api/v1/api/modules/20/release-notes/702/plan'),
 ('post', '/api/v1/api/modules/20/semantic-versioning/700/analyze'),
 ('post', '/api/v1/api/modules/20/social-research-1710-1759/{method}'),
 ('post', '/api/v1/api/modules/20/software-practice/685-709/analyze'),
 ('post', '/api/v1/api/modules/20/specialized-domain/analyze'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/resume'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/retrospective'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/ruminate'),
 ('post', '/api/v1/api/modules/20/technical-debt/693/schedule'),
 ('post', '/api/v1/api/modules/20/technical-spec-133-165/analyze'),
 ('post', '/api/v1/api/modules/20/technical-spec/199-229/{row}'),
 ('post', '/api/v1/api/modules/20/test-driven-development/687/check'),
 ('post', '/api/v1/api/modules/20/trunk-based-development/698/analyze'),
 ('put', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/plan'))
BATCH2_NOT_BOUND = {'GCW runtime not bound for authenticated tenant': 34, 'registry not bound for authenticated tenant': 3, 'investigator not bound for authenticated tenant': 4, 'twin registry not bound for authenticated tenant': 4, 'GCW service not bound for authenticated tenant': 107, 'predictor not bound for authenticated tenant': 2, 'model not bound for authenticated tenant': 5, 'transfer learner not bound for authenticated tenant': 2}
BATCH2_TOTAL_ROUTES = 246

PRE_BATCH2_REACHABLE = dict(REACHABLE)
REACHABLE = {**PRE_BATCH2_REACHABLE, **BATCH2_REACHABLE}
TOTAL_ROUTES = BATCH2_TOTAL_ROUTES


def test_additive_current_exact_operation_inventory(env):
    # Supersede only the active snapshot check; retain prior data as history.
    app, _, _ = env
    assert tuple(sorted(ops(app))) == BATCH2_INVENTORY
    assert len(CURRENT_INVENTORY) == CURRENT_TOTAL_ROUTES == 241
    assert len(PRE_BATCH2_REACHABLE) == 80
    assert len(BATCH2_REACHABLE) == 5
    assert len(REACHABLE) == 85
    assert BATCH2_TOTAL_ROUTES == 246
    assert BATCH2_NOT_BOUND == CURRENT_NOT_BOUND == NOT_BOUND
    assert sum(BATCH2_NOT_BOUND.values()) == 161
    assert BATCH2_TOTAL_ROUTES == len(REACHABLE) + sum(BATCH2_NOT_BOUND.values())
    assert set(BATCH2_REACHABLE).isdisjoint(PRE_BATCH2_REACHABLE)


def test_batch2_new_mounts_auth_and_reachability(env):
    _, client, headers = env
    for (method, path), status in BATCH2_REACHABLE.items():
        assert call(client, method, path).status_code == 401
        response = call(client, method, path, headers)
        assert response.status_code == status == 422, (path, response.text)


# Final combined B5/B7/B9 append-only snapshot, derived at cf2215b6.
FINAL_REACHABLE_ADDITIONS = {('post', '/api/v1/api/modules/20/engineering/accelerated_life_testing1544/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/environmental_testing1545/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/ergonomics/1525/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/failure-analysis/1520/plan'): 422,
 ('post', '/api/v1/api/modules/20/engineering/human-factors/1524/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/humidity_exposure1549/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/industrial-design/1526/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/reliability_testing1543/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/shock_testing1547/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/thermal_cycling1548/run'): 422,
 ('post', '/api/v1/api/modules/20/engineering/vibration_modal1546/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1300/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1301/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1302/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1303/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1304/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1305/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1306/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1307/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1308/run'): 422,
 ('post', '/api/v1/api/modules/20/legal/1309/run'): 422}
FINAL_INVENTORY = (('get', '/api/v1/api/modules/20/agi-runtime/world/hypotheses'),
 ('get', '/api/v1/api/modules/20/agi-runtime/world/snapshots/verify'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/calibration'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/events'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/memory/episodes'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/memory/facts'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/methods'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/retrospectives'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/compare'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/history'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/supervision'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/decision'),
 ('get',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/evidence'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/mcts'),
 ('get', '/api/v1/api/modules/20/api/modules/20/runtime/tools'),
 ('get', '/api/v1/api/modules/20/atomic-concepts-93-115/methods'),
 ('get', '/api/v1/api/modules/20/atomic-concepts/139-160'),
 ('get', '/api/v1/api/modules/20/bayesian-models'),
 ('get', '/api/v1/api/modules/20/cognitive-1960-2009/methods'),
 ('get', '/api/v1/api/modules/20/cognitive-learning-860-909/capabilities'),
 ('get', '/api/v1/api/modules/20/curiosity-investigator/queue'),
 ('get', '/api/v1/api/modules/20/digital-twins/{name}'),
 ('get', '/api/v1/api/modules/20/education/capabilities'),
 ('get', '/api/v1/api/modules/20/health'),
 ('get', '/api/v1/api/modules/20/learning-reasoning-810-859/capabilities'),
 ('get', '/api/v1/api/modules/20/memory/episodes'),
 ('get', '/api/v1/api/modules/20/memory/facts'),
 ('get', '/api/v1/api/modules/20/meta/calibration/curve'),
 ('get', '/api/v1/api/modules/20/meta/epistemic-calendar/due'),
 ('get', '/api/v1/api/modules/20/meta/insights/stale'),
 ('get', '/api/v1/api/modules/20/meta/knowledge-decay/forecast'),
 ('get', '/api/v1/api/modules/20/meta/world-models'),
 ('get', '/api/v1/api/modules/20/negotiation-behavior-85-109/methods'),
 ('get', '/api/v1/api/modules/20/optimization-story-235-280/capabilities'),
 ('get', '/api/v1/api/modules/20/political-social-1760-1809/capabilities'),
 ('get', '/api/v1/api/modules/20/skills'),
 ('get', '/api/v1/api/modules/20/social-research-1710-1759/capabilities'),
 ('get', '/api/v1/api/modules/20/standup'),
 ('get', '/api/v1/api/modules/20/tasks'),
 ('get', '/api/v1/api/modules/20/tasks/{task_id}'),
 ('get', '/api/v1/api/modules/20/technical-spec-133-165/methods'),
 ('get', '/api/v1/api/modules/20/technical-spec/199-229/requirements'),
 ('get', '/api/v1/api/modules/20/tools'),
 ('get', '/api/v1/api/modules/20/traces'),
 ('patch',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/risks/{risk_id}'),
 ('patch',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/schedule'),
 ('post',
  '/api/v1/api/modules/20/acceptance-test-driven-development/688/bookkeeping'),
 ('post', '/api/v1/api/modules/20/agi-runtime/evaluations/cross-domain'),
 ('post', '/api/v1/api/modules/20/agi-runtime/goals/proposals'),
 ('post', '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/activate'),
 ('post',
  '/api/v1/api/modules/20/agi-runtime/goals/{proposal_id}/request-activation'),
 ('post', '/api/v1/api/modules/20/agi-runtime/world/evidence'),
 ('post', '/api/v1/api/modules/20/agi-runtime/world/snapshots'),
 ('post', '/api/v1/api/modules/20/api-documentation/openapi'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/memory/facts'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/memory/recall'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/methods/{name}/activate'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/risk-registers/{identifier}/revise'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/sandbox/run'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/step'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tasks'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/close'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/context'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/preflight'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/step'),
 ('post',
  '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/steps/{node_id}/retry'),
 ('post', '/api/v1/api/modules/20/api/modules/20/runtime/tools/select'),
 ('post', '/api/v1/api/modules/20/architecture-decisions/705/record'),
 ('post', '/api/v1/api/modules/20/artificial-life/simulate'),
 ('post', '/api/v1/api/modules/20/atomic-concepts-70-92'),
 ('post', '/api/v1/api/modules/20/atomic-concepts-93-115/analyze'),
 ('post', '/api/v1/api/modules/20/atomic-concepts/139-160/{atomic_row_id}'),
 ('post', '/api/v1/api/modules/20/axial-fea/1512/solve'),
 ('post', '/api/v1/api/modules/20/bayesian-models/configure'),
 ('post', '/api/v1/api/modules/20/bayesian-models/evidence'),
 ('post', '/api/v1/api/modules/20/bdd-scenarios/686/execute'),
 ('post', '/api/v1/api/modules/20/cad-modeling/1511/evaluate'),
 ('post', '/api/v1/api/modules/20/calibration-predictor/ingest'),
 ('post', '/api/v1/api/modules/20/calibration-predictor/predict'),
 ('post', '/api/v1/api/modules/20/code-comments/706/audit'),
 ('post', '/api/v1/api/modules/20/code-formatting/708/inspect'),
 ('post', '/api/v1/api/modules/20/code-review/690/review'),
 ('post', '/api/v1/api/modules/20/cognitive-1960-2009/analyze'),
 ('post', '/api/v1/api/modules/20/cognitive-learning-860-909/{row_id}'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/authorize'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/enqueue'),
 ('post', '/api/v1/api/modules/20/curiosity-investigator/run'),
 ('post', '/api/v1/api/modules/20/decay-survival/evaluate'),
 ('post', '/api/v1/api/modules/20/decay-survival/forecast'),
 ('post', '/api/v1/api/modules/20/decay-survival/ingest'),
 ('post', '/api/v1/api/modules/20/decay-survival/refresh'),
 ('post', '/api/v1/api/modules/20/decay-survival/track'),
 ('post', '/api/v1/api/modules/20/design-for-six-sigma/1530/run'),
 ('post', '/api/v1/api/modules/20/differential-evolution/solve'),
 ('post', '/api/v1/api/modules/20/digital-twins'),
 ('post', '/api/v1/api/modules/20/digital-twins/{name}/assimilate'),
 ('post', '/api/v1/api/modules/20/digital-twins/{name}/forecast'),
 ('post', '/api/v1/api/modules/20/documentation-generation/703/generate'),
 ('post', '/api/v1/api/modules/20/education/{capability}'),
 ('post', '/api/v1/api/modules/20/engineering/1510-1559/analyze'),
 ('post',
  '/api/v1/api/modules/20/engineering/accelerated_life_testing1544/run'),
 ('post', '/api/v1/api/modules/20/engineering/design_of_experiments1539/run'),
 ('post', '/api/v1/api/modules/20/engineering/environmental_testing1545/run'),
 ('post', '/api/v1/api/modules/20/engineering/ergonomics/1525/run'),
 ('post', '/api/v1/api/modules/20/engineering/failure-analysis/1520/plan'),
 ('post', '/api/v1/api/modules/20/engineering/human-factors/1524/run'),
 ('post', '/api/v1/api/modules/20/engineering/humidity_exposure1549/run'),
 ('post', '/api/v1/api/modules/20/engineering/industrial-design/1526/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/measurement_systems_analysis1538/run'),
 ('post', '/api/v1/api/modules/20/engineering/process_capability1537/run'),
 ('post', '/api/v1/api/modules/20/engineering/reliability_testing1543/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/response_surface_methodology1541/run'),
 ('post', '/api/v1/api/modules/20/engineering/robust_design1542/run'),
 ('post', '/api/v1/api/modules/20/engineering/shock_testing1547/run'),
 ('post',
  '/api/v1/api/modules/20/engineering/statistical_process_control1536/run'),
 ('post', '/api/v1/api/modules/20/engineering/taguchi_methods1540/run'),
 ('post', '/api/v1/api/modules/20/engineering/thermal_cycling1548/run'),
 ('post', '/api/v1/api/modules/20/engineering/vibration_modal1546/run'),
 ('post', '/api/v1/api/modules/20/execution-truth-ledger'),
 ('post', '/api/v1/api/modules/20/feature-flags/697/evaluate'),
 ('post', '/api/v1/api/modules/20/flow-balance/1513/evaluate'),
 ('post', '/api/v1/api/modules/20/genetic-algorithms/solve'),
 ('post', '/api/v1/api/modules/20/genetic-algorithms/solve-quadratic'),
 ('post', '/api/v1/api/modules/20/genetic-programming/solve'),
 ('post', '/api/v1/api/modules/20/goals'),
 ('post', '/api/v1/api/modules/20/humanities/1810-1859/analyze'),
 ('post', '/api/v1/api/modules/20/ingest/email'),
 ('post', '/api/v1/api/modules/20/ingest/text'),
 ('post', '/api/v1/api/modules/20/learning-reasoning-810-859/{method}'),
 ('post', '/api/v1/api/modules/20/legacy-modernization/694/modernize'),
 ('post', '/api/v1/api/modules/20/legal-1260-1309/support'),
 ('post', '/api/v1/api/modules/20/legal/1300/run'),
 ('post', '/api/v1/api/modules/20/legal/1301/run'),
 ('post', '/api/v1/api/modules/20/legal/1302/run'),
 ('post', '/api/v1/api/modules/20/legal/1303/run'),
 ('post', '/api/v1/api/modules/20/legal/1304/run'),
 ('post', '/api/v1/api/modules/20/legal/1305/run'),
 ('post', '/api/v1/api/modules/20/legal/1306/run'),
 ('post', '/api/v1/api/modules/20/legal/1307/run'),
 ('post', '/api/v1/api/modules/20/legal/1308/run'),
 ('post', '/api/v1/api/modules/20/legal/1309/run'),
 ('post', '/api/v1/api/modules/20/legal/support'),
 ('post', '/api/v1/api/modules/20/mechanical-design/1510/evaluate'),
 ('post', '/api/v1/api/modules/20/memory/facts'),
 ('post', '/api/v1/api/modules/20/meta-transfer/learn'),
 ('post', '/api/v1/api/modules/20/meta-transfer/transfer'),
 ('post', '/api/v1/api/modules/20/meta/abstraction/rollup'),
 ('post', '/api/v1/api/modules/20/meta/antifragility/assess'),
 ('post', '/api/v1/api/modules/20/meta/asymmetry/evaluate'),
 ('post', '/api/v1/api/modules/20/meta/auction'),
 ('post', '/api/v1/api/modules/20/meta/base-rate/integrate'),
 ('post', '/api/v1/api/modules/20/meta/bayes/update'),
 ('post', '/api/v1/api/modules/20/meta/bias-scan'),
 ('post', '/api/v1/api/modules/20/meta/calibration/claims'),
 ('post', '/api/v1/api/modules/20/meta/calibration/claims/{claim_id}/resolve'),
 ('post', '/api/v1/api/modules/20/meta/causal/assess'),
 ('post', '/api/v1/api/modules/20/meta/constraints/analyze'),
 ('post', '/api/v1/api/modules/20/meta/context-switch'),
 ('post', '/api/v1/api/modules/20/meta/counterfactuals'),
 ('post', '/api/v1/api/modules/20/meta/critical-path'),
 ('post', '/api/v1/api/modules/20/meta/curiosity/explore'),
 ('post', '/api/v1/api/modules/20/meta/curiosity/gaps'),
 ('post', '/api/v1/api/modules/20/meta/decision-tree'),
 ('post', '/api/v1/api/modules/20/meta/decisions/opportunity-cost'),
 ('post', '/api/v1/api/modules/20/meta/decisions/regret'),
 ('post', '/api/v1/api/modules/20/meta/decisions/routine'),
 ('post', '/api/v1/api/modules/20/meta/decisions/sunk-cost'),
 ('post', '/api/v1/api/modules/20/meta/devils-advocate'),
 ('post', '/api/v1/api/modules/20/meta/disruption'),
 ('post', '/api/v1/api/modules/20/meta/epistemic-calendar/beliefs'),
 ('post', '/api/v1/api/modules/20/meta/ergodicity'),
 ('post', '/api/v1/api/modules/20/meta/ev/compute'),
 ('post', '/api/v1/api/modules/20/meta/flow/assess'),
 ('post', '/api/v1/api/modules/20/meta/flow/structure'),
 ('post', '/api/v1/api/modules/20/meta/flywheels'),
 ('post', '/api/v1/api/modules/20/meta/game'),
 ('post', '/api/v1/api/modules/20/meta/goals/check-conflicts'),
 ('post', '/api/v1/api/modules/20/meta/hypotheses'),
 ('post', '/api/v1/api/modules/20/meta/hypotheses/evidence'),
 ('post', '/api/v1/api/modules/20/meta/ideation/generate'),
 ('post', '/api/v1/api/modules/20/meta/improvement/proposals'),
 ('post',
  '/api/v1/api/modules/20/meta/improvement/proposals/{proposal_id}/apply'),
 ('post', '/api/v1/api/modules/20/meta/insights'),
 ('post', '/api/v1/api/modules/20/meta/insights/{insight_id}/develop'),
 ('post', '/api/v1/api/modules/20/meta/intuition'),
 ('post', '/api/v1/api/modules/20/meta/jtbd'),
 ('post', '/api/v1/api/modules/20/meta/kelly/size'),
 ('post', '/api/v1/api/modules/20/meta/littles-law'),
 ('post', '/api/v1/api/modules/20/meta/load-allocation'),
 ('post', '/api/v1/api/modules/20/meta/mechanism/check-incentives'),
 ('post', '/api/v1/api/modules/20/meta/mechanism/vcg'),
 ('post', '/api/v1/api/modules/20/meta/meta-learning/transfer'),
 ('post', '/api/v1/api/modules/20/meta/moats'),
 ('post', '/api/v1/api/modules/20/meta/monte-carlo'),
 ('post', '/api/v1/api/modules/20/meta/nash'),
 ('post', '/api/v1/api/modules/20/meta/network-effects'),
 ('post', '/api/v1/api/modules/20/meta/nonlinear/classify'),
 ('post', '/api/v1/api/modules/20/meta/nonlinear/extrapolate'),
 ('post', '/api/v1/api/modules/20/meta/optimism/adjust'),
 ('post', '/api/v1/api/modules/20/meta/optimism/records'),
 ('post', '/api/v1/api/modules/20/meta/optionality/assess'),
 ('post', '/api/v1/api/modules/20/meta/outside-view'),
 ('post', '/api/v1/api/modules/20/meta/pareto'),
 ('post', '/api/v1/api/modules/20/meta/perspectives'),
 ('post', '/api/v1/api/modules/20/meta/planning-fallacy/correct'),
 ('post', '/api/v1/api/modules/20/meta/planning-fallacy/records'),
 ('post', '/api/v1/api/modules/20/meta/planning-horizon'),
 ('post', '/api/v1/api/modules/20/meta/premortem'),
 ('post', '/api/v1/api/modules/20/meta/premortem/register'),
 ('post', '/api/v1/api/modules/20/meta/principal-agent'),
 ('post', '/api/v1/api/modules/20/meta/queue'),
 ('post', '/api/v1/api/modules/20/meta/real-options'),
 ('post', '/api/v1/api/modules/20/meta/red-team'),
 ('post', '/api/v1/api/modules/20/meta/reference-class/cases'),
 ('post', '/api/v1/api/modules/20/meta/reference-class/forecast'),
 ('post', '/api/v1/api/modules/20/meta/reframe'),
 ('post', '/api/v1/api/modules/20/meta/reversibility/assess'),
 ('post', '/api/v1/api/modules/20/meta/risk-of-ruin'),
 ('post', '/api/v1/api/modules/20/meta/scenarios'),
 ('post', '/api/v1/api/modules/20/meta/second-order'),
 ('post', '/api/v1/api/modules/20/meta/sensitivity'),
 ('post', '/api/v1/api/modules/20/meta/serendipity/plan'),
 ('post', '/api/v1/api/modules/20/meta/signaling'),
 ('post', '/api/v1/api/modules/20/meta/simulations'),
 ('post', '/api/v1/api/modules/20/meta/simulations/{record_id}/resolve'),
 ('post', '/api/v1/api/modules/20/meta/steelman'),
 ('post', '/api/v1/api/modules/20/meta/systems/leverage'),
 ('post', '/api/v1/api/modules/20/meta/systems/loops'),
 ('post', '/api/v1/api/modules/20/meta/temporal/compare'),
 ('post', '/api/v1/api/modules/20/meta/tipping-point'),
 ('post', '/api/v1/api/modules/20/meta/toc/observe'),
 ('post', '/api/v1/api/modules/20/meta/tornado'),
 ('post', '/api/v1/api/modules/20/meta/value-chain'),
 ('post', '/api/v1/api/modules/20/meta/world-models'),
 ('post', '/api/v1/api/modules/20/meta/world-models/{name}/evidence'),
 ('post', '/api/v1/api/modules/20/meta/world-models/{name}/revise'),
 ('post', '/api/v1/api/modules/20/mob-programming/692/audit'),
 ('post', '/api/v1/api/modules/20/mob-programming/692/plan'),
 ('post', '/api/v1/api/modules/20/naming-conventions/707/check'),
 ('post', '/api/v1/api/modules/20/negotiation-behavior-85-109/analyze'),
 ('post', '/api/v1/api/modules/20/optimization-story-235-280/{method}'),
 ('post', '/api/v1/api/modules/20/pair-programming/691/diagnostics'),
 ('post', '/api/v1/api/modules/20/particle-swarm/solve'),
 ('post', '/api/v1/api/modules/20/platform-engineering/585-634/analyze'),
 ('post', '/api/v1/api/modules/20/political-social-1760-1809/{row_id}'),
 ('post', '/api/v1/api/modules/20/propositional-reasoning/entail'),
 ('post', '/api/v1/api/modules/20/quality-assurance/1535/evaluate'),
 ('post', '/api/v1/api/modules/20/refactoring/689/rename-local'),
 ('post', '/api/v1/api/modules/20/release-notes/702/plan'),
 ('post', '/api/v1/api/modules/20/semantic-versioning/700/analyze'),
 ('post', '/api/v1/api/modules/20/social-research-1710-1759/{method}'),
 ('post', '/api/v1/api/modules/20/software-practice/685-709/analyze'),
 ('post', '/api/v1/api/modules/20/specialized-domain/analyze'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/resume'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/retrospective'),
 ('post', '/api/v1/api/modules/20/tasks/{task_id}/ruminate'),
 ('post', '/api/v1/api/modules/20/technical-debt/693/schedule'),
 ('post', '/api/v1/api/modules/20/technical-spec-133-165/analyze'),
 ('post', '/api/v1/api/modules/20/technical-spec/199-229/{row}'),
 ('post', '/api/v1/api/modules/20/test-driven-development/687/check'),
 ('post', '/api/v1/api/modules/20/trunk-based-development/698/analyze'),
 ('put', '/api/v1/api/modules/20/api/modules/20/runtime/tasks/{task_id}/plan'))
FINAL_NOT_BOUND = {'GCW runtime not bound for authenticated tenant': 34, 'registry not bound for authenticated tenant': 3, 'investigator not bound for authenticated tenant': 4, 'twin registry not bound for authenticated tenant': 4, 'GCW service not bound for authenticated tenant': 107, 'predictor not bound for authenticated tenant': 2, 'model not bound for authenticated tenant': 5, 'transfer learner not bound for authenticated tenant': 2}
FINAL_TOTAL_ROUTES = 267

PRE_FINAL_REACHABLE = dict(REACHABLE)
REACHABLE = {**PRE_FINAL_REACHABLE, **FINAL_REACHABLE_ADDITIONS}
TOTAL_ROUTES = FINAL_TOTAL_ROUTES

# Retain all prior snapshots as data; classify the current default separately.
HISTORICAL_FINAL_REACHABLE = dict(REACHABLE)
HISTORICAL_FINAL_NOT_BOUND = dict(FINAL_NOT_BOUND)
AGI_UNBOUND_OPERATIONS = {
    operation for operation in HISTORICAL_FINAL_REACHABLE
    if "/agi-runtime/" in operation[1]
}
PRE_FINAL_REACHABLE = {
    operation: status for operation, status in PRE_FINAL_REACHABLE.items()
    if operation not in AGI_UNBOUND_OPERATIONS
}
REACHABLE = {
    operation: status for operation, status in HISTORICAL_FINAL_REACHABLE.items()
    if operation not in AGI_UNBOUND_OPERATIONS
}
NOT_BOUND = {
    **HISTORICAL_FINAL_NOT_BOUND,
    "AGI runtime service not bound for authenticated tenant": 8,
}
CURRENT_NOT_BOUND = BATCH2_NOT_BOUND = FINAL_NOT_BOUND = NOT_BOUND


def test_additive_current_exact_operation_inventory(env):
    app, _, _ = env
    assert tuple(sorted(ops(app))) == FINAL_INVENTORY
    assert len(CURRENT_INVENTORY) == CURRENT_TOTAL_ROUTES == 241
    assert len(BATCH2_INVENTORY) == BATCH2_TOTAL_ROUTES == 246
    assert len(PRE_FINAL_REACHABLE) == 77
    assert len(FINAL_REACHABLE_ADDITIONS) == 21
    assert len(REACHABLE) == 98
    assert FINAL_TOTAL_ROUTES == 267
    assert FINAL_NOT_BOUND == BATCH2_NOT_BOUND == CURRENT_NOT_BOUND == NOT_BOUND
    assert sum(FINAL_NOT_BOUND.values()) == 169
    assert FINAL_TOTAL_ROUTES == len(REACHABLE) + sum(FINAL_NOT_BOUND.values())
    assert set(FINAL_REACHABLE_ADDITIONS).isdisjoint(PRE_FINAL_REACHABLE)
    assert len([path for _, path in REACHABLE if '/agi-runtime/' in path]) == 0
    assert len(AGI_UNBOUND_OPERATIONS) == 8
    assert len(HISTORICAL_FINAL_REACHABLE) == 106
    assert sum(HISTORICAL_FINAL_NOT_BOUND.values()) == 161


def test_final_combined_mounts_auth_and_reachability(env):
    _, client, headers = env
    for (method, path), status in FINAL_REACHABLE_ADDITIONS.items():
        assert call(client, method, path).status_code == 401
        response = call(client, method, path, headers)
        assert response.status_code == status == 422, (path, response.text)
