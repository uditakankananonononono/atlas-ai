"""Chunk-3 coverage: draft revision (compliance-gated rewrite) and
best-weekday publish-time suggestions over persisted Meta daily series."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models import ApprovalRequest
from app.modules.m06_social_media_manager.adapters import MetaGraphAdapter, NormalizedMetrics, PublishResult
from app.modules.m06_social_media_manager.analytics import Analytics, MetricsSnapshot
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.routes import get_analytics, get_scheduler, get_service, router
from app.modules.m06_social_media_manager.scheduler import Scheduler
from app.modules.m06_social_media_manager.service import MemorySocialRepository, Service

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
REVISED = "Snappier v2 copy"


class FakeApprovalStore:
    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest, *, user_id=None) -> ApprovalRequest:
        self.items.append(item)
        return item


class FakeDecisions:
    def status_of(self, approval_id: str) -> str | None:
        return None


class FakeAdapter:
    async def publish(self, request) -> PublishResult:
        return PublishResult(platform=request.platform, external_id="ext-1", url="https://x.example/1")


class FakeAdapterFactory:
    def for_platform(self, platform):
        return FakeAdapter()


class FakeMetrics:
    async def fetch_engagement(self, platform, since_days) -> dict:
        return {}


def make_client(revision_copy: str = REVISED):
    repository = MemorySocialRepository()

    async def generate(prompt, provider, model=None):
        if prompt.startswith("Rewrite this"):
            return "fake-model", revision_copy
        return "fake-model", '{"twitter": {"format": "thread", "copy": "Thread copy"}, "instagram": {"format": "carousel", "copy": "Carousel copy"}}'

    scheduler = Scheduler(repository=repository, decisions=FakeDecisions(), adapter_factory=FakeAdapterFactory(), clock=lambda: NOW)
    service = Service(approval_store=FakeApprovalStore(), generate=generate, metrics_client=FakeMetrics(), repository=repository, scheduler=scheduler)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_scheduler] = lambda: scheduler
    app.dependency_overrides[get_analytics] = lambda: Analytics(repository=repository)
    return TestClient(app), repository


def make_plan(client: TestClient, platforms: list[str]) -> dict:
    return client.post("/api/v1/social-media-manager/plans", json={"brief": "launch update", "platforms": platforms}).json()


def save_daily_snapshot(repository, platform: Platform, day: str, likes: int) -> None:
    repository.save_snapshot(
        MetricsSnapshot(
            id=f"snap-{day}",
            platform=platform,
            since_days=1,
            metrics=NormalizedMetrics(platform=platform.value, likes=likes, detail={"daily_series": [(day, likes)]}),
            captured_at=NOW,
        )
    )


def test_revision_route_rewrites_and_persists_copy():
    client, _repo = make_client()
    plan = make_plan(client, ["twitter"])
    response = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/drafts/twitter/revision',
        json={"feedback": "make it snappier"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["post_copy"] == REVISED
    assert body["draft"]["platform"] == "twitter"
    assert all(f["severity"] != "error" for f in body["findings"])
    stored = client.get(f'/api/v1/social-media-manager/plans/{plan["id"]}').json()
    assert next(d for d in stored["drafts"] if d["platform"] == "twitter")["post_copy"] == REVISED


def test_revision_route_unknown_plan_or_draft_is_404():
    client, _repo = make_client()
    plan = make_plan(client, ["twitter"])
    missing_plan = client.post(
        "/api/v1/social-media-manager/plans/nope/drafts/twitter/revision", json={"feedback": "shorter"}
    )
    assert missing_plan.status_code == 404
    missing_draft = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/drafts/tiktok/revision', json={"feedback": "shorter"}
    )
    assert missing_draft.status_code == 404


def test_revision_with_blocking_findings_keeps_old_copy():
    client, _repo = make_client(revision_copy="big brand collab with no disclosure")
    plan = make_plan(client, ["twitter"])
    response = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/drafts/twitter/revision',
        json={"feedback": "plug the brand", "sponsored": True},
    )
    assert response.status_code == 422
    codes = [item["code"] for item in response.json()["detail"]]
    assert "missing_disclosure" in codes
    stored = client.get(f'/api/v1/social-media-manager/plans/{plan["id"]}').json()
    assert next(d for d in stored["drafts"] if d["platform"] == "twitter")["post_copy"] == "Thread copy"


def test_best_time_route_uses_best_weekday():
    client, repository = make_client()
    # Seven days of Meta daily insights; Wednesday dominates.
    for offset, day in enumerate(["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20"]):
        save_daily_snapshot(repository, Platform.INSTAGRAM, day, 500 if offset == 2 else 10)
    response = client.get("/api/v1/social-media-manager/metrics/best-time/instagram")
    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "instagram"
    assert body["weekday"] == "Wednesday"
    next_at = datetime.fromisoformat(body["next_at"].replace("Z", "+00:00"))
    assert next_at.hour == 9 and next_at > datetime.now(timezone.utc)


def test_best_time_route_404_without_daily_series():
    client, repository = make_client()
    repository.save_snapshot(
        MetricsSnapshot(
            id="snap-empty",
            platform=Platform.TWITTER,
            since_days=1,
            metrics=NormalizedMetrics(platform="twitter", likes=9),
            captured_at=NOW,
        )
    )
    assert client.get("/api/v1/social-media-manager/metrics/best-time/twitter").status_code == 404


def test_meta_adapter_exposes_daily_series():
    adapter = MetaGraphAdapter(access_token="t", ig_user_id="ig-1")
    raw = {
        "data": [
            {
                "name": "likes",
                "period": "day",
                "values": [
                    {"value": 3, "end_time": "2026-09-18T07:00:00+0000"},
                    {"value": 4, "end_time": "2026-09-19T07:00:00+0000"},
                ],
            }
        ]
    }
    metrics = adapter.normalize_metrics(raw)
    assert metrics.likes == 7
    assert metrics.detail["daily_series"] == [("2026-09-18", 3), ("2026-09-19", 4)]
