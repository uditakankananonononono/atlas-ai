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
