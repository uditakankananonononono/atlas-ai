"""Controlled isolated final identity-field drift, not external evidence."""
import pytest
from test_executed_acceptance import repo
from app.modules.instinct_doc import executed_acceptance as mod


@pytest.mark.parametrize('field',['head','tree_digest','status_digest'])
def test_isolated_final_field_is_required(repo,monkeypatch,field):
    root,check=repo;original=mod.snapshot;calls=[]
    initial=original(root)
    def final_field(*args):
        calls.append(1);out=dict(initial)
        if len(calls)>1:out[field]='controlled-final-drift'
        return out
    monkeypatch.setattr(mod,'snapshot',final_field)
    monkeypatch.setattr(mod,'execute_tests',lambda *a:{'status':'SCOPED_PASS','head':initial['head'],'tree_digest':initial['tree_digest']})
    out=mod.audit_selected_checks(root,'source.txt',[check])
    assert out['tree_stable_after_runs'] is False
    assert out['scoped_passing_lines']==0
