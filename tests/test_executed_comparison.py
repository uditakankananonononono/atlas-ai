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
