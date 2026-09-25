import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.self_improve.gate import APPROVED, ManualApprovalGate
from app.self_improve.routes import router
from app.self_improve import wiring


@pytest.fixture()
def client(tmp_path, monkeypatch):
    gates = {}
    def factory(slug):
        gates[slug] = ManualApprovalGate(tmp_path / f"{slug}.json")
        return gates[slug]
    engines = wiring.attach_all(state_dir=tmp_path / "state", gate_factory=factory)
    monkeypatch.setattr(wiring, "_engines", engines)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), gates


def test_status_404_and_ok(client):
    http, _ = client
    assert http.get("/self-improve/nope/status").status_code == 404
    assert http.get("/self-improve/grant-writer/status").status_code == 200


def test_cycle_and_activation_over_http(client):
    http, gates = client
    for _ in range(2):
        r = http.post("/self-improve/grant-writer/gaps",
                      json={"signature": "filter only biology grants",
                            "exemplar": "a biology grant for phd students"})
        assert r.status_code == 200
    cycle = http.post("/self-improve/grant-writer/cycle", json={"max_new": 1}).json()
    proposal = cycle["proposals"][0]
    r = http.post(f"/self-improve/grant-writer/candidates/{proposal['key']}/activate",
                  json={"approval_id": proposal["approval_id"]})
    assert r.status_code == 403  # pending: human has not decided
    gates["grant-writer"].decide(proposal["approval_id"], APPROVED, decided_by="udita")
    r = http.post(f"/self-improve/grant-writer/candidates/{proposal['key']}/activate",
                  json={"approval_id": proposal["approval_id"]})
    assert r.status_code == 200
    r = http.post(f"/self-improve/grant-writer/features/{proposal['name']}/dispatch",
                  json={"items": ["a biology grant for phd students", "pizza"]})
    assert r.status_code == 200
    assert r.json()["count"] >= 1
