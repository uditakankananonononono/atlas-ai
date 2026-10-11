"""Row 1535 Quality Assurance: requirement/test/evidence graph evaluation.

Pure-function tests. The module under test is loaded through the package when
the full stack is installed, otherwise straight from its file path.
"""
import copy
import importlib
import importlib.util
import itertools
import pathlib
import random

import pytest

_REL = "backend/app/modules/m20_general_cognitive_worker/qa_evidence1535.py"
_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def qa():
    try:
        return importlib.import_module(
            "app.modules.m20_general_cognitive_worker.qa_evidence1535")
    except ModuleNotFoundError as exc:
        if exc.name == "app.modules.m20_general_cognitive_worker.qa_evidence1535":
            raise
    path = _ROOT / _REL
    if not path.exists():
        raise ModuleNotFoundError("qa_evidence1535 missing", name="qa_evidence1535")
    spec = importlib.util.spec_from_file_location("qa_evidence1535", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T0 = "2026-10-01T10:00:00+00:00"


def obs(oid, test_id, metric, value, **kw):
    d = dict(id=oid, test_id=test_id, metric=metric, value=value,
             source="lab-a", time=T0, signed=True)
    d.update(kw)
    return d


def cond(test_id, metric, op, threshold):
    return dict(test_id=test_id, metric=metric, op=op, threshold=threshold)


def req(rid, conds, mode="all", min_repeats=1):
    return dict(id=rid, mode=mode, min_repeats=min_repeats, conditions=conds)


def run(qa, reqs, observations, **opts):
    body = dict(requirements=reqs, observations=observations,
                defect_policy=opts.pop("defect_policy", "flag"))
    body.update(opts)
    return qa.evaluate_qa_evidence(body)


def status_of(res, rid):
    return {r["id"]: r["status"] for r in res["requirements"]}[rid]


# ---------------- comparator oracle ----------------
ORACLE = {
    "<": lambda v, t: v < t, "<=": lambda v, t: v <= t,
    ">": lambda v, t: v > t, ">=": lambda v, t: v >= t,
    "==": lambda v, t: v == t, "!=": lambda v, t: v != t,
}


@pytest.mark.parametrize("op", sorted(ORACLE))
def test_every_comparator_against_exhaustive_oracle(qa, op):
    grid = [-2, -1, 0, 1, 2, 1.5, 0.5]
    for v, t in itertools.product(grid, grid):
        res = run(qa, [req("R", [cond("T", "m", op, t)])], [obs("o1", "T", "m", v)])
        want = "SATISFIED" if ORACLE[op](v, t) else "REFUTED"
        assert status_of(res, "R") == want, (op, v, t)


def test_between_inclusive_bounds_exhaustive(qa):
    for v in [-1, 0, 1, 2, 3, 4, 1.999, 3.001]:
        res = run(qa, [req("R", [cond("T", "m", "between", [1, 3])])],
                  [obs("o1", "T", "m", v)])
        assert status_of(res, "R") == ("SATISFIED" if 1 <= v <= 3 else "REFUTED"), v


# ---------------- requirement coverage ----------------
def test_missing_evidence_is_missing_not_satisfied(qa):
    res = run(qa, [req("R1", [cond("T1", "m", ">=", 1)])], [])
    assert status_of(res, "R1") == "MISSING"
    assert res["release_status"] == "RELEASE-UNREADY"


def test_one_unsupported_requirement_makes_release_unready(qa):
    reqs = [req(f"R{i}", [cond(f"T{i}", "m", ">=", 1)]) for i in range(5)]
    observations = [obs(f"o{i}", f"T{i}", "m", 5) for i in range(4)]
    res = run(qa, reqs, observations)
    assert res["release_status"] == "RELEASE-UNREADY"
    assert res["coverage"]["satisfied_ids"] == ["R0", "R1", "R2", "R3"]
    assert res["coverage"]["unsupported"] == {"R4": "MISSING"}
    assert res["coverage"]["requirements_total"] == 5


def test_coverage_is_by_requirement_identity_not_count(qa):
    # three observations but they all cover R1; R2 and R3 remain uncovered
    reqs = [req("R1", [cond("T1", "m", ">=", 1)]),
            req("R2", [cond("T2", "m", ">=", 1)]),
            req("R3", [cond("T3", "m", ">=", 1)])]
    res = run(qa, reqs, [obs("a", "T1", "m", 2), obs("b", "T1", "m", 3),
                         obs("c", "T1", "m", 4)])
    assert res["coverage"]["satisfied_ids"] == ["R1"]
    assert set(res["coverage"]["unsupported"]) == {"R2", "R3"}
    assert res["release_status"] == "RELEASE-UNREADY"


def test_all_supported_gives_evidence_supported_without_release_authority(qa):
    res = run(qa, [req("R1", [cond("T1", "m", ">=", 1)])], [obs("a", "T1", "m", 2)])
    assert res["release_status"] == "EVIDENCE-SUPPORTED"
    assert res["release_authority"] is False
    assert res["release_granted"] is False
    assert res["physical_test_claimed"] is False


@pytest.mark.parametrize("flag", [True, False, "yes", 1])
def test_caller_release_flag_cannot_grant_release(qa, flag):
    res = run(qa, [req("R1", [cond("T1", "m", ">=", 1)])], [], caller_release_requested=flag)
    assert res["release_status"] == "RELEASE-UNREADY"
    assert res["release_granted"] is False
    assert res["caller_release_flag_ignored"] is True


# ---------------- refuting, mismatch, conflict ----------------
def test_refuting_observation_wins_over_supporting_repeat(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 10)])],
              [obs("a", "T", "m", 11), obs("b", "T", "m", 9)])
    assert status_of(res, "R") == "REFUTED"
    assert res["release_status"] == "RELEASE-UNREADY"


def test_mismatched_metric_and_unmapped_test_ids_are_not_evidence(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 1)])],
              [obs("a", "T", "other_metric", 50), obs("b", "ZZ", "m", 50)])
    assert status_of(res, "R") == "MISSING"
    assert res["mismatched_observations"] == ["a"]
    assert res["unmapped_observations"] == ["b"]


def test_same_run_conflicting_values_are_unresolved(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 10)])],
              [obs("a", "T", "m", 11, run_id="r1"), obs("b", "T", "m", 3, run_id="r1")])
    assert status_of(res, "R") == "UNRESOLVED"
    assert res["conflicts"] == [{"test_id": "T", "metric": "m", "run_id": "r1",
                                 "observation_ids": ["a", "b"]}]
    assert res["release_status"] == "RELEASE-UNREADY"


def test_same_run_identical_values_are_not_a_conflict(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 10)])],
              [obs("a", "T", "m", 11, run_id="r1"), obs("b", "T", "m", 11, run_id="r1")])
    assert status_of(res, "R") == "SATISFIED"
    assert res["conflicts"] == []


def test_different_runs_do_not_conflict(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 10)])],
              [obs("a", "T", "m", 11, run_id="r1"), obs("b", "T", "m", 3, run_id="r2")])
    assert status_of(res, "R") == "REFUTED"
    assert res["conflicts"] == []


# ---------------- ALL vs ANY, min repeats ----------------
def test_all_mode_needs_every_condition(qa):
    r = req("R", [cond("T1", "m", ">=", 1), cond("T2", "m", ">=", 1)], mode="all")
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 2)]), "R") == "MISSING"
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 2), obs("b", "T2", "m", 2)]), "R") == "SATISFIED"
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 2), obs("b", "T2", "m", 0)]), "R") == "REFUTED"


def test_any_mode_needs_one_condition(qa):
    r = req("R", [cond("T1", "m", ">=", 1), cond("T2", "m", ">=", 1)], mode="any")
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 2)]), "R") == "SATISFIED"
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 0)]), "R") == "MISSING"
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 0), obs("b", "T2", "m", 0)]), "R") == "REFUTED"
    assert status_of(run(qa, [r], [obs("a", "T1", "m", 0), obs("b", "T2", "m", 5)]), "R") == "SATISFIED"


@pytest.mark.parametrize("k", [1, 2, 3, 5])
def test_min_repeats_exact_boundary(qa, k):
    r = req("R", [cond("T", "m", ">=", 1)], min_repeats=k)
    below = [obs(f"o{i}", "T", "m", 2) for i in range(k - 1)]
    at = [obs(f"o{i}", "T", "m", 2) for i in range(k)]
    assert status_of(run(qa, [r], below), "R") == "MISSING"
    assert status_of(run(qa, [r], at), "R") == "SATISFIED"


def test_repeats_in_same_run_count_once(qa):
    r = req("R", [cond("T", "m", ">=", 1)], min_repeats=2)
    res = run(qa, [r], [obs("a", "T", "m", 2, run_id="r1"), obs("b", "T", "m", 2, run_id="r1")])
    assert status_of(res, "R") == "MISSING"
    res = run(qa, [r], [obs("a", "T", "m", 2, run_id="r1"), obs("b", "T", "m", 2, run_id="r2")])
    assert status_of(res, "R") == "SATISFIED"


# ---------------- defective observations ----------------
@pytest.mark.parametrize("field,bad", [("signed", False), ("signed", None),
                                       ("source", None), ("source", ""), ("time", None)])
def test_defect_flag_policy_excludes_and_lists(qa, field, bad):
    o = obs("a", "T", "m", 5)
    if bad is None:
        del o[field]
    else:
        o[field] = bad
    res = run(qa, [req("R", [cond("T", "m", ">=", 1)])], [o], defect_policy="flag")
    assert status_of(res, "R") == "MISSING"
    assert len(res["defects"]) == 1 and res["defects"][0]["observation_id"] == "a"
    assert res["defects"][0]["field"] == field
    assert res["release_status"] == "RELEASE-UNREADY"


@pytest.mark.parametrize("field,bad", [("signed", False), ("source", ""), ("time", "not-a-time")])
def test_defect_refuse_policy_raises_exact_error(qa, field, bad):
    o = obs("fresh-id-7Zq", "T", "m", 5)
    o[field] = bad
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond("T", "m", ">=", 1)])], [o], defect_policy="refuse")
    assert str(ei.value) == f"observation fresh-id-7Zq defective: {field}"


def test_naive_time_is_defective(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 1)])],
              [obs("a", "T", "m", 5, time="2026-10-01T10:00:00")])
    assert res["defects"][0]["field"] == "time"


def test_z_suffix_time_accepted(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 1)])],
              [obs("a", "T", "m", 5, time="2026-10-01T10:00:00Z")])
    assert res["defects"] == [] and status_of(res, "R") == "SATISFIED"


# ---------------- bounds N / N+1 ----------------
def _reqs(n):
    return [req(f"R{i}", [cond("T", "m", ">=", 0)]) for i in range(n)]


def test_requirement_count_bounds(qa):
    run(qa, _reqs(64), [])
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, _reqs(65), [])
    assert str(ei.value) == "requirements must have 1..64 items"
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [], [])
    assert str(ei.value) == "requirements must have 1..64 items"


def test_observation_count_bounds(qa):
    r = [req("R", [cond("T", "m", ">=", 0)])]
    run(qa, r, [obs(f"o{i}", "T", "m", 1) for i in range(512)])
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, r, [obs(f"o{i}", "T", "m", 1) for i in range(513)])
    assert str(ei.value) == "observations must have 0..512 items"


def test_conditions_per_requirement_bounds(qa):
    run(qa, [req("R", [cond(f"T{i}", "m", ">=", 0) for i in range(16)])], [])
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond(f"T{i}", "m", ">=", 0) for i in range(17)])], [])
    assert str(ei.value) == "requirement R conditions must have 1..16 items"
    with pytest.raises(qa.QAEvidenceError):
        run(qa, [req("R", [])], [])


def test_min_repeats_bounds(qa):
    run(qa, [req("R", [cond("T", "m", ">=", 0)], min_repeats=16)], [])
    for bad in (0, 17, -1, True, 1.5, "2"):
        with pytest.raises(qa.QAEvidenceError) as ei:
            run(qa, [req("R", [cond("T", "m", ">=", 0)], min_repeats=bad)], [])
        assert str(ei.value) == "requirement R min_repeats must be an integer 1..16"


def test_id_length_bounds(qa):
    run(qa, [req("r" * 128, [cond("T", "m", ">=", 0)])], [])
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("r" * 129, [cond("T", "m", ">=", 0)])], [])
    assert str(ei.value) == "requirement id must be a non-empty string up to 128 chars"


# ---------------- fresh-ID exact errors ----------------
def test_duplicate_requirement_id_exact_error(qa):
    rid = "REQ-" + "".join(random.Random(7).choices("abcdefghij", k=9))
    r = req(rid, [cond("T", "m", ">=", 0)])
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [r, copy.deepcopy(r)], [])
    assert str(ei.value) == f"duplicate requirement id: {rid}"


def test_duplicate_observation_id_exact_error(qa):
    oid = "obs-Qx93"
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond("T", "m", ">=", 0)])],
            [obs(oid, "T", "m", 1), obs(oid, "T", "m", 2)])
    assert str(ei.value) == f"duplicate observation id: {oid}"


@pytest.mark.parametrize("op", ["~", "", None, "BETWEEN", 5])
def test_unknown_operator_exact_error(qa, op):
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("rq-91", [cond("T", "m", op, 1)])], [])
    assert str(ei.value) == "requirement rq-91 condition 0 op is not supported"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "3", None])
def test_bad_threshold_and_value_refused(qa, bad):
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("rq-5", [cond("T", "m", ">=", bad)])], [])
    assert str(ei.value) == "requirement rq-5 condition 0 threshold must be a finite number"
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond("T", "m", ">=", 1)])], [obs("ob-31", "T", "m", bad)])
    assert str(ei.value) == "observation ob-31 value must be a finite number"


def test_between_threshold_shape(qa):
    for bad in ([1], [3, 1], [1, 2, 3], 5, ["a", 2]):
        with pytest.raises(qa.QAEvidenceError) as ei:
            run(qa, [req("rq-2", [cond("T", "m", "between", bad)])], [])
        assert str(ei.value) == "requirement rq-2 condition 0 threshold must be [low, high] with low <= high"


def test_bad_mode_and_policy_and_shapes(qa):
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond("T", "m", ">=", 0)], mode="most")], [])
    assert str(ei.value) == "requirement R mode must be 'all' or 'any'"
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond("T", "m", ">=", 0)])], [], defect_policy="ignore")
    assert str(ei.value) == "defect_policy must be 'refuse' or 'flag'"
    for bad in (None, [], "x", 3):
        with pytest.raises(qa.QAEvidenceError) as ei:
            qa.evaluate_qa_evidence(bad)
        assert str(ei.value) == "request must be an object"
    with pytest.raises(qa.QAEvidenceError) as ei:
        qa.evaluate_qa_evidence(dict(requirements=_reqs(1), observations=[], defect_policy="flag", extra=1))
    assert str(ei.value) == "unknown request field: extra"


def test_observation_requires_id_and_value_types(qa):
    with pytest.raises(qa.QAEvidenceError) as ei:
        run(qa, [req("R", [cond("T", "m", ">=", 0)])], [dict(test_id="T")])
    assert str(ei.value) == "observation id must be a non-empty string up to 128 chars"


# ---------------- determinism ----------------
def test_unsorted_input_gives_identical_output(qa):
    rng = random.Random(1535)
    reqs = [req(f"R{i:02d}", [cond(f"T{i % 4}", "m", ">=", i % 3), cond("TX", "m", "<", 9)],
                mode=("any" if i % 2 else "all"), min_repeats=1 + i % 2) for i in range(12)]
    observations = [obs(f"o{i:03d}", f"T{i % 4}", "m", rng.choice([0, 1, 2, 3]),
                        run_id=f"r{i % 5}") for i in range(60)]
    observations.append(obs("ox", "TX", "m", 2))
    base = run(qa, reqs, observations)
    for seed in range(8):
        r2, o2 = reqs[:], observations[:]
        random.Random(seed).shuffle(r2)
        random.Random(seed + 100).shuffle(o2)
        assert run(qa, r2, o2) == base


def test_audit_trace_is_ordered_and_complete(qa):
    reqs = [req("B", [cond("T2", "m", ">=", 1)]), req("A", [cond("T1", "m", ">=", 1)])]
    res = run(qa, reqs, [obs("z", "T1", "m", 5), obs("y", "T2", "m", 0)])
    assert [e["requirement_id"] for e in res["audit_trace"]] == ["A", "B"]
    assert res["audit_trace"][0]["conditions"][0]["supporting"] == ["z"]
    assert res["audit_trace"][1]["conditions"][0]["refuting"] == ["y"]
    assert [r["id"] for r in res["requirements"]] == ["A", "B"]


def test_input_not_mutated_and_no_io(qa, monkeypatch):
    reqs = [req("R", [cond("T", "m", ">=", 1)])]
    observations = [obs("a", "T", "m", 2)]
    snap = copy.deepcopy((reqs, observations))
    import builtins
    import socket

    def boom(*a, **k):
        raise AssertionError("io attempted")
    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(socket, "socket", boom)
    run(qa, reqs, observations)
    assert (reqs, observations) == snap


def test_result_states_no_physical_test_claim_and_no_persistence(qa):
    res = run(qa, [req("R", [cond("T", "m", ">=", 1)])], [obs("a", "T", "m", 2)])
    assert res["physical_test_claimed"] is False
    assert res["persisted"] is False and res["effects"] == []
    assert "supplied observations" in res["basis"]


def test_duplicate_condition_ids_across_requirements_share_evidence(qa):
    reqs = [req("R1", [cond("T", "m", ">=", 1)]), req("R2", [cond("T", "m", ">=", 5)])]
    res = run(qa, reqs, [obs("a", "T", "m", 3)])
    assert status_of(res, "R1") == "SATISFIED" and status_of(res, "R2") == "REFUTED"
