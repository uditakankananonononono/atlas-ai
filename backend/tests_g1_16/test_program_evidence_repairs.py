"""Bug-level regression checks; fake execution is always labelled injected."""
import hashlib
import importlib.util
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

path = os.path.join(os.path.dirname(__file__), '..', 'app', 'modules', 'instinct_doc', 'program_evidence_g1_16.py')
spec = importlib.util.spec_from_file_location('pe_repairs', path)
pe = importlib.util.module_from_spec(spec); sys.modules[spec.name] = pe; spec.loader.exec_module(pe)


def repo(root):
    p = root / 'repo'; p.mkdir()
    subprocess.run(['git', 'init', '-q', str(p)], check=True)
    (p / 'a').write_text('clean')
    subprocess.run(['git', '-C', str(p), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(p), '-c', 'user.name=test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'fixture'], check=True)
    return p


def test_all_unsupported_program_is_unsupported(tmp_path):
    report = pe.verify_program(str(tmp_path), [{'id': 'a'}, {'id': 'b'}])
    assert report['verdict'] == 'UNSUPPORTED'
    assert all(x['verdict'] == 'UNSUPPORTED' for x in report['projects'])


def test_partial_evidence_remains_partial(tmp_path):
    repo(tmp_path)
    report = pe.verify_program(str(tmp_path), [{'id': 'a', 'repo': {'path': 'repo'}}, {'id': 'b'}])
    assert report['verdict'] == 'PARTIAL'


def test_wired_module_and_leader_checks(tmp_path):
    data = tmp_path / 'a.csv'; data.write_bytes(b'1,2\n')
    (tmp_path / 'test_data.py').write_text("open('a.csv')")
    def runner(argv):
        out = b'2 passed\n' if argv == ['module'] else b'BENCH leader=L metric=auc subject=0.9 leader_value=0.8\n'
        return subprocess.CompletedProcess(argv, 0, out, b'')
    project = {'id': 'p', 'module_run': {'argv': ['module'], 'stdout_regex': '2 passed',
               'datasets': [{'path': 'a.csv', 'sha256': hashlib.sha256(data.read_bytes()).hexdigest(), 'origin': 'unverified-label'}],
               'referenced_in': ['test_data.py']},
               'leader_benchmarks': [{'argv': ['leader'], 'leader': 'L', 'metric': 'auc', 'higher_is_better': True}]}
    result = pe.verify_project(str(tmp_path), project, runner=runner)
    assert result['checks']['module_run']['ok']
    assert result['checks']['leader_benchmarks']['ok']
    missing = pe.verify_project(str(tmp_path), {'id': 'empty'}, runner=runner)
    assert not missing['checks']['module_run']['ok']
    assert not missing['checks']['leader_benchmarks']['ok']


def test_injected_runner_explicit_in_json_and_render(tmp_path):
    fake = lambda argv: subprocess.CompletedProcess(argv, 0, b'fake', b'')
    report = pe.verify_program(str(tmp_path), [{'id': 'a'}], runner=fake)
    assert report['runner_injected'] and report['projects'][0]['runner_injected']
    assert report['execution_mode'] == 'injected_runner_allowlist_bypassed'
    assert 'injected runner' in pe.render(report)
    assert not pe.verify_program(str(tmp_path), [])['runner_injected']


@pytest.mark.parametrize('tool', ['pdfinfo', 'pdffonts', 'pdftotext'])
def test_pdf_nonzero_exit_rejected_even_with_plausible_stdout(tmp_path, tool):
    outputs = {'pdfinfo': 'Pages: 50\n', 'pdffonts': 'header\nheader\nTimes-Roman Type1 yes\n',
               'pdftotext': '\n'.join(x + '\n' + ('word ' * 200) for x in pe.LENIENT.paper_sections) * 50}
    seen = []
    def run(argv, **kwargs):
        seen.append(argv[0])
        return subprocess.CompletedProcess(argv, 7 if argv[0] == tool else 0, outputs[argv[0]], '')
    with patch.object(pe.shutil, 'which', return_value='/usr/bin/fake'), patch.object(pe.subprocess, 'run', side_effect=run):
        result = pe.check_paper(str(tmp_path), {'path': 'paper.pdf'}, pe.LENIENT)
    assert not result['ok'] and result['reason'] == tool + '_failed'
    assert result['returncode'] == 7 and seen[-1] == tool


@pytest.mark.parametrize('staged', [False, True])
def test_repo_dirty_tracked_tree_refused(tmp_path, staged):
    p = repo(tmp_path)
    (p / 'a').write_text('modified')
    if staged: subprocess.run(['git', '-C', str(p), 'add', 'a'], check=True)
    result = pe.check_repo(str(tmp_path), {'path': 'repo'})
    assert result['reason'] == 'tracked_tree_dirty' and not result['ok']


def test_origin_is_configured_not_caller_selected(tmp_path):
    p = repo(tmp_path)
    origin = 'https://example.invalid/configured'
    subprocess.run(['git', '-C', str(p), 'remote', 'add', 'origin', origin], check=True)
    head = subprocess.check_output(['git', '-C', str(p), 'rev-parse', 'HEAD'], text=True).strip()
    called = []
    def probe(url): called.append(url); return head
    bad = pe.check_repo(str(tmp_path), {'path': 'repo', 'remote': 'https://evil.invalid/claimed'}, probe)
    assert bad['reason'] == 'origin_mismatch' and not called
    result = pe.check_repo(str(tmp_path), {'path': 'repo'}, probe)
    assert result['ok'] and called == [origin] and result['remote_verified']
    assert result['remote_probe_injected']


def test_claimed_remote_without_origin_is_rejected(tmp_path):
    repo(tmp_path)
    called = []
    result = pe.check_repo(str(tmp_path), {'path': 'repo', 'remote': 'https://caller.invalid/r'}, lambda url: called.append(url))
    assert result['reason'] == 'origin_mismatch' and not called


def test_untracked_files_do_not_change_tracked_clean(tmp_path):
    p = repo(tmp_path); (p / 'untracked').write_text('not a committed artifact')
    result = pe.check_repo(str(tmp_path), {'path': 'repo'})
    assert result['ok'] and result['tracked_clean'] and not result['remote_verified']


def test_docstring_does_not_authenticate_claims():
    assert 'does NOT verify provenance, scientific validity,' in pe.__doc__
    assert 'or judge authenticity' in pe.__doc__
    assert 'caller-supplied allowlist' in pe.__doc__


def test_project_command_allowlist_is_passed_to_new_checks(tmp_path):
    project = {'module_run': {}, 'leader_benchmarks': []}
    with patch.object(pe, 'check_module_run', return_value={'ok': False}) as module, patch.object(pe, 'check_leader_benchmarks', return_value={'ok': False}) as leader:
        pe.verify_project(str(tmp_path), project, command_allowlist=(('operator-command',),))
    assert module.call_args.args[-1] == (('operator-command',),)
    assert leader.call_args.args[-1] == (('operator-command',),)
