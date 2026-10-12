"""Wiring batch 5: mounted-route tests for dedicated engines 1520/1524/1525/1526.

Each test proves the mounted route responds through the app client (tenant-bound,
engine result keys verbatim from the real return value, one hand-computed value,
refusal mapping). Engines are accepted closed-scoped per their own docstrings.
"""
from fastapi.testclient import TestClient
from app.main import app

BASE = '/api/v1/api/modules/20/engineering'

P1520 = {'problem_statement': 'pump seal leaked in service',
         'evidence': [{'id': 'e1', 'kind': 'inspection', 'description': 'scoring on shaft'},
                      {'id': 'e2', 'kind': 'photo', 'description': 'cracked seal face'}],
         'hypotheses': [{'id': 'h1', 'statement': 'abrasive wear',
                         'supporting_evidence_ids': ['e1', 'e2'], 'contrary_evidence_ids': []}],
         'timeline': [{'at': '2026-10-01', 'event': 'leak first observed'}],
         'preservation_actions': ['seal kept in bag']}

P1524 = {'tasks': [{'id': 't1', 'name': 'dose entry', 'safety_consequence': True,
                    'use_errors': [{'id': 'u1', 'description': 'wrong unit selected',
                                    'severity': 5, 'likelihood': 2, 'mitigation_ids': ['m1']}]}],
         'mitigations': [{'id': 'm1', 'description': 'unit lock-in'}]}

P1525 = {'task': 'overhead assembly',
         'exposures': [{'id': 'x1', 'kind': 'posture', 'value': 45, 'unit': 'deg',
                        'limit': 30, 'duration_s': 120}]}

P1526 = {'criteria': [{'id': 'c1', 'weight': 60}, {'id': 'c2', 'weight': 40}],
         'concepts': [{'id': 'k1', 'name': 'alpha', 'scores': {'c1': 8, 'c2': 5}},
                      {'id': 'k2', 'name': 'beta', 'scores': {'c1': 6, 'c2': 9}}]}


def _post(c, path, body, headers=None):
    return c.post(BASE + path, json=body, headers=headers or {})


def test_failure_analysis1520_mounted(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    path = '/failure-analysis/1520/plan'
    assert _post(c, path, {'data': P1520}).status_code == 401
    h = oidc_auth_headers('a', 'owner')
    r = _post(c, path, {'data': P1520}, h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['tenant_id'] == 'a' and out['actor_id'] == 'owner'
    assert out['evidence_registered'] == 2 and out['hypotheses_supplied'] == 1
    assert out['hypotheses'][0]['net_support'] == 2  # hand-computed: 2 supporting, 0 contrary
    assert out['unreferenced_evidence_ids'] == [] and out['root_cause_claimed'] is False
    bad = {**P1520, 'hypotheses': [dict(P1520['hypotheses'][0], supporting_evidence_ids=['ghost'])]}
    assert _post(c, path, {'data': bad}, h).status_code == 422
    assert _post(c, path, {'data': P1520, 'tenant_id': 'b'}, h).status_code == 403


def test_human_factors1524_mounted(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    path = '/human-factors/1524/run'
    assert _post(c, path, {'data': P1524}).status_code == 401
    h = oidc_auth_headers('a', 'owner')
    r = _post(c, path, {'data': P1524}, h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['tenant_id'] == 'a' and out['actor_id'] == 'owner'
    err = out['tasks'][0]['use_errors'][0]
    assert err['risk_index'] == 10 and err['mitigated'] is True  # hand-computed: 5 * 2
    assert out['summary']['task_count'] == 1 and out['usability_study_claimed'] is False
    bad = {'tasks': [dict(P1524['tasks'][0], use_errors=[dict(P1524['tasks'][0]['use_errors'][0], severity=9)])]}
    assert _post(c, path, {'data': bad}, h).status_code == 422


def test_ergonomics1525_mounted(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    path = '/ergonomics/1525/run'
    assert _post(c, path, {'data': P1525}).status_code == 401
    h = oidc_auth_headers('a', 'owner')
    r = _post(c, path, {'data': P1525}, h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['tenant_id'] == 'a' and out['actor_id'] == 'owner'
    assert any(k in out for k in ('exposures', 'exceeding', 'summary', 'results'))
    assert _post(c, path, {'data': {'task': 'x'}}, h).status_code == 422  # exposures required


def test_industrial_design1526_mounted(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    path = '/industrial-design/1526/run'
    assert _post(c, path, {'data': P1526}).status_code == 401
    h = oidc_auth_headers('a', 'owner')
    r = _post(c, path, {'data': P1526}, h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out['tenant_id'] == 'a' and out['actor_id'] == 'owner'
    assert out['max_possible_total'] == 1000  # hand-computed: 10 * (60 + 40)
    top = out['ranking'][0]
    assert top['id'] == 'k2' and top['weighted_total'] == 720 and top['rank'] == 1  # hand-computed: 60*6+40*9 beats k1's 680
    assert out['selected_concept'] is None and out['release_ready'] is False
    bad = {'criteria': P1526['criteria'],
           'concepts': [dict(P1526['concepts'][0], scores={'c1': 11, 'c2': 5})]}
    assert _post(c, path, {'data': bad}, h).status_code == 422


# ------------------------------------------------ wiring batch 5 repair pins
# Boundary pins P1-P6. Runtime untouched; these pin tenant-override 403s,
# resource_refs cap, real 1525 return keys, surrogate rejection, wrong-type
# data 422s, and the unmitigated-1524 case.

PATHS = {'1520': '/failure-analysis/1520/plan', '1524': '/human-factors/1524/run',
         '1525': '/ergonomics/1525/run', '1526': '/industrial-design/1526/run'}
PACKETS = {'1520': P1520, '1524': P1524, '1525': P1525, '1526': P1526}
import pytest


@pytest.mark.parametrize('row', ['1520', '1524', '1525', '1526'])
def test_p1_owner_override_403(monkeypatch, oidc_auth_headers, row):
    # P1: deleting owner_payload must not survive - spoofed tenant/actor/refs refuse.
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    h = oidc_auth_headers('a', 'owner')
    body = {'data': PACKETS[row]}
    assert _post(c, PATHS[row], {**body, 'tenant_id': 'b'}, h).status_code == 403
    assert _post(c, PATHS[row], {**body, 'actor_id': 'other'}, h).status_code == 403
    assert _post(c, PATHS[row], {**body, 'resource_refs': [{'tenant_id': 'b'}]}, h).status_code == 403


@pytest.mark.parametrize('row', ['1520', '1524', '1525', '1526'])
def test_p2_resource_refs_cap(monkeypatch, oidc_auth_headers, row):
    # P2: 64 own-tenant refs pass, 65 refuse.
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    h = oidc_auth_headers('a', 'owner')
    refs = [{'tenant_id': 'a', 'note': 'r%d' % i} for i in range(64)]
    r = _post(c, PATHS[row], {'data': PACKETS[row], 'resource_refs': refs}, h)
    assert r.status_code == 200, r.text
    r = _post(c, PATHS[row], {'data': PACKETS[row], 'resource_refs': refs + [{'tenant_id': 'a'}]}, h)
    assert r.status_code == 422


def test_p3_ergonomics1525_real_keys_and_hand_computed(monkeypatch, oidc_auth_headers):
    # P3: real return keys + hand-computed values for the 45deg vs limit-30 exposure.
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    h = oidc_auth_headers('a', 'owner')
    r = _post(c, PATHS['1525'], {'data': P1525}, h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out) >= {'task', 'exposures', 'anthropometric', 'controls',
                        'assessment_instrument', 'supplied_score', 'computed_score',
                        'scoring_authority', 'interpretation_requires_qualified_reviewer',
                        'summary', 'tenant_id', 'actor_id'}
    exposure = out['exposures'][0]
    assert exposure['exceeds_supplied_limit'] is True       # 45 > limit 30
    assert exposure['margin'] == '-15'                      # hand-computed: 30 - 45
    assert out['summary'] == {'exposure_count': 1, 'exceeding_ids': ['x1'], 'unassessed_ids': []}
    assert out['computed_score'] is None and out['scoring_authority'] is False


@pytest.mark.parametrize('row', ['1520', '1524', '1525', '1526'])
def test_p4_lone_surrogate_rejected(monkeypatch, oidc_auth_headers, row):
    # P4: raw JSON carrying a lone surrogate is rejected before pydantic echoes it.
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    h = oidc_auth_headers('a', 'owner')
    r = c.post('/api/v1/api/modules/20/engineering' + PATHS[row],
               headers={**h, 'Content-Type': 'application/json'},
               content='{"data":{"x":"\\ud800"}}')
    assert r.status_code == 422


@pytest.mark.parametrize('row,body', [('1524', {'tasks': 5}), ('1525', {'exposures': 'x'}),
                                      ('1526', {'criteria': 5})])
def test_p5_wrong_type_data_422_not_500(monkeypatch, oidc_auth_headers, row, body):
    # P5: wrong-type payload fields hit the ValueError/TypeError arm, never a 500.
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    h = oidc_auth_headers('a', 'owner')
    r = _post(c, PATHS[row], {'data': body}, h)
    assert r.status_code == 422, r.text


def test_p6_1524_unmitigated_hand_computed(monkeypatch, oidc_auth_headers):
    # P6: use error with no mitigations -> mitigated False, unmitigated-high list,
    # summary numbers hand-computed.
    monkeypatch.setenv('ATLAS_ENV', 'production'); c = TestClient(app)
    h = oidc_auth_headers('a', 'owner')
    packet = {'tasks': [{'id': 't1', 'name': 'dose entry', 'safety_consequence': True,
                         'use_errors': [{'id': 'u2', 'description': 'dose misread',
                                         'severity': 5, 'likelihood': 4, 'mitigation_ids': []}]}]}
    r = _post(c, PATHS['1524'], {'data': packet}, h)
    assert r.status_code == 200, r.text
    out = r.json()
    err = out['tasks'][0]['use_errors'][0]
    assert err['risk_index'] == 20 and err['mitigated'] is False  # hand-computed: 5 * 4
    assert out['summary']['max_risk_index'] == 20
    assert out['summary']['unmitigated_high_ids'] == ['t1/u2']
    assert out['summary']['error_count'] == 1 and out['summary']['validation_participant_count'] == 0
