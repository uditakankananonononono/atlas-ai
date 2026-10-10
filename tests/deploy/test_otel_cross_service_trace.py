"""Hermetic checks for ATLAS-U-1211, the free local OpenTelemetry substitute for X03.

AUTHORED, NOT RUN. Hermetic tests use in-memory span exporters, fake broker callables and
an in-process FastAPI TestClient only: no network, no containers. The last test needs a
running local stack and is skipped unless ATLAS_OTEL_LIVE_JAEGER_URL is set; a skip is not a pass.
"""
import ast
import asyncio
import json
import os
import re
import urllib.request
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.platform import telemetry_bootstrap as tb

ROOT = Path(__file__).resolve().parents[2]
BOOT_PATH = ROOT / 'backend/app/platform/telemetry_bootstrap.py'
OVERRIDE_PATH = ROOT / 'deploy/local/docker-compose.otel.yml'
COLLECTOR_PATH = ROOT / 'deploy/otel/jaeger-local.yaml'
BASE_PATH = ROOT / 'deploy/local/docker-compose.yml'

# Digests read from the public Docker Hub registry (Docker-Content-Digest header) on 2026-10-10 IST.
PINNED = {
    'jaeger': 'jaegertracing/all-in-one:1.62.0@sha256:836e9b69c88afbedf7683ea7162e179de63b1f981662e83f5ebb68badadc710f',
    'otel-collector': 'otel/opentelemetry-collector-contrib:0.111.0@sha256:a2a52e43c1a80aa94120ad78c2db68780eb90e6d11c8db5b3ce2f6a0cc6b5029',
}


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader that accepts Compose merge tags; records which sequences used them."""


def _tagged(loader, node):
    return {'__tag__': node.tag, 'value': loader.construct_sequence(node)}


ComposeLoader.add_constructor('!override', _tagged)
ComposeLoader.add_constructor('!reset', _tagged)


def load(path):
    return yaml.load(path.read_text(), Loader=ComposeLoader)


def env_of(svc):
    env = svc['environment']
    return env if isinstance(env, dict) else dict(e.split('=', 1) for e in env)


def port_list(raw):
    """(values, replaced) where replaced is True when the list used !override."""
    if isinstance(raw, dict) and raw.get('__tag__') == '!override':
        return raw['value'], True
    return list(raw), False


def provider(service):
    exp = InMemorySpanExporter()
    prov = tb.build_provider(service, SimpleSpanProcessor(exp))
    return prov, exp


# ---- module docstring and startup scoping ---------------------------------

def test_module_docstring_carries_all_three_named_gaps_verbatim():
    doc = ast.get_docstring(ast.parse(BOOT_PATH.read_text()))
    assert 'Production-scale trace pipeline and retention' in doc
    assert ('Instrumentation coverage: the bootstrap covers app + worker startup paths ONLY; '
            'NO claim of full auto-instrumentation coverage of every service/library.') in doc
    assert ('Image freshness beyond author time: digests are pinned and verified via read-only '
            'public registry fetches at author time; they are not a rolling latest.') in doc


def test_docstring_and_compose_header_state_binding_and_auth():
    doc = ast.get_docstring(ast.parse(BOOT_PATH.read_text()))
    for needle in ('127.0.0.1', 'require_tenant', 'no unauthenticated path', 'ATLAS_OTEL_PROBE=1'):
        assert needle.lower() in doc.lower(), needle
    header = '\n'.join(l for l in OVERRIDE_PATH.read_text().splitlines() if l.startswith('#'))
    for needle in ('127.0.0.1', '!override', 'same Atlas auth dependency', 'no unauthenticated probe'):
        assert needle.lower() in header.lower(), needle


def test_bootstrap_is_additive_and_does_nothing_at_import_time():
    tree = ast.parse(BOOT_PATH.read_text())
    heavy = {'app', 'celery', 'uvicorn', 'fastapi', 'opentelemetry.sdk', 'opentelemetry.exporter'}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
            assert not any(mod == h or mod.startswith(h + '.') for h in heavy), mod
        else:
            assert isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign, ast.Expr, ast.If)), ast.dump(node)[:80]
            if isinstance(node, ast.If):
                assert 'main' in ast.unparse(node.test)
            if isinstance(node, ast.Expr):
                assert isinstance(node.value, ast.Constant)  # docstring only, no top-level calls


def test_api_startup_attaches_the_real_atlas_auth_dependency_to_the_probe():
    tree = ast.parse(BOOT_PATH.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_start_api')
    imports = [n for n in ast.walk(fn) if isinstance(n, ast.ImportFrom)]
    assert any(n.module == 'app.auth.context' and any(a.name == 'require_tenant' for a in n.names) for n in imports)
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'register_probe_route']
    assert len(calls) == 1
    kw = {k.arg: k.value for k in calls[0].keywords}
    assert isinstance(kw['auth_dependency'], ast.Name) and kw['auth_dependency'].id == 'require_tenant'
    # the probe is only registered under the opt-in gate
    gate = [n for n in ast.walk(fn) if isinstance(n, ast.If) and 'probe_enabled' in ast.unparse(n.test)]
    assert gate and any(c in ast.walk(gate[0]) for c in calls)


# ---- settings --------------------------------------------------------------

def test_settings_defaults_and_refusals():
    s = tb.load_settings('api', {'ATLAS_OTEL_COLLECTOR_ENDPOINT': 'otel-collector:4317'})
    assert (s.service_name, s.endpoint, s.probe_enabled) == ('atlas-api', 'otel-collector:4317', False)
    w = tb.load_settings('worker', {'ATLAS_OTEL_COLLECTOR_ENDPOINT': 'otel-collector:4317', 'ATLAS_OTEL_PROBE': '1'})
    assert (w.service_name, w.probe_enabled) == ('atlas-worker', True)
    for bad_env in ({}, {'ATLAS_OTEL_COLLECTOR_ENDPOINT': ''},
                    {'ATLAS_OTEL_COLLECTOR_ENDPOINT': 'http://otel-collector:4317'},
                    {'ATLAS_OTEL_COLLECTOR_ENDPOINT': 'otel-collector'},
                    {'ATLAS_OTEL_COLLECTOR_ENDPOINT': 'a b:4317'}):
        with pytest.raises(ValueError):
            tb.load_settings('api', bad_env)
    with pytest.raises(ValueError):
        tb.load_settings('beat', {'ATLAS_OTEL_COLLECTOR_ENDPOINT': 'otel-collector:4317'})


# ---- real propagation across two providers ----------------------------------

def test_one_trace_spans_api_and_worker_services_with_correct_parenting():
    api_prov, api_exp = provider('atlas-api')
    wrk_prov, wrk_exp = provider('atlas-worker')
    sent = []
    with api_prov.get_tracer('t').start_as_current_span('GET /x'):
        tb.publish_probe(api_prov.get_tracer('t'), lambda name, kwargs: sent.append((name, kwargs)))
    assert sent[0][0] == tb.PROBE_TASK_NAME
    result = tb.run_probe_task(wrk_prov.get_tracer('t'), sent[0][1]['carrier'])
    api_spans, wrk_spans = api_exp.get_finished_spans(), wrk_exp.get_finished_spans()
    publish = next(s for s in api_spans if s.name == 'atlas.otel.probe.publish')
    run = wrk_spans[0]
    assert {s.context.trace_id for s in list(api_spans) + list(wrk_spans)} == {publish.context.trace_id}
    assert run.parent.span_id == publish.context.span_id
    assert api_spans[0].resource.attributes['service.name'] == 'atlas-api'
    assert run.resource.attributes['service.name'] == 'atlas-worker'
    assert result['trace_id'] == format(publish.context.trace_id, '032x')


def test_worker_without_carrier_starts_a_different_trace():
    api_prov, api_exp = provider('atlas-api')
    wrk_prov, wrk_exp = provider('atlas-worker')
    sent = []
    tb.publish_probe(api_prov.get_tracer('t'), lambda name, kwargs: sent.append(kwargs))
    for carrier in (None, {}, {'traceparent': 'garbage'}, {'traceparent': 123}):
        tb.run_probe_task(wrk_prov.get_tracer('t'), carrier)
    publish_trace = api_exp.get_finished_spans()[0].context.trace_id
    for s in wrk_exp.get_finished_spans():
        assert s.context.trace_id != publish_trace and s.parent is None


# ---- ASGI middleware ----------------------------------------------------------

async def drive(app, path, headers=()):
    scope = {'type': 'http', 'method': 'GET', 'path': path, 'query_string': b'', 'scheme': 'http',
             'headers': [(k.lower().encode(), v.encode()) for k, v in headers]}
    out = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(msg):
        out.append(msg)
    await app(scope, receive, send)
    return out


def make_inner(calls):
    async def inner(scope, receive, send):
        calls.append(scope['path'])
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    return inner


def test_middleware_wraps_requests_in_a_server_span_continuing_incoming_traceparent():
    prov, exp = provider('atlas-api')
    calls = []
    app = tb.TraceMiddleware(make_inner(calls), tracer=prov.get_tracer('t'))
    tp = '00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01'
    out = asyncio.run(drive(app, '/api/v1/things', [('traceparent', tp)]))
    assert calls == ['/api/v1/things'] and out[0]['status'] == 204
    span = exp.get_finished_spans()[0]
    assert span.name == 'GET /api/v1/things'
    assert format(span.context.trace_id, '032x') == '0af7651916cd43dd8448eb211c80319c'
    assert format(span.parent.span_id, '016x') == 'b7ad6b7169203331'
    assert span.attributes['http.response.status_code'] == 204


def test_middleware_never_answers_the_probe_path_itself():
    prov, exp = provider('atlas-api')
    calls = []
    app = tb.TraceMiddleware(make_inner(calls), tracer=prov.get_tracer('t'))
    out = asyncio.run(drive(app, tb.PROBE_PATH))
    assert calls == [tb.PROBE_PATH] and out[0]['status'] == 204  # reached the inner app, which owns auth


def test_middleware_passes_non_http_scopes_through_untouched():
    prov, exp = provider('atlas-api')
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope['type'])
    app = tb.TraceMiddleware(inner, tracer=prov.get_tracer('t'))

    async def go():
        await app({'type': 'lifespan'}, None, None)
    asyncio.run(go())
    assert seen == ['lifespan'] and exp.get_finished_spans() == ()


# ---- probe route: auth negative and positive ---------------------------------

def make_app(*, register=True):
    prov, exp = provider('atlas-api')
    sent = []
    app = FastAPI()

    def fake_auth(x_test_auth: str | None = Header(default=None)):
        if x_test_auth != 'ok':
            raise HTTPException(status_code=401, detail='unauthenticated')

    if register:
        tb.register_probe_route(app, tracer=prov.get_tracer('t'), auth_dependency=fake_auth,
                                send_task=lambda name, kwargs: sent.append((name, kwargs)))
    app.add_middleware(tb.TraceMiddleware, tracer=prov.get_tracer('t'))
    return app, sent, exp


def test_probe_without_credentials_is_refused_and_enqueues_nothing():
    app, sent, exp = make_app()
    client = TestClient(app)
    assert client.get(tb.PROBE_PATH).status_code == 401
    assert client.get(tb.PROBE_PATH, headers={'x-test-auth': 'nope'}).status_code == 401
    assert sent == []
    assert not any(s.name == 'atlas.otel.probe.publish' for s in exp.get_finished_spans())


def test_probe_with_credentials_enqueues_once_and_returns_the_trace_id():
    app, sent, exp = make_app()
    r = TestClient(app).get(tb.PROBE_PATH, headers={'x-test-auth': 'ok'})
    assert r.status_code == 200 and len(sent) == 1 and sent[0][0] == tb.PROBE_TASK_NAME
    assert r.json()['trace_id'] in sent[0][1]['carrier']['traceparent']
    spans = {s.name: s for s in exp.get_finished_spans()}
    server, publish = spans['GET ' + tb.PROBE_PATH], spans['atlas.otel.probe.publish']
    assert publish.context.trace_id == server.context.trace_id
    assert publish.parent.span_id == server.context.span_id


def test_probe_route_does_not_exist_unless_registered():
    app, sent, _ = make_app(register=False)
    assert TestClient(app).get(tb.PROBE_PATH, headers={'x-test-auth': 'ok'}).status_code == 404
    assert sent == []


# ---- override file ----------------------------------------------------------------

def test_override_defines_new_services_and_only_command_env_deps_ports_on_existing_ones():
    base = load(BASE_PATH)['services']
    over = load(OVERRIDE_PATH)
    assert set(over) <= {'services'}
    svcs = over['services']
    assert set(svcs) == {'jaeger', 'otel-collector', 'api', 'worker'}
    for name in ('api', 'worker'):
        assert name in base and set(svcs[name]) <= {'command', 'environment', 'depends_on', 'ports'}
    assert not ({'jaeger', 'otel-collector'} & set(base))


def test_every_published_port_is_loopback_and_base_mappings_are_replaced_not_appended():
    base, svcs = load(BASE_PATH)['services'], load(OVERRIDE_PATH)['services']
    for name, svc in svcs.items():
        ports, replaced = port_list(svc.get('ports', []))
        assert all(str(p).startswith('127.0.0.1:') for p in ports), (name, ports)
        if name in base and base[name].get('ports'):
            # Compose appends port lists unless !override is used, which would keep the base public mapping.
            assert replaced, name
            assert ports, name
    assert 'api' in svcs and port_list(svcs['api']['ports'])[0] == ['127.0.0.1:8000:8080']
    assert svcs['api']['ports']['value'] == ['127.0.0.1:8000:8080']
    assert 'ports' not in svcs['otel-collector']  # collector is reachable on the compose network only


def test_api_and_worker_commands_run_the_bootstrap_with_their_mode():
    svcs = load(OVERRIDE_PATH)['services']
    assert svcs['api']['command'] == ['python', '-m', 'app.platform.telemetry_bootstrap', 'api']
    assert svcs['worker']['command'] == ['python', '-m', 'app.platform.telemetry_bootstrap', 'worker']


def test_instrumentation_env_matches_collector_receiver_and_avoids_legacy_exporter():
    cfg = load(COLLECTOR_PATH)
    port = cfg['receivers']['otlp']['protocols']['grpc']['endpoint'].rsplit(':', 1)[1]
    svcs = load(OVERRIDE_PATH)['services']
    for name in ('api', 'worker'):
        env = env_of(svcs[name])
        assert env['ATLAS_OTEL_COLLECTOR_ENDPOINT'] == f'otel-collector:{port}'
        assert 'OTEL_EXPORTER_OTLP_ENDPOINT' not in env  # telemetry.py would use insecure=False
        assert 'otel-collector' in svcs[name]['depends_on']
    assert str(env_of(svcs['api'])['ATLAS_OTEL_PROBE']) == '1'
    assert 'ATLAS_OTEL_PROBE' not in env_of(svcs['worker'])


def test_override_secrets_are_not_inlined():
    text = OVERRIDE_PATH.read_text()
    for needle in ('PASSWORD', 'TOKEN_KEY', 'ENCRYPTION_KEY', 'googlecloud', 'GOOGLE_APPLICATION_CREDENTIALS'):
        assert needle not in text


def test_new_images_carry_the_exact_verified_digests():
    svcs = load(OVERRIDE_PATH)['services']
    for name, ref in PINNED.items():
        assert svcs[name]['image'] == ref
        assert re.fullmatch(r'[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}', svcs[name]['image'])
        assert 'build' not in svcs[name]


def test_collector_mounts_the_in_repo_config_and_the_file_exists():
    svc = load(OVERRIDE_PATH)['services']['otel-collector']
    src, dst = svc['volumes'][0].split(':')[:2]
    assert (BASE_PATH.parent / src).resolve() == COLLECTOR_PATH.resolve() and COLLECTOR_PATH.is_file()
    assert f'--config={dst}' in svc['command']


def test_jaeger_enables_otlp():
    j = load(OVERRIDE_PATH)['services']['jaeger']
    assert str(env_of(j)['COLLECTOR_OTLP_ENABLED']).lower() == 'true'
    assert any(str(p).endswith(':16686') for p in j['ports'])


def test_collector_config_is_local_traces_only_and_exports_to_jaeger_plaintext():
    cfg = load(COLLECTOR_PATH)
    assert 'googlecloud' not in json.dumps(cfg)
    assert set(cfg['receivers']['otlp']['protocols']) == {'grpc', 'http'}
    pipes = cfg['service']['pipelines']
    assert set(pipes) == {'traces'}
    assert pipes['traces']['receivers'] == ['otlp']
    assert all(e in cfg['exporters'] for e in pipes['traces']['exporters'])
    assert all(p in cfg['processors'] for p in pipes['traces']['processors'])
    exp = cfg['exporters']['otlp/jaeger']
    assert exp['endpoint'] == 'jaeger:4317' and exp['tls']['insecure'] is True


# ---- live acceptance (NOT hermetic; skipped by default) -------------------------------

@pytest.mark.skipif(not os.getenv('ATLAS_OTEL_LIVE_JAEGER_URL'),
                    reason='needs the local compose stack up and an authenticated GET /_otel/probe issued on the api')
def test_live_jaeger_has_one_trace_with_atlas_api_and_atlas_worker():
    base = os.environ['ATLAS_OTEL_LIVE_JAEGER_URL'].rstrip('/')
    assert base.startswith(('http://127.0.0.1', 'http://localhost'))
    with urllib.request.urlopen(f'{base}/api/traces?service=atlas-api&limit=20', timeout=10) as r:
        payload = json.load(r)
    found = []
    for trace in payload['data']:
        names = {trace['processes'][s['processID']]['serviceName'] for s in trace['spans']}
        if {'atlas-api', 'atlas-worker'} <= names:
            found.append(trace['traceID'])
    assert found, 'no single trace contained spans from both atlas-api and atlas-worker'


# ---- R4 pins: contiguous auth literal and the three named gaps in the compose header ----

NO_UNAUTH_LITERAL = 'no unauthenticated path'
THREE_GAPS = (
    'Production-scale trace pipeline and retention',
    'Instrumentation coverage: the bootstrap covers app + worker startup paths ONLY; '
    'NO claim of full auto-instrumentation coverage of every service/library.',
    'Image freshness beyond author time: digests are pinned and verified via read-only '
    'public registry fetches at author time; they are not a rolling latest.',
)


def test_literal_no_unauthenticated_path_is_contiguous_on_one_line_in_docstring_and_header():
    doc = ast.get_docstring(ast.parse(BOOT_PATH.read_text()))
    assert any(NO_UNAUTH_LITERAL in line for line in doc.splitlines()), 'docstring wraps or lacks the literal'
    header_lines = [l for l in OVERRIDE_PATH.read_text().splitlines() if l.startswith('#')]
    assert any(NO_UNAUTH_LITERAL in line for line in header_lines), 'header wraps or lacks the literal'


def test_compose_header_carries_each_of_the_three_named_gaps_on_a_single_line():
    header_lines = [l for l in OVERRIDE_PATH.read_text().splitlines() if l.startswith('#')]
    for gap in THREE_GAPS:
        assert any(gap in line for line in header_lines), gap
