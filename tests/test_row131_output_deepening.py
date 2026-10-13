"""Exact local identity output, controlled passing execution receipt."""
from test_executed_acceptance import repo
from app.modules.instinct_doc import executed_acceptance as m
from app.modules.instinct_doc.repo_evidence import snapshot,source_inventory

def test_report_retains_exact_local_identity_and_dirty_state(repo,monkeypatch):
    root,check=repo
    (root/'tests/test_ok.py').write_text('dirty local test bytes')
    snap=snapshot(root);source=source_inventory(root,'source.txt')
    monkeypatch.setattr(m,'execute_tests',lambda *a:dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest']))
    out=m.audit_selected_checks(root,'source.txt',[check])
    assert out['source_sha256']==source['sha256']
    assert [r['line_sha256'] for r in out['lines']]==[r['sha256'] for r in source['rows']]
    assert out['head']==snap['head'] and out['tree_digest']==snap['tree_digest']
    assert out['dirty'] is True
