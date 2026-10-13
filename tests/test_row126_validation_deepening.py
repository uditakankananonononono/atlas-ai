"""Project observation upper edges and isolated status drift."""
import pytest
from test_project_code_execution_summary import repo
from app.modules.instinct_doc import code_test_summary_p256 as m
from app.modules.instinct_doc import repo_evidence as e

@pytest.mark.parametrize('case',['bytes','execute','projects'])
def test_project_upper_edges_refused(repo,case):
    root,item=repo
    kw={};items=[item]
    if case=='bytes':kw['max_initial_bytes']=64_000_001
    if case=='execute':kw['execute']=1
    if case=='projects':items=[dict(item,id='P'+str(i)) for i in range(257)]
    with pytest.raises(ValueError):m.inspect_projects(root,items,**kw)

def test_isolated_final_status_digest_drift_demotes(repo,monkeypatch):
    root,item=repo;original=e.snapshot;calls=[]
    def snapshot(path):
        value=original(path);calls.append(1)
        if len(calls)==2:value=dict(value,status_digest='isolated-drift')
        return value
    monkeypatch.setattr(e,'snapshot',snapshot)
    out=m.inspect_projects(root,[item])
    assert out['final_snapshot_stable'] is False
    assert out['projects'][0]['failure_reason']=='final_project_tree_drift'
