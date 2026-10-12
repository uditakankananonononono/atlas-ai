"""Exact upper-edge refusals; controlled execution avoids 1001 subprocesses."""
import pytest
from test_executed_acceptance import repo
from app.modules.instinct_doc import executed_acceptance as m
from app.modules.instinct_doc.repo_evidence import EvidenceError,snapshot

@pytest.mark.parametrize('case',['checks','id','paths'])
def test_acceptance_exact_upper_edges_refused(repo,monkeypatch,case):
    root,check=repo;snap=snapshot(root);calls=[]
    def execute(*a):
        calls.append(a)
        return dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest'])
    monkeypatch.setattr(m,'execute_tests',execute)
    checks=[check]
    if case=='checks':checks=[dict(check,id='check'+str(i)) for i in range(1001)]
    if case=='id':checks=[dict(check,id='x'*129)]
    if case=='paths':checks=[dict(check,test_paths=check['test_paths']*101)]
    with pytest.raises(EvidenceError):m.audit_selected_checks(root,'source.txt',checks)
    assert calls==[]
