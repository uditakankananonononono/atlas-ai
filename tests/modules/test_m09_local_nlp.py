"""Contract tests. Real-model tests are opt-in and never use fake vectors."""
import os
import math
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.modules.m09_knowledge_workspace import routes
from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository, SuggestionRow, NodeRow
from app.modules.m09_knowledge_workspace.schemas import NodeCreate, NodeUpdate
from app.modules.m09_knowledge_workspace.service import Service
from app.modules.m09_knowledge_workspace.local_nlp import NLPUnavailable, validate_vector
from test_m09_knowledge_workspace import Repo

@pytest.mark.parametrize('vector', [None, [], [0,0], [float('nan'),1], [float('inf'),1]])
def test_invalid_vectors_fail(vector):
    with pytest.raises(NLPUnavailable):validate_vector(vector)

def test_error_before_node_or_suggestion_write():
    repo=Repo()
    def broken(text):raise NLPUnavailable('test adapter unavailable')
    service=Service(repo,embed=lambda t:[1,0],extract_entities=broken)
    with pytest.raises(NLPUnavailable):service.create_node(NodeCreate(node_type='note',title='No write'))
    assert not repo.nodes and not repo.suggestions

def test_same_dimension_different_identity_not_compared():
    repo=Repo()
    a=Service(repo,embed=lambda t:[1,0],extract_entities=lambda t:[],embedding_identity={'model':'a','dimension':2})
    b=Service(repo,embed=lambda t:[1,0],extract_entities=lambda t:[],embedding_identity={'model':'b','dimension':2})
    a.create_node(NodeCreate(node_type='note',title='old'))
    new=b.create_node(NodeCreate(node_type='note',title='new'))
    assert not repo.suggestions
    assert new.metadata['_atlas_m09_nlp']['incompatible_nodes_skipped']==1

def test_unversioned_old_vectors_not_compared():
    repo=Repo();svc=Service(repo,embed=lambda t:[1,0],extract_entities=lambda t:[])
    old=svc.create_node(NodeCreate(node_type='note',title='old'))
    old.metadata={}
    new=svc.create_node(NodeCreate(node_type='note',title='new'))
    assert not repo.suggestions
    assert new.metadata['_atlas_m09_nlp']['incompatible_nodes_skipped']==1

def test_api_unavailable_is_503_and_no_write(monkeypatch):
    monkeypatch.setenv('ATLAS_M09_EMBEDDING_PROVIDER','unsupported')
    tenant='m09-unavailable-contract'
    app=FastAPI();app.include_router(routes.router)
    client=TestClient(app)
    response=client.post('/knowledge-workspace/nodes',headers={'X-Atlas-Tenant':tenant},json={'node_type':'note','title':'Must not persist'})
    assert response.status_code==503
    assert SqlGraphRepository(tenant,'local-user').list_nodes()==[]

@pytest.mark.skipif(os.getenv('ATLAS_M09_RUN_REAL_TESTS')!='1',reason='real downloaded models required')
def test_real_default_api_with_sql_and_ner(tmp_path):
    from uuid import uuid4
    tenant='m09-real-'+str(uuid4())
    app=FastAPI();app.include_router(routes.router);client=TestClient(app)
    headers={'X-Atlas-Tenant':tenant,'X-Atlas-Actor':'real-model-test'}
    status=client.get('/knowledge-workspace/nlp-status',headers=headers)
    assert status.status_code==200 and status.json()['embedding']['dimension']==384
    payload={'node_type':'note','title':'Paris','body':'Paris is the capital of France.'}
    first=client.post('/knowledge-workspace/nodes',headers=headers,json=payload)
    second=client.post('/knowledge-workspace/nodes',headers=headers,json=payload)
    mention=client.post('/knowledge-workspace/nodes',headers=headers,json={'node_type':'note','title':'Travel log','body':'I visited Paris with Alice last summer.'})
    assert first.status_code==second.status_code==mention.status_code==201
    a,b,m=first.json(),second.json(),mention.json()
    assert len(a['embedding'])==384 and all(math.isfinite(x) for x in a['embedding'])
    repo=SqlGraphRepository(tenant,'real-model-test')
    with repo.sessions() as db:
        suggestions=list(db.scalars(select(SuggestionRow).where(SuggestionRow.tenant_id==tenant)))
        related=[s for s in suggestions if s.source_id==b['id'] and s.target_id==a['id'] and s.relationship=='related_to']
        mentions=[s for s in suggestions if s.source_id==m['id'] and s.target_id==a['id'] and s.relationship=='mentions']
        assert related and related[0].score>0.999 and mentions
        assert all(s.status=='pending' for s in suggestions)
    update=client.patch('/knowledge-workspace/nodes/'+a['id'],headers=headers,json={'expected_version':1,'body':'Paris is a city in France.'})
    assert update.status_code==200 and update.json()['version']==2
    # A separate tenant cannot contribute to this tenant's graph.
    assert SqlGraphRepository('other-'+tenant,'real-model-test').list_nodes()==[]
    evidence={'status':status.json(),'nodes':[{k:v for k,v in n.items() if k!='embedding'} for n in (a,b,m)],
              'identical_text_similarity':related[0].score,
              'suggestions':[{'relationship':s.relationship,'status':s.status,'score':s.score,'reasons':s.reasons} for s in suggestions],
              'update_status':update.status_code}
    import json
    output=os.getenv('ATLAS_M09_EVIDENCE_PATH')
    if output:open(output,'w').write(json.dumps(evidence,indent=2))
