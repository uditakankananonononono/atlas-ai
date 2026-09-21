import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m15_document_generator.design_support_333_359 import FEATURES,design_support_333_359
BASE={'brief':'Build and test a concept','decision_owner':'design-team'}
def payload(fid):
 d=dict(BASE)
 if fid<335:d|={'requirements':[{'id':'r','text':'safe use'}],'hazards':[{'id':'h','severity':3,'likelihood':2}],'controls':[{'id':'c','addresses':['h']}],'verification_plan':['prototype test']}
 elif fid<344:d|={'gameplay_loops':[{'id':'loop'}],'content_nodes':[{'id':'level'}],'playtests':[{'completion_rate':.8,'duration_minutes':10}],'economy':{'sources':[{'amount':5}],'sinks':[{'amount':3}]}}
 elif fid<353:d|={'participants':[{'id':'p','lived_experience':'self-described'}],'needs':[{'id':'captions'}],'variants':[{'id':'v','addresses':['captions']}],'required_message_keys':['start','stop'],'locales':[{'locale':'as','messages':{'start':'x'}}]}
 else:d|={'stakeholders':[{'id':'user'}],'evidence':[{'id':'interview'}],'criteria':[{'id':'value','weight':2}],'ideas':[{'id':'i','scores':{'value':4}}],'tests':['prototype interview']}
 return d
@pytest.mark.parametrize('fid',range(333,360))
def test_every_exact_tail_row_is_substantive(fid):
 o=design_support_333_359(fid,payload(fid));assert o['feature_id']==fid and o['concept']==FEATURES[fid] and o['review_required'] and o['boundary']
def test_marine_toy_hazard_register_links_controls_and_requires_test():
 o=design_support_333_359(333,payload(333));assert o['risk_register'][0]=={'hazard_id':'h','severity':3,'likelihood':2,'risk_score':6,'control_ids':['c'],'residual_status':'requires_test'}
def test_game_balance_uses_playtest_and_economy_metrics():
 o=design_support_333_359(342,payload(342));assert o['balance_metrics']=={'mean_completion_rate':.8,'mean_duration_minutes':10,'currency_net':2}
def test_localization_preserves_missing_keys_for_linguist_review():
 o=design_support_333_359(345,payload(345));assert o['locales'][0]['missing_keys']==['stop'] and o['locales'][0]['status']=='incomplete'
def test_inclusive_coverage_exposes_unmet_need():
 d=payload(349);d['needs'].append({'id':'switch'});o=design_support_333_359(349,d);assert o['coverage'][1]=={'need_id':'switch','variant_ids':[],'status':'gap'}
def test_process_scoring_refuses_score_when_criterion_missing():
 d=payload(354);d['criteria'].append({'id':'risk','weight':1});o=design_support_333_359(354,d);assert o['ideas'][0]['weighted_score'] is None and o['ideas'][0]['missing_criteria']==['risk']
def test_negative_paths_reject_missing_owner_and_domain_inputs():
 with pytest.raises(ValueError):design_support_333_359(333,{'brief':'x'})
 with pytest.raises(ValueError):design_support_333_359(335,BASE)
 with pytest.raises(ValueError):design_support_333_359(360,BASE)
def test_mounted_route_is_tenant_scoped():
 r=TestClient(app).post('/api/v1/document-generator/design-333-359/support',headers={'x-atlas-tenant':'design-t'},json={'feature_id':359,'data':payload(359)});assert r.status_code==200 and r.json()['tenant_id']=='design-t' and r.json()['concept']=='Service Design'
