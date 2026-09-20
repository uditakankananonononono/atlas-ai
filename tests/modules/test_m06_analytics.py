"""Tests for metrics ingestion, trends, and A/B statistical evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m06_social_media_manager.adapters import NormalizedMetrics
from app.modules.m06_social_media_manager.analytics import (
    ABTest,
    ABTestNotFoundError,
    ABTestStateError,
    Analytics,
    MetricsSnapshot,
    best_day_recommendation,
    engagement_rate,
    evaluate_ab,
    snapshot_delta,
)
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.service import MemorySocialRepository

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def metrics(**overrides) -> NormalizedMetrics:
    base = dict(platform="instagram", impressions=1000, reach=800, engagement=50, likes=40, comments=5, shares=5)
    base.update(overrides)
    return NormalizedMetrics(**base)


class FakeSource:
    def __init__(self, normalized: NormalizedMetrics) -> None:
        self.normalized = normalized
        self.calls: list[tuple[Platform, int]] = []

    async def fetch_normalized(self, platform: Platform, since_days: int) -> NormalizedMetrics:
        self.calls.append((platform, since_days))
        return self.normalized


def make_analytics() -> tuple[Analytics, MemorySocialRepository]:
    repository = MemorySocialRepository()
    return Analytics(repository=repository), repository


def make_snapshot(repo, platform=Platform.INSTAGRAM, captured_at=NOW, **metric_overrides):
    return repo.save_snapshot(
        MetricsSnapshot(id=f"snap-{captured_at.timestamp()}-{len(metric_overrides)}", platform=platform, since_days=1,
                        metrics=metrics(platform=platform.value, **metric_overrides), captured_at=captured_at)
    )


def test_engagement_rate_math():
    assert engagement_rate({"impressions": 1000, "engagement": 50}) == 0.05
    assert engagement_rate({"impressions": 0, "engagement": 50}) == 0.0
    assert engagement_rate({"impressions": 100, "likes": 3, "comments": 1, "shares": 1}) == 0.05


def test_snapshot_delta_reports_pct_change():
    older = MetricsSnapshot(id="a", platform=Platform.INSTAGRAM, since_days=1, metrics=metrics(), captured_at=NOW)
    newer = MetricsSnapshot(id="b", platform=Platform.INSTAGRAM, since_days=1,
                            metrics=metrics(impressions=2000, engagement=75), captured_at=NOW + timedelta(days=1))
    delta = snapshot_delta(older, newer)
    assert delta["impressions"]["change_pct"] == 100.0
    assert delta["engagement"]["change_pct"] == 50.0
    assert delta["follower_count"]["change_pct"] is None  # before=0: no honest percentage


def test_best_day_recommendation_needs_a_week():
    series = [((NOW - timedelta(days=i)).date().isoformat(), 10) for i in range(3)]
    assert best_day_recommendation(series) is None
    series = [((NOW - timedelta(days=i)).date().isoformat(), 100 if (NOW - timedelta(days=i)).weekday() == 1 else 5) for i in range(21)]
    assert best_day_recommendation(series) == "Tuesday"


def test_evaluate_ab_significant_winner():
    result = evaluate_ab(
        {"impressions": 10000, "engagement": 900},
        {"impressions": 10000, "engagement": 400},
    )
    assert result.significant is True
    assert result.winner == "a"
    assert result.rate_a > result.rate_b


def test_evaluate_ab_inconclusive_when_close_or_empty():
    close = evaluate_ab({"impressions": 100, "engagement": 5}, {"impressions": 100, "engagement": 6})
    assert close.significant is False
    assert close.winner == "inconclusive"
    empty = evaluate_ab({"impressions": 0}, {"impressions": 1000, "engagement": 50})
    assert empty.winner == "inconclusive"


@pytest.mark.anyio
async def test_capture_persists_normalized_snapshot():
    analytics, repository = make_analytics()
    source = FakeSource(metrics())
    snapshot = await analytics.capture(source, Platform.INSTAGRAM, 1)
    assert source.calls == [(Platform.INSTAGRAM, 1)]
    stored = repository.get_snapshot(snapshot.id)
    assert stored.metrics.impressions == 1000


def test_trend_requires_two_snapshots_then_reports_delta():
    analytics, repository = make_analytics()
    assert analytics.trend(Platform.INSTAGRAM) is None
    make_snapshot(repository, captured_at=NOW, impressions=1000)
    make_snapshot(repository, captured_at=NOW + timedelta(days=1), impressions=1500)
    trend = analytics.trend(Platform.INSTAGRAM)
    assert trend["impressions"]["change_pct"] == 50.0


def test_ab_test_lifecycle_to_verdict():
    analytics, repository = make_analytics()
    test = repository.save_ab_test(
        ABTest(id="t1", plan_id="p", platform=Platform.TWITTER, variant_a="A", variant_b="B", approval_id="appr-1")
    )
    with pytest.raises(ABTestStateError):
        analytics.conclude_ab_test("t1")  # cannot conclude before running
    analytics.start_ab_test(test, external_id_a="pa", external_id_b="pb")
    analytics.record_variant_metrics("t1", "a", {"impressions": 10000, "engagement": 900})
    analytics.record_variant_metrics("t1", "b", {"impressions": 10000, "engagement": 400})
    concluded, evaluation = analytics.conclude_ab_test("t1")
    assert evaluation.winner == "a"
    assert concluded.status == "concluded"
    assert concluded.verdict == "a"
    assert repository.get_ab_test("t1").verdict == "a"
    with pytest.raises(ABTestNotFoundError):
        analytics.record_variant_metrics("nope", "a", {})
    with pytest.raises(ValueError):
        analytics.record_variant_metrics("t1", "c", {})
