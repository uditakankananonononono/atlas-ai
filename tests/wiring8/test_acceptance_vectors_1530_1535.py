"""Exact supplied-input acceptance vectors for landed engines 1530 and 1535.

Literal hand-derived expectations (acceptance cards 1530/1535) pinned against
the mounted batch-6 routes. Accepted AS the closed-scoped engines over
caller-supplied declarations only; not a test run, certification, validation,
release or approval. No sigma level, statistical validation, physical test or
release authority is pinned or implied.
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app

PATH1530 = '/api/v1/api/modules/20/design-for-six-sigma/1530/run'
PATH1535 = '/api/v1/api/modules/20/quality-assurance/1535/evaluate'

DATA1530 = {'dmadv_phase': 'verify', 'ctqs': [
    {'id': 'C1', 'name': 'Width', 'specification': {'unit': 'mm', 'lower': 1, 'target': 2, 'upper': 3}},
    {'id': 'C2', 'name': 'Finish'}],
    'verification_plan': [{'id': 'p1', 'ctq_id': 'C1', 'method': 'caller inspection plan'}]}
EXPECTED1530 = {'phase': 'verify', 'phase_index': 4,
    'open_ctq_ids': ['C2'], 'unverified_ctq_ids': ['C2'],
    'plan_items_by_ctq': {'C1': 1, 'C2': 0},
    'phase_gate_notes': ['open_ctq_at_design_or_verify', 'unverified_ctq_at_verify'],
    'statistical_validation_claimed': False, 'sigma_level_computed': False,
    'summary': {'ctq_count': 2, 'open_count': 1, 'unverified_count': 1, 'plan_item_count': 1}}

DATA1535 = {'defect_policy': 'flag', 'caller_release_requested': True,
    'requirements': [
        {'id': 'R1', 'conditions': [{'test_id': 't1', 'metric': 'm1', 'op': '<=', 'threshold': 5}]},
        {'id': 'R2', 'conditions': [{'test_id': 't2', 'metric': 'm2', 'op': 'between', 'threshold': [1, 2]}]}],
    'observations': [
        {'id': 'o1', 'test_id': 't1', 'metric': 'm1', 'value': 4, 'signed': True,
         'source': 'caller', 'time': '2026-10-11T10:00:00Z'},
        {'id': 'o2', 'test_id': 't2', 'metric': 'm2', 'value': 3, 'signed': True,
         'source': 'caller', 'time': '2026-10-11T10:00:00Z'},
        {'id': 'o3', 'test_id': 't1', 'metric': 'm1', 'value': 9, 'signed': False,
         'source': 'caller', 'time': '2026-10-11T10:00:00Z'}]}
EXPECTED1535 = {'release_status': 'RELEASE-UNREADY',
    'release_authority': False, 'release_granted': False, 'caller_release_flag_ignored': True,
    'physical_test_claimed': False, 'persisted': False, 'effects': [],
    'basis': 'evaluation of supplied observations against predeclared acceptance conditions; no test was run',
    'requirements': [{'id': 'R1', 'status': 'SATISFIED'}, {'id': 'R2', 'status': 'REFUTED'}],
    'coverage': {'requirements_total': 2, 'satisfied_ids': ['R1'], 'unsupported': {'R2': 'REFUTED'}},
    'unmapped_observations': [], 'mismatched_observations': [], 'conflicts': [],
    'defects': [{'observation_id': 'o3', 'field': 'signed'}],
    'audit_trace': [
        {'requirement_id': 'R1', 'mode': 'all', 'status': 'SATISFIED', 'conditions': [
            {'test_id': 't1', 'metric': 'm1', 'op': '<=', 'threshold': 5, 'status': 'SATISFIED',
             'supporting': ['o1'], 'refuting': [], 'distinct_supporting_runs': 1, 'min_repeats': 1}]},
        {'requirement_id': 'R2', 'mode': 'all', 'status': 'REFUTED', 'conditions': [
            {'test_id': 't2', 'metric': 'm2', 'op': 'between', 'threshold': [1, 2], 'status': 'REFUTED',
             'supporting': [], 'refuting': ['o2'], 'distinct_supporting_runs': 0, 'min_repeats': 1}]}]}

REFUSALS = [
    (PATH1530, {}, 'DFSS1530:invalid_phase'),
    (PATH1530, dict(DATA1530, zz=True), 'DFSS1530:unknown_key'),
    (PATH1530, {'dmadv_phase': 'verify', 'ctqs': [{'id': 'C1', 'name': 'Width'}],
                'verification_plan': [{'id': 'p1', 'ctq_id': 'ZZ', 'method': 'caller inspection plan'}]},
     'DFSS1530:unknown_ctq'),
    (PATH1530, {'dmadv_phase': 'verify',
                'ctqs': [{'id': 'C1', 'name': 'Width'}, {'id': 'C1', 'name': 'Weight'}]},
     'DFSS1530:duplicate_id:ctqs'),
    (PATH1535, {}, "defect_policy must be 'refuse' or 'flag'"),
    (PATH1535, dict(DATA1535, zz=True), 'unknown request field: zz'),
    (PATH1535, dict(DATA1535, defect_policy='refuse'), 'observation o3 defective: signed'),
]


@pytest.fixture
def mounted(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    return TestClient(app)


@pytest.mark.parametrize('path,data,expected', [
    (PATH1530, DATA1530, EXPECTED1530), (PATH1535, DATA1535, EXPECTED1535)])
def test_exact_acceptance_vector(mounted, oidc_auth_headers, path, data, expected):
    r = mounted.post(path, json={'data': deepcopy(data)},
                     headers=oidc_auth_headers('vector-tenant', 'vector-actor'))
    assert r.status_code == 200, r.text
    assert r.json() == dict(expected, tenant_id='vector-tenant', actor_id='vector-actor')


@pytest.mark.parametrize('path,packet,detail', REFUSALS)
def test_exact_engine_refusal_details(mounted, oidc_auth_headers, path, packet, detail):
    r = mounted.post(path, json={'data': deepcopy(packet)}, headers=oidc_auth_headers())
    assert r.status_code == 422
    assert r.json() == {'detail': detail}
