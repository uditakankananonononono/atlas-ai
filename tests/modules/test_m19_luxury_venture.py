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

def test_pitch_package_is_complete_review_only_and_selectable():
 from app.modules.m19_idea_incubator.luxury_venture import PitchPackageRequest,build_pitch_package
 p=build_pitch_package(PitchPackageRequest(brief=VentureBrief.model_validate(brief())))
 assert p['filename'].endswith('.md') and '# ' in p['markdown'] and '## Evidence' in p['markdown'] and '## Scorecard' in p['markdown']
 assert 'No brand affiliation' in p['markdown'] and p['review_status']=='pending' and not p['external_action_started']
 with pytest.raises(ValueError,match='concept_id'):build_pitch_package(PitchPackageRequest(brief=VentureBrief.model_validate(brief()),concept_id='absent'))
def test_mounted_pitch_export_and_tenant_isolated_portfolio_persistence():
 c=TestClient(app);a={'x-atlas-tenant':'lux-a','x-atlas-actor':'owner'};b={'x-atlas-tenant':'lux-b','x-atlas-actor':'owner'}
 p=c.post('/api/v1/idea-incubator/luxury-venture-studio/pitch-package',json={'brief':brief()},headers=a)
 assert p.status_code==200 and p.json()['media_type']=='text/markdown'
 saved=c.post('/api/v1/idea-incubator/luxury-venture-studio/portfolio',json={'brief':brief(),'owner_id':'owner'},headers=a)
 assert saved.status_code==201 and saved.json()['metadata']['review_status']=='pending'
 assert any(x['id']==saved.json()['id'] for x in c.get('/api/v1/idea-incubator/portfolio/ideas',headers=a).json())
 assert all(x['id']!=saved.json()['id'] for x in c.get('/api/v1/idea-incubator/portfolio/ideas',headers=b).json())

def outreach():return {'concept_id':'guest_or_owner_intelligence','recipient_organization':'Example Hotel','recipient_role':'Innovation lead','channel':'email','subject':'Review-only service concept','body':'We developed a cited concept addressing consented guest recognition. Would you review the problem framing?','evidence_refs':['s1','s2']}
def test_outreach_creates_pending_tenant_approval_but_does_not_send():
 c=TestClient(app);h={'x-atlas-tenant':'lux-out','x-atlas-actor':'owner'}
 r=c.post('/api/v1/idea-incubator/luxury-venture-studio/outreach-preview',json={'package':{'brief':brief()},'outreach':outreach()},headers=h)
 assert r.status_code==201 and r.json()['status']=='pending' and r.json()['action_type']=='luxury_venture_outreach'
 assert r.json()['payload']['sent'] is False and r.json()['payload']['tenant_id']=='lux-out'
def test_outreach_rejects_false_affiliation_and_uncited_evidence():
 c=TestClient(app);h={'x-atlas-tenant':'lux-safe','x-atlas-actor':'owner'}
 x=outreach();x['body']='We are an official partner and this demand is guaranteed.'
 assert c.post('/api/v1/idea-incubator/luxury-venture-studio/outreach-preview',json={'package':{'brief':brief()},'outreach':x},headers=h).status_code==422
 x=outreach();x['evidence_refs']=['absent']
 assert c.post('/api/v1/idea-incubator/luxury-venture-studio/outreach-preview',json={'package':{'brief':brief()},'outreach':x},headers=h).status_code==422

def test_measured_outcome_becomes_immutable_evidence_without_auto_promotion():
 c=TestClient(app);h={'x-atlas-tenant':'lux-learn','x-atlas-actor':'owner'}
 saved=c.post('/api/v1/idea-incubator/luxury-venture-studio/portfolio',json={'brief':brief(),'owner_id':'owner'},headers=h).json();iid=saved['id']
 exp=c.post(f'/api/v1/idea-incubator/portfolio/ideas/{iid}/experiments',json={'name':'Five interviews','hypothesis':'Three rank problem top two','method':'Structured interviews','metric':'qualified confirmations','target':3},headers=h).json();eid=exp['id']
 assert c.patch(f'/api/v1/idea-incubator/portfolio/ideas/{iid}/experiments/{eid}',json={'status':'running'},headers=h).status_code==200
 out=c.post(f'/api/v1/idea-incubator/luxury-venture-studio/portfolio/{iid}/experiments/{eid}/outcome',json={'outcome':{'status':'succeeded','observed_value':4,'target':3,'learnings':'Four participants independently confirmed the problem priority.','source_refs':['interview-notes-1']}},headers=h)
 assert out.status_code==200 and out.json()['learning_summary']['promotion_recommendation']=='advance_to_owner_review'
 assert out.json()['learning_summary']['automatic_promotion'] is False and not out.json()['idea_stage_changed']
 dossier=c.get(f'/api/v1/idea-incubator/portfolio/ideas/{iid}',headers=h).json()
 assert dossier['experiments'][0]['status']=='succeeded' and dossier['evidence_summary']['supporting_count']==1
 assert c.post(f'/api/v1/idea-incubator/luxury-venture-studio/portfolio/{iid}/experiments/{eid}/outcome',json={'outcome':{'status':'succeeded','observed_value':4,'target':3,'learnings':'Duplicate outcome must be rejected as immutable.','source_refs':['interview-notes-1']}},headers=h).status_code==409
def test_outcome_status_must_match_measured_target():
 from app.modules.m19_idea_incubator.luxury_venture import VentureOutcome,summarize_outcome
 with pytest.raises(ValueError,match='conflicts'):summarize_outcome(VentureOutcome(status='succeeded',observed_value=1,target=3,learnings='The target was not met in the measured test.',source_refs=['r']))
