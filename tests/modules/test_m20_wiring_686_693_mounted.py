"""Mounted-route checks for the software-practice engines 686 to 693.

Each engine is called through the app client with a hand-made input and one hand-computed value. Every route is
owner-bound: no token is 401, a payload owner that differs from the caller is 403, bad engine input is 422.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

BASE = '/api/v1/api/modules/20'
DIFF = "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1,0 +1,1 @@\n+x = 1\n"


def receipt(stage, ordinal, rev, outcome):
    return {'stage': stage, 'ordinal': ordinal, 'revision_ref': rev, 'suite_ref': 's', 'evidence_ref': 'e-' + stage,
            'results': [{'id': 't1', 'outcome': outcome}]}


CASES = {
    '686': (BASE + '/bdd-scenarios/686/execute',
            {'data': {'scenarios': [{'name': 'counter', 'given': [{'op': 'assign', 'var': 'count', 'value': 0}],
                                     'when': [{'op': 'increment', 'var': 'count', 'by': 2},
                                              {'op': 'increment', 'var': 'count', 'by': 3}],
                                     'then': [{'assert': 'equals', 'var': 'count', 'value': 5}]}]}},
            {'data': {'scenarios': []}},
            lambda j: j['status'] == 'all_passed' and j['steps_executed'] == 4),
    '687': (BASE + '/test-driven-development/687/check',
            {'data': {'as_of': 'now', 'cycles': [{'id': 'c1', 'behavior': 'adds', 'receipts': [
                receipt('red', 1, 'r1', 'FAIL'), receipt('green', 2, 'r2', 'PASS'), receipt('refactor', 3, 'r3', 'PASS')]}]}},
            {'data': {'as_of': 'now', 'cycles': 'x'}},
            lambda j: j['consistent_cycles'] == 1 and j['tests_executed'] is False
            and j['cycles'][0]['declaration_consistent'] is True),
    '688': (BASE + '/acceptance-test-driven-development/688/bookkeeping',
            {'data': {'feature': 'login', 'acceptance_criteria': [{'id': 'c1', 'text': 'user can sign in'}],
                      'examples': [{'criterion_id': 'c1', 'text': 'valid password'}],
                      'stakeholders': ['pm', 'qa'], 'agreed_by': ['pm']}},
            {'data': {'feature': 'login'}},
            lambda j: j['pending_agreement'] == ['qa'] and j['agreement_complete'] is False
            and j['uncovered_criterion_ids'] == [] and j['tests_executed'] is False),
    '689': (BASE + '/refactoring/689/rename-local',
            {'source': 'def f(a):\n    t = a + 1\n    return t\n', 'old': 't', 'new': 'total'},
            {'source': 'def f(a):\n    return a\n', 'old': 't', 'new': 'total'},
            lambda j: j['renamed_occurrences'] == 2 and 'total = a + 1' in j['source']
            and j['repository_behavior_verified'] is False),
    '690': (BASE + '/code-review/690/review',
            {'diff': DIFF, 'review_checklist': ['no secrets'], 'author': 'asha'},
            {'diff': 'not a diff', 'review_checklist': [], 'author': 'asha'},
            lambda j: j['files'] == ['src/a.py'] and j['added_lines'] == 1 and j['decision'] == 'comments_only'
            and [f['rule'] for f in j['findings']] == ['missing-tests'] and j['human_review_required'] is True),
    '691': (BASE + '/pair-programming/691/diagnostics',
            {'data': {'session_id': 's1', 'task': 'rate limiter', 'participants': ['asha', 'biren'],
                      'rotations': [{'driver_id': 'asha', 'duration_minutes': 30},
                                    {'driver_id': 'biren', 'duration_minutes': 30, 'handoff_note': 'n'}],
                      'understanding_checks': [{'item': 'goal', 'confirmed': True}]}},
            {'data': {'session_id': 's1'}},
            lambda j: j['drive_minutes'] == {'asha': 30, 'biren': 30} and j['total_minutes'] == 60
            and j['dominant_driver'] is None),
    '692-plan': (BASE + '/mob-programming/692/plan',
                 {'participants': ['a', 'b', 'c'], 'task': 't', 'session_minutes': 30, 'rotation_minutes': 10},
                 {'participants': ['a', 'b'], 'task': 't', 'session_minutes': 30, 'rotation_minutes': 10},
                 lambda j: [(t['driver'], t['navigator'], t['minutes']) for t in j['turns']]
                 == [('a', 'b', 10), ('b', 'c', 10), ('c', 'a', 10)] and j['everyone_drives'] is True),
    '692-audit': (BASE + '/mob-programming/692/audit',
                  {'participants': ['a', 'b', 'c'],
                   'log': [{'driver': 'a', 'start_minute': 0, 'end_minute': 10},
                           {'driver': 'b', 'start_minute': 10, 'end_minute': 20},
                           {'driver': 'c', 'start_minute': 20, 'end_minute': 30}]},
                  {'participants': ['a', 'b'], 'log': []},
                  lambda j: j['ok'] is True and j['driver_minutes'] == {'a': 10, 'b': 10, 'c': 10}),
    '693': (BASE + '/technical-debt/693/schedule',
            {'data': {'budget_hours': 10, 'items': [
                {'id': 'a', 'benefit': 9, 'cost': 7}, {'id': 'b', 'benefit': 8, 'cost': 4, 'depends_on': ['d']},
                {'id': 'c', 'benefit': 5, 'cost': 4}, {'id': 'd', 'benefit': 0, 'cost': 1}]}},
            {'data': {'budget_hours': 10, 'items': []}},
            lambda j: j['selected_ids'] == ['b', 'c', 'd'] and j['total_benefit'] == 13 and j['total_cost'] == 9),
}


@pytest.mark.parametrize('key', sorted(CASES))
def test_mounted_route_responds_owner_bound(key, monkeypatch, oidc_auth_headers):
    path, good, bad, check = CASES[key]
    monkeypatch.setenv('ATLAS_ENV', 'production')
    c = TestClient(app, raise_server_exceptions=False)
    assert c.post(path, json=good).status_code == 401
    # tenants unique to this case: the app limits requests per tenant and actor, shared by every test in the process
    own = 'w' + key.replace('-', '')
    for tenant, actor in [(own + 'a', 'owner'), (own + 'b', 'other')]:
        r = c.post(path, headers=oidc_auth_headers(tenant, actor), json=good)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j['tenant_id'] == tenant and j['actor_id'] == actor
        assert check(j), j
    h = oidc_auth_headers(own + 'a', 'owner')
    for extra in ({'tenant_id': 'b'}, {'actor_id': 'other'}, {'resource_refs': [{'tenant_id': 'b'}]}):
        assert c.post(path, headers=h, json={**good, **extra}).status_code == 403
    assert c.post(path, headers=h, json={**good, 'tenant_id': own + 'a', 'actor_id': 'owner'}).status_code == 200
    r = c.post(path, headers=h, json=bad)
    assert r.status_code == 422, r.text
    r = c.post(path, headers={**h, 'Content-Type': 'application/json'}, content=json.dumps({'x': '\ud800'}))
    assert r.status_code == 422 and '\ud800' not in r.text
