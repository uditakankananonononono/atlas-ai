"""Pins for the shipped executor. Providers below are explicit test doubles."""
import pytest
from app.core.providers import ProviderOutcomeUnknown
from app.modules.m12_ai_research_lab.bounded_evidence import EvidenceRejected
from app.modules.m12_ai_research_lab.models import ModelResult, ModelCapability, RouteRequest, TaskType
from app.modules.m12_ai_research_lab.executor import ResearchExecutor, RetryPolicy, ConfidenceUnavailable
from app.modules.m12_ai_research_lab.router import ModelRouter
from app.modules.m12_ai_research_lab.wiring import build_service


def request():
    return RouteRequest(TaskType.RESEARCH, 1, 1, 20000, "tenant")


class Provider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def executor(provider):
    catalog = [ModelCapability(m, frozenset({TaskType.RESEARCH}), 1000, 0, 1, .9)
               for m in ("a", "b")]
    return ResearchExecutor(ModelRouter(catalog), provider, RetryPolicy(base_delay_seconds=0))


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["object", "cycle", "depth", "bytes", "key_utf8"])
async def test_shipped_executor_rejects_nested_return_without_fallback(kind):
    metadata = {"nested": object()}
    if kind == "cycle":
        metadata = {}; metadata["self"] = metadata
    elif kind == "depth":
        metadata = {}
        for _ in range(1000):metadata = {"child": metadata}
    elif kind == "bytes":metadata = {"big": "x" * 1048577}
    elif kind == "key_utf8":metadata = {"\ud800": "bad"}
    provider = Provider(ModelResult("answer", "reported", .9, metadata=metadata))
    with pytest.raises(ProviderOutcomeUnknown):
        await executor(provider).execute(request(), "task")
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_shipped_executor_detaches_nested_result():
    provider = Provider(ModelResult("answer", "reported", .9, metadata={"nested": [1]}))
    result = await executor(provider).execute(request(), "task")
    result.metadata["nested"].append(2)
    assert provider.result.metadata == {"nested": [1]}


@pytest.mark.asyncio
async def test_context_rejected_before_provider():
    provider = Provider(ModelResult("answer", "reported", .9))
    with pytest.raises(EvidenceRejected):
        await executor(provider).execute(request(), "task", {"bad": object()})
    assert provider.calls == []


@pytest.mark.asyncio
async def test_service_constructed_through_real_wiring_guards_return(monkeypatch):
    from app.modules.m12_ai_research_lab import wiring
    calls = []
    async def generate(self, **kwargs):
        calls.append(kwargs)
        return ModelResult("answer", "reported", .9, metadata={"bad": object()})
    monkeypatch.setattr(wiring.AtlasProvider, "generate", generate)
    service = build_service()
    with pytest.raises(ProviderOutcomeUnknown):
        await service.execute(request(), "task")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_service_missing_confidence_remains_review(monkeypatch):
    from app.modules.m12_ai_research_lab import wiring
    async def generate(self, **kwargs):return ModelResult("answer", "reported")
    monkeypatch.setattr(wiring.AtlasProvider, "generate", generate)
    with pytest.raises(ConfidenceUnavailable):
        await build_service().execute(request(), "task")


def test_mounted_service_refuses_nested_evidence_with_unknown_409(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m12_ai_research_lab import wiring
    from app.modules.m12_ai_research_lab.routes import router, get_service
    calls = []
    async def generate(self, **kwargs):
        calls.append(kwargs)
        return ModelResult("answer", "reported", .9, metadata={"bad": object()})
    monkeypatch.setattr(wiring.AtlasProvider, "generate", generate)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext("tenant", "tester")
    app.dependency_overrides[get_service] = build_service
    response = TestClient(app).post("/ai-research-lab/run", json={
        "task_type": "research", "prompt": "task", "output_tokens": 1,
        "budget_cents": 1, "latency_tolerance_ms": 20000,
    })
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["state"] == "unknown"
    assert response.json()["detail"]["retry_allowed"] is False
    assert len(calls) == 1


def test_main_base_adapter_does_not_invent_confidence(monkeypatch):
    import asyncio
    from app.modules.m12_ai_research_lab import wiring
    async def generate(*args):return "model", "answer"
    monkeypatch.setattr(wiring, "generate", generate)
    result = asyncio.run(wiring.AtlasProvider().generate(model_id="ollama:model", prompt="task", context={}))
    assert result.confidence is None
    assert result.metadata["confidence_source"] == "unavailable"


def test_main_base_mounted_missing_confidence_requires_review(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth.context import TenantContext, require_tenant
    from app.modules.m12_ai_research_lab import wiring
    from app.modules.m12_ai_research_lab.routes import router, get_service
    async def generate(*args):return "model", "answer"
    monkeypatch.setattr(wiring, "generate", generate)
    app = FastAPI();app.include_router(router)
    app.dependency_overrides[require_tenant] = lambda: TenantContext("tenant", "tester")
    app.dependency_overrides[get_service] = build_service
    response = TestClient(app).post("/ai-research-lab/run", json={
        "task_type": "research", "prompt": "task", "output_tokens": 1,
        "budget_cents": 1, "latency_tolerance_ms": 20000,
    })
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["state"] == "review_required"
    assert response.json()["detail"]["result"]["confidence"] is None
