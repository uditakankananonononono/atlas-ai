import httpx
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json() == {"status": "ok"}

def test_lists_all_spec_modules_plus_claire():
    modules = client.get("/api/v1/modules").json()
    assert [m["id"] for m in modules] == list(range(22))

def test_approval_flow_end_to_end():
    plan = client.post("/api/v1/goals/plan", json={"goal": "Research professors and draft outreach email"}).json()
    request = plan["approval_requests"][0]
    assert request["status"] == "pending"
    assert any(item["id"] == request["id"] for item in client.get("/api/v1/approvals").json())
    decided = client.post(f'/api/v1/approvals/{request["id"]}/decision', json={"decision": "approved"})
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert [e["event"] for e in client.get(f'/api/v1/approvals/{request["id"]}/audit').json()] == ["created", "approved"]
    assert client.post(f'/api/v1/approvals/{request["id"]}/decision', json={"decision": "denied"}).status_code == 409

def test_ai_missing_byok_is_clear(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post("/api/v1/ai/generate", json={"prompt": "hello"})
    assert response.status_code == 503
    assert response.json()["detail"] == "OPENAI_API_KEY is not configured"

def test_openai_byok_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    def handler(request: httpx.Request):
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "draft output"}}]})
    real_client = httpx.AsyncClient
    monkeypatch.setattr("app.core.providers.httpx.AsyncClient", lambda **_: real_client(transport=httpx.MockTransport(handler)))
    response = client.post("/api/v1/ai/generate", json={"prompt": "write a draft"})
    assert response.status_code == 200
    assert response.json()["text"] == "draft output"
