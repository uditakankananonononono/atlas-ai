import json
import pytest
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from starlette.routing import Mount, WebSocketRoute
from app.modules.m20_general_cognitive_worker.mounted_openapi704 import mounted_documentation


class Input(BaseModel):
    name: str


def test_actual_prefixes_parameters_schemas_no_handler_execution():
    app = FastAPI(title='Fixture', version='1')
    router = APIRouter(prefix='/nested')
    calls = []
    @router.post('/items/{id}', response_model=Input)
    def handler(id: int, body: Input, page: int = 1):
        calls.append('executed')
        return body
    app.include_router(router, prefix='/api/v1')
    result = mounted_documentation(app)
    op = result['openapi']['paths']['/api/v1/nested/items/{id}']['post']
    assert op['requestBody']['content']['application/json']['schema']['$ref'].endswith('/Input')
    assert {p['name'] for p in op['parameters']} == {'id', 'page'}
    assert result['documented_http_operation_count'] == 1
    assert calls == [] and result['endpoint_handlers_executed'] is False
    assert result['security_enforcement_verified'] is False
    assert result['response_behavior_verified'] is False
    assert json.loads(result['canonical_json']) == result['openapi']


def test_ignores_stale_cache_and_reports_hidden_mounts():
    app = FastAPI()
    app.openapi()  # Cache before adding routes.
    @app.get('/late')
    def late():
        return 'late'
    @app.get('/hidden', include_in_schema=False)
    def hidden():
        return 'hidden'
    app.mount('/child', FastAPI())
    async def ws(websocket):
        pass
    app.routes.append(WebSocketRoute('/socket', ws))
    result = mounted_documentation(app)
    assert '/late' in result['openapi']['paths']
    assert '/hidden' not in result['openapi']['paths']
    assert any(r['path'] == '/hidden' for r in result['undocumented_route_entries'])
    assert {r['kind'] for r in result['unsupported_routes']} == {'mount', 'websocket'}


def test_duplicate_route_or_operation_id_refused():
    app = FastAPI()
    app.add_api_route('/same', lambda: None, methods=['GET'])
    app.add_api_route('/same', lambda: None, methods=['GET'])
    with pytest.raises(ValueError, match='duplicate mounted method/path'):
        mounted_documentation(app)
    app = FastAPI()
    app.add_api_route('/one', lambda: None, methods=['GET'], operation_id='same')
    app.add_api_route('/two', lambda: None, methods=['GET'], operation_id='same')
    with pytest.raises(ValueError, match='duplicate mounted operation IDs'):
        mounted_documentation(app)


def test_routes_auth_and_real_mount_export(monkeypatch):
    from fastapi.testclient import TestClient
    from app.auth.context import require_tenant, TenantContext
    from app.modules.m20_general_cognitive_worker.openapi704_routes import router
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/m20')
    client = TestClient(app)
    prefix = '/api/v1/m20/api-documentation'
    assert client.get(prefix + '/mounted').status_code == 401
    assert client.get(prefix + '/mounted/download').status_code == 401
    # The generation assertions below deliberately override auth, not the 401 evidence.
    app.dependency_overrides[require_tenant] = lambda: TenantContext('t', 'a')
    response = client.get(prefix + '/mounted')
    assert response.status_code == 200
    result = response.json()
    assert prefix + '/mounted/download' in result['openapi']['paths']
    download = client.get(prefix + '/mounted/download')
    assert download.status_code == 200
    assert download.json() == result['openapi']
    assert download.headers['etag'] == '"' + result['sha256'] + '"'
    assert download.headers['cache-control'] == 'private, no-store'
