"""Project-indexed source counts and executed tests, not supplied totals."""
import subprocess
import pytest
from app.modules.instinct_doc.code_test_summary_p256 import inspect_projects


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init', '-q'); git('config', 'user.name', 'test'); git('config', 'user.email', 'test@example.invalid')
    git('remote', 'add', 'origin', 'https://example.invalid/project')
    (tmp_path / 'core.py').write_text('x=1\ny=2\n')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_ok.py').write_text('def test_ok(): assert 1 == 1\n')
    git('add', '.'); git('commit', '-qm', 'fixture')
    return tmp_path, {'id': 'P1', 'code_paths': ['core.py'], 'test_paths': ['tests/test_ok.py']}


def test_counts_read_from_bytes_without_execution(repo):
    root, item = repo
    row = inspect_projects(root, [item])['projects'][0]
    assert row['code_files'] == 1 and row['code_lines'] == 2
    assert row['test_files'] == 1 and row['test_lines'] == 1
    assert row['execution'] is None and row['status'] == 'UNVERIFIED'
    assert row['coverage_percent'] is None and not row['completion_verified']


def test_selected_project_tests_execute(repo):
    root, item = repo
    row = inspect_projects(root, [item], execute=True)['projects'][0]
    assert row['status'] == 'SCOPED_PASS'
    assert row['execution']['counts']['tests'] == 1
    assert not row['completion_verified']


def test_missing_path_preserves_gap(repo):
    root, item = repo
    item['code_paths'] = ['absent']
    row = inspect_projects(root, [item], execute=True)['projects'][0]
    assert row['status'] == 'UNVERIFIED' and row['errors']
    assert row['execution'] is None


def test_supplied_statistics_or_duplicates_refused(repo):
    root, item = repo
    with pytest.raises(ValueError): inspect_projects(root, [item, item])
    item['code_lines'] = 999
    with pytest.raises(ValueError): inspect_projects(root, [item])
