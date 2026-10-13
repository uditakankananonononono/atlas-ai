"""Real application mount with test RS256 identities, no engine oracle or stub."""
from copy import deepcopy
import pytest

PATH = '/api/v1/api/modules/20/legal/1272/run'
PAYLOAD = {
    'jurisdiction': 'Declared-Jurisdiction', 'as_of': '2026-01-01',
    'authorities': [{'id': 'a1', 'citation_text': 'Supplied citation',
                     'jurisdiction': 'Declared-Jurisdiction', 'effective_date': '2020-01-01'}],
    'items': [{'id': 'i1', 'signature': 'unknown', 'ratification': 'ratified',
               'reservation': 'none', 'entry_into_force': 'in_force',
               'domestic_effect': 'directly_applicable', 'source_ids': ['a1', 'missing']}],
}


@pytest.fixture
def mounted(monkeypatch, oidc_auth_headers):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    monkeypatch.setenv('ATLAS_ENV', 'production')
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        yield client, oidc_auth_headers('fixture-tenant', 'fixture-actor')


def post(mounted, data):
    client, headers = mounted
    return client.post(PATH, headers=headers, json={'data': data})


def test_real_mounted_dispatch_records_treaties(mounted):
    before = deepcopy(PAYLOAD)
    response = post(mounted, PAYLOAD)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['row'] == 1272
    assert result['status'] == 'caller_declared_treaties_bookkeeping_only'
    assert result['tenant_id'] == 'fixture-tenant' and result['actor_id'] == 'fixture-actor'
    assert result['review_state'] == 'blocked'
    assert result['classified'][0]['unclassified_fields'] == ['signature']
    assert result['classified'][0]['missing_source_ids'] == ['missing']
    assert result['counts'] == {'items': 1, 'unclassified': 1, 'blocked_items': 1}
    assert result['treaty_status_decided'] is False and result['legal_conclusion'] is None
    assert result['filing_or_external_effect'] is False
    assert result['authorities_independently_verified'] is False
    assert result['requires_licensed_counsel'] is True
    assert PAYLOAD == before


def test_clear_declarations_still_require_counsel(mounted):
    data = deepcopy(PAYLOAD)
    data['items'][0].update(signature='signed', source_ids=['a1'])
    response = post(mounted, data)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['review_state'] == 'counsel_review_required'
    assert result['counts'] == {'items': 1, 'unclassified': 0, 'blocked_items': 0}
    assert result['authority_flags'] == [{'id': 'a1', 'jurisdiction_mismatch': False,
                                          'effective_after_as_of': False, 'independently_verified': False}]


@pytest.mark.parametrize('authority_change,flag', [
    ({'jurisdiction': 'Other-Jurisdiction'}, 'jurisdiction_mismatch'),
    ({'effective_date': '2027-01-01'}, 'effective_after_as_of'),
])
def test_authority_flags_block_even_complete_item(mounted, authority_change, flag):
    data = deepcopy(PAYLOAD)
    data['items'][0].update(signature='signed', source_ids=['a1'])
    data['authorities'][0].update(authority_change)
    response = post(mounted, data)
    assert response.status_code == 200, response.text
    assert response.json()['authority_flags'][0][flag] is True
    assert response.json()['review_state'] == 'blocked'


@pytest.mark.parametrize('field,reason', [
    ('decide', 'CONCLUSION_REFUSED'), ('send', 'EXTERNAL_EFFECT_REFUSED'),
    ('extra', 'UNKNOWN_KEY'),
])
def test_refusal_maps_to_422_without_echo(mounted, field, reason):
    data = deepcopy(PAYLOAD)
    data[field] = 'private-fixture-value'
    response = post(mounted, data)
    assert response.status_code == 422, response.text
    assert response.json() == {'detail': 'TREAT1272:' + reason}
    assert 'private-fixture-value' not in response.text


def test_unknown_vocabulary_refused(mounted):
    data = deepcopy(PAYLOAD)
    data['items'][0]['signature'] = 'invented'
    response = post(mounted, data)
    assert response.status_code == 422, response.text
    assert response.json() == {'detail': 'TREAT1272:UNKNOWN_VALUE:signature'}


def test_missing_and_duplicate_authority_checks(mounted):
    data = deepcopy(PAYLOAD)
    data['authorities'].append(deepcopy(data['authorities'][0]))
    response = post(mounted, data)
    assert response.status_code == 422, response.text
    assert response.json() == {'detail': 'TREAT1272:DUPLICATE:authority_id'}


def test_actual_mount_auth_and_scope(mounted):
    client, headers = mounted
    assert client.post(PATH, json={'data': PAYLOAD}).status_code == 401
    assert client.post(PATH, headers={'X-Atlas-Tenant': 'fixture-tenant', 'X-Atlas-Actor': 'fixture-actor'},
                       json={'data': PAYLOAD}).status_code == 401
    for scope in ({'tenant_id': 'other'}, {'actor_id': 'other'},
                  {'resource_refs': [{'tenant_id': 'other'}]}):
        response = client.post(PATH, headers=headers, json={'data': PAYLOAD, **scope})
        assert response.status_code == 403, response.text
