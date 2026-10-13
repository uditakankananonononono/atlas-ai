"""Mounted HTTP behavior, no engine import at collection or direct-engine oracle.

Development identity headers only: no production OIDC/provider/retention proof.
Tests can collect before either historical engine/route introduction.
"""
import pytest

PREFIX = '/api/v1/api/modules/20'
HEADERS = {'X-Atlas-Tenant': 'fixture-owner', 'X-Atlas-Actor': 'fixture-actor'}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '1')
    monkeypatch.setenv('ATLAS_ENV', 'development')
    monkeypatch.setenv('ATLAS_M10_TIMESTAMP_SCHEME', 'off')
    # Import the real application inside fixture, never at collection.
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as mounted:
        yield mounted


def test_row688_mounted_agreement_bookkeeping(client):
    payload = {'feature': 'Export report',
               'acceptance_criteria': [{'id': 'AC1', 'text': 'CSV download starts'},
                                       {'id': 'AC2', 'text': 'File contains header'}],
               'examples': [{'criterion_id': 'AC1', 'text': 'User picks CSV'}],
               'stakeholders': ['qa', 'developer'], 'agreed_by': ['qa']}
    response = client.post(PREFIX + '/acceptance-test-driven-development/688/bookkeeping',
                           json={'data': payload}, headers=HEADERS)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['tenant_id'] == 'fixture-owner'
    assert result['actor_id'] == 'fixture-actor'
    assert result['agreement_complete'] is False
    assert result['pending_agreement'] == ['developer']
    assert result['uncovered_criterion_ids'] == ['AC2']
    assert result['tests_executed'] is False


def test_row810_mounted_sm2_observed_state(client):
    payload = {'source': {'title': 'Declared fixture', 'url': 'https://example.invalid/source'},
               'objective': 'remember supplied concepts',
               'items': [{'id': 'one', 'evidence_id': 'r1', 'quality': 5,
                          'repetitions': 1, 'interval_days': 1, 'ease': 2.6,
                          'reviewed_at': '2026-10-07T00:00:00+05:30'}]}
    response = client.post(PREFIX + '/learning-reasoning-810-859/spaced_repetition',
                           json={'payload': payload}, headers=HEADERS)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['row_id'] == 810
    result = data['result']
    row = result['schedule'][0]
    assert row['interval_days'] == 6
    assert row['repetitions'] == 2
    assert row['id'] == 'one' and row['evidence_id'] == 'r1'
    assert result['algorithm'] == 'SM-2 interval/state calculation'
    assert row['ease'] == pytest.approx(2.7)
    assert row['previous_state'] == {'repetitions': 1, 'interval_days': 1, 'ease': 2.6}
    assert row['due_at'] == '2026-10-13T00:00:00+05:30'
    assert row['lapse'] is False and row['same_session_retry_required'] is False
    assert data['tenant_id'] == 'fixture-owner'
    assert data['actor_id'] == 'fixture-actor'
