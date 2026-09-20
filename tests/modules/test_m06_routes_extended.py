"""Route-level integration tests for the extended Social Media Manager.

Wires service + scheduler + analytics on a shared in-memory repository with
fake decisions/adapters/metrics, exactly as the production dependencies are
composed - only the network and LLM are mocked. Covers the success path
(brief -> compliance-checked schedule -> approve -> gated publish with
receipt) and the safety paths (422 on blocking compliance, sponsored
disclosure enforcement, revoked approvals, failed adapters).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models import ApprovalRequest
from app.modules.m06_social_media_manager.adapters import PublishResult
from app.modules.m06_social_media_manager.analytics import Analytics
from app.modules.m06_social_media_manager.routes import get_analytics, get_scheduler, get_service, router
from app.modules.m06_social_media_manager.scheduler import Scheduler
from app.modules.m06_social_media_manager.service import MemorySocialRepository, Service

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
DUE = (NOW - timedelta(hours=1)).isoformat()


class FakeApprovalStore:
    def __init__(self) -> None:
        self.items: list[ApprovalRequest] = []

    def put(self, item: ApprovalRequest) -> ApprovalRequest:
        self.items.append(item)
        return item


class FakeDecisions:
    def __init__(self) -> None:
        self.statuses: dict[str, str] = {}

    def status_of(self, approval_id: str) -> str | None:
        return self.statuses.get(approval_id)


class FakeAdapter:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, request) -> PublishResult:
        self.published.append(request)
        return PublishResult(platform=request.platform, external_id="ext-9", url="https://x.example/9")


class FakeAdapterFactory:
    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def for_platform(self, platform):
        return self.adapter


class FakeMetrics:
    async def fetch_engagement(self, platform, since_days) -> dict:
        return {"impressions": 500, "engagement": 25}


async def fake_generate(prompt, provider, model=None) -> tuple[str, str]:
    return "fake-model", '{"instagram": {"format": "carousel", "copy": "Slide by slide"}, "twitter": {"format": "thread", "copy": "Thread copy"}}'


def make_client(copy: str | None = None):
    repository = MemorySocialRepository()
    store, decisions, adapter = FakeApprovalStore(), FakeDecisions(), FakeAdapter()

    async def generate(prompt, provider, model=None):
        if copy is None:
            return await fake_generate(prompt, provider, model)
        return "fake-model", '{"instagram": {"format": "carousel", "copy": ' + __import__("json").dumps(copy) + "}}"

    scheduler = Scheduler(repository=repository, decisions=decisions, adapter_factory=FakeAdapterFactory(adapter), clock=lambda: NOW)
    service = Service(approval_store=store, generate=generate, metrics_client=FakeMetrics(), repository=repository, scheduler=scheduler)
    analytics = Analytics(repository=repository)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_scheduler] = lambda: scheduler
    app.dependency_overrides[get_analytics] = lambda: analytics
    return TestClient(app), store, decisions, adapter, repository


def make_plan(client: TestClient, platforms: list[str] | None = None) -> dict:
    return client.post("/api/v1/social-media-manager/plans", json={"brief": "ISEF update", "platforms": platforms or ["twitter"]}).json()


def test_schedule_persists_entries_and_links_approvals():
    client, store, _decisions, _adapter, _repository = make_client()
    plan = make_plan(client)
    response = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE})
    assert response.status_code == 201
    request = response.json()[0]
    assert request["payload"]["schedule_id"]
    entries = client.get(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule').json()
    assert len(entries) == 1
    assert entries[0]["status"] == "awaiting_approval"
    assert entries[0]["approval_id"] == request["id"]


def test_gated_publish_end_to_end_via_routes():
    client, store, decisions, adapter, _repository = make_client()
    plan = make_plan(client)
    request = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE}).json()[0]
    # Pending approval: the gate publishes nothing.
    assert client.post("/api/v1/social-media-manager/schedules/execute-due").json() == []
    decisions.statuses[request["id"]] = "approved"
    synced = client.post("/api/v1/social-media-manager/schedules/sync").json()
    assert synced[0]["status"] == "approved"
    records = client.post("/api/v1/social-media-manager/schedules/execute-due").json()
    assert len(records) == 1
    assert records[0]["external_id"] == "ext-9"
    entry = client.get(f'/api/v1/social-media-manager/schedules/{request["payload"]["schedule_id"]}').json()
    assert entry["status"] == "published"
    assert entry["external_url"] == "https://x.example/9"


def test_overlong_instagram_caption_gets_422_with_issue_codes():
    client, store, _d, _a, _r = make_client(copy="x" * 2300)
    plan = make_plan(client, ["instagram"])
    response = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE})
    assert response.status_code == 422
    codes = [issue["code"] for issue in response.json()["detail"]]
    assert "caption_too_long" in codes
    # Fail closed: no approval filed, no entry persisted.
    assert store.items == []
    assert client.get(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule').json() == []


def test_sponsored_requires_disclosure_before_scheduling():
    client, store, _d, _a, _r = make_client(copy="Love this serum!")
    plan = make_plan(client, ["instagram"])
    blocked = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE, "sponsored": True})
    assert blocked.status_code == 422
    assert "missing_disclosure" in [i["code"] for i in blocked.json()["detail"]]
    assert store.items == []
    # The unsponsored variant of the same plan is fine.
    ok = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE})
    assert ok.status_code == 201


def test_compliance_endpoint_reports_warnings():
    client, _s, _d, _a, _r = make_client(copy="Tag a friend to win! https://example.com")
    plan = make_plan(client, ["instagram"])
    issues = client.get(f'/api/v1/social-media-manager/plans/{plan["id"]}/compliance').json()
    codes = {i["code"] for i in issues}
    assert "engagement_bait" in codes
    assert "link_not_clickable" in codes
    assert all(i["severity"] == "warning" for i in issues)


def test_cancel_reschedule_and_attach_media_routes():
    client, _s, decisions, adapter, _r = make_client()
    plan = make_plan(client, ["instagram"])
    request = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE}).json()[0]
    entry_id = request["payload"]["schedule_id"]
    moved = client.post(f"/api/v1/social-media-manager/schedules/{entry_id}/reschedule", json={"publish_at": "2026-09-21T09:00:00+00:00"})
    assert moved.status_code == 200
    # Instagram needs rendered media before the gate will publish.
    decisions.statuses[request["id"]] = "approved"
    client.post("/api/v1/social-media-manager/schedules/sync")
    client.post(f"/api/v1/social-media-manager/schedules/{entry_id}/reschedule", json={"publish_at": DUE})
    assert client.post("/api/v1/social-media-manager/schedules/execute-due").json() == []
    assert client.get(f"/api/v1/social-media-manager/schedules/{entry_id}").json()["status"] == "failed"
    # A cancelled entry rejects media attachment with 409.
    client2, _s2, _d2, _a2, _r2 = make_client()
    plan2 = make_plan(client2, ["instagram"])
    req2 = client2.post(f'/api/v1/social-media-manager/plans/{plan2["id"]}/schedule', json={"publish_at": DUE}).json()[0]
    eid2 = req2["payload"]["schedule_id"]
    client2.post(f"/api/v1/social-media-manager/schedules/{eid2}/cancel")
    conflict = client2.post(f"/api/v1/social-media-manager/schedules/{eid2}/media", json={"media_urls": ["https://cdn.example.com/a.jpg"]})
    assert conflict.status_code == 409
    assert client2.get(f"/api/v1/social-media-manager/schedules/{eid2}").json()["status"] == "cancelled"
    assert adapter.published == []


def test_snapshot_capture_and_trend_via_routes():
    client, _s, _d, _a, _r = make_client()
    first = client.post("/api/v1/social-media-manager/metrics/snapshots", json={"platform": "instagram", "since_days": 1})
    assert first.status_code == 201
    assert first.json()["metrics"]["impressions"] == 500
    client.post("/api/v1/social-media-manager/metrics/snapshots", json={"platform": "instagram", "since_days": 1})
    snapshots = client.get("/api/v1/social-media-manager/metrics/snapshots?platform=instagram").json()
    assert len(snapshots) == 2
    trend = client.get("/api/v1/social-media-manager/metrics/trend/instagram").json()
    assert "impressions" in trend
    assert client.get("/api/v1/social-media-manager/metrics/trend/tiktok").status_code == 404


def test_ab_test_full_lifecycle_via_routes():
    client, _s, _d, _a, _r = make_client()
    plan = make_plan(client, ["twitter"])
    proposal = client.post(
        f'/api/v1/social-media-manager/plans/{plan["id"]}/ab-tests',
        json={"platform": "twitter", "variant_caption": "Alternate caption"},
    )
    assert proposal.status_code == 201
    test_id = proposal.json()["payload"]["ab_test_id"]
    test = client.get(f"/api/v1/social-media-manager/ab-tests/{test_id}").json()
    assert test["status"] == "proposed"
    started = client.post(f"/api/v1/social-media-manager/ab-tests/{test_id}/start", json={"external_id_a": "pa", "external_id_b": "pb"})
    assert started.json()["status"] == "running"
    client.post(f"/api/v1/social-media-manager/ab-tests/{test_id}/metrics", json={"variant": "a", "impressions": 10000, "engagement": 900})
    client.post(f"/api/v1/social-media-manager/ab-tests/{test_id}/metrics", json={"variant": "b", "impressions": 10000, "engagement": 400})
    evaluation = client.post(f"/api/v1/social-media-manager/ab-tests/{test_id}/conclude").json()
    assert evaluation["winner"] == "a"
    assert evaluation["significant"] is True
    assert client.get(f"/api/v1/social-media-manager/ab-tests/{test_id}").json()["verdict"] == "a"
    assert client.get("/api/v1/social-media-manager/ab-tests/nope").status_code == 404


def test_revoked_approval_blocks_gate_via_routes():
    client, _s, decisions, adapter, _r = make_client()
    plan = make_plan(client)
    request = client.post(f'/api/v1/social-media-manager/plans/{plan["id"]}/schedule', json={"publish_at": DUE}).json()[0]
    decisions.statuses[request["id"]] = "approved"
    client.post("/api/v1/social-media-manager/schedules/sync")
    decisions.statuses[request["id"]] = "denied"  # revoked between sync and gate
    assert client.post("/api/v1/social-media-manager/schedules/execute-due").json() == []
    assert adapter.published == []
    entry = client.get(f'/api/v1/social-media-manager/schedules/{request["payload"]["schedule_id"]}').json()
    assert entry["status"] == "denied"
