from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m08_startup_growth.lane_models import EvidenceKind, ExperimentStatus, MeasurementDefinition
from app.modules.m08_startup_growth.lane_repository import ConflictError
from app.modules.m08_startup_growth.lane_service import InvalidTransitionError, StartupGrowthService, ValidationError


def running_experiment(service, minimum=2):
    exp = service.create_experiment(name="CTA", hypothesis="A clearer CTA increases signup",
        primary_metric="signup", variants=[{"key":"control","weight":.5},{"key":"treatment","weight":.5}],
        minimum_sample_size=minimum, experiment_id="exp-1")
    service.transition_experiment(exp.id, ExperimentStatus.RUNNING)
    return exp


def test_experiment_lifecycle_assignment_is_stable_and_validation():
    s = StartupGrowthService(); exp = running_experiment(s)
    assert s.assign_variant(exp.id, "u-1") == s.assign_variant(exp.id, "u-1")
    assert s.assign_variant(exp.id, "u-1") in {"control", "treatment"}
    with pytest.raises(InvalidTransitionError):
        s.transition_experiment(exp.id, ExperimentStatus.DRAFT)
    with pytest.raises(ValidationError):
        s.create_experiment(name="bad", hypothesis="x", primary_metric="y",
                            variants=[{"key":"a","weight":.8},{"key":"b","weight":.8}])


def test_metric_ingestion_is_idempotent_and_collision_safe():
    s = StartupGrowthService(); running_experiment(s)
    kwargs = dict(event_id="e1", experiment_id="exp-1", subject_id="u", variant_key="control", metric="signup", value=1)
    assert s.record_metric(**kwargs) is True
    assert s.record_metric(**kwargs) is False
    with pytest.raises(ConflictError):
        s.record_metric(**{**kwargs, "value": 0})
    with pytest.raises(ValidationError):
        s.record_metric(**{**kwargs, "event_id":"e2", "variant_key":"bogus"})


def test_experiment_analysis_deduplicates_subjects_and_reports_winner():
    s = StartupGrowthService(); running_experiment(s, minimum=2)
    rows = [("c1","c1","control",0),("c2","c2","control",0),
            ("t1","t1","treatment",1),("t2","t2","treatment",1),
            ("t2-retry","t2","treatment",1)]
    for event, subject, variant, value in rows:
        s.record_metric(event_id=event, experiment_id="exp-1", subject_id=subject,
                        variant_key=variant, metric="signup", value=value)
    result = s.analyze_experiment("exp-1")
    assert result["ready"] is True and result["winner"] == "treatment"
    assert result["variants"]["treatment"]["subjects"] == 2
    lo, hi = result["variants"]["treatment"]["conversion_interval"]
    assert 0 < lo < hi <= 1


def test_funnel_enforces_order_and_segment_filter():
    s = StartupGrowthService()
    s.create_funnel(name="Activation", funnel_id="f1", steps=[{"key":"visit"},{"key":"signup"},{"key":"activate"}])
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = [("1","u1","visit",0,"organic"),("2","u1","signup",1,"organic"),("3","u1","activate",2,"organic"),
            ("4","u2","visit",0,"paid"),("5","u2","activate",1,"paid"),
            ("6","u3","signup",0,"organic"),("7","u3","visit",1,"organic")]
    for eid, uid, step, minutes, channel in data:
        s.record_funnel_event(event_id=eid, funnel_id="f1", subject_id=uid, step_key=step,
                              occurred_at=t+timedelta(minutes=minutes), segment={"channel":channel})
    all_result = s.analyze_funnel("f1")
    assert [r["subjects"] for r in all_result["steps"]] == [3, 1, 1]
    paid = s.analyze_funnel("f1", segment={"channel":"paid"})
    assert [r["subjects"] for r in paid["steps"]] == [1, 0, 0]


def test_customer_evidence_synthesis_has_traceability():
    s = StartupGrowthService()
    s.add_customer_evidence(evidence_id="a", kind=EvidenceKind.INTERVIEW, source="call-1", customer_id="c1",
                            text="Onboarding is confusing and slow", tags=["Onboarding", "friction"], sentiment=-.8)
    s.add_customer_evidence(evidence_id="b", kind=EvidenceKind.SUPPORT, source="ticket-9", customer_id="c2",
                            text="The onboarding checklist was confusing", tags=["onboarding"], sentiment=-.4)
    report = s.synthesize_evidence(tags={"onboarding"})
    assert report["evidence_count"] == 2 and report["distinct_customers"] == 2
    assert report["tag_counts"]["onboarding"] == 2
    assert report["top_terms"]["confusing"] == 2
    assert set(report["source_ids"]) == {"a", "b"}
    assert report["average_sentiment"] == pytest.approx(-.6)


def test_measurement_scorecard_direction_and_missing_values():
    s = StartupGrowthService()
    s.define_measurement(MeasurementDefinition("activation", "Activation", "Activated / signed up", "growth", "activated/signups", .4))
    s.define_measurement(MeasurementDefinition("cac", "CAC", "Spend / new customers", "finance", "spend/customers", 50, "decrease"))
    s.define_measurement(MeasurementDefinition("nps", "NPS", "Survey NPS", "success", "promoters-detractors", 40))
    result = s.measurement_scorecard({"activation":.42, "cac":62})
    assert (result["on_track"], result["off_track"], result["unmeasured"]) == (1,1,1)
    with pytest.raises(ValidationError):
        s.measurement_scorecard({"made_up": 1})
