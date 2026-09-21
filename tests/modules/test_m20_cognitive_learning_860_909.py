from datetime import datetime,timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import *
from app.modules.m20_general_cognitive_worker.cognitive_learning_routes_860_909 import router
S=[{'source_id':'s','observed_at':datetime.now(timezone.utc).isoformat(),'kind':'primary'}]
def complete(i):
 d={x:f'{x} evidence' for x in STAGES[i]}
 for key in ('typed_links','relations','typed_edges'):
  if key in d:d[key]=[{'from':'a','to':'b','type':'related_to'}]
 if 'revised_confidence' in d:d['revised_confidence']=[{'belief':'x','confidence':.7}]
 return {'sources':S,'inputs':d,'learner_goals':['learn'],'criteria':['accuracy'],'ethical_review':i in (890,891)}
@pytest.mark.parametrize('i',range(860,910))
def test_each_row_has_exact_concept_and_distinct_complete_workflow(i):
 o=execute(i,complete(i));assert o['row_id']==i and o['capability']==ROWS[i] and o['key']==KEYS[i] and o['complete'] and not o['evidence_gaps'] and len(o['workflow'])==len(STAGES[i]) and not o['assessment']['grade_or_credential_awarded'] and o['actions_taken']==[]
def test_historical_thinking_requires_source_classification():
 p=complete(860);p['sources'][0]['kind']='blog'
 with pytest.raises(CognitiveLearningError,match='primary or secondary'):execute(860,p)
def test_critical_thinking_has_claim_evidence_assumption_alternatives():assert STAGES[861][:4]==['claim','evidence','assumptions','alternatives']
def test_creative_divergent_convergent_are_not_collapsed():assert STAGES[862]!=STAGES[864]!=STAGES[865]
def test_reframing_perspective_paradigm_are_distinct():assert len({tuple(STAGES[i]) for i in (867,868,869)})==3
def test_missing_stage_is_explicit_gap():
 p=complete(870);del p['inputs']['boundary_cases'];o=execute(870,p);assert not o['complete'] and o['evidence_gaps']==['boundary_cases']
@pytest.mark.parametrize('i,edge_key',[(871,'typed_links'),(875,'relations'),(876,'typed_edges')])
def test_graph_knowledge_requires_typed_relations(i,edge_key):
 p=complete(i);p['inputs'][edge_key]=[{'from':'a','to':'b'}]
 with pytest.raises(CognitiveLearningError,match='relation type'):execute(i,p)
def test_belief_revision_confidence_range():
 p=complete(880);p['inputs']['revised_confidence']=[{'belief':'x','confidence':1.2}]
 with pytest.raises(CognitiveLearningError,match='confidence'):execute(880,p)
def test_theory_and_conceptual_change_are_distinct():assert STAGES[881]!=STAGES[882]
def test_learning_modes_883_895_each_unique():assert len({tuple(STAGES[i]) for i in range(883,896)})==13
@pytest.mark.parametrize('i',[890,891])
def test_conditioning_requires_explicit_ethical_review(i):
 p=complete(i);p['ethical_review']=False
 with pytest.raises(CognitiveLearningError,match='ethical_review'):execute(i,p)
def test_conditioning_with_review_remains_draft():
 p=complete(890);p['ethical_review']=True;assert execute(890,p)['status'].startswith('draft')
def test_observational_social_vicarious_are_distinct():assert len({tuple(STAGES[i]) for i in (892,893,894)})==3
def test_project_problem_inquiry_discovery_guided_are_distinct():assert len({tuple(STAGES[i]) for i in range(898,903)})==5
def test_direct_and_explicit_are_distinct():assert STAGES[903]!=STAGES[904]
def test_implicit_incidental_intentional_formal_informal_distinct():assert len({tuple(STAGES[i]) for i in range(905,910)})==5
def test_formal_learning_rejects_credential_claim():
 p=complete(908);p['inputs']['credential_boundary']=True
 with pytest.raises(CognitiveLearningError,match='limits'):execute(908,p)
def test_provenance_required():
 p=complete(861);p['sources']=[]
 with pytest.raises(CognitiveLearningError,match='sources'):execute(861,p)
def test_exact_range_and_titles():assert set(ROWS)==set(range(860,910)) and ROWS[860]=='Historical Thinking' and ROWS[909]=='Informal Learning'
def test_mounted_boundary():
 a=FastAPI();a.include_router(router,prefix='/api/modules/20');c=TestClient(a);r=c.post('/api/modules/20/cognitive-learning-860-909/861',json={'payload':complete(861)});assert r.status_code==200 and r.json()['capability']=='Critical Thinking'
def test_capabilities_route_lists_fifty():
 a=FastAPI();a.include_router(router);assert len(TestClient(a).get('/cognitive-learning-860-909/capabilities').json())==50
def test_unknown_row_rejected():
 a=FastAPI();a.include_router(router);assert TestClient(a).post('/cognitive-learning-860-909/859',json={'payload':{}}).status_code==422

def test_critical_thinking_weights_evidence_and_reports_uncertainty():
 p={'tenant_id':'school-a','sources':[{'source_id':'s','observed_at':'2026-09-21','kind':'primary'}],
    'inputs':{k:'present' for k in STAGES[861]}}
 p['inputs']['evidence']=[{'id':'e1','relevance':.8,'reliability':.5,'independence':.5,'direction':'support'},{'id':'e2','relevance':.6,'reliability':1,'direction':'against'}]
 p['inputs']['alternatives']=['rival']
 o=execute(861,p)
 assert o['tenant_id']=='school-a' and o['computed']['total_support']==.2
 assert o['computed']['total_counterevidence']==.6 and o['evaluation']['uncertainty']<.2

def test_graph_validation_finds_dangling_edges():
 p={'sources':[{'source_id':'s','observed_at':'2026-09-21'}], 'inputs':{k:'x' for k in STAGES[876]}}
 p['inputs'].update(nodes=['a'],typed_edges=[{'source':'a','target':'missing','type':'supports'}])
 assert execute(876,p)['computed']['graph_valid'] is False

def test_cross_tenant_reference_is_rejected():
 p={'tenant_id':'a','resource_refs':[{'tenant_id':'b','id':'secret'}],'sources':[{'source_id':'s','observed_at':'2026'}],'inputs':{'claim':'x'}}
 with pytest.raises(CognitiveLearningError,match='cross-tenant'): execute(861,p)

def test_bad_evidence_score_is_rejected():
 p={'sources':[{'source_id':'s','observed_at':'2026'}],'inputs':{k:'x' for k in STAGES[861]}}
 p['inputs']['evidence']=[{'relevance':2,'reliability':1}]
 with pytest.raises(CognitiveLearningError,match='scores'): execute(861,p)
