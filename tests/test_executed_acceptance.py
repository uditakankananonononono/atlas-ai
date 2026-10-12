"""Passing scoped tests cannot release a semantic completion gate."""
import subprocess
import pytest
from app.modules.instinct_doc.executed_acceptance import audit_selected_checks
from app.modules.instinct_doc.repo_evidence import source_inventory, EvidenceError


@pytest.fixture
def repo(tmp_path):
    def git(*a): subprocess.run(['git','-C',str(tmp_path),*a],check=True,capture_output=True)
    git('init','-q');git('config','user.name','test');git('config','user.email','test@example.invalid')
    git('remote','add','origin','https://example.invalid/repo')
    (tmp_path/'source.txt').write_text('first\nsecond\n')
    (tmp_path/'tests').mkdir();(tmp_path/'tests/test_ok.py').write_text('def test_ok(): assert True')
    git('add','.');git('commit','-qm','fixture')
    line=source_inventory(tmp_path,'source.txt')['rows'][0]
    return tmp_path,dict(id='check',line_id=line['id'],line_sha256=line['sha256'],test_paths=['tests/test_ok.py'])


def test_pass_and_missing_line_keep_blockers(repo):
    root,check=repo
    out=audit_selected_checks(root,'source.txt',[check])
    assert out['scoped_passing_lines']==1
    assert len(out['blockers'])==2
    assert out['semantic_verified_lines']==0
    assert not out['candy_gate']['release']
    assert out['lines'][0]['checks'][0]['run']['counts']['tests']==1


def test_all_selected_lines_pass_still_no_candy(repo):
    root,check=repo
    line=source_inventory(root,'source.txt')['rows'][1]
    other=dict(check,id='second',line_id=line['id'],line_sha256=line['sha256'])
    out=audit_selected_checks(root,'source.txt',[check,other])
    assert out['scoped_passing_lines']==2 and not out['candy_gate']['release']


def test_fake_semantic_label_and_stale_source_refused(repo):
    root,check=repo
    check['semantic_verified']=True
    with pytest.raises(EvidenceError):audit_selected_checks(root,'source.txt',[check])
    check.pop('semantic_verified');check['line_sha256']='0'*64
    with pytest.raises(EvidenceError):audit_selected_checks(root,'source.txt',[check])


def test_later_invalid_shape_runs_nothing(repo, monkeypatch):
    from app.modules.instinct_doc import executed_acceptance as mod
    root,check=repo;calls=[]
    monkeypatch.setattr(mod,'execute_tests',lambda *a:calls.append(a))
    with pytest.raises(EvidenceError):mod.audit_selected_checks(root,'source.txt',[check,{'id':'bad'}])
    assert calls==[]


def test_mixed_failure_and_source_mutation_not_promoted(repo,monkeypatch):
    from app.modules.instinct_doc import executed_acceptance as mod
    from app.modules.instinct_doc.repo_evidence import snapshot
    root,check=repo;snap=snapshot(root)
    def changed(*a):
        (root/'source.txt').write_text('changed\n')
        return {'status':'SCOPED_PASS','head':snap['head'],'tree_digest':snap['tree_digest']}
    monkeypatch.setattr(mod,'execute_tests',changed)
    out=mod.audit_selected_checks(root,'source.txt',[check])
    assert not out['source_stable_after_runs'] and out['scoped_passing_lines']==0
    assert all(r['check_status']=='UNVERIFIED' for r in out['lines'])


def test_missing_line_not_scoped_pass(repo):
    root,check=repo
    out=audit_selected_checks(root,'source.txt',[check])
    assert out['lines'][1]['check_status']=='UNVERIFIED'
    assert out['lines'][1]['checks']==[]
    assert not out['lines'][0]['test_line_pairing_verified']


def test_actual_mixed_pass_fail_receipts(repo):
    root,check=repo
    (root/'tests/test_bad.py').write_text('def test_bad(): assert False')
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'commit','-qm','failure fixture'],check=True)
    line=source_inventory(root,'source.txt')['rows'][1]
    bad=dict(check,id='bad',line_id=line['id'],line_sha256=line['sha256'],test_paths=['tests/test_bad.py'])
    out=audit_selected_checks(root,'source.txt',[check,bad])
    assert out['scoped_passing_lines']==1
    assert out['lines'][1]['checks'][0]['run']['counts']['failures']==1
    assert not out['candy_gate']['release']


def test_postrun_inventory_error_preserves_receipts(repo,monkeypatch):
    from app.modules.instinct_doc import executed_acceptance as mod
    root,check=repo;original=mod.source_inventory;calls=[]
    def fail_second(*a):
        calls.append(1)
        if len(calls)>1:raise OSError('injected post-read')
        return original(*a)
    monkeypatch.setattr(mod,'source_inventory',fail_second)
    out=mod.audit_selected_checks(root,'source.txt',[check])
    assert out['post_run_source_error']=='OSError'
    assert out['lines'][0]['checks'][0]['run']['counts']['tests']==1
    assert out['scoped_passing_lines']==0


def test_helper_exception_and_head_drift_unverified(repo,monkeypatch):
    from app.modules.instinct_doc import executed_acceptance as mod
    root,check=repo
    def failed(*a):raise RuntimeError('injected helper')
    monkeypatch.setattr(mod,'execute_tests',failed)
    out=mod.audit_selected_checks(root,'source.txt',[check])
    assert out['lines'][0]['checks'][0]['run']['error']=='RuntimeError'
    monkeypatch.setattr(mod,'execute_tests',lambda *a:{'status':'SCOPED_PASS','head':'other','tree_digest':'other'})
    assert mod.audit_selected_checks(root,'source.txt',[check])['scoped_passing_lines']==0


def test_inventory_bytes_hash_and_disclosures(repo):
    import hashlib
    root,check=repo
    out=audit_selected_checks(root,'source.txt',[check])
    assert out['source_artifact_sha256']==hashlib.sha256((root/'source.txt').read_bytes()).hexdigest()
    assert out['source_path']=='source.txt' and out['head'] and out['tree_digest']
    assert not out['aggregate_budget_enforced'] and not out['execution_is_sandboxed']
