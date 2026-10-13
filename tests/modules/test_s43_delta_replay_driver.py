"""Trusted-local replay driver mechanics, no historical execution claim."""
import importlib.util
from pathlib import Path
import pytest


def test_missing_audit_parent_created_and_output_not_overwritten(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    loader=importlib.util.spec_from_file_location('driver',root/'tests/modules/s43_delta_mutations.py')
    driver=importlib.util.module_from_spec(loader);loader.loader.exec_module(driver)
    repo=tmp_path/'repo';(repo/'scripts/release').mkdir(parents=True)
    (repo/'audits/s43-delta').mkdir(parents=True)
    (repo/'audits/s43-delta/operators.json').write_text('{}')
    (repo/'scripts/release/scoped_mutations.py').write_text(
        'def execute(spec,output):\n'
        '    assert output.parent.is_dir()\n'
        '    if output.exists():raise ValueError("evidence output exists")\n'
        '    output.mkdir()\n'
        '    return {"all_caught": True}\n')
    monkeypatch.setattr(driver,'R',repo)
    output=tmp_path/'absent/audit/fresh'
    assert driver.replay(output)=={'all_caught':True}
    with pytest.raises(ValueError,match='exists'):driver.replay(output)


@pytest.mark.parametrize('scenario,expected_status,exit_code', [
    ('assertion', 'CAUGHT', 0),
    ('runtime_exception', 'CAUGHT', 0),
    ('survived', 'SURVIVED', 1),
    ('failed_plus_skip', 'INVALID', 1),
    ('invalid_site', 'INVALID-SITE', 1),
    ('baseline_failed', None, 1),
])
def test_cli_uses_real_shared_runner_and_returns_failure_for_nonrelease(
        tmp_path, scenario, expected_status, exit_code):
    """Real child pytest in an inert git fixture, not a runner stub."""
    import hashlib
    import json
    import os
    import shutil
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    repo = tmp_path / 'fixture'
    for folder in ('scripts/release', 'tests/modules', 'audits/s43-delta'):
        (repo / folder).mkdir(parents=True)
    shutil.copyfile(root / 'scripts/release/scoped_mutations.py',
                    repo / 'scripts/release/scoped_mutations.py')
    driver = repo / 'tests/modules/s43_delta_mutations.py'
    shutil.copyfile(root / 'tests/modules/s43_delta_mutations.py', driver)
    source = repo / 'scripts/value.py'
    original = b'value = 1\n'
    source.write_bytes(original)
    fixture = repo / 'tests/test_value.py'
    fixture.write_text(
        'import runpy\nimport pytest\n'
        'value = runpy.run_path("scripts/value.py")["value"]\n'
        'def test_value():\n'
        f'    if value == 2 and {scenario == "runtime_exception"!r}:\n'
        '        raise RuntimeError("changed branch fixture")\n'
        f'    assert value == {0 if scenario == "baseline_failed" else 1}\n'
        'def test_companion():\n'
        f'    if value == 2 and {scenario == "failed_plus_skip"!r}:\n'
        '        pytest.skip("mutated companion")\n'
        '    assert True\n')
    spec = {'row': 'inert driver fixture', 'selectors': ['tests/test_value.py'],
            'timeout_seconds': 15,
            'environment': {'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'},
            'limits': ['trusted local fixture, no product or external effect'],
            'mutations': [{'id': 'value', 'path': 'scripts/value.py',
                           'old': 'missing site' if scenario == 'invalid_site' else 'value = 1',
                           'new': 'value = 1 # inert' if scenario == 'survived' else 'value = 2'}]}
    (repo / 'audits/s43-delta/operators.json').write_text(json.dumps(spec))
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
    subprocess.run(['git', '-c', 'user.name=Instinct', '-c', 'user.email=agent@instinct.com',
                    'commit', '-qm', 'inert fixture'], cwd=repo, check=True)
    output = repo / 'absent/parent/fresh'
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    result = subprocess.run([sys.executable, str(driver), '--output', str(output)],
                            cwd=repo, env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == exit_code, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == json.loads((output / 'receipt.json').read_text())
    assert report['all_caught'] is (exit_code == 0)
    assert source.read_bytes() == original
    if expected_status is None:
        assert report['baseline']['status'] == 'BASELINE-NOT-RELEASED'
        assert report['mutations'] == []
    else:
        assert report['baseline']['status'] == 'PASS'
        mutation = report['mutations'][0]
        assert mutation['status'] == expected_status
        assert mutation['restore_verified'] is True
        assert mutation['restored_sha256'] == hashlib.sha256(original).hexdigest()
        if expected_status != 'INVALID-SITE':
            log = (output / 'value.log').read_text()
            assert ('FAILED tests/test_value.py::test_value' in log) is (scenario != 'survived')
            if scenario == 'runtime_exception':
                assert 'RuntimeError: changed branch fixture' in log
            if scenario == 'failed_plus_skip':
                assert '1 skipped' in log
    second = subprocess.run([sys.executable, str(driver), '--output', str(output)],
                            cwd=repo, env=env, capture_output=True, text=True, timeout=45)
    assert second.returncode == 1
    assert 'evidence output exists' in second.stderr
    assert report == json.loads((output / 'receipt.json').read_text())
