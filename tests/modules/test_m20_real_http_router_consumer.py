"""A15 loopback provider fixtures: real HTTP, not live model acceptance."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
import pytest
from sqlalchemy import create_engine
from app.core import model_catalog as catalog, providers
from app.platform.reliability import CircuitBreaker
from app.modules.m20_general_cognitive_worker.model_adapters import FreeFirstPlannerModel
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import TaskState

PLAN = '[{"id":"one","title":"Inspect fixture evidence","risk":"read"}]'


@contextmanager
def fixture_server(outcome='ok'):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append({'path': self.path, 'body': body})
            if outcome == '503':
                status, response = 503, b'{"error":"fixture"}'
            elif outcome == 'json':
                status, response = 200, b'not-json'
            else:
                status = 200
                envelope = ({'message': {'content': PLAN}} if self.path == '/api/chat' else
                            {'choices': [{'message': {'content': PLAN}}]})
                response = json.dumps(envelope).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', seen
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def bind_loopback(monkeypatch, base):
    monkeypatch.setenv('ATLAS_OLLAMA_URL', base)
    monkeypatch.setenv('ATLAS_LOCAL_OPENAI_URL', base + '/v1')
    monkeypatch.delenv('ATLAS_LOCAL_OPENAI_KEY', raising=False)
    monkeypatch.setenv('ATLAS_ALLOW_PAID', 'true')  # private skip must still win
    for key in ('ollama', 'openai_compat'):
        monkeypatch.setitem(providers._BREAKERS, key, CircuitBreaker())
    monkeypatch.setitem(catalog.CATALOG, 'a15-fixture', catalog.CatalogEntry(
        'A15 fixture', 'Loopback protocol fixture, no real model', False,
        routes=(catalog.Route('ollama', 'hosted-free-canary', catalog.HOSTED_FREE),
                catalog.Route('openai_compat', 'hosted-paid-canary', catalog.HOSTED_PAID),
                catalog.Route('ollama', 'fixture-ollama', catalog.LOCAL),
                catalog.Route('openai_compat', 'fixture-compatible', catalog.SELF_HOSTED))))


def open_runtime(path):
    engine = create_engine(f'sqlite:///{path}')
    repo = GCWRepository(engine, tenant_id='a15-fixture')
    repo.create_schema()
    model = FreeFirstPlannerModel(model_name='a15-fixture')
    return engine, repo, model, GCWRuntime(repo, planner_model=model, require_method_review=True)


@pytest.mark.parametrize('route', ['ollama', 'openai_compat'])
def test_actual_http_private_runtime_plan_routes_and_reopens(tmp_path, monkeypatch, route):
    with fixture_server() as (base, seen):
        bind_loopback(monkeypatch, base)
        if route == 'openai_compat':
            breaker = CircuitBreaker()
            breaker.opened_at = breaker.clock()
            monkeypatch.setitem(providers._BREAKERS, 'ollama', breaker)
        path = tmp_path / 'plan.sqlite'
        engine, repo, model, runtime = open_runtime(path)
        context = runtime.submit_goal('private fixture novel goal', run_immediately=False)
        assert len(seen) == 1
        request = seen[0]
        assert request['path'] == ('/api/chat' if route == 'ollama' else '/v1/chat/completions')
        assert request['body']['model'] == ('fixture-ollama' if route == 'ollama' else 'fixture-compatible')
        assert 'private fixture novel goal' in request['body']['messages'][0]['content']
        if route == 'ollama':
            assert request['body']['stream'] is False
        assert model.last_route == (route, request['body']['model'])
        assert context.plan[0].title == 'Inspect fixture evidence'
        assert len(repo.list_methods()) == 1 and repo.list_methods()[0][1] == 'proposed'
        assert repo.list_actions(task_id=context.id) == []
        engine.dispose()
        fresh_engine, fresh_repo, _, fresh = open_runtime(path)
        assert fresh_repo.load_task(context.id).plan[0].title == 'Inspect fixture evidence'
        name = fresh_repo.list_methods()[0][0].name
        assert fresh.planner.method_status(name) == 'proposed'
        assert fresh.planner._match_method(context.goal) is None
        assert len(seen) == 1
        fresh_engine.dispose()


@pytest.mark.parametrize('outcome', ['503', 'json'])
def test_actual_http_unknown_holds_no_backup_or_restart_call(tmp_path, monkeypatch, outcome):
    with fixture_server(outcome) as (base, seen):
        bind_loopback(monkeypatch, base)
        path = tmp_path / 'unknown.sqlite'
        engine, repo, _, runtime = open_runtime(path)
        context = runtime.submit_goal('unknown private fixture goal', run_immediately=False)
        assert context.state == TaskState.BLOCKED and context.model_outcome_unknown
        assert repo.load_task(context.id).model_outcome_unknown
        assert repo.list_methods() == [] and repo.list_actions(task_id=context.id) == []
        assert len(seen) == 1 and seen[0]['path'] == '/api/chat'
        assert seen[0]['body']['model'] == 'fixture-ollama'
        engine.dispose()
        fresh_engine, _, _, fresh = open_runtime(path)
        assert fresh.run_task(context.id).model_outcome_unknown
        assert len(seen) == 1
        fresh_engine.dispose()
