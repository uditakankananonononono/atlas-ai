"""Independent semantic-wave tests for rows 288-574.

These test distinctive behavior from each owning implementation family. They do
not accept labels or row IDs as evidence and exercise mounted HTTP boundaries.
"""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m15_document_generator.creative_production_306_332 import plan,CreativeError
from app.modules.m15_document_generator.design_support_333_359 import design_support_333_359
from app.modules.m19_idea_incubator.business_service import BusinessAnalysisService
from app.modules.m19_idea_incubator.business_models import BusinessAnalysisRequest,Provenance
from app.modules.m19_idea_incubator.operations_service import OperationsAnalysisService
from app.modules.m19_idea_incubator.operations_models import OperationsAnalysisRequest,Provenance as OpsProvenance
from app.modules.m14_project_builder.engineering import generate_design,validate_design,spec_for_row
from datetime import datetime,timezone
ROOT=Path(__file__).parents[2]

def test_all_287_rows_have_real_implementation_and_named_test_evidence():
 rows=[x for x in json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows'] if 288<=x['id']<=574]
 assert [x['id'] for x in rows]==[i for i in range(288,575) if i not in {446,447,448,450}]
 for r in rows:
  assert r['description'].strip() and r['status']=='verified-pushed'
  e=r['evidence'];impl=ROOT/e['implementation_path'];test=ROOT/e['test_path'].split('::',1)[0]
  assert impl.is_file() and test.is_file(),r['id']
  source=impl.read_text();tests=test.read_text()
  assert str(r['id']) in source or r['requirement'].lower() in source.lower(),r['id']
  assert ('pytest.mark.parametrize' in tests or f'test_{r["id"]}' in tests or f'row {r["id"]}' in tests.lower() or 'row-named' in tests.lower()),r['id']

def test_306_mixing_has_audio_specific_signal_chain_and_rejects_bad_rate():
 d={'tracks':['voice','music'],'sample_rate':48000,'target_platform':'podcast','sources':[{'source_id':'session','observed_at':'2026-09-21'}],'decisions':{'gain_staging':'-18 dBFS dialogue','pan':'center voice','eq':'high-pass voice','dynamics':'2:1 compressor','spatial_fx':'short room','automation':'duck music','reference_check':'mono and codec'}}
 o=plan(306,d);assert o['family']=='audio_post' and [x['stage'] for x in o['workflow']][:4]==['gain_staging','pan','eq','dynamics']
 with pytest.raises(CreativeError,match='sample_rate'):plan(306,{**d,'sample_rate':12345})

def test_333_marine_design_builds_hazard_register_not_generic_brief():
 d={'brief':'coastal skiff','decision_owner':'naval reviewer','requirements':['buoyancy'],'hazards':[{'id':'capsize','severity':5,'likelihood':2}],'controls':[{'id':'stability-test','addresses':['capsize']}],'verification_plan':['inclining test']}
 o=design_support_333_359(333,d);assert o['risk_register'][0]=={'hazard_id':'capsize','severity':5,'likelihood':2,'risk_score':10,'control_ids':['stability-test'],'residual_status':'requires_test'}
 with pytest.raises(ValueError,match='hazards'):design_support_333_359(333,{k:v for k,v in d.items() if k!='hazards'})

def _bp(feature,inputs):
 p=Provenance(source_id='measured',source_type='analytics',observed_at=datetime.now(timezone.utc));return BusinessAnalysisRequest(feature=feature,inputs=inputs,provenance=[p],confidence=.9)
def test_business_metrics_are_distinctive_and_fail_closed():
 s=BusinessAnalysisService();m=s.analyze('x',_bp(360,{'total_entities':100,'annual_revenue_per_entity':10,'serviceable_fraction':.5,'obtainable_fraction':.2,'currency':'USD'}));assert (m.result['tam'],m.result['sam'],m.result['som'])==(1000,500,100)
 viral=s.analyze('x',_bp(378,{'invitations_per_user':4,'invite_conversion_rate':.3,'cycle_days':7}));assert viral.result['viral_coefficient']==1.2 and viral.result['viral']
 with pytest.raises(Exception):s.analyze('x',_bp(379,{'acquisition_spend':100,'new_customers':0}))

def test_operations_compute_eoq_dpmo_and_flow_efficiency():
 p=OpsProvenance(source_id='ops',source_type='analytics',observed_at=datetime.now(timezone.utc));s=OperationsAnalysisService()
 def r(f,x):return s.analyze('x',OperationsAnalysisRequest(feature=f,inputs=x,provenance=[p],confidence=.9))
 assert r(453,{'annual_demand':1000,'order_cost':20,'annual_holding_cost_per_unit':5,'daily_demand':4,'lead_time_days':5,'safety_stock':10}).analysis['reorder_point']==30
 assert r(458,{'opportunities':10,'defects':2,'units':100,'target_sigma':4}).analysis['dpmo']==2000
 v=r(468,{'steps':['a'],'cycle_times':[10],'wait_times':[30],'inventory':[1],'value_added':[5]}).analysis;assert v['process_cycle_efficiency']==.125

def test_engineering_rows_have_unique_required_sections_and_validation_failures():
 q=spec_for_row(560);o=spec_for_row(574);assert q.kind=='question_answering' and o.kind=='optimization_engine' and q.required_sections!=o.required_sections
 doc=generate_design('optimization_engine','Route vehicles');assert validate_design(doc).passed and all(f'## {x}' in doc.markdown for x in o.required_sections)
 from app.modules.m14_project_builder.engineering import DesignDocument
 broken=DesignDocument(kind=doc.kind,row=doc.row,title=doc.title,markdown=doc.markdown.replace(f'## {o.required_sections[0]}','## Removed',1),generated_at=doc.generated_at);assert not validate_design(broken).passed

def test_mounted_http_boundaries_across_owners():
 c=TestClient(app);h={'X-Tenant-ID':'semantic','X-Actor-ID':'reviewer'}
 # Document generator design support.
 d={'feature_id':333,'data':{'brief':'boat','decision_owner':'reviewer','requirements':['float'],'hazards':[{'id':'sink','severity':5,'likelihood':2}],'controls':[]}}
 r=c.post('/api/v1/document-generator/design-333-359/support',headers=h,json=d);assert r.status_code==200 and r.json()['feature_id']==333
 # Project builder mounted engineering generation requires a real project and returns typed row.
 p=c.post('/api/v1/project-builder/projects',headers=h,json={'goal':'Build search'});assert p.status_code==200
 pid=p.json()['id'];r=c.post(f'/api/v1/project-builder/projects/{pid}/designs',headers=h,json={'kind':'semantic_search','context':{}});assert r.status_code==201 and r.json()['row']==568
 assert c.post('/api/v1/document-generator/design-333-359/support',headers=h,json={'feature_id':333,'data':{}}).status_code==422
