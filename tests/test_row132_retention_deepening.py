"""Blocker/receipt identity retention and source postread failure disclosure."""
from test_executed_acceptance import repo
from app.modules.instinct_doc import executed_acceptance as m
from app.modules.instinct_doc.repo_evidence import snapshot

def test_blocker_and_check_identity_retained(repo,monkeypatch):
    root,check=repo;snap=snapshot(root)
    monkeypatch.setattr(m,'execute_tests',lambda *a:dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest']))
    out=m.audit_selected_checks(root,'source.txt',[check])
    assert [b['line_id'] for b in out['blockers']]==[r['line_id'] for r in out['lines']]
    assert [b['reason'] for b in out['blockers']]==[r['reason'] for r in out['lines']]
    assert out['lines'][0]['checks'][0]['id']==check['id']

def test_postread_error_explicitly_demotes_source_stability(repo,monkeypatch):
    root,check=repo;snap=snapshot(root);original=m.source_inventory;calls=[]
    def source(*a):
        calls.append(1)
        if len(calls)>1:raise OSError('controlled postread')
        return original(*a)
    monkeypatch.setattr(m,'source_inventory',source)
    monkeypatch.setattr(m,'execute_tests',lambda *a:dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest']))
    out=m.audit_selected_checks(root,'source.txt',[check])
    assert out['source_stable_after_runs'] is False
    assert out['scoped_passing_lines']==0
