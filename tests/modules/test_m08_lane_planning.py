from datetime import date, datetime, timedelta, timezone

import pytest

from app.modules.m08_startup_growth.lane_planning import (
    GrowthInitiative, GrowthMeasurementWorkflow, GrowthSnapshot, InitiativePortfolio,
    InitiativeStatus, LifecycleEvent, PlanningValidationError, RetentionAnalyzer,
)


def test_rice_portfolio_ranking_evidence_and_dependencies():
    p = InitiativePortfolio()
    p.add(GrowthInitiative("foundation", "Tracking", 1, 1, 1, 10, status=InitiativeStatus.DONE))
    p.add(GrowthInitiative("viral", "Referral loop", 3, .8, 2, 100, ("ev-7",), dependencies=("foundation",)))
    p.add(GrowthInitiative("copy", "Change copy", 1, .2, .5, 50))
    assert [x["id"] for x in p.ranked()] == ["viral", "copy", "foundation"]
    assert [x["id"] for x in p.ranked(require_evidence=True)] == ["viral"]
    assert [x.id for x in p.ready()] == ["viral", "copy"]


def test_unknown_dependency_remains_blocker():
    p = InitiativePortfolio()
    p.add(GrowthInitiative("x", "Blocked idea", 1, 1, 1, 1, dependencies=("missing",)))
    assert p.ready() == []
    assert p.ranked()[0]["blocked_by"] == ["missing"]


def test_retention_uses_acquisition_relative_periods_and_ignores_pre_acquisition():
    t = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    events = [
        LifecycleEvent("pre", "u1", t-timedelta(days=1), "active"),
        LifecycleEvent("a1", "u1", t, "signup", segment={"plan":"free"}),
        LifecycleEvent("x1", "u1", t+timedelta(days=2), "active", segment={"plan":"free"}),
        LifecycleEvent("x2", "u1", t+timedelta(days=8), "active", segment={"plan":"free"}),
        LifecycleEvent("a2", "u2", t+timedelta(hours=1), "signup", segment={"plan":"free"}),
        LifecycleEvent("x3", "u2", t+timedelta(days=1), "active", segment={"plan":"free"}),
        LifecycleEvent("a3", "u3", t, "signup", segment={"plan":"paid"}),
    ]
    result = RetentionAnalyzer(events).cohorts(acquisition_event="signup", activity_event="active", periods=3)
    assert result[0]["size"] == 3
    assert [cell["retained"] for cell in result[0]["retention"]] == [2, 1, 0]
    free = RetentionAnalyzer(events).cohorts(acquisition_event="signup", activity_event="active",
                                              periods=2, segment={"plan":"free"})
    assert free[0]["size"] == 2


def test_retention_rejects_duplicate_event_ids():
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(PlanningValidationError):
        RetentionAnalyzer([LifecycleEvent("x", "a", stamp, "active"), LifecycleEvent("x", "b", stamp, "active")])


def test_growth_scorecard_handles_zero_denominators_and_trends():
    w = GrowthMeasurementWorkflow()
    result = w.scorecard([
        GrowthSnapshot(date(2026,1,1),100,40,30,10,3000,50),
        GrowthSnapshot(date(2026,1,8),120,60,40,12,4800,60),
    ])
    assert result["current"]["activation_rate"] == .5
    assert result["current"]["revenue_per_active_user"] == 80
    assert result["relative_change"]["acquisition"] == pytest.approx(.2)
    zero = w.scorecard([GrowthSnapshot(date(2026,1,1),0,0,0,0,0,0)])
    assert zero["current"]["activation_rate"] is None


def test_robust_anomaly_signal_and_snapshot_invariants():
    w = GrowthMeasurementWorkflow()
    snapshots = [GrowthSnapshot(date(2026,1,1)+timedelta(days=7*i), 100 if i < 4 else 500,
                                40, 30, 10, 3000, 50) for i in range(5)]
    alerts = w.anomalies(snapshots)
    assert any(a["metric"] == "acquisition" and a["period"] == "2026-01-29" for a in alerts)
    with pytest.raises(PlanningValidationError):
        GrowthSnapshot(date(2026,1,1),10,11,1,0,0,5)
