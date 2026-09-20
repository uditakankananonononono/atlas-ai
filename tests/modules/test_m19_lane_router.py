from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.m19_idea_incubator.lane_router import get_service, router
from app.modules.m19_idea_incubator.lane_service import IdeaIncubatorService


def client():
    app = FastAPI()
    app.include_router(router)
    service = IdeaIncubatorService()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_create_and_dossier_endpoints():
    c = client()
    created = c.post("/api/modules/19/ideas", json={
        "title": "Idea", "problem": "Problem", "proposed_solution": "Solution", "owner_id": "u1"
    })
    assert created.status_code == 201
    idea_id = created.json()["id"]
    response = c.get(f"/api/modules/19/ideas/{idea_id}")
    assert response.status_code == 200
    assert response.json()["idea"]["version"] == 1
    assert response.json()["evidence_summary"]["supporting_count"] == 0


def test_not_found_and_validation_errors_are_mapped():
    c = client()
    missing = "00000000-0000-0000-0000-000000000000"
    assert c.get(f"/api/modules/19/ideas/{missing}").status_code == 404
    created = c.post("/api/modules/19/ideas", json={
        "title": "Idea", "problem": "Problem", "proposed_solution": "Solution", "owner_id": "u1"
    }).json()
    invalid = c.post(f"/api/modules/19/ideas/{created['id']}/decisions", json={
        "to_stage": "approved", "rationale": "Too early", "actor_id": "u1"
    })
    assert invalid.status_code == 422
