import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m19_idea_incubator.luxury_venture import VentureBrief,build_luxury_venture

def brief():return {'brand_or_segment':'luxury hospitality','sector':'luxury_hospitality','customer_job':'Give returning guests relevant personal service without covert tracking.','constraints':['consent','brand tone'],'sources':[{'source_id':'s1','url':'https://example.com/report','title':'Guest report','observed_at':'2026-09-22','finding':'Guests value recognition but want control over stored preferences.'},{'source_id':'s2','url':'https://example.com/ops','title':'Operations report','observed_at':'2026-09-22','finding':'Service recovery is delayed when context is split across teams.'}],'signals':[{'signal_id':'privacy','statement':'Guests require visible preference controls.','source_ids':['s1'],'importance':.9},{'signal_id':'handoff','statement':'Staff handoffs lose actionable context.','source_ids':['s2'],'importance':.8}],'capabilities':[{'capability_id':'consented-memory','description':'Tenant-scoped preference ledger with revocation','readiness':.8}]}
def test_builds_three_ranked_cited_concepts_and_zero_cost_validation():
 out=build_luxury_venture(VentureBrief.model_validate(brief()))
 assert len(out['concepts'])==3 and out['recommended_concept_id']==out['concepts'][0]['concept_id']
 assert all(x['evidence_refs'] for x in out['concepts']) and all(x['scores']['weighted_total'] for x in out['concepts'])
 assert out['validation_experiment']['budget_limit']==0 and not out['validation_experiment']['external_action_started']
 assert out['pitch_brief']['status']=='review_only' and out['side_effects']==[]
def test_signal_importance_and_capability_readiness_change_scores():
 a=brief();b=brief();b['signals'][0]['importance']=.1;b['capabilities'][0]['readiness']=.1
 x=build_luxury_venture(VentureBrief.model_validate(a));y=build_luxury_venture(VentureBrief.model_validate(b))
 assert x['concepts'][0]['scores']['weighted_total']>y['concepts'][0]['scores']['weighted_total']
def test_rejects_unknown_or_duplicate_source_references():
 x=brief();x['signals'][0]['source_ids']=['missing']
 with pytest.raises(ValueError,match='unknown'):build_luxury_venture(VentureBrief.model_validate(x))
 x=brief();x['sources'][1]['source_id']='s1'
 with pytest.raises(ValueError,match='unique'):build_luxury_venture(VentureBrief.model_validate(x))
def test_mounted_route_is_tenant_scoped_and_has_no_effects():
 r=TestClient(app).post('/api/v1/idea-incubator/luxury-venture-studio',json=brief(),headers={'x-atlas-tenant':'venture-test','x-atlas-actor':'owner'})
 assert r.status_code==200 and r.json()['side_effects']==[] and r.json()['validation_experiment']['requires_approval_before_contact']
