"""Metrics ingestion, trends, and A/B evaluation for the Social Media Manager.

Daily metrics pulls come through the official platform adapters (read-only),
are normalized, and persisted as tenant-scoped snapshots so trends survive
restarts. Deterministic statistics (engagement rate, snapshot-over-snapshot
deltas, best-day recommendations, A/B significance) live here as pure
functions; the LLM only writes the human-readable narrative on top, with
these deterministic findings as its input and as the fallback when the
provider is down.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .adapters import NormalizedMetrics
from .models import Platform

# -- value objects ---------------------------------------------------------------


@dataclass
class MetricsSnapshot:
    """One normalized daily pull for one platform."""

    id: str
    platform: Platform
    since_days: int
    metrics: NormalizedMetrics
    captured_at: datetime


@dataclass
class ABTest:
    """A caption A/B test over two published variants."""

    id: str
    plan_id: str
    platform: Platform
    variant_a: str
    variant_b: str
    approval_id: str
    status: str = "proposed"  # proposed -> running -> concluded
    external_id_a: str | None = None
    external_id_b: str | None = None
    metrics_a: dict[str, int] = field(default_factory=dict)
    metrics_b: dict[str, int] = field(default_factory=dict)
    verdict: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ABEvaluation:
    """Two-proportion z-test over per-variant engagement rates."""

    winner: str  # "a" | "b" | "inconclusive"
    rate_a: float
    rate_b: float
    z_score: float
    significant: bool
    explanation: str


class SnapshotNotFoundError(KeyError):
    """Raised when a caller references an unknown metrics snapshot."""


class ABTestNotFoundError(KeyError):
    """Raised when a caller references an unknown A/B test."""


class ABTestStateError(RuntimeError):
    """Raised when an A/B test cannot advance (e.g. evaluate before running)."""


class MetricsSource(Protocol):
    """Anything that can return normalized engagement for a platform."""

    async def fetch_normalized(self, platform: Platform, since_days: int) -> NormalizedMetrics: ...


class AnalyticsRepository(Protocol):
    """Persistence boundary for snapshots and A/B tests."""

    def save_snapshot(self, snapshot: MetricsSnapshot) -> MetricsSnapshot: ...
    def get_snapshot(self, snapshot_id: str) -> MetricsSnapshot | None: ...
    def list_snapshots(self, platform: Platform | None = None) -> list[MetricsSnapshot]: ...
    def save_ab_test(self, test: ABTest) -> ABTest: ...
    def get_ab_test(self, test_id: str) -> ABTest | None: ...
    def list_ab_tests(self, plan_id: str | None = None) -> list[ABTest]: ...


# -- deterministic statistics -----------------------------------------------------


def engagement_rate(metrics: NormalizedMetrics | dict[str, int]) -> float:
    """Engagements per impression; 0.0 when impressions are unknown."""
    get = (lambda key: metrics.get(key, 0)) if isinstance(metrics, dict) else (lambda key: getattr(metrics, key, 0))
    impressions = int(get("impressions"))
    if impressions <= 0:
        return 0.0
    engagement = int(get("engagement")) or (
        int(get("likes")) + int(get("comments")) + int(get("shares"))
    )
    return engagement / impressions


def snapshot_delta(older: MetricsSnapshot, newer: MetricsSnapshot) -> dict[str, Any]:
    """Absolute and relative change between two pulls of the same platform."""
    delta: dict[str, Any] = {"platform": newer.platform.value}
    for metric_name in ("impressions", "reach", "engagement", "likes", "comments", "shares", "follower_count"):
        before = getattr(older.metrics, metric_name)
        after = getattr(newer.metrics, metric_name)
        change = after - before
        delta[metric_name] = {
            "before": before,
            "after": after,
            "change": change,
            "change_pct": round(100.0 * change / before, 1) if before else None,
        }
    return delta


def best_day_recommendation(daily_series: list[tuple[str, int]]) -> str | None:
    """Name the weekday with the highest average engagement, e.g. 'Tuesday'.

    ``daily_series`` is (ISO date, engagement) pairs, as returned by the Meta
    Graph API's period=day insights. Returns None when the series is too
    small to say anything honest.
    """
    if len(daily_series) < 7:
        return None
    by_weekday: dict[int, list[int]] = {}
    for day, engagement in daily_series:
        weekday = datetime.fromisoformat(day).weekday()
        by_weekday.setdefault(weekday, []).append(engagement)
    best_weekday = max(by_weekday, key=lambda day: sum(by_weekday[day]) / len(by_weekday[day]))
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][best_weekday]


def evaluate_ab(metrics_a: dict[str, int], metrics_b: dict[str, int]) -> ABEvaluation:
    """Two-proportion z-test on engagement rates at 95% confidence.

    Honest by construction: with no impressions on either variant, or a
    z-score under 1.96, the verdict is 'inconclusive' - never a coin flip
    dressed up as a result.
    """
    impressions_a, impressions_b = int(metrics_a.get("impressions", 0)), int(metrics_b.get("impressions", 0))
    rate_a, rate_b = engagement_rate(metrics_a), engagement_rate(metrics_b)
    if impressions_a <= 0 or impressions_b <= 0:
        return ABEvaluation(
            winner="inconclusive",
            rate_a=rate_a,
            rate_b=rate_b,
            z_score=0.0,
            significant=False,
            explanation="both variants need impressions before a verdict is possible",
        )
    pooled = (rate_a * impressions_a + rate_b * impressions_b) / (impressions_a + impressions_b)
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / impressions_a + 1 / impressions_b))
    if standard_error == 0:
        z_score = 0.0
    else:
        z_score = (rate_a - rate_b) / standard_error
    significant = abs(z_score) >= 1.96
    if not significant:
        winner = "inconclusive"
        explanation = (
            f"engagement rates {rate_a:.4f} vs {rate_b:.4f} are not statistically distinguishable "
            f"(z={z_score:.2f}); keep the test running or call it a tie"
        )
    else:
        winner = "a" if z_score > 0 else "b"
        explanation = (
            f"variant {winner.upper()} wins with engagement rate {max(rate_a, rate_b):.4f} "
            f"vs {min(rate_a, rate_b):.4f} (z={abs(z_score):.2f} >= 1.96)"
        )
    return ABEvaluation(winner=winner, rate_a=rate_a, rate_b=rate_b, z_score=z_score, significant=significant, explanation=explanation)


class Analytics:
    """Ingestion, trends, and A/B lifecycle over the analytics repository."""

    def __init__(self, *, repository: AnalyticsRepository) -> None:
        self._repository = repository

    # -- ingestion --------------------------------------------------------------

    async def capture(self, source: MetricsSource, platform: Platform, since_days: int) -> MetricsSnapshot:
        """Pull normalized metrics through an official adapter and persist them."""
        normalized = await source.fetch_normalized(platform, since_days)
        snapshot = MetricsSnapshot(
            id=str(uuid.uuid4()),
            platform=platform,
            since_days=since_days,
            metrics=normalized,
            captured_at=datetime.now(timezone.utc),
        )
        return self._repository.save_snapshot(snapshot)

    def get_snapshot(self, snapshot_id: str) -> MetricsSnapshot:
        snapshot = self._repository.get_snapshot(snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(snapshot_id)
        return snapshot

    def list_snapshots(self, platform: Platform | None = None) -> list[MetricsSnapshot]:
        return self._repository.list_snapshots(platform)

    def trend(self, platform: Platform) -> dict[str, Any] | None:
        """Snapshot-over-snapshot delta for a platform; None with < 2 pulls."""
        snapshots = self._repository.list_snapshots(platform)
        if len(snapshots) < 2:
            return None
        ordered = sorted(snapshots, key=lambda snapshot: snapshot.captured_at)
        return snapshot_delta(ordered[-2], ordered[-1])

    # -- A/B lifecycle ------------------------------------------------------------

    def start_ab_test(self, test: ABTest, external_id_a: str, external_id_b: str) -> ABTest:
        """Mark a proposed test running once both variant posts exist."""
        if test.status != "proposed":
            raise ABTestStateError(f"cannot start a test in state {test.status}")
        test.external_id_a = external_id_a
        test.external_id_b = external_id_b
        test.status = "running"
        return self._repository.save_ab_test(test)

    def record_variant_metrics(self, test_id: str, variant: str, metrics: dict[str, int]) -> ABTest:
        test = self._test(test_id)
        if variant == "a":
            test.metrics_a = dict(metrics)
        elif variant == "b":
            test.metrics_b = dict(metrics)
        else:
            raise ValueError("variant must be 'a' or 'b'")
        return self._repository.save_ab_test(test)

    def conclude_ab_test(self, test_id: str) -> tuple[ABTest, ABEvaluation]:
        """Evaluate a running test and persist its verdict."""
        test = self._test(test_id)
        if test.status != "running":
            raise ABTestStateError(f"cannot conclude a test in state {test.status}")
        evaluation = evaluate_ab(test.metrics_a, test.metrics_b)
        test.verdict = evaluation.winner
        test.status = "concluded"
        return self._repository.save_ab_test(test), evaluation

    def get_ab_test(self, test_id: str) -> ABTest:
        return self._test(test_id)

    def list_ab_tests(self, plan_id: str | None = None) -> list[ABTest]:
        return self._repository.list_ab_tests(plan_id)

    def _test(self, test_id: str) -> ABTest:
        test = self._repository.get_ab_test(test_id)
        if test is None:
            raise ABTestNotFoundError(test_id)
        return test
