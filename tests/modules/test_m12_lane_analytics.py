"""Tests for run comparison and spend analytics."""

from app.modules.m12_ai_research_lab.lane_analytics import (
    diff_manifests, spend_by_model,
)
from app.modules.m12_ai_research_lab.lane_models import StepRecord
from app.modules.m12_ai_research_lab.lane_runs import build_manifest

TS = "2026-09-20T12:00:00+00:00"


def manifest(run_id, cost, steps, seed=1, cfg=None, code="v1", status="completed"):
    return build_manifest(
        run_id=run_id, workflow_name="wf", config=cfg or {"a": 1},
        run_input="in", code_version=code, seed=seed, steps=steps,
        status=status, total_cost_micro=cost, created_at_utc=TS,
    )


def step(step_id, model="m1", cost=100, tokens=(10, 5), status="completed"):
    return StepRecord(step_id=step_id, kind="llm", status=status,
                      model_id=model, cost_micro=cost,
                      input_tokens=tokens[0], output_tokens=tokens[1])


def test_identical_manifests_diff_clean():
    m1 = manifest("r1", 100, (step("s"),))
    m2 = manifest("r2", 100, (step("s"),))
    d = diff_manifests(m1, m2)
    assert d.identical
    assert all(sd.change == "unchanged" for sd in d.step_diffs)


def test_diff_detects_config_seed_code_and_cost_changes():
    m1 = manifest("r1", 100, (step("s"),), seed=1, code="v1")
    m2 = manifest("r2", 250, (step("s", cost=250),), seed=2, cfg={"a": 2}, code="v2")
    d = diff_manifests(m1, m2)
    assert not d.identical
    assert d.config_changed and d.seed_changed and d.code_version_changed
    assert d.cost_delta_micro == 150
    sd = d.step_diffs[0]
    assert sd.change == "changed" and "cost_micro" in sd.changed_fields


def test_diff_added_removed_steps():
    m1 = manifest("r1", 100, (step("a"), step("b")))
    m2 = manifest("r2", 100, (step("b"), step("c")))
    d = diff_manifests(m1, m2)
    changes = {sd.step_id: sd.change for sd in d.step_diffs}
    assert changes == {"a": "removed", "b": "unchanged", "c": "added"}


def test_status_change_tracked():
    m1 = manifest("r1", 0, (), status="running")
    m2 = manifest("r2", 0, (), status="failed")
    d = diff_manifests(m1, m2)
    assert d.status_change == ("running", "failed")


def test_spend_by_model_aggregates_and_orders():
    manifests = [
        manifest("r1", 300, (step("s1", model="gpt-x", cost=300, tokens=(100, 50)),)),
        manifest("r2", 200, (step("s1", model="gpt-x", cost=100, tokens=(50, 25)),
                             step("s2", model="cheap", cost=100, tokens=(200, 100)))),
    ]
    agg = spend_by_model(manifests)
    assert [a.model_id for a in agg] == ["gpt-x", "cheap"]  # cost desc
    gx = agg[0]
    assert gx.runs == 2 and gx.steps == 2 and gx.cost_micro == 400
    assert gx.input_tokens == 150 and gx.output_tokens == 75
    assert agg[1].runs == 1 and agg[1].cost_micro == 100


def test_spend_by_model_skips_modelless_steps():
    m = manifest("r1", 0, (StepRecord(step_id="s", kind="echo", status="completed"),))
    assert spend_by_model([m]) == ()
