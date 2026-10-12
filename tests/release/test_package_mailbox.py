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
    assert receipt['selector_argv'][-3:-1] == ['tests/test_slice.py', '-q']
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


def amend(root, git, text):
    (root/'tests/test_slice.py').write_text(text)
    git('add', '.')
    git('commit', '-qm', 'selector fixture')


@pytest.mark.parametrize('change', ["Path('note.txt').write_text('changed')", "Path('new.txt').write_text('new')"])
def test_post_test_checkout_drift_refused(tmp_path, change):
    root,base,git=repo(tmp_path)
    amend(root,git,'from pathlib import Path\ndef test_change():\n    '+change+'\n')
    with pytest.raises(ValueError,match='post-test checkout drift'):
        module.package(root,base,'HEAD',['tests/test_slice.py'],sys.executable,tmp_path/'out')


def test_all_skipped_is_not_pass(tmp_path):
    root,base,git=repo(tmp_path)
    amend(root,git,"import pytest\ndef test_skip():\n    pytest.skip('fixture')\n")
    receipt=module.package(root,base,'HEAD',['tests/test_slice.py'],sys.executable,tmp_path/'out')
    assert receipt['test_result']=='FAIL'
    assert receipt['selector_counts']['tests']==receipt['selector_counts']['skipped']==1


def test_interpreter_and_controlled_environment_recorded(tmp_path,monkeypatch):
    root,base,git=repo(tmp_path)
    monkeypatch.setenv('PYTEST_ADDOPTS','--ignore=tests')
    monkeypatch.setenv('PRIVATE_TEST_TOKEN','not-a-real-secret')
    monkeypatch.setenv('PATH',str(Path(sys.executable).parent)+':'+__import__('os').environ['PATH'])
    receipt=module.package(root,base,'HEAD',['tests/test_slice.py'],'python',tmp_path/'out')
    assert Path(receipt['selector_argv'][0]).is_absolute()
    assert receipt['python_executable_sha256']==module.sha256(receipt['selector_argv'][0])
    assert 'PYTEST_ADDOPTS' not in receipt['selector_environment']
    assert 'PRIVATE_TEST_TOKEN' not in receipt['selector_environment']
    assert receipt['test_result']=='PASS'


def test_external_symlink_selector_refused(tmp_path):
    root,base,git=repo(tmp_path)
    external=tmp_path/'outside.py';external.write_text('def test_outside(): assert True\n')
    (root/'tests/test_link.py').symlink_to(external)
    git('add','.');git('commit','-qm','symlink fixture')
    with pytest.raises(ValueError,match='escapes repository'):
        module.package(root,base,'HEAD',['tests/test_link.py'],sys.executable,tmp_path/'out')
