"""Task-indexed change evidence with source-hash binding."""
from pathlib import Path
import subprocess
import pytest
from app.modules.instinct_doc.repo_evidence import EvidenceError, source_inventory, task_progress


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args])
    git('init', '-q')
    git('config', 'user.name', 'test')
    git('config', 'user.email', 'test@example.invalid')
    git('remote', 'add', 'origin', 'https://example.invalid/repo')
    (tmp_path / 'source.txt').write_text('task source\n')
    (tmp_path / 'code.py').write_text('x=1\n')
    git('add', '.')
    git('commit', '-qm', 'fixture')
    line = source_inventory(tmp_path, 'source.txt')['rows'][0]
    selector = {'task_id': 'TASK-1', 'line_id': line['id'], 'line_sha256': line['sha256'], 'paths': ['code.py']}
    return tmp_path, selector


def test_task_commit_changes_computed(repo):
    root, selector = repo
    result = task_progress(root, 'source.txt', [selector])
    task = result['tasks'][0]
    assert task['status'] == 'CHANGE_OBSERVED'
    assert task['events'][0]['changed_paths'] == ['code.py']
    assert not task['completion_verified']
    assert task['current_files']['code.py']['bytes'] == 4


def test_stale_source_hash_refused(repo):
    root, selector = repo
    selector['line_sha256'] = '0' * 64
    with pytest.raises(EvidenceError, match='source hash'):
        task_progress(root, 'source.txt', [selector])


@pytest.mark.parametrize('path', ['../outside', '/etc/passwd', 'absent.py'])
def test_bad_paths_refused(repo, path):
    root, selector = repo
    selector['paths'] = [path]
    with pytest.raises(EvidenceError):
        task_progress(root, 'source.txt', [selector])


def test_duplicate_task_or_supplied_done_refused(repo):
    root, selector = repo
    with pytest.raises(EvidenceError, match='duplicate'):
        task_progress(root, 'source.txt', [selector, selector])
    selector['status'] = 'done'
    with pytest.raises(EvidenceError, match='exact'):
        task_progress(root, 'source.txt', [selector])


def test_untracked_selector_refused(repo):
    root, selector = repo
    (root / 'new.py').write_text('x=2')
    selector['paths'] = ['new.py']
    with pytest.raises(EvidenceError, match='tracked'):
        task_progress(root, 'source.txt', [selector])


def test_bounded_history_disclosed(repo):
    root, selector = repo
    result = task_progress(root, 'source.txt', [selector], limit=1)
    assert result['history_may_be_truncated']
    assert result['commits_inspected'] == 1


def test_dirty_disclosure_and_root_boundary(repo):
    root, selector = repo
    (root / 'code.py').write_text('changed')
    out = task_progress(root, 'source.txt', [selector])
    assert out['dirty']
    assert not out['source_identity_authenticated']
    assert out['tasks'][0]['events'][0]['root_or_shallow_boundary']
    assert not out['tasks'][0]['events'][0]['task_time_anchor_verified']


def test_nonascii_tab_path_event(repo):
    root, selector = repo
    name = 'file\t雪.py'
    (root / name).write_text('x=2')
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), 'commit', '-qm', 'path fixture'], check=True)
    selector['paths'] = [name]
    event = task_progress(root, 'source.txt', [selector])['tasks'][0]['events'][0]
    assert event['changed_paths'] == [name]
    assert not event['root_or_shallow_boundary']
    assert event['commit_at']
