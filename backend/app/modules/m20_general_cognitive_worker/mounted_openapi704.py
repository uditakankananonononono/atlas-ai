"""Document actual mounted FastAPI HTTP routes without executing their handlers.

A fresh runtime schema, not caller descriptions or a stale OpenAPI cache. Hidden
routes, websockets and mounts are listed, not silently called documented. Declared
schemas are not evidence of response correctness or authentication enforcement.
"""
from __future__ import annotations
import hashlib
import json
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi import routing
from starlette.routing import Mount, WebSocketRoute

HTTP_METHODS = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'}


def mounted_documentation(app):
    operations = []
    hidden = []
    unsupported = []
    seen = set()
    contexts = routing.iter_route_contexts(app.routes) if hasattr(routing, 'iter_route_contexts') else app.routes
    for route in contexts:
        original = getattr(route, 'original_route', route)
        if isinstance(original, APIRoute):
            for method in sorted(route.methods or []):
                if route.include_in_schema:
                    key = (route.path_format, method.lower())
                    if key in seen:
                        raise ValueError('duplicate mounted method/path; ambiguous runtime documentation')
                    seen.add(key)
                    operations.append({'path': route.path_format, 'method': method.lower(),
                                       'route_name': route.name,
                                       'endpoint_module': route.endpoint.__module__,
                                       'endpoint_name': route.endpoint.__qualname__})
                else:
                    hidden.append({'path': route.path_format, 'method': method.lower(),
                                   'reason': 'include_in_schema_false'})
        elif isinstance(original, Mount):
            unsupported.append({'path': route.path, 'kind': 'mount',
                                'reason': 'subapplication_schema_not_merged'})
        elif isinstance(original, WebSocketRoute):
            unsupported.append({'path': route.path, 'kind': 'websocket',
                                'reason': 'not_an_openapi_http_operation'})
        else:
            hidden.append({'path': getattr(route, 'path', None), 'method': None,
                           'reason': 'non_fastapi_route_not_in_generated_schema'})
    # Do not use app.openapi(): its cached document can predate late mounts.
    document = get_openapi(title=app.title, version=app.version, openapi_version=app.openapi_version,
                          description=app.description, routes=app.routes, servers=app.servers,
                          tags=app.openapi_tags, separate_input_output_schemas=app.separate_input_output_schemas)
    emitted = {(path, method) for path, entry in document.get('paths', {}).items()
               for method in entry if method in HTTP_METHODS}
    if emitted != seen:
        raise ValueError('mounted/schema operation mismatch')
    ids = [entry.get('operationId') for item in document.get('paths', {}).values()
           for method, entry in item.items() if method in HTTP_METHODS]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate mounted operation IDs')
    canonical = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(canonical.encode()) > 16_000_000:
        raise ValueError('runtime schema exceeds export size limit')
    return {'openapi': document, 'canonical_json': canonical,
            'sha256': hashlib.sha256(canonical.encode()).hexdigest(),
            'documented_http_operation_count': len(operations),
            'source_trace': sorted(operations, key=lambda x: (x['path'], x['method'])),
            'undocumented_route_entries': hidden, 'unsupported_routes': unsupported,
            'route_table_inspected': True, 'endpoint_handlers_executed': False,
            'security_enforcement_verified': False, 'response_behavior_verified': False,
            'deployment_verified': False, 'external_effects': [],
            'boundary': 'Fresh documentation of mounted FastAPI declarations only. '
                        'No traffic execution, response correctness, security enforcement, '
                        'deployment or subapplication coverage is claimed.'}
