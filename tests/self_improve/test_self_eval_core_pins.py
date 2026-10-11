"""Tests-only pins for independently reported C6 core survivors."""
from dataclasses import FrozenInstanceError
import inspect
import json
import sys
import time

import pytest
from app.self_improve import self_eval as se


@pytest.mark.parametrize('value,field', [
    (se.Case(), 'args'),
    (se.Probe('probe', lambda: 1, (se.Case(),)), 'name'),
    (se.ProbeResult('probe', 1, 1, 0, 0, .1, .1, ()), 'name'),
    (se.Regression('probe', 'reason', 'detail'), 'probe'),
    (se.PytestResult(0, 1, 0, 0, .1, 'tail'), 'tail'),
    (se.EvalReport('module', 1, (), 0, 0, 0, 0, None, (), None, None), 'module_slug'),
])
def test_all_six_records_are_frozen(value, field):
    original = getattr(value, field)
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, original)
    assert getattr(value, field) == original


def probe():
    return se.Probe('probe', lambda: 1, (se.Case(expect=1),))


def clock_for(duration):
    ticks = iter((0.0, duration))
    return lambda: next(ticks)


def test_existing_and_nested_state_directory(tmp_path):
    existing = tmp_path / 'existing'
    existing.mkdir()
    first = se.ModuleSelfEvaluator('module', existing)
    first.evaluate([probe()])
    second = se.ModuleSelfEvaluator('module', existing)
    assert len(second.history()) == 1
    nested = tmp_path / 'new' / 'nested' / 'state'
    assert not nested.exists()
    third = se.ModuleSelfEvaluator('module', nested)
    assert nested.is_dir()
    assert third.history() == []


@pytest.mark.parametrize('corrupt_line', [1, 3])
def test_corrupt_history_exact_one_based_line(tmp_path, corrupt_line):
    evaluator = se.ModuleSelfEvaluator('module', tmp_path)
    path = tmp_path / 'module.self-eval.jsonl'
    path.write_text('{}\n' * (corrupt_line - 1) + '{not JSON\n', encoding='utf-8')
    with pytest.raises(se.SelfEvalError, match=r'^corrupt history line ' + str(corrupt_line) + r':'):
        evaluator.history()


def test_stored_json_exact_sorted_keys(tmp_path):
    evaluator = se.ModuleSelfEvaluator('module', tmp_path, now=lambda: 123.0, clock=clock_for(.25))
    report = evaluator.evaluate([probe()], pytest_result=se.PytestResult(0, 1, 0, 0, .2, 'x'))
    raw = (tmp_path / 'module.self-eval.jsonl').read_text(encoding='utf-8')
    assert raw == json.dumps(report.to_dict(), sort_keys=True) + '\n'
    assert json.loads(raw) == report.to_dict()


@pytest.mark.parametrize('current,expected', [(.375, False), (.375 - 2**-20, False), (.375 + 2**-20, True)])
def test_latency_absolute_slack_boundary(tmp_path, current, expected):
    # Exact binary fractions: factor test passes in every case. Only absolute
    # latency difference decides, catching +/- and > versus >= mutations.
    baseline = se.ModuleSelfEvaluator('module', tmp_path, latency_factor=1.0,
                                     latency_min_abs_s=.25, clock=clock_for(.125))
    baseline.evaluate([probe()])
    evaluator = se.ModuleSelfEvaluator('module', tmp_path, latency_factor=1.0,
                                      latency_min_abs_s=.25, clock=clock_for(current))
    report = evaluator.evaluate([probe()])
    assert bool(report.regressions) is expected
    assert [r.reason for r in report.regressions] == (['latency_regressed'] if expected else [])


def test_init_optional_parameters_keyword_only(tmp_path):
    with pytest.raises(TypeError):
        se.ModuleSelfEvaluator('module', tmp_path, 3.0)
    signature = inspect.signature(se.ModuleSelfEvaluator)
    assert signature.parameters['latency_factor'].kind is inspect.Parameter.KEYWORD_ONLY


def test_evaluate_pytest_result_keyword_only(tmp_path):
    evaluator = se.ModuleSelfEvaluator('module', tmp_path)
    with pytest.raises(TypeError):
        evaluator.evaluate([probe()], None)
    assert inspect.signature(evaluator.evaluate).parameters['pytest_result'].kind is inspect.Parameter.KEYWORD_ONLY


def test_run_pytest_cwd_keyword_only(tmp_path):
    with pytest.raises(TypeError):
        se.run_pytest(['test_x.py'], tmp_path)
    assert inspect.signature(se.run_pytest).parameters['cwd'].kind is inspect.Parameter.KEYWORD_ONLY


def test_timeout_default_exactly_120():
    assert inspect.signature(se.run_pytest).parameters['timeout'].default == 120


@pytest.mark.parametrize('path', [None, 1, True])
def test_nonstring_pytest_path_refused_before_process(tmp_path, path, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('invalid path reached subprocess')
    monkeypatch.setattr(se.subprocess, 'run', unexpected)
    with pytest.raises(ValueError, match='paths must be non-empty strings'):
        se.run_pytest([path], cwd=tmp_path)


def test_real_duration_positive_approximately_sleep(tmp_path):
    (tmp_path / 'test_sleep.py').write_text('import time\ndef test_sleep():\n    time.sleep(0.3)\n', encoding='utf-8')
    start = time.perf_counter()
    result = se.run_pytest(['test_sleep.py'], cwd=tmp_path, python=sys.executable)
    elapsed = time.perf_counter() - start
    assert result.returncode == 0
    assert result.duration_s > 0
    assert result.duration_s >= .3
    assert result.duration_s == pytest.approx(elapsed, abs=.15)
    # Startup overhead is environment-dependent, so no brittle sleep-only upper bound.


def test_real_output_tail_exactly_2000(tmp_path):
    (tmp_path / 'test_tail.py').write_text("def test_tail():\n    print('A' * 7000 + 'TAIL_SENTINEL')\n    assert False\n", encoding='utf-8')
    result = se.run_pytest(['test_tail.py'], cwd=tmp_path, python=sys.executable)
    assert result.returncode == 1
    assert len(result.tail) == 2000
    assert 'TAIL_SENTINEL' in result.tail
    assert '1 failed' in result.tail
