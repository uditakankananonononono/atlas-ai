"""Acceptance pins for the mounted API documentation route (row 704): one hand-derived document, exact refusal text, caps."""
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

PATH = '/api/v1/api/modules/20/api-documentation/openapi'


@pytest.fixture
def call(monkeypatch, oidc_auth_headers, request):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    counter = {'n': 0}
    node = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]

    def go(data, expect=200, **extra):
        counter['n'] += 1  # the app limits requests per tenant and actor, so every call uses its own tenant derived from the test node id
        tenant = 'acc704-%s-%d' % (node, counter['n'])
        r = client.post(PATH, headers=oidc_auth_headers(tenant, 'owner'), json={'data': data, **extra})
        assert r.status_code == expect, r.text[:300]
        j = r.json()
        if expect == 200:
            assert j.pop('tenant_id') == tenant and j.pop('actor_id') == 'owner'
            return j
        return j['detail']
    return go


def base():
    return {
        'info': {'title': 'Pets', 'version': '1.0.0'},
        'schemas': {'Pet': {'source_ref': 'src/m.py:1', 'schema': {
            'type': 'object', 'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}},
            'required': ['id', 'name']}}},
        'operations': [{
            'operation_id': 'getPet', 'method': 'get', 'path': '/pets/{petId}', 'summary': 'Fetch a pet',
            'source_ref': 'src/r.py:5',
            'parameters': [{'name': 'petId', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}, 'example': 7}],
            'responses': {'200': {'description': 'ok', 'schema': {'$ref': '#/components/schemas/Pet'},
                                  'example': {'id': 7, 'name': 'Rex'}},
                          '404': {'description': 'missing'}}}]}


def op(i, **kw):
    return {'operation_id': 'op%d' % i, 'method': 'get', 'path': '/p%d' % i, 'summary': 's', 'source_ref': 'r',
            'responses': {'200': {'description': 'ok'}}, **kw}


EXPECTED_DOC = {
    'openapi': '3.1.0',
    'info': {'title': 'Pets', 'version': '1.0.0'},
    'paths': {'/pets/{petId}': {'get': {
        'operationId': 'getPet', 'summary': 'Fetch a pet', 'x-source-ref': 'src/r.py:5',
        'parameters': [{'name': 'petId', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}, 'example': 7}],
        'responses': {
            '200': {'description': 'ok', 'content': {'application/json': {
                'schema': {'$ref': '#/components/schemas/Pet'}, 'example': {'id': 7, 'name': 'Rex'}}}},
            '404': {'description': 'missing'}}}}},
    'components': {'schemas': {'Pet': {
        'type': 'object', 'additionalProperties': False, 'x-source-ref': 'src/m.py:1',
        'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}}, 'required': ['id', 'name']}}},
}


def test_exact_document_trace_examples_and_flags(call):
    j = call(base())
    assert j['openapi'] == EXPECTED_DOC
    assert j['source_trace'] == [{'kind': 'schema', 'name': 'Pet', 'source_ref': 'src/m.py:1'},
                                 {'kind': 'operation', 'name': 'getPet', 'source_ref': 'src/r.py:5'}]
    assert j['client_examples'] == [
        {'kind': 'parameter', 'operation_id': 'getPet', 'name': 'petId', 'example': 7, 'valid': True},
        {'kind': 'response', 'operation_id': 'getPet', 'status': '200', 'example': {'id': 7, 'name': 'Rex'}, 'valid': True}]
    assert j['implementation_verified'] is False
    assert len(j['limits']) == 4 and j['limits'][0].startswith('Documents only the supplied operation and schema')
    assert j['limits'][3] == 'No security schemes, servers, callbacks, links, non-JSON media types or generator packages.'


def test_canonical_json_and_digest_are_consistent(call):
    j = call(base())
    text = j['canonical_json']
    assert json.loads(text) == j['openapi']
    assert text == json.dumps(j['openapi'], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    assert j['sha256'] == hashlib.sha256(text.encode('utf-8')).hexdigest()
    # regression pin of the engine's digest for this exact input (engine-computed, then re-hashed above)
    assert j['sha256'] == 'ccd20452c68f061f033b0eacf2c665efa1473ad067cf68747fa59168e4455af6'
    assert call(base())['sha256'] == j['sha256']      # deterministic


def test_input_is_order_independent_and_key_order_does_not_change_output(call):
    d = base()
    flipped = json.loads(json.dumps(d))
    flipped['operations'][0]['responses'] = dict(reversed(list(flipped['operations'][0]['responses'].items())))
    assert call(flipped)['openapi']['paths'] == call(d)['openapi']['paths']
    assert list(call(flipped)['openapi']['paths']['/pets/{petId}']['get']['responses']) == ['200', '404']


def mut(path, value):
    d = copy.deepcopy(base())
    cur = d
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value
    return d


def test_exact_refusal_text(call):
    d = base()
    cases = [
        ({'operations': d['operations']}, 'info must be an object'),
        ({**d, 'x': 1}, 'unknown key in request'),
        ({**d, 'operations': []}, 'operations must be a non-empty list'),
        (mut(['operations', 0, 'method'], 'trace'), 'operation 0: method must be one of get, put, post, delete, patch'),
        ({**d, 'operations': d['operations'] * 2}, "duplicate operation_id 'getPet'"),
        (mut(['operations', 0, 'path'], 'pets'), "path must start with '/' and be at most 200 characters"),
        (mut(['operations', 0, 'path'], '/pets/{petId}/{petId}'), 'path has duplicate placeholder names'),
        (mut(['operations', 0, 'path'], '/pets/{petId}/b c'), 'path has an invalid segment'),
        (mut(['operations', 0, 'parameters'], []),
         "operation 'getPet': path template placeholders ['petId'] must match declared path parameters []"),
        (mut(['operations', 0, 'responses', '200', 'schema', '$ref'], '#/components/schemas/Nope'),
         "dangling $ref to 'Nope'"),
        (mut(['operations', 0, 'responses', '200', 'example'], {'id': 7}),
         "example operation 'getPet' response 200: missing required 'name'"),
        (mut(['operations', 0, 'responses', '200', 'example'], {'id': 7, 'name': 'R', 'x': 1}),
         "example operation 'getPet' response 200: unexpected property"),
        (mut(['operations', 0, 'responses'], {}), "operation 'getPet': responses must be a non-empty object"),
        (mut(['operations', 0, 'responses', '200x'], {'description': 'd'}), "operation 'getPet': invalid response status"),
        (mut(['operations', 0, 'request_body'], {'schema': {'type': 'string'}}),
         "operation 'getPet': get operations cannot have a request body"),
        (mut(['schemas', 'Pet', 'schema', 'type'], 'date'), "schema 'Pet': unsupported schema type"),
        (mut(['schemas', 'Pet', 'schema', 'required'], ['id', 'id']), "schema 'Pet': required has duplicate entries"),
        (mut(['schemas', 'Pet', 'schema', 'required'], ['zz']), "schema 'Pet': required property not in properties"),
    ]
    for data, message in cases:
        assert call(data, 422) == message, message


def ops(n):
    return {'info': {'title': 'T', 'version': '1'}, 'operations': [op(i) for i in range(n)]}


def test_operation_cap_64_65(call):
    assert len(call(ops(64))['openapi']['paths']) == 64
    assert call(ops(65), 422) == 'operations exceed 64'


def test_schema_cap_64_65(call):
    def with_schemas(n):
        d = ops(1)
        d['schemas'] = {'S%d' % i: {'source_ref': 'r', 'schema': {'type': 'string'}} for i in range(n)}
        return d
    assert len(call(with_schemas(64))['openapi']['components']['schemas']) == 64
    assert call(with_schemas(65), 422) == 'schemas exceed 64'


def test_parameter_cap_16_17(call):
    def with_params(n):
        d = ops(1)
        d['operations'][0]['parameters'] = [{'name': 'q%d' % i, 'in': 'query', 'schema': {'type': 'string'}} for i in range(n)]
        return d
    assert len(call(with_params(16))['openapi']['paths']['/p0']['get']['parameters']) == 16
    assert call(with_params(17), 422) == "operation 'op0': parameters exceed 16"


def test_response_cap_8_9(call):
    def with_resp(n):
        d = ops(1)
        d['operations'][0]['responses'] = {str(200 + i): {'description': 'd'} for i in range(n)}
        return d
    assert len(call(with_resp(8))['openapi']['paths']['/p0']['get']['responses']) == 8
    assert call(with_resp(9), 422) == "operation 'op0': responses exceed 8"


def test_enum_cap_32_33(call):
    def with_enum(n):
        d = ops(1)
        d['schemas'] = {'E': {'source_ref': 'r', 'schema': {'type': 'string', 'enum': ['v%d' % i for i in range(n)]}}}
        return d
    assert len(call(with_enum(32))['openapi']['components']['schemas']['E']['enum']) == 32
    assert call(with_enum(33), 422) == "schema 'E': enum exceeds 32 values"


def test_property_cap_64_65(call):
    def with_props(n):
        d = ops(1)
        d['schemas'] = {'O': {'source_ref': 'r', 'schema': {
            'type': 'object', 'properties': {'p%d' % i: {'type': 'string'} for i in range(n)}}}}
        return d
    assert len(call(with_props(64))['openapi']['components']['schemas']['O']['properties']) == 64
    assert call(with_props(65), 422) == "schema 'O': properties exceed 64"


def test_schema_nesting_depth_8_9_arrays(call):
    def nested(levels):
        s = {'type': 'string'}
        for _ in range(levels):
            s = {'type': 'array', 'items': s}
        d = ops(1)
        d['schemas'] = {'N': {'source_ref': 'r', 'schema': s}}
        return d
    call(nested(8))
    assert call(nested(9), 422) == "schema 'N'" + '.items' * 8 + ': schema depth bound 8 exceeded'


def test_path_length_200_201(call):
    def with_path(n):
        d = ops(1)
        d['operations'][0]['path'] = '/' + 'a' * (n - 1)
        return d
    assert call(with_path(200))['openapi']['paths']
    assert call(with_path(201), 422) == "path must start with '/' and be at most 200 characters"


def test_text_length_500_501(call):
    def with_summary(n):
        d = ops(1)
        d['operations'][0]['summary'] = 'a' * n
        return d
    assert call(with_summary(500))['openapi']['paths']['/p0']['get']['summary'] == 'a' * 500
    assert 'exceeds 500 characters' in call(with_summary(501), 422)


def test_input_size_bound(call):
    d = ops(1)
    d['operations'][0]['summary'] = 'a'
    d['info']['title'] = 'T'
    d['x'] = 'a' * 270000
    assert call(d, 422) == 'input size bound exceeded (262144 bytes)'
