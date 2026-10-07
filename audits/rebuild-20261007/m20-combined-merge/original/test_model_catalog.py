"""Free-first open-model routing: real provider code paths with the HTTP boundary captured."""
from __future__ import annotations

import asyncio

import pytest

from app.core import model_catalog as mc
from app.core import providers
from app.core.providers import ProviderError


@pytest.fixture
def calls(monkeypatch):
    seen: list[dict] = []
    replies: dict[str, object] = {}

    async def fake_post(provider, url, *, headers=None, params=None, payload):
        seen.append({"provider": provider, "url": url, "headers": headers or {}, "payload": payload})
        default = {"message": {"content": f"ok from {provider}"}} if provider == "ollama" else {"choices": [{"message": {"content": f"ok from {provider}"}}]}
        reply = replies.get(provider, default)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(providers, "_post", fake_post)
    for var in ("ATLAS_ALLOW_PAID", "HF_TOKEN", "FUGU_API_KEY", "FUGU_BASE_URL", "ATLAS_LOCAL_OPENAI_URL", "ATLAS_LOCAL_OPENAI_KEY"):
        monkeypatch.delenv(var, raising=False)
    return seen, replies


def test_local_openai_compatible_server_needs_no_key(calls, monkeypatch):
    seen, _ = calls
    monkeypatch.setenv("ATLAS_LOCAL_OPENAI_URL", "http://127.0.0.1:8080/v1/")
    model, text = asyncio.run(providers.generate("hi", "llamacpp", "inkling"))
    assert (model, text) == ("inkling", "ok from openai_compat")
    assert seen[0]["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert "Authorization" not in seen[0]["headers"]


def test_huggingface_router_uses_hub_id_and_token(calls, monkeypatch):
    seen, _ = calls
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    model, _ = asyncio.run(providers.generate("hi", "hf", "thinkingmachines/Inkling-Small"))
    assert model == "thinkingmachines/Inkling-Small"
    assert seen[0]["url"] == "https://router.huggingface.co/v1/chat/completions"
    assert seen[0]["headers"]["Authorization"] == "Bearer hf_test"


def test_huggingface_rejects_path_tricks(calls, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    for bad in ("../../etc", "a/b/c", "a/b?x=1", "/abs"):
        with pytest.raises(ProviderError, match="invalid model identifier"):
            asyncio.run(providers.generate("hi", "huggingface", bad))


def test_huggingface_without_token_fails_closed(calls):
    with pytest.raises(ProviderError, match="HF_TOKEN"):
        asyncio.run(providers.generate("hi", "huggingface", "thinkingmachines/Inkling"))


def test_fugu_is_paid_and_blocked_by_default(calls, monkeypatch):
    seen, _ = calls
    monkeypatch.setenv("FUGU_API_KEY", "k")
    monkeypatch.setenv("FUGU_BASE_URL", "https://fugu.example")
    with pytest.raises(ProviderError, match="paid"):
        asyncio.run(providers.generate("hi", "fugu"))
    assert seen == []


def test_fugu_when_paid_explicitly_enabled_appends_v1(calls, monkeypatch):
    seen, _ = calls
    monkeypatch.setenv("ATLAS_ALLOW_PAID", "true")
    monkeypatch.setenv("FUGU_API_KEY", "k")
    monkeypatch.setenv("FUGU_BASE_URL", "https://fugu.example/")
    model, _ = asyncio.run(providers.generate("hi", "sakana", "fugu-ultra"))
    assert model == "fugu-ultra"
    assert seen[0]["url"] == "https://fugu.example/v1/chat/completions"


def test_catalog_resolves_names_honestly():
    assert mc.resolve("Inkling").open_weights is True
    assert mc.resolve("Sakana Fugu").open_weights is False
    assert all(r.kind == mc.HOSTED_PAID for r in mc.resolve("fugu").routes)
    with pytest.raises(ProviderError, match="not wired"):
        mc.resolve("Ultron")
    with pytest.raises(ProviderError, match="unknown model name"):
        mc.resolve("skynet")


def test_free_first_falls_through_to_next_free_route(calls, monkeypatch):
    seen, replies = calls
    replies["ollama"] = ProviderError("Ollama request failed after retries")
    provider, _, text = asyncio.run(mc.generate_free_first("hi"))
    assert provider == "openai_compat" and text == "ok from openai_compat"
    assert [c["provider"] for c in seen] == ["ollama", "openai_compat"]


def test_free_first_stops_instead_of_paying(calls, monkeypatch):
    seen, replies = calls
    monkeypatch.setenv("FUGU_API_KEY", "k")
    monkeypatch.setenv("FUGU_BASE_URL", "https://fugu.example")
    with pytest.raises(ProviderError, match="stopped instead of using a paid provider"):
        asyncio.run(mc.generate_free_first("hi", "fugu"))
    assert seen == []


def test_named_inkling_prefers_local_then_free_tier(calls, monkeypatch):
    seen, replies = calls
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    provider, model, _ = asyncio.run(mc.generate_free_first("hi", "inkling"))
    assert (provider, model) == ("huggingface", "thinkingmachines/Inkling-Small")
    assert seen[0]["payload"]["model"] == "thinkingmachines/Inkling-Small"


def test_inkling_falls_back_to_self_hosted_when_hf_credits_run_out(calls, monkeypatch):
    seen, replies = calls
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    replies["huggingface"] = ProviderError("Huggingface request failed (402)")
    provider, model, _ = asyncio.run(mc.generate_free_first("hi", "inkling"))
    assert (provider, model) == ("openai_compat", "inkling")
    assert [c["provider"] for c in seen] == ["huggingface", "huggingface", "openai_compat"]


def test_hf_credit_exhaustion_message_is_plain(calls, monkeypatch):
    _, replies = calls
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    replies["huggingface"] = ProviderError("Huggingface request failed (402)")
    with pytest.raises(ProviderError, match="credits exhausted"):
        asyncio.run(providers.generate("hi", "hf", "thinkingmachines/Inkling-Small"))


def test_catalog_view_lists_sources_for_every_entry():
    view = mc.catalog_view()
    assert {v["key"] for v in view} == {"inkling", "inkling-small", "fugu", "ultron"}
    assert all(v["sources"] for v in view)


def test_real_http_roundtrip_against_local_openai_server(monkeypatch):
    """No monkeypatched transport: a real local server speaks the OpenAI chat schema."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append({"path": self.path, "body": body})
            out = json.dumps({"choices": [{"message": {"content": "local says hi"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 3}}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("ATLAS_LOCAL_OPENAI_URL", f"http://127.0.0.1:{server.server_port}/v1")
        monkeypatch.delenv("ATLAS_LOCAL_OPENAI_KEY", raising=False)
        model, text = asyncio.run(providers.generate("hello", "vllm", "inkling-small"))
    finally:
        server.shutdown()
    assert (model, text) == ("inkling-small", "local says hi")
    assert received[0]["path"] == "/v1/chat/completions"
    assert received[0]["body"]["messages"][0]["content"] == "hello"


def test_http_routes_require_tenant_and_stop_before_paid(oidc_auth_headers, monkeypatch, calls):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.auth.context import require_tenant
    from app.core.model_routes import router

    monkeypatch.setenv("ATLAS_ENV", "production")
    app = FastAPI()
    app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_tenant)])
    client = TestClient(app)
    assert client.get("/api/v1/models/catalog").status_code in {401, 403}
    headers = oidc_auth_headers()
    view = client.get("/api/v1/models/catalog", headers=headers).json()
    assert view["paid_allowed"] is False and len(view["models"]) == 4
    ok = client.post("/api/v1/models/generate", headers=headers, json={"prompt": "hi"})
    assert ok.status_code == 200 and ok.json()["provider"] == "ollama"
    blocked = client.post("/api/v1/models/generate", headers=headers, json={"prompt": "hi", "model_name": "fugu"})
    assert blocked.status_code == 503 and "paid" in blocked.json()["detail"]


def test_health_probe_is_zero_token_and_reports_each_provider(monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hits: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(("GET", self.path))
            out = json.dumps({"data": [{"id": "local"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

        def do_POST(self):  # noqa: N802
            hits.append(("POST", self.path)); self.send_response(500); self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("ATLAS_LOCAL_OPENAI_URL", f"http://127.0.0.1:{server.server_port}/v1")
        monkeypatch.setenv("ATLAS_OLLAMA_URL", "http://127.0.0.1:1")
        for var in ("HF_TOKEN", "FUGU_API_KEY", "FUGU_BASE_URL", "ATLAS_ALLOW_PAID", "ATLAS_LOCAL_OPENAI_KEY"):
            monkeypatch.delenv(var, raising=False)
        rows = {r["provider"]: r for r in asyncio.run(mc.health(timeout=2))}
    finally:
        server.shutdown()
    assert hits == [("GET", "/v1/models")]
    assert rows["openai_compat"]["reachable"] is True
    assert rows["ollama"]["reachable"] is False and rows["ollama"]["configured"] is True
    assert rows["huggingface"]["configured"] is False
    assert "paid provider disabled" in rows["fugu"]["detail"]
