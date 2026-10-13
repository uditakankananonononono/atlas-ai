"""Disclosure contracts remain narrow; selected receipts cannot open release."""
from test_executed_acceptance import repo
from app.modules.instinct_doc import executed_acceptance as m
from app.modules.instinct_doc.repo_evidence import snapshot

def test_disclosure_boundaries_remain_present(repo,monkeypatch):
    root,check=repo;snap=snapshot(root)
    monkeypatch.setattr(m,'execute_tests',lambda *a:dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest']))
    out=m.audit_selected_checks(root,'source.txt',[check])
    assert 'no authenticated semantic evidence channel' in out['candy_gate']['reason']
    assert 'no aggregate time/disk budget' in out['execution_scope']
    assert 'non-atomic' in out['snapshot_boundary']
    assert 'declared export hash is separate' in out['source_artifact_hash_scope']
    assert 'not semantic proof' in out['boundary']
