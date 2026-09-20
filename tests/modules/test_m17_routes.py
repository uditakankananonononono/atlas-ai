from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.modules.m17_advice_essay.in_memory_repository import InMemoryModule17Repository
from app.modules.m17_advice_essay.routes import build_router
from app.modules.m17_advice_essay.service import AdviceEssayService


def test_route_rejects_payload_for_another_owner():
    from fastapi import FastAPI

    owner = uuid4(); other = uuid4(); service = AdviceEssayService(InMemoryModule17Repository())
    app = FastAPI(); app.include_router(build_router(lambda: service, lambda: owner)); client = TestClient(app)
    response = client.post("/v1/modules/17/sources", json={
        "owner_id": str(other), "source_kind": "user_submitted", "media_kind": "text",
        "platform": "notes", "content": "Use detail.", "permission_basis": "owner upload"
    })
    assert response.status_code == 403


def test_critique_uses_authenticated_owner_not_request_owner():
    from fastapi import FastAPI

    owner = uuid4(); service = AdviceEssayService(InMemoryModule17Repository())
    app = FastAPI(); app.include_router(build_router(lambda: service, lambda: owner)); client = TestClient(app)
    response = client.post("/v1/modules/17/essay/critique", json={
        "prompt": "Describe curiosity", "draft": "Since I was a child, I loved questions."
    })
    assert response.status_code == 200
    assert response.json()["owner_id"] == str(owner)


def test_communication_coaching_endpoint_is_mounted_and_owner_scoped():
    from fastapi import FastAPI

    owner = uuid4(); service = AdviceEssayService(InMemoryModule17Repository())
    app = FastAPI(); app.include_router(build_router(lambda: service, lambda: owner)); client = TestClient(app)
    payload = {
        "owner_id": str(owner), "skill": "socratic_method", "context": "Teach reasoning",
        "goal": "Help the learner inspect assumptions", "audience": "Student",
        "student_authored_work": True,
    }
    response = client.post("/v1/modules/17/communication/coaching", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["review_required"] is True
    assert body["external_action_proposed"] is False
    payload["owner_id"] = str(uuid4())
    assert client.post("/v1/modules/17/communication/coaching", json=payload).status_code == 403


def test_collaboration_coaching_endpoint_is_mounted_and_owner_scoped():
    from fastapi import FastAPI
    owner=uuid4(); service=AdviceEssayService(InMemoryModule17Repository())
    app=FastAPI(); app.include_router(build_router(lambda: service, lambda: owner)); client=TestClient(app)
    payload={"owner_id":str(owner),"skill":"facilitation","context":"Planning","objective":"Fair decision"}
    response=client.post("/v1/modules/17/collaboration/coaching",json=payload)
    assert response.status_code==200
    assert response.json()["external_action_proposed"] is False
    payload["owner_id"]=str(uuid4())
    assert client.post("/v1/modules/17/collaboration/coaching",json=payload).status_code==403


def test_trust_wellbeing_endpoint_is_mounted_and_owner_scoped():
    from fastapi import FastAPI
    owner=uuid4(); service=AdviceEssayService(InMemoryModule17Repository())
    app=FastAPI(); app.include_router(build_router(lambda:service,lambda:owner)); client=TestClient(app)
    payload={"owner_id":str(owner),"skill":"stress_management","context":"Busy week","goal":"Choose a low-risk step"}
    response=client.post("/v1/modules/17/trust-wellbeing/coaching",json=payload)
    assert response.status_code==200
    assert "not emergency or crisis support" in response.json()["escalation_boundary"].lower()
    payload["owner_id"]=str(uuid4())
    assert client.post("/v1/modules/17/trust-wellbeing/coaching",json=payload).status_code==403
