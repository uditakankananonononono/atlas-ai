"""Local comparison observes execution without supplied scores or victories."""
import subprocess
import pytest
from app.modules.instinct_doc.executed_comparison import compare_selected_tests
from app.modules.instinct_doc.repo_evidence import EvidenceError


@pytest.fixture
def repo(tmp_path):
    def git(*a): subprocess.run(['git', '-C', str(tmp_path), *a], check=True, capture_output=True)
    git('init', '-q'); git('config', 'user.name', 'test'); git('config', 'user.email', 'test@example.invalid')
    git('remote', 'add', 'origin', 'https://example.invalid/repo')
    (tmp_path / 'tests').mkdir()
    for name, assertion in [('a', 'True'), ('b', 'True'), ('fail', 'False')]:
        (tmp_path / ('tests/test_' + name + '.py')).write_text('def test_run(): assert ' + assertion)
    git('add', '.'); git('commit', '-qm', 'fixture')
    return tmp_path


def test_repeated_actual_timings_no_victory(repo):
    result = compare_selected_tests(repo, [{'id':'a','test_paths':['tests/test_a.py']}, {'id':'b','test_paths':['tests/test_b.py']}], repeats=2)
    assert all(row['status'] == 'SCOPED_PASS' and row['median_seconds'] > 0 for row in result['subjects'])
    assert all(len(row['runs']) == 2 for row in result['subjects'])
    assert result['winner'] is None and not result['benchmark_victory_verified']


def test_failed_comparator_cannot_rank(repo):
    result = compare_selected_tests(repo, [{'id':'a','test_paths':['tests/test_a.py']}, {'id':'bad','test_paths':['tests/test_fail.py']}], repeats=1)
    assert result['subjects'][1]['status'] == 'UNVERIFIED'
    assert result['subjects'][1]['median_seconds'] is None


def test_supplied_score_and_repeat_bounds_refused(repo):
    with pytest.raises(EvidenceError): compare_selected_tests(repo, [{'id':'a','test_paths':[], 'score':1}, {'id':'b','test_paths':[]}])
    with pytest.raises(EvidenceError): compare_selected_tests(repo, [], repeats=0)


def test_invalid_later_subject_does_not_execute(repo, monkeypatch):
    from app.modules.instinct_doc import executed_comparison as mod
    calls=[]
    monkeypatch.setattr(mod,'execute_tests',lambda *a,**k:calls.append(a))
    with pytest.raises(EvidenceError):
        mod.compare_selected_tests(repo,[{'id':'ok','test_paths':['tests/test_a.py']},{'id':'bad','test_paths':['missing']}])
    assert calls==[]


def test_cross_subject_drift_and_bad_duration_unverified(repo, monkeypatch):
    from app.modules.instinct_doc import executed_comparison as mod
    from app.modules.instinct_doc.repo_evidence import snapshot
    snap=snapshot(repo);calls=[]
    def injected(*args):
        calls.append(1)
        return {'head':snap['head'],'tree_digest':snap['tree_digest'] if len(calls)==1 else 'drift','status':'SCOPED_PASS','duration_seconds':1}
    monkeypatch.setattr(mod,'execute_tests',injected)
    out=mod.compare_selected_tests(repo,[{'id':'a','test_paths':['tests/test_a.py']},{'id':'b','test_paths':['tests/test_b.py']}],repeats=1)
    assert not out['cross_subject_coherent']
    assert all(r['status']=='UNVERIFIED' and r['median_seconds'] is None for r in out['subjects'])
    monkeypatch.setattr(mod,'execute_tests',lambda *a:{'head':snap['head'],'tree_digest':snap['tree_digest'],'status':'SCOPED_PASS','duration_seconds':float('nan')})
    out=mod.compare_selected_tests(repo,[{'id':'a','test_paths':['tests/test_a.py']},{'id':'b','test_paths':['tests/test_b.py']}],repeats=1)
    assert all(r['status']=='UNVERIFIED' for r in out['subjects'])


def test_helper_exception_keeps_bounded_failure(repo, monkeypatch):
    from app.modules.instinct_doc import executed_comparison as mod
    def failed(*a):raise RuntimeError('injected failure')
    monkeypatch.setattr(mod,'execute_tests',failed)
    out=mod.compare_selected_tests(repo,[{'id':'a','test_paths':['tests/test_a.py']},{'id':'b','test_paths':['tests/test_b.py']}],repeats=1)
    assert all(r['status']=='UNVERIFIED' for r in out['subjects'])
    assert not out['aggregate_budget_enforced'] and not out['execution_is_sandboxed']


@pytest.mark.parametrize('repeats',[True,-1,0,6])
def test_repeat_bounds(repo,repeats):
    with pytest.raises(EvidenceError):compare_selected_tests(repo,[{'id':'a','test_paths':['tests/test_a.py']},{'id':'b','test_paths':['tests/test_b.py']}],repeats=repeats)
