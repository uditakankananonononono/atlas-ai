"""Row 1535 QA evidence: test-only pins for boundaries the first suite did not assert.

Pure-function tests over the frozen core. The module is loaded through the package
when the full stack is installed, otherwise straight from its file path.
"""
import importlib
import importlib.util
import pathlib

import pytest

_REL = "backend/app/modules/m20_general_cognitive_worker/qa_evidence1535.py"
_ROOT = pathlib.Path(__file__).resolve().parents[2]
T0 = "2026-10-01T10:00:00+00:00"


@pytest.fixture(scope="module")
def qa():
    try:
        return importlib.import_module("app.modules.m20_general_cognitive_worker.qa_evidence1535")
    except ModuleNotFoundError as exc:
        if exc.name == "app.modules.m20_general_cognitive_worker.qa_evidence1535":
            raise
    spec = importlib.util.spec_from_file_location("qa_evidence1535", _ROOT / _REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def obs(oid, test_id, metric, value, **kw):
    d = dict(id=oid, test_id=test_id, metric=metric, value=value, source="lab-a", time=T0, signed=True)
    d.update(kw)
    return d


def cond(test_id, metric, op, threshold):
    return dict(test_id=test_id, metric=metric, op=op, threshold=threshold)


def run(qa, reqs, observations, policy="flag"):
    return qa.evaluate_qa_evidence(dict(requirements=reqs, observations=observations, defect_policy=policy))


def refusal(qa, reqs, observations, policy="refuse"):
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, reqs, observations, policy)
    return str(ei.value)


R1 = [dict(id="R", conditions=[cond("T", "m", ">=", 1)])]
LONG = "x" * 129
OK128 = "x" * 128


# L45: a non-string, non-empty time is a time defect, never an unhandled exception.
@pytest.mark.parametrize("bad", [12345, 1.5, ["2026-10-01T10:00:00+00:00"], {"t": 1}, True])
def test_non_string_time_is_a_time_defect_not_a_crash(qa, bad):
    res = run(qa, R1, [obs("a", "T", "m", 5, time=bad)])
    assert res["defects"] == [{"observation_id": "a", "field": "time"}]
    assert res["requirements"] == [{"id": "R", "status": "MISSING"}]
    assert refusal(qa, R1, [obs("a", "T", "m", 5, time=bad)]) == "observation a defective: time"


@pytest.mark.parametrize("bad", ["", None, "Z", "not-a-time", "2026-10-01T10:00:00"])
def test_empty_none_and_malformed_time_is_a_time_defect(qa, bad):
    res = run(qa, R1, [obs("a", "T", "m", 5, time=bad)])
    assert res["defects"] == [{"observation_id": "a", "field": "time"}]


def test_a_valid_z_and_offset_time_is_accepted(qa):
    for t in ("2026-10-01T10:00:00Z", "2026-10-01T10:00:00+05:30", "2026-10-01T10:00:00-07:00"):
        res = run(qa, R1, [obs("a", "T", "m", 5, time=t)])
        assert res["defects"] == [] and res["requirements"] == [{"id": "R", "status": "SATISFIED"}]


# L70: min_repeats and mode default when the keys are absent (the helper in the first suite always set them).
def test_absent_min_repeats_defaults_to_one_and_absent_mode_to_all(qa):
    r = [dict(id="R", conditions=[cond("T", "m", ">=", 1)])]
    one = run(qa, r, [obs("a", "T", "m", 5)])
    assert one["requirements"] == [{"id": "R", "status": "SATISFIED"}]
    c = one["audit_trace"][0]["conditions"][0]
    assert (c["min_repeats"], c["distinct_supporting_runs"], one["audit_trace"][0]["mode"]) == (1, 1, "all")
    none = run(qa, r, [])
    assert none["requirements"] == [{"id": "R", "status": "MISSING"}]
    assert none["audit_trace"][0]["conditions"][0]["min_repeats"] == 1


# L81: condition test_id and metric are each checked on their own.
@pytest.mark.parametrize("field,bad", [("test_id", ""), ("test_id", 5), ("test_id", None), ("test_id", LONG),
                                       ("metric", ""), ("metric", 5), ("metric", None), ("metric", LONG)])
def test_condition_test_id_and_metric_are_each_validated_alone(qa, field, bad):
    c = cond("T", "m", ">=", 1)
    c[field] = bad
    msg = refusal(qa, [dict(id="R", conditions=[c])], [])
    assert msg == "requirement R condition 0 test_id and metric must be non-empty strings up to 128 chars"


def test_condition_ids_of_exactly_128_chars_are_accepted(qa):
    res = run(qa, [dict(id="R", conditions=[cond(OK128, OK128, ">=", 1)])], [])
    assert res["requirements"] == [{"id": "R", "status": "MISSING"}]


# L110: observation test_id and metric are each checked on their own.
@pytest.mark.parametrize("field,bad", [("test_id", ""), ("test_id", 5), ("test_id", None), ("test_id", LONG),
                                       ("metric", ""), ("metric", 5), ("metric", None), ("metric", LONG)])
def test_observation_test_id_and_metric_are_each_validated_alone(qa, field, bad):
    o = obs("a", "T", "m", 5)
    o[field] = bad
    for policy in ("refuse", "flag"):
        assert refusal(qa, R1, [o], policy) == "observation a test_id and metric must be non-empty strings up to 128 chars"


def test_observation_ids_of_exactly_128_chars_are_accepted(qa):
    res = run(qa, [dict(id="R", conditions=[cond(OK128, OK128, ">=", 1)])], [obs("a", OK128, OK128, 5)])
    assert res["requirements"] == [{"id": "R", "status": "SATISFIED"}]


# L88: between [low, high] allows low == high and refuses low > high.
def test_between_with_equal_bounds_is_accepted_and_is_a_point(qa):
    r = [dict(id="R", conditions=[cond("T", "m", "between", [5, 5])])]
    assert run(qa, r, [obs("a", "T", "m", 5)])["requirements"] == [{"id": "R", "status": "SATISFIED"}]
    assert run(qa, r, [obs("a", "T", "m", 5.0001)])["requirements"] == [{"id": "R", "status": "REFUTED"}]
    assert run(qa, r, [obs("a", "T", "m", 4.9999)])["requirements"] == [{"id": "R", "status": "REFUTED"}]
    zero = [dict(id="R", conditions=[cond("T", "m", "between", [0, 0])])]
    assert run(qa, zero, [obs("a", "T", "m", 0)])["requirements"] == [{"id": "R", "status": "SATISFIED"}]


@pytest.mark.parametrize("bad", [[5, 4], [5, 4.999], [0.1, 0], [1, -1]])
def test_between_with_low_above_high_is_refused(qa, bad):
    msg = refusal(qa, [dict(id="R", conditions=[cond("T", "m", "between", bad)])], [])
    assert msg == "requirement R condition 0 threshold must be [low, high] with low <= high"


# L172: mismatched means a wanted test seen with a metric that is not paired with it.
def test_mismatched_and_unmapped_pairing_is_by_test_and_metric_together(qa):
    reqs = [dict(id="R1", conditions=[cond("T1", "m1", ">=", 1)]),
            dict(id="R2", conditions=[cond("T2", "m2", ">=", 1)])]
    res = run(qa, reqs, [
        obs("a", "T1", "m1", 5),   # paired, neither
        obs("b", "T1", "m2", 5),   # wanted test, metric belongs to the other test -> mismatched
        obs("c", "T2", "m1", 5),   # wanted test, metric belongs to the other test -> mismatched
        obs("d", "T2", "m2", 5),   # paired, neither
        obs("e", "T3", "m1", 5),   # unknown test, wanted metric -> unmapped
        obs("f", "T3", "m9", 5),   # unknown test, unknown metric -> unmapped
        obs("g", "T1", "m9", 5),   # wanted test, unknown metric -> mismatched
    ])
    assert res["mismatched_observations"] == ["b", "c", "g"]
    assert res["unmapped_observations"] == ["e", "f"]
    assert res["requirements"] == [{"id": "R1", "status": "SATISFIED"}, {"id": "R2", "status": "SATISFIED"}]


def test_no_observation_is_both_unmapped_and_mismatched_and_paired_ones_are_neither(qa):
    reqs = [dict(id="R1", conditions=[cond("T1", "m1", ">=", 1)])]
    res = run(qa, reqs, [obs("a", "T1", "m1", 5), obs("b", "T1", "m2", 5), obs("c", "T2", "m1", 5)])
    assert res["mismatched_observations"] == ["b"] and res["unmapped_observations"] == ["c"]
    assert not set(res["mismatched_observations"]) & set(res["unmapped_observations"])
    assert "a" not in res["mismatched_observations"] + res["unmapped_observations"]
