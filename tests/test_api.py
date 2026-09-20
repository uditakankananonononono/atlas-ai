from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json() == {"status": "ok"}

def test_lists_all_spec_modules_plus_claire():
    modules = client.get("/api/v1/modules").json()
    assert [m["id"] for m in modules] == list(range(22))

def test_outreach_is_gated():
    plan = client.post("/api/v1/goals/plan", json={"goal": "Research professors and draft outreach email"}).json()
    assert any(step["module_id"] == 4 for step in plan["steps"])
    assert any(step["module_id"] == 5 and step["requires_approval"] for step in plan["steps"])
    assert plan["approval_requests"][0]["status"] == "pending"
