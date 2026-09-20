"""Tests for the M12 evaluation harness."""

import pytest

from app.modules.m12_ai_research_lab.lane_evaluation import (
    run_check, run_evaluation,
)
from app.modules.m12_ai_research_lab.lane_models import EvalCase


def case(cid, inp, *checks):
    return EvalCase(case_id=cid, input=inp, checks=tuple(checks))


def test_all_check_types():
    assert run_check("hello world", {"type": "exact", "value": "hello world"}).passed
    assert not run_check("hello", {"type": "exact", "value": "world"}).passed
    assert run_check({"a": 1}, {"type": "json_equals", "value": {"a": 1}}).passed
    assert not run_check({"a": 1}, {"type": "json_equals", "value": {"a": 2}}).passed
    assert run_check("abcdef", {"type": "contains", "value": "cde"}).passed
    assert not run_check("abc", {"type": "contains", "value": "z"}).passed
    assert run_check("clean", {"type": "not_contains", "value": "bad"}).passed
    assert not run_check("bad actor", {"type": "not_contains", "value": "bad"}).passed
    assert run_check("abc123", {"type": "regex", "pattern": r"\d+"}).passed
    assert not run_check("abc", {"type": "regex", "pattern": r"\d+"}).passed
    assert run_check(3.14, {"type": "numeric", "value": 3.0, "tolerance": 0.2}).passed
    assert not run_check(3.14, {"type": "numeric", "value": 3.0, "tolerance": 0.1}).passed
    assert run_check("x", {"type": "type", "value": "str"}).passed
    assert run_check(True, {"type": "type", "value": "bool"}).passed
    assert not run_check(True, {"type": "type", "value": "int"}).passed  # bool is not int here


def test_invalid_checks_fail_loudly_not_crash():
    r = run_check("x", {"type": "regex", "pattern": "["})
    assert not r.passed and "invalid regex" in r.detail
    r = run_check("x", {"type": "nope"})
    assert not r.passed and "unsupported" in r.detail
    r = run_check("x", {"type": "type", "value": "wat"})
    assert not r.passed and "unknown type" in r.detail


def test_runner_exception_fails_case_without_aborting_suite():
    def runner(inp):
        if inp == "explode":
            raise RuntimeError("kaput")
        return "fine"

    cases = (
        case("a-ok", "ok", {"type": "exact", "value": "fine"}),
        case("b-bad", "explode", {"type": "exact", "value": "fine"}),
        case("c-ok", "ok", {"type": "exact", "value": "fine"}),
    )
    rep = run_evaluation(cases, runner, eval_id="e1",
                         created_at_utc="2026-09-20T00:00:00+00:00")
    assert rep.total == 3 and rep.passed == 2 and rep.failed == 1
    bad = [r for r in rep.case_results if r.case_id == "b-bad"][0]
    assert "runner raised" in bad.checks[0].detail
    assert "kaput" in bad.checks[0].detail


def test_report_is_deterministic_regardless_of_case_order():
    cases = [
        case("z", 1, {"type": "numeric", "value": 1}),
        case("a", 2, {"type": "numeric", "value": 2}),
        case("m", 3, {"type": "numeric", "value": 3}),
    ]
    r1 = run_evaluation(cases, lambda x: x, eval_id="e",
                        created_at_utc="2026-09-20T00:00:00+00:00")
    r2 = run_evaluation(list(reversed(cases)), lambda x: x, eval_id="e",
                        created_at_utc="2026-09-20T00:00:00+00:00")
    assert r1.digest() == r2.digest()
    assert [c.case_id for c in r1.case_results] == ["a", "m", "z"]
    assert r1.pass_rate == 1.0


def test_output_hashes_stable():
    rep1 = run_evaluation((case("a", "in", {"type": "contains", "value": "x"}),),
                          lambda i: {"answer": "xyz"}, eval_id="e",
                          created_at_utc="2026-09-20T00:00:00+00:00")
    rep2 = run_evaluation((case("a", "in", {"type": "contains", "value": "x"}),),
                          lambda i: {"answer": "xyz"}, eval_id="e",
                          created_at_utc="2026-09-20T00:00:00+00:00")
    assert rep1.case_results[0].output_hash == rep2.case_results[0].output_hash
    assert rep1.digest() == rep2.digest()


def test_multi_check_case_fails_if_any_check_fails():
    c = case("a", "hello", {"type": "contains", "value": "hell"},
             {"type": "contains", "value": "nope"})
    rep = run_evaluation((c,), lambda x: x, eval_id="e",
                         created_at_utc="2026-09-20T00:00:00+00:00")
    assert rep.failed == 1
    results = rep.case_results[0].checks
    assert results[0].passed and not results[1].passed


def test_case_validation():
    with pytest.raises(ValueError):
        EvalCase(case_id="", input=1, checks=({"type": "exact", "value": 1},))
    with pytest.raises(ValueError):
        EvalCase(case_id="a", input=1, checks=())
