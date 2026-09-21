import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m21_claire.owner_workflow_279_329 import FEATURES,claire_owner_workflow_279_329,preference_feedback_4_6_9
BASE={'goal':'deliver verified result','acceptance_criteria':[{'criterion':'tests pass','evidence_ids':['e']} ]}
def payload(row):
 d=dict(BASE)
 if row in set(range(284,310))|{322,327,328,329}:d|={'plans':[{'id':'p','operation':'preview','external_effect':True,'risk':'medium','approval':{'decision':'approved','scope':'p'},'rollback':'restore'}],'evidence':[{'id':'e','provenance':'test runner','verification':'verified'}],'tests':['unit']}
 elif row in set(range(313,321))|{323,325}:d|={'approval_request':{'id':'a','operation':'install','decision':'approved','scope':'one-package'},'budget':{'seconds':2,'cost':0,'attempts':1,'limits':{'seconds':10,'cost':1,'attempts':2}}}
 else:d|={'evidence':[{'id':'e','provenance':'test runner','verification':'verified'}],'decision_evidence':[{'input':'goal','alternative':'preview only','outcome':'selected'}],'honest_limits':['external state unverified']}
 return d
@pytest.mark.parametrize('row',range(279,330))
def test_every_claire_owner_row_exact_and_substantive(row):
 o=claire_owner_workflow_279_329(row,payload(row));assert o['row_id']==row and o['concept']==FEATURES[row] and o['review_required'] and o['boundary'] and 'hidden chain-of-thought' in o['disclaimer']
def test_completion_claim_needs_verified_evidence_for_every_criterion():
 assert claire_owner_workflow_279_329(321,payload(321))['completion_claim']=='complete';d=payload(321);d['evidence'][0]['verification']='unverified';assert claire_owner_workflow_279_329(321,d)['completion_claim']=='not_verified_complete'
def test_external_action_without_exact_approval_is_blocked():
 d=payload(286);d['plans'][0]['approval']['scope']='other';o=claire_owner_workflow_279_329(286,d);assert not o['plans'][0]['authorized'] and o['plans'][0]['execution_status']=='blocked_pending_approval'
def test_revocation_stop_and_budget_overrun_block_action():
 for change in ({'stop_requested':True},{'approval_request':{'id':'a','operation':'install','decision':'revoked'}},{'budget':{'seconds':20,'cost':0,'attempts':1,'limits':{'seconds':10,'cost':1,'attempts':2}}}):
  d=payload(325);d.update(change);assert claire_owner_workflow_279_329(325,d)['stopped']
def pref(fid,decision='approved'):
 return {'consent':{'status':'granted','scope':'writing-assistant'},'provenance':[{'source':'owner correction','id':'m1'}],'examples':[{'id':'x','purpose':'match concise style'}],'holdout':[{'baseline_score':.5,'candidate_score':.8}], 'candidates':[{'id':'a','score':.9},{'id':'b','score':.5}],'owner_decision':decision}
@pytest.mark.parametrize('fid,name',[(4,'Voice Fine-Tuning'),(6,'Preference Ranking'),(9,'Human-in-the-Loop Reinforcement (Weekly)')])
def test_thin_rows_require_holdout_consent_provenance_and_owner_approval(fid,name):
 o=preference_feedback_4_6_9(fid,pref(fid));assert o['concept']==name and o['holdout_evaluation']['improved'] and o['behavior_mutated'] and o['promotion_status']=='promoted'
def test_no_silent_mutation_without_owner_approval():
 o=preference_feedback_4_6_9(4,pref(4,'pending'));assert not o['behavior_mutated'] and o['promotion_status'].startswith('blocked')
def test_revocation_detector_evasion_and_impersonation_are_rejected():
 d=pref(4);d['consent']['revoked_at']='2026-01-01'
 with pytest.raises(ValueError,match='revoked'):preference_feedback_4_6_9(4,d)
 for purpose in ('detector evasion','impersonate a person'):
  d=pref(4);d['examples'][0]['purpose']=purpose
  with pytest.raises(ValueError):preference_feedback_4_6_9(4,d)
def test_routes_mounted_and_tenant_scoped():
 c=TestClient(app);r=c.post('/api/v1/claire/owner-workflow-279-329',headers={'x-atlas-tenant':'claire-t'},json={'row_id':329,'data':payload(329)});assert r.status_code==200 and r.json()['tenant_id']=='claire-t'
 p=c.post('/api/v1/claire/preference-feedback-4-6-9',headers={'x-atlas-tenant':'claire-t'},json={'feature_id':6,'data':pref(6)});assert p.status_code==200 and p.json()['behavior_mutated']
