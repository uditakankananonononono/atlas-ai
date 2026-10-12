"""Local Git snapshots do not prove remote/project ownership."""
import subprocess
import pytest
from app.modules.instinct_doc.repo_register_p253 import create_register, add_entry, bind_local_repositories


def setup(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    def git(*args):
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
    git('init', '-q')
    git('config', 'user.name', 'test')
    git('config', 'user.email', 'test@example.invalid')
    git('remote', 'add', 'origin', 'https://example.invalid/configured')
    (repo / 'code.py').write_text('x=1')
    git('add', '.')
    git('commit', '-qm', 'fixture')
    r = create_register()
    for ident in ['a', 'b']:
        r = add_entry(r, dict(id=ident, project_id='project', kind='link', value='https://example.invalid/' + ident, source_ref='fixture'))
    binding = dict(entry_id='a', local_path='repo', row_ids=['row'], project_ids=['project'])
    return r, binding


def test_local_snapshot_and_missing_reference(tmp_path):
    r, binding = setup(tmp_path)
    result = bind_local_repositories(r, tmp_path, [binding])
    assert result['counts'] == {'LOCAL-SNAPSHOT': 1, 'UNVERIFIED': 1}
    row = result['entries'][0]
    assert row['snapshot']['tracked_files'] == 1
    assert not row['snapshot']['dirty']
    assert not row['remote_verified'] and not row['ownership_verified'] and not row['completion_verified']
    assert 'origin' not in row['snapshot']
    assert result['unbound_entry_ids'] == ['b']


@pytest.mark.parametrize('path', ['../outside', '/etc', 'missing'])
def test_invalid_root_unverified(tmp_path, path):
    r, binding = setup(tmp_path)
    binding['local_path'] = path
    assert bind_local_repositories(r, tmp_path, [binding])['entries'][0]['status'] == 'UNVERIFIED'


def test_symlink_root_unverified(tmp_path):
    r, binding = setup(tmp_path)
    (tmp_path / 'link').symlink_to(tmp_path / 'repo')
    binding['local_path'] = 'link'
    assert bind_local_repositories(r, tmp_path, [binding])['entries'][0]['status'] == 'UNVERIFIED'


def test_dirty_snapshot_disclosed(tmp_path):
    r, binding = setup(tmp_path)
    (tmp_path / 'repo/code.py').write_text('changed')
    row = bind_local_repositories(r, tmp_path, [binding])['entries'][0]
    assert row['snapshot']['dirty']
    assert not row['completion_verified']


def test_caller_verified_label_refused(tmp_path):
    r, binding = setup(tmp_path)
    binding['status'] = 'VERIFIED'
    with pytest.raises(ValueError, match='bad_fields'):
        bind_local_repositories(r, tmp_path, [binding])


def test_snapshot_content_hash_and_no_locator_digest(tmp_path):
    import hashlib
    r, binding = setup(tmp_path)
    row = bind_local_repositories(r, tmp_path, [binding])['entries'][0]
    assert len(row['snapshot']['tree_digest']) == 64
    assert 'origin_sha256' not in row['snapshot']
    assert 'declared_value_sha256' not in row
    assert row['snapshot']['origin_configured']


def test_ambient_git_directory_ignored(tmp_path, monkeypatch):
    r, binding = setup(tmp_path)
    monkeypatch.setenv('GIT_DIR', '/nonexistent/redirect')
    row = bind_local_repositories(r, tmp_path, [binding])['entries'][0]
    assert row['status'] == 'LOCAL-SNAPSHOT'
