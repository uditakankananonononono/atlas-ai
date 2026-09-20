"""Tenant-scoped SQL persistence tests for the module's durable stores."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m06_social_media_manager.adapters import NormalizedMetrics
from app.modules.m06_social_media_manager.analytics import ABTest, MetricsSnapshot
from app.modules.m06_social_media_manager.models import ContentPlan, Platform, PlatformDraft
from app.modules.m06_social_media_manager.scheduler import PublishRecord, ScheduleEntry
from app.modules.m06_social_media_manager.sql_repository import SqlSocialRepository

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def make_repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'m6.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    return SqlSocialRepository("a", sessions), SqlSocialRepository("b", sessions)


def test_schedule_round_trip_is_tenant_scoped(tmp_path):
    a, b = make_repo(tmp_path)
    entry = ScheduleEntry(
        id="sch-1", plan_id="p", platform=Platform.TWITTER, format="thread", text="hello",
        publish_at=NOW, approval_id="appr-1", thread_chunks=["hello 1/1"],
    )
    a.save_schedule(entry)
    loaded = a.get_schedule("sch-1")
    assert loaded.text == "hello"
    assert loaded.thread_chunks == ["hello 1/1"]
    assert loaded.status == "awaiting_approval"
    assert b.get_schedule("sch-1") is None
    assert b.list_schedules() == []
    loaded.status = "approved"
    a.save_schedule(loaded)
    assert a.get_schedule("sch-1").status == "approved"
    assert a.list_schedules(plan_id="p")[0].id == "sch-1"
    assert a.list_schedules(plan_id="other") == []


def test_publish_records_round_trip(tmp_path):
    a, b = make_repo(tmp_path)
    a.save_publish_record(PublishRecord(schedule_id="sch-1", platform="twitter", external_id="x1",
                                        external_url="https://x.example/1", draft_only=False, published_at=NOW))
    records = a.list_publish_records("sch-1")
    assert len(records) == 1
    assert records[0].external_id == "x1"
    assert b.list_publish_records("sch-1") == []


def test_snapshots_round_trip_and_platform_filter(tmp_path):
    a, b = make_repo(tmp_path)
    a.save_snapshot(MetricsSnapshot(id="snap-1", platform=Platform.INSTAGRAM, since_days=1,
                                    metrics=NormalizedMetrics(platform="instagram", impressions=100), captured_at=NOW))
    a.save_snapshot(MetricsSnapshot(id="snap-2", platform=Platform.TWITTER, since_days=1,
                                    metrics=NormalizedMetrics(platform="twitter", follower_count=50), captured_at=NOW))
    assert a.get_snapshot("snap-1").metrics.impressions == 100
    assert {s.id for s in a.list_snapshots(Platform.TWITTER)} == {"snap-2"}
    assert len(a.list_snapshots()) == 2
    assert b.get_snapshot("snap-1") is None


def test_ab_tests_round_trip(tmp_path):
    a, b = make_repo(tmp_path)
    a.save_ab_test(ABTest(id="t1", plan_id="p", platform=Platform.TWITTER, variant_a="A", variant_b="B",
                          approval_id="appr-1", created_at=NOW))
    test = a.get_ab_test("t1")
    assert test.status == "proposed"
    test.status = "running"
    test.metrics_a = {"impressions": 100, "engagement": 9}
    a.save_ab_test(test)
    assert a.get_ab_test("t1").metrics_a["engagement"] == 9
    assert a.list_ab_tests(plan_id="p")[0].id == "t1"
    assert b.get_ab_test("t1") is None
