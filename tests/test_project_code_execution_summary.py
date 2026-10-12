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


def test_invalid_later_shape_executes_nothing(repo, monkeypatch):
    from app.modules.instinct_doc import code_test_summary_p256 as mod
    root,item=repo;calls=[]
    monkeypatch.setattr('app.modules.instinct_doc.repo_evidence.execute_tests',lambda *a:calls.append(a))
    with pytest.raises(ValueError):mod.inspect_projects(root,[item,{'id':'bad'}],execute=True)
    assert calls==[]


def test_helper_error_confined_and_pairing_disclaimed(repo, monkeypatch):
    root,item=repo
    def failed(*a):raise RuntimeError('injected')
    monkeypatch.setattr('app.modules.instinct_doc.repo_evidence.execute_tests',failed)
    out=inspect_projects(root,[item,dict(item,id='P2')],execute=True)
    assert all(row['status']=='UNVERIFIED' for row in out['projects'])
    assert all(not row['selection_pairing_verified'] for row in out['projects'])
    assert not out['aggregate_budget_enforced']


def test_drifted_run_not_promoted(repo, monkeypatch):
    root,item=repo
    monkeypatch.setattr('app.modules.instinct_doc.repo_evidence.execute_tests',lambda *a:{'status':'SCOPED_PASS','head':'drift','tree_digest':'drift'})
    row=inspect_projects(root,[item],execute=True)['projects'][0]
    assert row['status']=='UNVERIFIED' and not row['snapshot_coherent']


def test_failing_test_and_dirty_snapshot(repo):
    root,item=repo
    (root/'tests/test_ok.py').write_text('def test_ok(): assert False')
    out=inspect_projects(root,[item],execute=True)
    assert out['dirty'] and out['projects'][0]['status']=='UNVERIFIED'


def test_no_run_coherence_unknown_and_reason(repo):
    root,item=repo
    row=inspect_projects(root,[item])['projects'][0]
    assert row['snapshot_coherent'] is None
    assert row['failure_reason']=='not_executed'
    assert 'Top-level' in row['dirty_scope']


def test_file_drift_between_snapshot_and_read_refused(repo,monkeypatch):
    from app.modules.instinct_doc import repo_evidence as evidence
    root,item=repo
    original=evidence.snapshot
    def changed(path):
        result=original(path)
        (root/'core.py').write_bytes(b'changed')
        return result
    monkeypatch.setattr(evidence,'snapshot',changed)
    row=inspect_projects(root,[item])['projects'][0]
    assert row['errors'] and row['failure_reason']=='final_project_tree_drift'


def test_initial_byte_budget_is_hard_cap(repo):
    root,item=repo
    out=inspect_projects(root,[item],max_initial_bytes=4)
    assert out['retained_initial_bytes']<=4
    assert out['byte_budget_rejected_paths']
    assert out['projects'][0]['status']=='UNVERIFIED'


def test_cross_project_later_byte_change_detected(repo,monkeypatch):
    from app.modules.instinct_doc import repo_evidence as evidence
    root,item=repo;original=evidence.safe_file;reads=[]
    class ChangedFile:
        def read_bytes(self):return b'other bytes'
    def delayed(path,name):
        reads.append(name)
        # Initial capture and first project's read succeed; second read changes.
        if name=='core.py' and reads.count(name)==4:return ChangedFile()
        return original(path,name)
    monkeypatch.setattr(evidence,'safe_file',delayed)
    out=inspect_projects(root,[item,dict(item,id='P2')])
    assert not out['projects'][0]['errors']
    assert out['projects'][1]['errors']


def test_dirty_success_not_promoted(repo):
    root,item=repo
    (root/'core.py').write_text('x=2\n')
    row=inspect_projects(root,[item],execute=True)['projects'][0]
    assert row['execution']['status']=='SCOPED_PASS'
    assert row['status']=='UNVERIFIED'
    assert row['failure_reason']=='dirty_initial_tree'


@pytest.mark.parametrize('receipt',[None,[],{}, {'head':'x','tree_digest':'x'}])
def test_malformed_project_receipt_keeps_all_rows(repo,monkeypatch,receipt):
    root,item=repo
    monkeypatch.setattr('app.modules.instinct_doc.repo_evidence.execute_tests',lambda *a:receipt)
    out=inspect_projects(root,[item,dict(item,id='P2')],execute=True)
    assert len(out['projects'])==2
    assert all(row['status']=='UNVERIFIED' for row in out['projects'])


def test_later_project_mutation_demotes_earlier_pass(repo,monkeypatch):
    from app.modules.instinct_doc import repo_evidence as evidence
    root,item=repo;snap=evidence.snapshot(root);calls=[]
    def later_change(*a):
        calls.append(1)
        if len(calls)==2:(root/'core.py').write_text('later mutation')
        return {'status':'SCOPED_PASS','head':snap['head'],'tree_digest':snap['tree_digest']}
    monkeypatch.setattr(evidence,'execute_tests',later_change)
    out=inspect_projects(root,[item,dict(item,id='P2')],execute=True)
    assert not out['final_snapshot_stable']
    assert all(row['status']=='UNVERIFIED' for row in out['projects'])
    assert out['projects'][0]['failure_reason']=='final_project_tree_drift'
