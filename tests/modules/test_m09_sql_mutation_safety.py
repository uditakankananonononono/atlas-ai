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
