"""Row 1276 Mediation: mounted-route tests through the full app with real RS256 identities.

Row text (coverage-register row 1276): requirement "Mediation", description empty.
Claim scope: POST /api/v1/api/modules/20/mediation-1276/organize runs mediation1276.organize behind
the production bearer verifier and returns caller-declared closed-vocabulary bookkeeping in a
tenant/actor envelope. Not claimed: any mediation outcome, settlement, legal conclusion, authority
verification, filing or contact. Tests never use the development auth bypass.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app

URL = '/api/v1/api/modules/20/mediation-1276/organize'
AUTH = {'id': 'a1', 'citation_text': 'Supplied citation text', 'jurisdiction': 'Declared-Jurisdiction',
        'effective_date': '2020-01-01'}


def item(i='i1', **kw):
    d = {'id': i, 'interest_kind': 'interest_declared', 'authority_to_settle': 'full_authority',
         'confidentiality': 'confidential_declared', 'option_kind': 'settlement_option',
         'binding_effect': 'nonbinding', 'source_ids': ['a1']}
    d.update(kw)
    return d


def payload(**kw):
    d = {'jurisdiction': 'Declared-Jurisdiction', 'as_of': '2026-01-01', 'authorities': [dict(AUTH)], 'items': [item()]}
    d.update(kw)
    return d


def post(c, body, headers):
    r = c.post(URL, json=body, headers=headers)
    assert r.status_code in (200, 422), (r.status_code, r.text)
    return r


@pytest.fixture
def real_auth(monkeypatch, oidc_auth_headers):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    return oidc_auth_headers


def test_row1276_no_credentials_and_identity_headers_alone_are_401(real_auth):
    c = TestClient(app)
    assert c.post(URL, json=payload()).status_code == 401
    r = c.post(URL, json=payload(), headers={'X-Atlas-Tenant': 'tenant-a', 'X-Atlas-Actor': 'tester', 'X-Tenant-ID': 'tenant-a'})
    assert r.status_code == 401, r.text
    assert post(c, payload(), real_auth()).status_code == 200


def test_row1276_mounted_organize_returns_bookkeeping_in_principal_envelope(real_auth):
    c = TestClient(app)
    r = c.post(URL, json=payload(), headers=real_auth('tenant-a', 'alice'))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j['module_id'] == 20 and j['tenant_id'] == 'tenant-a' and j['actor_id'] == 'alice'
    assert j['requires_licensed_counsel'] is True
    res = j['result']
    assert res['row'] == 1276 and res['status'] == 'caller_declared_mediation_bookkeeping_only'
    assert res['review_state'] == 'counsel_review_required'
    assert res['counts'] == {'items': 1, 'unclassified': 0, 'blocked_items': 0}
    assert res['settlement_reached'] is False and res['legal_conclusion'] is None
    assert res['filing_or_external_effect'] is False and res['authorities_independently_verified'] is False


def test_row1276_envelope_identity_follows_the_token_not_the_body(real_auth):
    c = TestClient(app)
    a = post(c, payload(), real_auth('tenant-a', 'alice')).json()
    b = post(c, payload(), real_auth('tenant-b', 'bob')).json()
    assert (a['tenant_id'], a['actor_id']) == ('tenant-a', 'alice')
    assert (b['tenant_id'], b['actor_id']) == ('tenant-b', 'bob')
    assert a['result'] == b['result']
    r = c.post(URL, json=payload(tenant_id='tenant-b', actor_id='bob'), headers=real_auth('tenant-a', 'alice'))
    assert r.status_code == 422 and r.json()['detail'].startswith('MED1276:'), r.text


def test_row1276_unclassified_and_unresolved_sources_block_review(real_auth):
    c = TestClient(app)
    p = payload(items=[item(option_kind='unknown', source_ids=['missing-id'])])
    r = c.post(URL, json=p, headers=real_auth())
    assert r.status_code == 200, r.text
    res = r.json()['result']
    assert res['review_state'] == 'blocked'
    assert res['classified'][0]['unclassified_fields'] == ['option_kind']
    assert res['classified'][0]['missing_source_ids'] == ['missing-id']
    assert res['counts']['blocked_items'] == 1


def test_row1276_authority_mismatches_are_flagged_and_block(real_auth):
    c = TestClient(app)
    p = payload(authorities=[dict(AUTH, jurisdiction='Other', effective_date='2027-01-01')])
    res = post(c, p, real_auth()).json()['result']
    f = res['authority_flags'][0]
    assert f['jurisdiction_mismatch'] is True and f['effective_after_as_of'] is True
    assert f['independently_verified'] is False and res['review_state'] == 'blocked'


def test_row1276_refusals_are_422_and_never_echo_values(real_auth):
    c = TestClient(app)
    secret = 'SECRET-VALUE-ZZ'
    cases = [payload(items=[item(interest_kind=secret)]), payload(jurisdiction='x' * 300), payload(as_of='2026-13-01'),
             payload(decide=secret), payload(file=secret), payload(items=[]), payload(extra=secret),
             payload(items=[item(), item()])]
    for body in cases:
        r = c.post(URL, json=copy.deepcopy(body), headers=real_auth())
        assert r.status_code == 422, body
        assert r.json()['detail'].startswith('MED1276:'), r.text
        assert secret not in r.text


def test_row1276_matches_direct_engine_result_and_rejects_wrong_shapes(real_auth):
    from app.modules.m20_general_cognitive_worker.mediation1276 import organize
    c = TestClient(app)
    h = real_auth()
    assert post(c, payload(), h).json()['result'] == organize(payload())
    assert c.get(URL, headers=h).status_code == 405
    assert c.post(URL, json=[1], headers=h).status_code == 422
