import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location('package_mailbox', Path(__file__).resolve().parents[2] / 'scripts/release/package_mailbox.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Instinct')
    git('config', 'user.email', 'agent@instinct.com')
    (root / 'tests').mkdir()
    (root / 'tests/test_slice.py').write_text('def test_local_slice():\n    assert 2 + 2 == 4\n')
    git('add', '.')
    git('commit', '-qm', 'base')
    base = git('rev-parse', 'HEAD')
    (root / 'note.txt').write_text('local evidence\n')
    git('add', '.')
    git('commit', '-qm', 'release')
    return root, base, git


def test_git_am_round_trip_binds_mailbox_log_selector_and_trees(tmp_path):
    root, base, git = repo(tmp_path)
    output = tmp_path / 'output'
    receipt = module.package(root, base, 'HEAD', ['tests/test_slice.py'], sys.executable, output)
    assert receipt['test_result'] == 'PASS'
    assert receipt['base_tree'] == git('rev-parse', base + '^{tree}')
    assert receipt['result_tree'] == git('rev-parse', 'HEAD^{tree}')
    assert receipt['mailbox_sha256'] == module.sha256(output / 'repair.mbox')
    assert receipt['selector_log_sha256'] == module.sha256(output / 'selector.log')
    assert receipt['selector_argv'][-2:] == ['tests/test_slice.py', '-q']
    assert receipt['git_am_tree_verified'] is True
    assert json.loads((output / 'receipt.json').read_text()) == receipt
    with pytest.raises(ValueError, match='overwrite'):
        module.package(root, base, 'HEAD', ['tests/test_slice.py'], sys.executable, output)


@pytest.mark.parametrize('selector', ['../tests/test_slice.py', '/tests/test_slice.py', 'tests/', 'tests/missing.py'])
def test_invalid_or_missing_selectors_refused_before_evidence_creation(tmp_path, selector):
    root, base, _ = repo(tmp_path)
    output = tmp_path / 'output'
    with pytest.raises(ValueError):module.package(root, base, 'HEAD', [selector], sys.executable, output)
    assert not output.exists()


def test_non_instinct_release_identity_refused(tmp_path):
    root, base, git = repo(tmp_path)
    git('-c', 'user.name=Other', '-c', 'user.email=other@invalid', 'commit', '--amend', '--reset-author', '-qm', 'wrong identity')
    with pytest.raises(ValueError, match='identity mismatch'):
        module.package(root, base, 'HEAD', ['tests/test_slice.py'], sys.executable, tmp_path / 'out')


def test_dirty_checkout_refused(tmp_path):
    root, base, _ = repo(tmp_path)
    (root / 'note.txt').write_text('changed\n')
    with pytest.raises(ValueError, match='clean'):
        module.package(root, base, 'HEAD', ['tests/test_slice.py'], sys.executable, tmp_path / 'out')
