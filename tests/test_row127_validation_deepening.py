"""Comparison boundaries and invalid-duration retention, controlled receipts."""
import pytest
from test_executed_comparison import repo
from app.modules.instinct_doc import executed_comparison as m
from app.modules.instinct_doc.repo_evidence import EvidenceError,snapshot

@pytest.mark.parametrize('case',['subjects','id','paths'])
def test_comparison_upper_edges_refused_before_execution(repo,monkeypatch,case):
    subjects=[dict(id='a',test_paths=['tests/test_a.py']),dict(id='b',test_paths=['tests/test_b.py'])]
    if case=='subjects':subjects=[dict(subjects[0],id='s'+str(i)) for i in range(11)]
    if case=='id':subjects[0]['id']='x'*129
    if case=='paths':subjects[0]['test_paths']*=101
    snap=snapshot(repo);calls=[]
    def execute(*a):
        calls.append(a)
        return dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest'],duration_seconds=1)
    monkeypatch.setattr(m,'execute_tests',execute)
    with pytest.raises(EvidenceError):m.compare_selected_tests(repo,subjects,repeats=1)
    assert calls==[]

def test_negative_duration_refused_and_workload_disclaimed(repo,monkeypatch):
    snap=snapshot(repo)
    monkeypatch.setattr(m,'execute_tests',lambda *a:dict(status='SCOPED_PASS',head=snap['head'],tree_digest=snap['tree_digest'],duration_seconds=-0.5))
    subjects=[dict(id='a',test_paths=['tests/test_a.py']),dict(id='b',test_paths=['tests/test_b.py'])]
    out=m.compare_selected_tests(repo,subjects,repeats=1)
    for row in out['subjects']:
        assert row['status']=='UNVERIFIED'
        assert row['runs'][0]['duration_seconds'] is None
        assert row['runs'][0]['error']=='EvidenceError'
        assert row['semantic_workload_equivalence_verified'] is False
