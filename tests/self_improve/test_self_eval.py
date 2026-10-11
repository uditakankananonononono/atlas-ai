import json
import sys
from pathlib import Path

import pytest

from app.self_improve.engine import SelfImprovementEngine
from app.self_improve import self_eval as se
from app.self_improve.self_eval import (
    Case, Probe, ModuleSelfEvaluator, SelfEvalError, NO_EXPECT, run_pytest)


class Clock:
    def __init__(self, step=0.0):
        self.t = 0.0
        self.step = step

    def __call__(self):
        v = self.t
        self.t += self.step
        return v


def ev(tmp_path, clock=None, **kw):
    return ModuleSelfEvaluator("mod-a", tmp_path / "st", clock=clock or Clock(0.01),
                               now=lambda: 1000.0, **kw)


def good():
    return Probe("double", lambda x: x * 2, (Case(args=(2,), expect=4), Case(args=(5,), expect=10)))


def test_pass_counts_and_rate(tmp_path):
    r = ev(tmp_path).evaluate([good()])
    assert (r.total_cases, r.passed, r.failed, r.errored) == (2, 2, 0, 0)
    assert r.pass_rate == 1.0 and r.regressions == () and r.baseline_at is None
    assert r.probes[0].name == "double" and r.module_slug == "mod-a" and r.at == 1000.0


def test_fail_vs_error_split(tmp_path):
    def boom(x):
        if x == 1:
            raise KeyError("k")
        return x
    p = Probe("p", boom, (Case(args=(1,)), Case(args=(2,), expect=3), Case(args=(3,), expect=3)))
    r = ev(tmp_path).evaluate([p])
    pr = r.probes[0]
    assert (pr.passed, pr.failed, pr.errored) == (1, 1, 1)
    assert pr.error_types == ("KeyError",)
    assert r.pass_rate == pytest.approx(1 / 3)


def test_check_callable_and_check_error(tmp_path):
    p = Probe("p", lambda: [1, 2], (Case(check=lambda v: len(v) == 2), Case(check=lambda v: len(v) == 3),
                                    Case(check=lambda v: 1 / 0)))
    pr = ev(tmp_path).evaluate([p]).probes[0]
    assert (pr.passed, pr.failed, pr.errored) == (1, 1, 1)
    assert pr.error_types == ("ZeroDivisionError",)


def test_no_expect_passes_if_no_raise(tmp_path):
    p = Probe("p", lambda: None, (Case(),))
    assert ev(tmp_path).evaluate([p]).passed == 1
    assert Case().expect is NO_EXPECT


def test_expect_none_is_a_real_expectation(tmp_path):
    p = Probe("p", lambda: 1, (Case(expect=None),))
    assert ev(tmp_path).evaluate([p]).failed == 1
    p2 = Probe("p", lambda: None, (Case(expect=None),))
    assert ev(tmp_path).evaluate([p2]).passed == 1


def test_kwargs_passed(tmp_path):
    p = Probe("p", lambda a, b=0: a - b, (Case(args=(5,), kwargs={"b": 2}, expect=3),))
    assert ev(tmp_path).evaluate([p]).passed == 1


def test_latency_from_clock(tmp_path):
    r = ev(tmp_path, Clock(0.5)).evaluate([good()])
    assert r.probes[0].median_latency_s == pytest.approx(0.5)
    assert r.probes[0].max_latency_s == pytest.approx(0.5)


def test_latency_median_and_max(tmp_path):
    seq = iter([0, 1, 0, 3, 0, 2])
    p = Probe("p", lambda: 1, (Case(), Case(), Case()))
    r = ModuleSelfEvaluator("mod-a", tmp_path / "s", clock=lambda: next(seq)).evaluate([p])
    assert r.probes[0].median_latency_s == 2 and r.probes[0].max_latency_s == 3


def test_validation_errors(tmp_path):
    with pytest.raises(ValueError):
        Probe("", lambda: 1, (Case(),))
    with pytest.raises(ValueError):
        Probe("p", lambda: 1, ())
    with pytest.raises(ValueError):
        Case(expect=1, check=lambda v: True)
    e = ev(tmp_path)
    with pytest.raises(ValueError):
        e.evaluate([])
    with pytest.raises(ValueError):
        e.evaluate([good(), good()])
    with pytest.raises(ValueError):
        ModuleSelfEvaluator("bad/slug", tmp_path)
    with pytest.raises(ValueError):
        ModuleSelfEvaluator("", tmp_path)
    assert issubclass(SelfEvalError, ValueError)


def test_history_appended_and_baseline_used(tmp_path):
    e = ev(tmp_path)
    e.evaluate([good()])
    r2 = e.evaluate([good()])
    assert r2.baseline_at == 1000.0 and r2.regressions == ()
    h = e.history()
    assert len(h) == 2 and h[0]["probes"][0]["name"] == "double"
    f = Path(tmp_path / "st" / "mod-a.self-eval.jsonl")
    assert len(f.read_text().splitlines()) == 2


def test_probe_regressed(tmp_path):
    e = ev(tmp_path)
    e.evaluate([good()])
    bad = Probe("double", lambda x: x + 2, (Case(args=(2,), expect=4), Case(args=(5,), expect=10)))
    r = e.evaluate([bad])
    assert [(g.probe, g.reason) for g in r.regressions] == [("double", "probe_regressed")]


def test_already_failing_baseline_is_not_regression(tmp_path):
    e = ev(tmp_path)
    bad = Probe("double", lambda x: x + 2, (Case(args=(5,), expect=10),))
    e.evaluate([bad])
    assert e.evaluate([bad]).regressions == ()


def test_probe_missing(tmp_path):
    e = ev(tmp_path)
    other = Probe("other", lambda: 1, (Case(),))
    e.evaluate([good(), other])
    r = e.evaluate([good()])
    assert [(g.probe, g.reason) for g in r.regressions] == [("other", "probe_missing")]


def test_latency_regression_factor_and_abs(tmp_path):
    base = ev(tmp_path, Clock(0.1))
    base.evaluate([good()])
    slow = ModuleSelfEvaluator("mod-a", tmp_path / "st", clock=Clock(0.5), now=lambda: 2000.0)
    r = slow.evaluate([good()])
    assert [(g.probe, g.reason) for g in r.regressions] == [("double", "latency_regressed")]
    assert r.baseline_at == 1000.0


def test_latency_exactly_at_factor_not_regression(tmp_path):
    ev(tmp_path, Clock(0.25)).evaluate([good()])
    r = ModuleSelfEvaluator("mod-a", tmp_path / "st", clock=Clock(0.75)).evaluate([good()])
    assert r.regressions == ()
    ModuleSelfEvaluator("mod-a", tmp_path / "st2", clock=Clock(0.25)).evaluate([good()])
    r = ModuleSelfEvaluator("mod-a", tmp_path / "st2", clock=Clock(0.8125)).evaluate([good()])
    assert [g.reason for g in r.regressions] == ["latency_regressed"]


def test_latency_below_abs_floor_not_regression(tmp_path):
    ev(tmp_path, Clock(0.0001)).evaluate([good()])
    r = ModuleSelfEvaluator("mod-a", tmp_path / "st", clock=Clock(0.0009)).evaluate([good()])
    assert r.regressions == ()


def test_corrupt_history_raises(tmp_path):
    e = ev(tmp_path)
    e.evaluate([good()])
    with open(tmp_path / "st" / "mod-a.self-eval.jsonl", "a") as fh:
        fh.write("{not json\n")
    with pytest.raises(SelfEvalError):
        e.history()
    with pytest.raises(SelfEvalError):
        e.evaluate([good()])


def test_to_dict_json_safe(tmp_path):
    r = ev(tmp_path).evaluate([good()])
    d = r.to_dict()
    json.dumps(d)
    assert d["pass_rate"] == 1.0 and d["module_slug"] == "mod-a" and d["pytest"] is None
    assert d["probes"][0]["error_types"] == []


def test_pass_rate_none_never_with_probes(tmp_path):
    assert ev(tmp_path).evaluate([good()]).pass_rate is not None


def test_record_gaps_into_real_engine(tmp_path):
    e = ev(tmp_path)
    eng = SelfImprovementEngine(module_id=1, module_slug="mod-a", state_dir=tmp_path / "eng")
    bad = Probe("double", lambda x: x + 2, (Case(args=(3,), expect=6),))
    e.evaluate([good()])
    r = e.evaluate([bad])
    evs = e.record_gaps(r, eng)
    sigs = sorted(x.signature for x in evs)
    assert sigs == ["selfeval:double:failing", "selfeval:double:probe_regressed"]
    stored = eng.store.all("mod-a")
    assert sorted(s.signature for s in stored) == sigs
    assert all(s.kind == "repeated_error" for s in stored)
    assert any("failed=1" in s.detail for s in stored)
    # twice gives the detector its recurrence
    e.record_gaps(r, eng)
    assert {g.signature for g in eng.detector.detect("mod-a")} == set(sigs)


def test_record_gaps_latency_kind_and_clean_report(tmp_path):
    class Rec:
        def __init__(self): self.calls = []
        def record_gap(self, signature, *, kind, detail, exemplar):
            self.calls.append((signature, kind)); return signature
    ev(tmp_path, Clock(0.1)).evaluate([good()])
    slow = ModuleSelfEvaluator("mod-a", tmp_path / "st", clock=Clock(1.0)).evaluate([good()])
    rec = Rec()
    ev(tmp_path).record_gaps(slow, rec)
    assert rec.calls == [("selfeval:double:latency_regressed", "capability_miss")]
    clean = ev(tmp_path).evaluate([good()])
    rec2 = Rec()
    assert ev(tmp_path).record_gaps(clean, rec2) == [] and rec2.calls == []


def test_pytest_failure_signature(tmp_path):
    class Rec:
        def __init__(self): self.calls = []
        def record_gap(self, signature, *, kind, detail, exemplar):
            self.calls.append((signature, kind)); return 1
    pr = se.PytestResult(returncode=1, passed=2, failed=1, errors=0, duration_s=0.1, tail="x")
    r = ev(tmp_path).evaluate([good()], pytest_result=pr)
    assert r.pytest == pr and r.to_dict()["pytest"]["failed"] == 1
    rec = Rec(); ev(tmp_path).record_gaps(r, rec)
    assert rec.calls == [("selfeval:pytest:failing", "repeated_error")]
    ok = se.PytestResult(0, 3, 0, 0, 0.1, "")
    rec2 = Rec(); ev(tmp_path).record_gaps(ev(tmp_path).evaluate([good()], pytest_result=ok), rec2)
    assert rec2.calls == []


def _mk_tests(d, body):
    d.mkdir(parents=True, exist_ok=True)
    (d / "test_x.py").write_text(body)


def test_run_pytest_real_pass_and_fail(tmp_path):
    _mk_tests(tmp_path / "ok", "def test_a():\n    assert True\ndef test_b():\n    assert 1 == 1\n")
    r = run_pytest(["test_x.py"], cwd=tmp_path / "ok")
    assert (r.returncode, r.passed, r.failed, r.errors) == (0, 2, 0, 0) and r.duration_s >= 0
    _mk_tests(tmp_path / "bad", "def test_a():\n    assert True\ndef test_b():\n    assert 1 == 2\ndef test_c():\n    raise_it\n")
    r = run_pytest(["test_x.py"], cwd=tmp_path / "bad")
    assert r.returncode == 1 and r.passed == 1 and r.failed == 2
    assert "test_b" in r.tail


def test_run_pytest_collection_error_and_unparseable(tmp_path):
    _mk_tests(tmp_path / "ce", "import nonexistent_zzz\n")
    r = run_pytest(["test_x.py"], cwd=tmp_path / "ce")
    assert r.returncode != 0 and r.errors == 1
    (tmp_path / "empty").mkdir()
    r = run_pytest(["nothing.py"], cwd=tmp_path / "empty")
    assert r.returncode != 0 and r.passed is None


def test_run_pytest_timeout(tmp_path):
    _mk_tests(tmp_path / "slow", "import time\ndef test_a():\n    time.sleep(5)\n")
    with pytest.raises(SelfEvalError):
        run_pytest(["test_x.py"], cwd=tmp_path / "slow", timeout=1)


def test_run_pytest_rejects_bad_args(tmp_path):
    with pytest.raises(ValueError):
        run_pytest([], cwd=tmp_path)
    with pytest.raises(ValueError):
        run_pytest(["-x; rm"], cwd=tmp_path)


def test_stdlib_only():
    import re
    src = Path(se.__file__).read_text()
    mods = set(re.findall(r"^(?:from|import)\s+([A-Za-z_]\w*)", src, re.M))
    assert mods <= {"__future__", "dataclasses", "json", "math", "re", "statistics", "subprocess",
                    "sys", "time", "os", "pathlib", "typing", "collections"}
    assert "requests" not in src and "socket" not in src


def test_check_true_only_passes(tmp_path):
    p = Probe("p", lambda: 1, (Case(check=lambda v: True),))
    pr = ev(tmp_path).evaluate([p]).probes[0]
    assert (pr.passed, pr.failed) == (1, 0)
    p = Probe("p", lambda: 1, (Case(check=lambda v: False),))
    pr = ev(tmp_path).evaluate([p]).probes[0]
    assert (pr.passed, pr.failed) == (0, 1)


def test_baseline_is_most_recent_not_first(tmp_path):
    e = ev(tmp_path)
    e.evaluate([good()])
    bad = Probe("double", lambda x: x + 2, (Case(args=(5,), expect=10),))
    assert [g.reason for g in e.evaluate([bad]).regressions] == ["probe_regressed"]
    assert e.evaluate([bad]).regressions == ()


def test_baseline_errored_not_clean(tmp_path):
    e = ev(tmp_path)
    def boom(x): raise RuntimeError("x")
    e.evaluate([Probe("p", boom, (Case(args=(1,)),))])
    r = e.evaluate([Probe("p", lambda x: x, (Case(args=(1,), expect=2),))])
    assert r.regressions == ()


def test_clean_to_errored_only_is_regression(tmp_path):
    e = ev(tmp_path)
    e.evaluate([Probe("p", lambda x: x, (Case(args=(1,), expect=1),))])
    def boom(x): raise RuntimeError("x")
    r = e.evaluate([Probe("p", boom, (Case(args=(1,), expect=1),))])
    assert [g.reason for g in r.regressions] == ["probe_regressed"]


def test_new_probe_not_in_baseline_is_ignored(tmp_path):
    e = ev(tmp_path)
    e.evaluate([good()])
    r = e.evaluate([good(), Probe("newp", lambda: 1, (Case(expect=2),))])
    assert r.regressions == () and r.failed == 1


def test_errored_only_probe_emits_failing_gap(tmp_path):
    class Rec:
        def __init__(self): self.calls = []
        def record_gap(self, signature, *, kind, detail, exemplar):
            self.calls.append((signature, kind, exemplar)); return 1
    def boom(): raise ValueError("x")
    r = ev(tmp_path).evaluate([Probe("p", boom, (Case(),))])
    rec = Rec(); ev(tmp_path).record_gaps(r, rec)
    assert [(c[0], c[1]) for c in rec.calls] == [("selfeval:p:failing", "repeated_error")]
    assert rec.calls[0][2]["error_types"] == ["ValueError"]


def test_pytest_tail_keeps_end_and_is_bounded(tmp_path):
    _mk_tests(tmp_path / "long", "def test_a():\n    print('A' * 6000)\n    assert 1 == 2\n")
    r = run_pytest(["test_x.py"], cwd=tmp_path / "long")
    assert len(r.tail) <= 2000 and "1 failed" in r.tail[-200:]


def test_pytest_subprocess_has_no_aws_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SELFEVAL_PROBE", "x")
    _mk_tests(tmp_path / "env", "import os\ndef test_a():\n    assert 'AWS_SELFEVAL_PROBE' not in os.environ\n")
    r = run_pytest(["test_x.py"], cwd=tmp_path / "env")
    assert r.returncode == 0 and r.passed == 1


def test_slug_rules(tmp_path):
    for bad in ("a b", "a.b", "../x", "a/b"):
        with pytest.raises(ValueError):
            ModuleSelfEvaluator(bad, tmp_path)
    ModuleSelfEvaluator("a-b_c1", tmp_path)
