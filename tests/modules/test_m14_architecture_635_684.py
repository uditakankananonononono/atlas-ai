import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m14_project_builder.architecture_support_635_684 import FEATURES,architecture_support_635_684
BASE={'system':'checkout','decision_owner':'platform-team'}
def payload(fid):
 d=dict(BASE)
 if fid<643:d|={'services':[{'id':'api'}],'windows':[{'name':'30d','total':1000,'good':995,'target':.99}],'incident_roles':['commander'],'runbook_steps':['assess']}
 elif fid<648:d|={'jobs':[{'id':'a','priority':1,'enqueued_at':'1'},{'id':'b','priority':2,'enqueued_at':'2'}],'dependencies':[{'from':'a','to':'b'}],'resource_limits':{'workers':2}}
 elif fid<658:d|={'messages':[{'id':'1','idempotency_key':'k','attempt':1},{'id':'2','idempotency_key':'k','attempt':3}],'delivery_policy':{'semantics':'at-least-once','base_delay_seconds':2,'max_delay_seconds':10,'max_attempts':3},'transaction_boundaries':['outbox']}
 elif fid<671:d|={'components':[{'id':'domain'},{'id':'adapter'}],'interfaces':[{'id':'port','consumer':'adapter','provider':'domain'}],'failure_isolation':['timeout']}
 else:d|={'contexts':[{'id':'sales','language':{'customer':'buyer'}},{'id':'support','language':{'customer':'caller'}}],'domain_events':[{'context_id':'sales','past_tense_name':'OrderPlaced'}],'aggregates':[{'id':'order'}]}
 return d
@pytest.mark.parametrize('fid',range(635,685))
def test_each_exact_ledger_row_is_implemented(fid):
 o=architecture_support_635_684(fid,payload(fid));assert o['feature_id']==fid and o['concept']==FEATURES[fid] and o['review_required'] and o['boundary']
def test_slo_and_error_budget_math_is_auditable():
 o=architecture_support_635_684(636,payload(636));w=o['sli_windows'][0];assert w['actual_sli']==.995 and w['allowed_bad_events']==10 and w['budget_remaining']==5
def test_dag_scheduler_rejects_cycles():
 d=payload(646);d['dependencies'].append({'from':'b','to':'a'})
 with pytest.raises(ValueError,match='cycle'):architecture_support_635_684(646,d)
def test_delivery_detects_duplicate_and_dlq_boundary():
 o=architecture_support_635_684(652,payload(652));assert not o['delivery_analysis'][0]['duplicate'] and o['delivery_analysis'][1]['duplicate'] and o['delivery_analysis'][1]['destination']=='dead_letter'
def test_pattern_validation_detects_unknown_component():
 d=payload(667);d['interfaces'][0]['provider']='missing';o=architecture_support_635_684(667,d);assert o['structural_violations'][0]['violation']=='unknown_component'
def test_ubiquitous_language_surfaces_context_collision():
 o=architecture_support_635_684(673,payload(673));assert o['language_collisions']==[{'term':'customer','meanings':['buyer','caller']}]
def test_negative_missing_owner_and_invalid_sli():
 with pytest.raises(ValueError):architecture_support_635_684(635,{'system':'x'})
 d=payload(635);d['windows'][0]['good']=1001
 with pytest.raises(ValueError):architecture_support_635_684(635,d)
def test_mounted_route_uses_tenant_boundary():
 r=TestClient(app).post('/api/v1/project-builder/architecture-635-684/support',headers={'x-atlas-tenant':'arch-t'},json={'feature_id':684,'data':payload(684)});assert r.status_code==200 and r.json()['tenant_id']=='arch-t' and r.json()['concept']=='Event Storming'
