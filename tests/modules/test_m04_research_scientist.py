"""Offline tests for module 4."""

import sys
import types
from dataclasses import dataclass
from typing import Any

# The snapshot lacks this convention-mandated shared type; integration owns the real file.
if "app.modules.types" not in sys.modules:
    shared_types = types.ModuleType("app.modules.types")

    @dataclass(frozen=True)
    class ModuleSpec:
        id: int
        slug: str
        name: str
        router: Any
        service_type: type

    shared_types.ModuleSpec = ModuleSpec
    sys.modules["app.modules.types"] = shared_types

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist.routes import router
from app.modules.m04_research_scientist.schemas import HypothesisRequest, PaperInput
from app.modules.m04_research_scientist.service import Service


def paper(paper_id: str, title: str, abstract: str) -> dict[str, str]:
    return {"paper_id": paper_id, "title": title, "abstract": abstract, "source": "arxiv"}


def test_clusters_related_literature_and_leaves_outlier():
    service = Service()
    papers = [
        PaperInput(**paper("p1", "Spatial transcriptomics in tumors", "Spatial transcriptomics maps tumor immune cells and tissue niches.")),
        PaperInput(**paper("p2", "Tumor spatial transcriptomics", "Tumor tissue niches are profiled with spatial transcriptomics and immune markers.")),
        PaperInput(**paper("p3", "Quantum error correction", "Quantum codes reduce errors in superconducting qubit processors.")),
    ]
    result = service.cluster_papers(papers, similarity_threshold=0.2)
    assert result.clusters[0].paper_ids == ["p1", "p2"]
    assert result.unclustered_paper_ids == ["p3"]


def test_hypothesis_uses_injected_byok_provider_without_network():
    calls = []

    async def fake_generate(prompt: str, provider: str, model: str | None):
        calls.append((prompt, provider, model))
        return "mock-model", "H1: treatment X increases outcome Y; reject if the effect is non-positive. [p1]"

    request = HypothesisRequest(
        research_question="Can treatment X improve outcome Y in this model?",
        papers=[PaperInput(**paper("p1", "Treatment X", "Treatment X is associated with improved outcome Y in a pilot cohort."))],
    )
    import asyncio
    result = asyncio.run(Service(fake_generate).generate_hypothesis(request))
    assert result.model == "mock-model"
    assert result.evidence_paper_ids == ["p1"]
    assert "[p1]" in result.hypothesis
    assert calls and "falsification criterion" in calls[0][0]


def test_analysis_is_only_proposed_and_network_access_is_rejected():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    safe = client.post("/research-scientist/analyses/proposals", json={
        "objective": "Compare two pre-cleaned expression matrices",
        "language": "python",
        "code": "print('analysis')",
        "network_access": False,
    })
    assert safe.status_code == 200
    assert safe.json()["requires_approval"] is True
    assert safe.json()["status"] == "pending"
    unsafe = client.post("/research-scientist/analyses/proposals", json={
        "objective": "Download and execute remote analysis code",
        "language": "python",
        "code": "print('unsafe')",
        "network_access": True,
    })
    assert unsafe.status_code == 422
    assert unsafe.json()["detail"] == "analysis execution proposals must disable network access"


def test_duplicate_paper_ids_fail_closed():
    service = Service()
    duplicate = PaperInput(**paper("same", "A sufficiently long title", "A sufficiently long abstract for validation and testing."))
    try:
        service.cluster_papers([duplicate, duplicate])
    except ValueError as exc:
        assert str(exc) == "paper_id values must be unique"
    else:
        raise AssertionError("duplicate IDs should be rejected")

def test_route_persists_analysis_approval():
 app=FastAPI();app.include_router(router)
 response=TestClient(app).post("/research-scientist/analyses/proposals",headers={"x-atlas-tenant":"research-tenant","x-atlas-actor":"u"},json={"objective":"Run an approved differential analysis","language":"python","code":"print(1)","network_access":False})
 assert response.status_code==200 and response.json()["status"]=="pending" and response.json()["approval_id"]


def test_provider_backed_hypothesis_requires_authentication_in_production(monkeypatch):
    monkeypatch.setenv("ATLAS_ENV", "production")
    app = FastAPI(); app.include_router(router)
    response = TestClient(app).post("/research-scientist/hypotheses", json={
        "research_question": "Can treatment X improve outcome Y in this model?",
        "papers": [paper("p1", "Treatment X", "Treatment X is associated with outcome Y in a pilot cohort.")],
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "OIDC bearer token required"
