"""Tests for module 6 (Social Media Manager).

All network and LLM work is mocked. Covers the success path (brief -> plan ->
approval-gated schedule, analytics suggestions) and the safety path (provider
failure falls back, scheduling never publishes without approval).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models import ApprovalRequest
from app.core.providers import ProviderError
from app.modules.m06_social_media_manager import router, spec
from app.modules.m06_social_media_manager.routes import get_service
from app.modules.m06_social_media_manager.service import (
    OfficialSocialMetricsClient,
    Platform,
    Service,
)


class FakeApprovalStore:
    """Captures filed approvals; performs no persistence."""

    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items.append(item)
        return item


class FakeMetricsClient:
    """Returns canned engagement metrics; records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[Platform, int]] = []

    async def fetch_engagement(self, platform: Platform, since_days: int) -> dict:
        self.calls.append((platform, since_days))
        return {"platform": platform.value, "impressions": 1200, "engagement": 84}


async def fake_generate(prompt: str, provider: str, model: str | None = None) -> tuple[str, str]:
    """Deterministic BYOK stand-in returning strategist JSON."""
    return "fake-model", (
        '{"instagram": {"format": "carousel", "copy": "Our ISEF update, slide by slide"},'
        ' "twitter": {"format": "thread", "copy": "A thread on our ISEF update 1/"}}'
    )


async def failing_generate(prompt: str, provider: str, model: str | None = None) -> tuple[str, str]:
    raise ProviderError("no key configured")


def make_service(generate=fake_generate) -> tuple[Service, FakeApprovalStore, FakeMetricsClient]:
    store, metrics = FakeApprovalStore(), FakeMetricsClient()
    return Service(approval_store=store, generate=generate, metrics_client=metrics), store, metrics


def make_client(service: Service) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_spec_matches_catalog_entry():
    assert spec.id == 6
    assert spec.slug == "social-media-manager"
    assert spec.name == "Social Media Manager"
    assert spec.service_type is Service
    assert spec.router is router


def test_plan_success_path_uses_strategist_formats():
    service, _store, _metrics = make_service()
    client = make_client(service)
    response = client.post(
        "/api/v1/social-media-manager/plans",
        json={"brief": "Share our ISEF project update", "platforms": ["instagram", "twitter"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    drafts = {d["platform"]: d for d in body["drafts"]}
    assert drafts["instagram"]["format"] == "carousel"
    assert drafts["instagram"]["post_copy"] == "Our ISEF update, slide by slide"
    # Carousel drafts carry image prompts for the self-hosted ComfyUI renderer.
    assert all(p["engine"] == "comfyui-sdxl" for p in drafts["instagram"]["asset_prompts"])
    assert drafts["twitter"]["format"] == "thread"
    fetched = client.get(f'/api/v1/social-media-manager/plans/{body["id"]}')
    assert fetched.status_code == 200
    assert fetched.json()["brief"] == "Share our ISEF project update"


def test_schedule_files_approvals_and_never_publishes():
    service, store, metrics = make_service()
    client = make_client(service)
    plan = client.post(
        "/api/v1/social-media-manager/plans",
        json={"brief": "Share our ISEF project update", "platforms": ["instagram"]},
    ).json()
    response = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule',
        json={"publish_at": "2026-09-25T13:30:00+05:30"},
    )
    assert response.status_code == 201
    requests = response.json()
    assert len(requests) == 1
    request = requests[0]
    assert request["status"] == "pending"
    assert request["module_id"] == 6
    assert request["action_type"] == "schedule_post"
    assert request["payload"]["platform"] == "instagram"
    assert request["payload"]["api"] == "meta-graph-api"
    # Safety: the schedule endpoint only filed an approval; no platform call happened.
    assert len(store.items) == 1
    assert metrics.calls == []
    assert client.get(f'/api/v1/social-media-manager/plans/{plan["id"]}').json()["status"] == "pending_approval"


def test_provider_failure_falls_back_to_default_formats():
    service, _store, _metrics = make_service(generate=failing_generate)
    client = make_client(service)
    response = client.post("/api/v1/social-media-manager/plans", json={"brief": "New blog post is live"})
    assert response.status_code == 201
    drafts = {d["platform"]: d for d in response.json()["drafts"]}
    assert drafts["instagram"]["format"] == "carousel"
    assert drafts["tiktok"]["format"] == "video_script_60s"
    assert drafts["twitter"]["format"] == "thread"
    assert drafts["linkedin"]["format"] == "article_post"


def test_ab_test_requires_existing_draft_and_files_approval():
    service, store, _metrics = make_service()
    client = make_client(service)
    plan = client.post(
        "/api/v1/social-media-manager/plans", json={"brief": "ISEF update", "platforms": ["twitter"]}
    ).json()
    ok = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/ab-tests',
        json={"platform": "twitter", "variant_caption": "Alternate caption"},
    )
    assert ok.status_code == 201
    assert ok.json()["action_type"] == "ab_test"
    assert ok.json()["status"] == "pending"
    assert len(store.items) == 1
    missing = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/ab-tests',
        json={"platform": "tiktok", "variant_caption": "No draft for this"},
    )
    assert missing.status_code == 404


def test_unknown_plan_returns_404():
    service, _store, _metrics = make_service()
    client = make_client(service)
    assert client.get("/api/v1/social-media-manager/plans/nope").status_code == 404
    assert client.post("/api/v1/social-media-manager/plans/nope/schedule", json={}).status_code == 404


def test_analytics_report_success_path():
    service, _store, metrics = make_service()
    client = make_client(service)
    response = client.post(
        "/api/v1/social-media-manager/analytics/reports", json={"platform": "instagram", "since_days": 14}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["platform"] == "instagram"
    assert metrics.calls == [(Platform.INSTAGRAM, 14)]
    # The fake strategist returns an object, not a suggestion array, so the
    # service falls back to its no-pattern message rather than crashing.
    assert body["suggestions"] == ["No actionable pattern found in the pulled metrics."]
    assert client.get(f'/api/v1/social-media-manager/analytics/reports/{body["id"]}').status_code == 200


def test_analytics_without_metrics_client_is_clear():
    service, store, _metrics = make_service()
    service._metrics = None
    client = make_client(service)
    response = client.post("/api/v1/social-media-manager/analytics/reports", json={"platform": "twitter"})
    assert response.status_code == 503


def test_official_metrics_client_calls_x_api_v2_with_bearer_token():
    asyncio.run(_check_x_api_v2_call())


async def _check_x_api_v2_call():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"data": {"public_metrics": {"followers_count": 10}}})

    client = OfficialSocialMetricsClient(x_bearer_token="secret-token", transport=httpx.MockTransport(handler))
    result = await client.fetch_engagement(Platform.TWITTER, 7)
    assert result["data"]["public_metrics"]["followers_count"] == 10
    assert seen["url"].startswith("https://api.twitter.com/2/users/me")
    assert seen["authorization"] == "Bearer secret-token"
    # The token is sent as a header only; it never appears in the returned payload.
    assert "secret-token" not in str(result)


def test_official_metrics_client_missing_token_fails_closed():
    asyncio.run(_check_missing_token())


async def _check_missing_token():
    client = OfficialSocialMetricsClient()
    with pytest.raises(ProviderError):
        await client.fetch_engagement(Platform.INSTAGRAM, 7)
