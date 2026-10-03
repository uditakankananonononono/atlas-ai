"""Real CPU/SQL regressions for audit findings, not fake embedding acceptance."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from sqlalchemy import event, select
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository, SuggestionRow, NodeRow, AuditRow, EdgeRow
from app.modules.m09_knowledge_workspace.schemas import NodeCreate, NodeUpdate
from app.modules.m09_knowledge_workspace.service import Service, ConflictError

pytestmark=pytest.mark.skipif(os.getenv('ATLAS_M09_RUN_REAL_TESTS')!='1',reason='requires real trained CPU models')

def setup():
    tenant='sql-safety-'+str(uuid4());repo=SqlGraphRepository(tenant,'tester');return tenant,repo,Service(repo)

def suggestions(repo):
    with repo.sessions() as db:return list(db.scalars(select(SuggestionRow).where(SuggestionRow.tenant_id==repo.tenant_id)))

def test_stale_suggestion_acceptance_after_source_or_target_edit():
    for edited_side in ('source','target'):
        tenant,repo,svc=setup();client=TestClient(app);headers={'X-Atlas-Tenant':tenant}
        payload={'node_type':'note','title':'Paris','body':'Paris is the capital of France.'}
        a=svc.create_node(NodeCreate(**payload));b=svc.create_node(NodeCreate(**payload))
        old=next(s for s in suggestions(repo) if s.relationship=='related_to')
        edited=b if edited_side=='source' else a
        r=client.patch('/api/v1/knowledge-workspace/nodes/'+edited.id,headers=headers,json={'expected_version':1,'title':'Database backups','body':'SQLite transactions and concurrency control.'})
        assert r.status_code==200
        r=client.post('/api/v1/knowledge-workspace/suggestions/'+old.id+'/review',headers=headers,json={'accept':True})
        assert r.status_code==409
        assert not repo.edges_for({a.id,b.id})

def test_suggestion_insert_failure_rolls_back_node_and_audit():
    _,repo,svc=setup();a=svc.create_node(NodeCreate(node_type='note',title='Paris',body='Paris is the capital of France.'))
    def fail(mapper,connection,target):
        if target.tenant_id==repo.tenant_id:raise RuntimeError('forced suggestion storage failure')
    event.listen(SuggestionRow,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='forced suggestion'):svc.create_node(NodeCreate(node_type='note',title=a.title,body=a.body))
    finally:event.remove(SuggestionRow,'before_insert',fail)
    assert len(repo.list_nodes())==1
    with repo.sessions() as db:assert len(list(db.scalars(select(AuditRow).where(AuditRow.tenant_id==repo.tenant_id))))==1

def test_overlapping_expected_version_updates_have_one_winner():
    _,repo,svc=setup();a=svc.create_node(NodeCreate(node_type='note',title='Paris'))
    barrier=Barrier(2)
    class Overlap(Service):
        def _prepare(self,node):
            result=super()._prepare(node);barrier.wait(timeout=15);return result
    def write(title):
        try:
            return Overlap(SqlGraphRepository(repo.tenant_id,'tester')).update_node(a.id,NodeUpdate(expected_version=1,title=title)).version
        except ConflictError:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,['Paris one','Paris two']))
    assert sorted(map(str,results))==['2','conflict']
    assert repo.get_node(a.id).version==2

def test_untrained_named_ner_configuration_is_rejected(tmp_path,monkeypatch):
    import spacy
    from app.modules.m09_knowledge_workspace.local_nlp import get_local_nlp,NLPUnavailable
    blank=spacy.blank('en');blank.add_pipe('ner');blank.initialize();blank.to_disk(tmp_path/'blank')
    monkeypatch.setenv('ATLAS_M09_SPACY_MODEL',str(tmp_path/'blank'))
    with pytest.raises(NLPUnavailable):get_local_nlp()

def test_update_suggestion_failure_rolls_back_node_invalidation_and_audit():
    _,repo,svc=setup();a=svc.create_node(NodeCreate(node_type='note',title='Paris'))
    b=svc.create_node(NodeCreate(node_type='note',title='Paris'))
    old=list(suggestions(repo));old_ids={s.id for s in old}
    def fail(mapper,connection,target):
        if target.tenant_id==repo.tenant_id:raise RuntimeError('forced proposal refresh failure')
    event.listen(SuggestionRow,'before_update',fail)
    try:
        with pytest.raises(RuntimeError,match='forced proposal'):svc.update_node(b.id,NodeUpdate(expected_version=1,body='Paris'))
    finally:event.remove(SuggestionRow,'before_update',fail)
    assert repo.get_node(b.id).version==1
    assert {s.id for s in suggestions(repo)}==old_ids
    assert all(s.status=='pending' for s in suggestions(repo))

def test_review_edge_failure_rolls_back_status_and_audit():
    _,repo,svc=setup();a=svc.create_node(NodeCreate(node_type='note',title='Paris'));b=svc.create_node(NodeCreate(node_type='note',title='Paris'))
    old=next(s for s in suggestions(repo) if s.relationship=='related_to')
    def fail(mapper,connection,target):
        if target.tenant_id==repo.tenant_id:raise RuntimeError('forced edge insert failure')
    event.listen(EdgeRow,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='forced edge'):svc.review(old.id,True)
    finally:event.remove(EdgeRow,'before_insert',fail)
    assert repo.get_suggestion(old.id).status.value=='pending' and not repo.edges_for({a.id,b.id})

def test_overlapping_reviews_have_one_winner_and_one_edge():
    _,repo,svc=setup();a=svc.create_node(NodeCreate(node_type='note',title='Paris'));b=svc.create_node(NodeCreate(node_type='note',title='Paris'))
    old=next(s for s in suggestions(repo) if s.relationship=='related_to')
    barrier=Barrier(2)
    def approve(_):
        barrier.wait(timeout=15)
        try:return Service(SqlGraphRepository(repo.tenant_id,'tester')).review(old.id,True).status.value
        except ConflictError:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(approve,[0,1]))
    assert sorted(results)==['accepted','conflict'] and len(repo.edges_for({a.id,b.id}))==1

def test_manual_opposing_child_edges_cannot_commit_cycle(monkeypatch):
    _,repo,svc=setup();a=svc.create_node(NodeCreate(node_type='note',title='Parent'));b=svc.create_node(NodeCreate(node_type='note',title='Child'))
    client=TestClient(app);headers={'X-Atlas-Tenant':repo.tenant_id}
    barrier=Barrier(2);original=Service._reachable
    def overlap(self,*args):
        answer=original(self,*args);barrier.wait(timeout=15);return answer
    monkeypatch.setattr(Service,'_reachable',overlap)
    def write(pair):
        return client.post('/api/v1/knowledge-workspace/edges',headers=headers,json={'source_id':pair[0],'target_id':pair[1],'relationship':'child_of'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,[(a.id,b.id),(b.id,a.id)]))
    assert sorted(results)==[201,409]
    assert len(repo.edges_for({a.id,b.id}))==1
