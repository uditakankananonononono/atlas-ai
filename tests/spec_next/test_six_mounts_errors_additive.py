"""HTTP refusal pins for six supplied-input routes, not live-provider evidence."""
from copy import deepcopy
import importlib
import pytest
from fastapi.testclient import TestClient
from app.main import app

CASES = [
    ('/api/v1/c32/psyche', 'app.modules.c32.psyche_routes', 'tag_evidence',
     {'text': 'happy'}, 'text', '', None, 'TREND_REFUSED_FIELDS'),
    ('/api/v1/c33/niches', 'app.modules.c33.niches_routes', 'generate',
     {'taxonomy': ['a'], 'audiences': ['b'], 'formats': ['c']},
     'taxonomy', [], None, 'SOCIAL_REFUSED_FIELDS'),
    ('/api/v1/c33/persona', 'app.modules.c33.persona_routes', 'profile',
     {'field': 'writing', 'samples': ['A supplied sample.']},
     'samples', [], None, 'SOCIAL_REFUSED_FIELDS'),
    ('/api/v1/c33/content', 'app.modules.c33.content_routes', 'compose',
     {'theme': 'repairs', 'notes': ['Use replaceable screws'], 'sources': [],
      'angle': 'repair before replacement', 'audience': 'makers'},
     'notes', [], None, 'SOCIAL_REFUSED_FIELDS'),
    ('/api/v1/c34/industry', 'app.modules.c34.industry_routes', 'run',
     {'taxonomy': [{'code': 'R', 'name': 'Root', 'parent': None}],
      'touched': [], 'needs': [], 'capabilities': [], 'min_gap_severity': 0},
     'taxonomy', [], None, 'PROTO_REFUSED_BAD_TYPE:request_fields'),
    ('/api/v1/c34/tool', 'app.modules.c34.tool_routes', 'run',
     {'as_of': '2026-10-15', 'requested_by_owner': True, 'company': 'Example',
      'need': {'id': 'columns', 'type': 'csv_transform',
               'description': 'retain columns', 'fields': ['name']}},
     'company', '', None, 'PROTO_REFUSED_BAD_TYPE:request'),
]

@pytest.fixture
def http(oidc_auth_headers, monkeypatch):
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH', '0')
    monkeypatch.setenv('ATLAS_ENV', 'production')
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, oidc_auth_headers()

@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize('kind', ['empty', 'wrong_type'])
def test_real_module_refusal_is_http_400(case, kind, http):
    path, module, function, valid, key, empty, wrong_type, fields_error = case
    request = deepcopy(valid)
    request[key] = empty if kind == 'empty' else wrong_type
    client, headers = http
    # Derive the exact detail from the underlying module, not the HTTP handler.
    underlying = getattr(importlib.import_module(module), function)
    with pytest.raises((ValueError, TypeError)) as error:
        if function in ('generate', 'profile'):
            underlying(**request)
        elif function == 'tag_evidence':
            underlying(request['text'])
        else:
            underlying(request)
    response = client.post(path, json=request, headers=headers)
    assert response.status_code == 400, response.text
    assert response.json() == {'detail': str(error.value)}

@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize('exception', [ValueError, TypeError], ids=['ValueError', 'TypeError'])
def test_both_module_exception_classes_map_to_400(case, exception, http, monkeypatch):
    path, module, function, valid, *_ = case
    detail = 'MODULE_BOUNDARY_' + exception.__name__
    def refuse(*args, **kwargs):
        raise exception(detail)
    # Both catches are part of the route contract. Some modules currently use
    # ValueError for every JSON-domain bad type, so inject TypeError at the
    # callable boundary rather than claiming a natural TypeError witness.
    monkeypatch.setattr(importlib.import_module(module), function, refuse)
    client, headers = http
    response = client.post(path, json=deepcopy(valid), headers=headers)
    assert response.status_code == 400, response.text
    assert response.json() == {'detail': detail}

MISSING = [(case, key) for case in CASES for key in case[3]]
@pytest.mark.parametrize('case,key', MISSING, ids=[c[0] + ':' + key for c, key in MISSING])
def test_each_required_key_absence_is_a_field_refusal(case, key, http):
    path, module, function, valid, _, _, _, fields_error = case
    request = deepcopy(valid)
    del request[key]
    client, headers = http
    response = client.post(path, json=request, headers=headers)
    assert response.status_code == 400, response.text
    assert response.json() == {'detail': fields_error}

@pytest.mark.parametrize('case', CASES, ids=[c[0] for c in CASES])
def test_empty_request_is_a_field_refusal(case, http):
    client, headers = http
    response = client.post(case[0], json={}, headers=headers)
    assert response.status_code == 400, response.text
    assert response.json() == {'detail': case[-1]}

@pytest.mark.parametrize('value', ['', None, 7, 'x' * 200001])
def test_psyche_text_boundaries_are_http_refusals(value, http):
    client, headers = http
    response = client.post(CASES[0][0], json={'text': value}, headers=headers)
    assert response.status_code == 400, response.text
    assert response.json()['detail'].startswith('TREND_REFUSED_')

@pytest.mark.parametrize('payload', [{'taxonomy': ['a']}, {}])
def test_niches_partial_required_keys_are_field_refusals(payload, http):
    client, headers = http
    response = client.post(CASES[1][0], json=payload, headers=headers)
    assert response.status_code == 400, response.text
    assert response.json() == {'detail': 'SOCIAL_REFUSED_FIELDS'}
