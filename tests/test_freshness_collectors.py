from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest
from app.collectors.freshness import (
    FreshnessPolicy, FreshnessState, compare, freshness_state, snapshot,
)
from app.collectors.public_sources import Provenance, PublicRecord

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def record(external_id="source:1", title="One"):
    provenance = Provenance("source", "Source", "https://example.org", "https://example.org/1", NOW)
    return PublicRecord(external_id, "scholarship", title, None, None, None, None, None, None,
                        "https://example.org/1", provenance)


def test_freshness_states_cover_never_stale_fresh_and_clock_skew():
    policy = FreshnessPolicy(timedelta(hours=6))
    assert freshness_state(None, now=NOW, policy=policy) is FreshnessState.NEVER_COLLECTED
    assert freshness_state(NOW - timedelta(hours=6), now=NOW, policy=policy) is FreshnessState.FRESH
    assert freshness_state(NOW - timedelta(hours=7), now=NOW, policy=policy) is FreshnessState.STALE
    assert freshness_state(NOW + timedelta(minutes=6), now=NOW, policy=policy) is FreshnessState.CLOCK_SKEW


def test_snapshots_produce_added_changed_removed_and_unchanged():
    old = snapshot("source", [record("source:1"), record("source:2")], collected_at=NOW)
    current = snapshot("source", [record("source:1"), record("source:2", "Changed"),
                                  record("source:3")], collected_at=NOW + timedelta(hours=1))
    changes = compare(old, current)
    assert changes.added == ("source:3",)
    assert changes.changed == ("source:2",)
    assert changes.removed == ()
    assert changes.unchanged == ("source:1",)


def test_snapshot_rejects_duplicate_or_cross_source_records():
    with pytest.raises(ValueError, match="duplicate"):
        snapshot("source", [record(), record()], collected_at=NOW)
    other = replace(record(), provenance=replace(record().provenance, source_id="other"))
    with pytest.raises(ValueError, match="another source"):
        snapshot("source", [other], collected_at=NOW)
