"""Temporary git repos and executed subprocess tests, no fabricated receipts."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.modules.instinct_doc.repo_evidence import (
    EvidenceError, build_report, code_summary, datasets, execute_tests,
    safe_file, snapshot, source_inventory,
)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    def cmd(*args):
        subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    cmd('init', '-q')
    cmd('config', 'user.name', 'evidence test')
    cmd('config', 'user.email', 'test@example.invalid')
    cmd('remote', 'add', 'origin', 'https://example.invalid/repo.git')
    files = {
        'source.txt': 'Exact line one\n\nExact line two\n',
        'backend/app/modules/demo/core.py': 'def thin():\n    pass\n',
        'backend/app/integrations/demo.py': 'import json\nfrom urllib import request\n',
        'data/items.csv': 'id,label\n1,a\n2,b\n',
        'data/records.jsonl': '{"x":1}\n{"x":2}\n',
        'data/config.json': '{"sources": ["not-a-dataset"]}',
        'tests/test_good.py': 'def test_add():\n    assert 2 + 2 == 4\n',
        'tests/test_bad.py': 'def test_bad():\n    assert False\n',
        'tests/test_skip.py': 'import pytest\n@pytest.mark.skip(reason="offline")\ndef test_skip():\n    pass\n',
        'tests/test_empty.py': '# no tests\n',
        'tests/test_slow.py': 'import time\ndef test_slow():\n    time.sleep(10)\n',
        'tests/test_mutating.py': 'from pathlib import Path\ndef test_change():\n    Path("data/items.csv").write_text("id,label\\n1,changed\\n")\n',
        'tests/test_secret.py': 'import os\ndef test_secret():\n    assert "ATLAS_PRIVATE_TOKEN" not in os.environ\n',
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    cmd('add', '.')
    cmd('commit', '-qm', 'fixture state')
    return root


def test_source_lines_verbatim_not_summary(repo):
    source = source_inventory(repo, 'source.txt')
    import hashlib
    assert [row['sha256'] for row in source['rows']] == [hashlib.sha256(x.encode()).hexdigest() for x in ['Exact line one', 'Exact line two']]
    assert all('text' not in row for row in source['rows'])
    assert [row['id'] for row in source['rows']] == ['export:L1', 'export:L3']
    assert all(row['status'] == 'UNVERIFIED' for row in source['rows'])


@pytest.mark.parametrize('bad', ['../secret', '/etc/passwd', '.git/config', 'missing'])
def test_unsafe_paths_rejected(repo, bad):
    with pytest.raises(EvidenceError):
        safe_file(repo, bad)


def test_symlink_and_html_rejected(repo, tmp_path):
    (repo / 'link').symlink_to(repo / 'source.txt')
    with pytest.raises(EvidenceError):
        safe_file(repo, 'link')
    (repo / 'html').write_text('<!doctype html><html>sign in</html>')
    with pytest.raises(EvidenceError):
        source_inventory(repo, 'html')


def test_computed_inventory_not_caller_counts(repo):
    snap = snapshot(repo)
    summary = code_summary(repo, snap['files'])
    assert summary['code_files'] == 2
    assert summary['test_files'] == 7
    assert summary['findings'][0]['kind'] == 'pass_only_function'
    data = datasets(repo, snap['files'])
    assert data['artifact_count'] == 2
    assert [x['records'] for x in data['artifacts']] == [2, 2]
    assert data['provenance_verified_dataset_count'] is None
    report = build_report(repo, 'source.txt')
    assert report['repository']['origin'] == 'https://example.invalid/repo.git'
    assert report['integrations']['working_external_tool_count'] is None
    assert not report['candy_gate']['release']
    assert len(report['compliance']) == 2
    assert report['chatgpt_judge']['reports'] == []
    assert report['benchmark_table'] == []
    assert report['self_improvement_plans'][0]['module'] == 'demo'
    assert report['progress'][0]['status'] == 'COMMIT_OBSERVED'


def test_executed_subprocess_pass(repo):
    run = execute_tests(repo, ['tests/test_good.py'])
    assert run['status'] == 'SCOPED_PASS'
    assert run['counts'] == {'tests': 1, 'failures': 0, 'errors': 0, 'skipped': 0}
    assert run['tree_stable']
    assert '<testcase' in run['junit_xml']
    report = build_report(repo, 'source.txt', ['tests/test_good.py'])
    assert report['benchmark_table'][0]['kind'] == 'selected_test_execution'
    assert report['candy_gate']['release'] is False


@pytest.mark.parametrize('path', ['tests/test_bad.py', 'tests/test_skip.py', 'tests/test_empty.py'])
def test_fail_skip_empty_cannot_verify(repo, path):
    run = execute_tests(repo, [path])
    assert run['status'] == 'UNVERIFIED'


def test_timeout_fail_closed(repo):
    run = execute_tests(repo, ['tests/test_slow.py'], timeout=1)
    assert run['timed_out']
    assert run['exit_code'] is None
    assert run['status'] == 'UNVERIFIED'


def test_tree_mutation_cannot_verify(repo):
    run = execute_tests(repo, ['tests/test_mutating.py'])
    assert not run['tree_stable']
    assert run['status'] == 'UNVERIFIED'


def test_secrets_not_passed_to_subprocess(repo, monkeypatch):
    monkeypatch.setenv('ATLAS_PRIVATE_TOKEN', 'do-not-copy')
    run = execute_tests(repo, ['tests/test_secret.py'])
    assert run['status'] == 'SCOPED_PASS'


@pytest.mark.parametrize('paths', [[], ['backend/app/modules/demo/core.py'], ['../secret'], ['tests/test_good.py::test_add']])
def test_arbitrary_command_target_refused(repo, paths):
    with pytest.raises(EvidenceError):
        execute_tests(repo, paths)


def test_untracked_test_cannot_execute(repo):
    (repo / 'tests/test_untracked.py').write_text('def test_x(): assert True')
    with pytest.raises(EvidenceError):
        execute_tests(repo, ['tests/test_untracked.py'])


def test_changed_dataset_recomputed(repo):
    first = build_report(repo, 'source.txt')
    (repo / 'data/items.csv').write_text('id,label\n1,a\n2,b\n3,c\n')
    second = build_report(repo, 'source.txt')
    assert second['repository']['tree_digest'] != first['repository']['tree_digest']
    assert second['datasets']['artifacts'][0]['records'] == 3
    assert second['repository']['dirty']
    assert not second['candy_gate']['release']


def test_deleted_tracked_file_prevents_pass(repo):
    (repo / 'data/items.csv').unlink()
    run = execute_tests(repo, ['tests/test_good.py'])
    assert run['status'] == 'UNVERIFIED'
    assert snapshot(repo)['errors']


def test_malformed_dataset_does_not_invent_count(repo):
    (repo / 'data/records.jsonl').write_text('{not json}')
    data = datasets(repo, snapshot(repo)['files'])
    assert data['artifacts'][1]['records'] is None
    assert data['artifacts'][1]['source_status'] == 'UNVERIFIED'


def test_cli_requires_explicit_execution_opt_in(tmp_path):
    cli = Path(__file__).resolve().parents[1] / 'tools/program_evidence.py'
    run = subprocess.run([sys.executable, str(cli), '--test', 'tests/test_program_repo_evidence.py',
                          '--output', str(tmp_path / 'report.json')], capture_output=True, text=True)
    assert run.returncode == 2
    assert 'opt in' in run.stderr
    assert not (tmp_path / 'report.json').exists()


def test_report_digest_computed(repo):
    from app.modules.instinct_doc.repo_evidence import canonical_digest
    report = build_report(repo, 'source.txt')
    result_digest = report.pop('report_sha256')
    assert canonical_digest(report) == result_digest


def test_public_manifest_excludes_source_text():
    root = Path(__file__).resolve().parents[1]
    source = source_inventory(root, 'docs/program-evidence/source-manifest.json')
    assert len(source['rows']) == 256
    assert source['sha256'] == '575b3745949b5859370faf3d27ab61fc9af07c55b9daf7f6bf1238ce55a76d3a'
    assert source['source_text_included'] is False
    assert all('text' not in row for row in source['rows'])
