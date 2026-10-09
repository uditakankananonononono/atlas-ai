"""Transport/protocol protection tests, not real-model acceptance evidence."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from instinct_models.providers import ChatResult, Provider, ProviderError
from app.modules.m21_claire.runtime.engine import Engine, ModelUnavailable
from app.modules.m21_claire.runtime.model_adapter import InvalidModelOutput, LocalSharedModel, parse_decision
from app.modules.m21_claire.runtime.tools import ReadOnlyToolRegistry


class Response(Provider):
    def __init__(self, text='{"final":"done"}', error=None):
        self.text, self.error = text, error
        self.messages = None
    def available(self): return True
    def chat(self, messages, *, tools=None, max_tokens=1024):
        self.messages = messages
        if self.error: raise self.error
        return ChatResult("test", "transport-only", self.text, [], {})


def run(coro): return asyncio.run(coro)


@pytest.mark.parametrize("text", [
    'null', '[]', 'true', '{"final":"done","final":"other"}',
    '{"final":"done","extra":1}', '{"final":"done","tool_call":{"name":"x"}}',
    '{"tool_call":{"name":"x","arguments":{},"extra":1}}',
    '{"replan":{"reason":"x","steps":["y"],"extra":1}}',
    '{"tool_call":{"name":"x","arguments":{"n":NaN}}}',
    '{"final":1}', '{"final":"x"} trailing', '```json\n{"final":"x"}\n```',
    '['*33 + '0' + ']'*33, 'x'*65537, '\ud800',
])
def test_invalid_json_shape_is_refused(text):
    with pytest.raises(InvalidModelOutput): parse_decision(text)


@pytest.mark.parametrize("text", [
    '{"final":"brackets [\\\" ] are text"}',
    '{"tool_call":{"name":"lookup","arguments":{"key":"k"}}}',
    '{"replan":{"reason":"retry","steps":["lookup"]}}',
])
def test_each_supported_decision(text):
    assert parse_decision(text)


def test_declared_provider_failure_blocks_without_diagnostics():
    rep = run(Engine(LocalSharedModel(Response(error=ProviderError("https://secret/?token=x"))),
                     ReadOnlyToolRegistry()).run("lookup"))
    assert rep.stop_reason == "model_unavailable"
    assert "secret" not in rep.model_dump_json()


def test_invalid_provider_decision_blocks_without_raw_text():
    rep = run(Engine(LocalSharedModel(Response('https://secret/?token=x')),
                     ReadOnlyToolRegistry()).run("lookup"))
    assert rep.stop_reason == "model_invalid_output"
    assert "secret" not in rep.model_dump_json()


def test_programming_bug_stays_loud():
    with pytest.raises(TypeError):
        run(LocalSharedModel(Response(error=TypeError("bug"))).decide([]))


def test_hosted_and_non_loopback_rejected():
    p = Response(); p.locality = "hosted"
    with pytest.raises(ValueError): LocalSharedModel(p)
    for url in ("https://example.com", "http://10.0.0.1:8000/v1", "http://user:pass@localhost:8000/v1"):
        with pytest.raises(ProviderError): LocalSharedModel.select("ornith", url, "model")


def test_missing_provider():
    p = Response(); p.available = lambda: False
    with pytest.raises(ModelUnavailable): run(LocalSharedModel(p).decide([]))


def test_native_calls_do_not_change_json_protocol():
    p = Response()
    p.chat = lambda *a, **kw: ChatResult("test", "m", "", [{"name":"x"}], {})
    with pytest.raises(InvalidModelOutput): run(LocalSharedModel(p).decide([]))


def test_actual_http_transport_selected_model_and_message_protocol():
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            body = json.dumps({"choices":[{"message":{"content":'{"final":"transport checked"}'}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    try:
        m = LocalSharedModel.select("hermes", f"http://127.0.0.1:{server.server_port}/v1", "selected-test-model")
        assert run(m.decide([{"role":"user","content":"transport only"}])).final == "transport checked"
        assert requests == [("/v1/chat/completions", {"model":"selected-test-model", "messages":[{"role":"user","content":"transport only"}], "max_tokens":1024})]
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_cancellation_and_snapshot_thread_limit():
    entered, release = threading.Event(), threading.Event()
    p = Response()
    original_chat = p.chat
    def slow(messages, **kw):
        entered.set(); release.wait(3)
        return original_chat(messages, **kw)
    p.chat = slow
    async def check():
        messages = [{"role":"user","content":"original"}]
        task = asyncio.create_task(LocalSharedModel(p).decide(messages))
        while not entered.is_set(): await asyncio.sleep(.01)
        messages[0]["content"] = "changed"
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        release.set()
    try: run(check())
    finally: release.set()
    assert p.messages == [{"role":"user","content":"original"}]


def test_mounted_goal_with_adapter_persists_protocol_blocker(tmp_path, monkeypatch):
    # Synthetic provider deliberately returns a bad decision. This verifies the
    # mounted worker path's honesty, not model intelligence or live OIDC.
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m21_claire.runtime import routes
    from app.modules.m21_claire.runtime.goals import GoalStore
    from app.modules.m21_claire.runtime.worker import Worker
    store = GoalStore(f"sqlite:///{tmp_path}/g.db", create_schema=True)
    monkeypatch.setattr(routes, "_store", store)
    app.dependency_overrides[require_tenant] = lambda: TenantContext("t", "a")
    try:
        with TestClient(app) as client:
            url = "/api/v1/claire/runtime/goals"
            response = client.post(url, json={"purpose":"lookup k", "acceptance_criteria":[{"kind":"tool_receipt", "tool":"lookup", "min_count":1}]})
            assert response.status_code == 201
            gid = response.json()["id"]
            run(Worker(store, lambda claim: Engine(LocalSharedModel(Response('bad JSON')), ReadOnlyToolRegistry()), "w").run_once())
            body = client.get(f"{url}/{gid}").json()
            assert body["status"] == "blocked"
            assert body["blocker"] == "model_invalid_output"
            assert body["report"]["receipts"] == []
    finally:
        app.dependency_overrides.pop(require_tenant, None)
        store.close()
