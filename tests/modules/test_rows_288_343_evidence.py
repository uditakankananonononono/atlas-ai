"""Named, row-level evidence tests for the assigned creative/design band."""
from tests.modules.test_m06_creative import make_client,CREATIVE_INPUT
from datetime import datetime,timezone
from app.modules.m15_document_generator.creative_production_306_332 import SPECS
def production_payload(i):
 _,req,stages=SPECS[i];p={'sources':[{'source_id':'brief-1','observed_at':datetime.now(timezone.utc).isoformat()}],'decisions':{s:s+' decision' for s in stages},'human_review':True}
 for k in req:p[k]=k+' value'
 if i==306:p['tracks']=['vocal','music'];p['sample_rate']=48000
 if i==307:p['mix']='mix.wav';p['loudness_standard']={'integrated_lufs':-14}
 if i==310:p['episodes']=[{'title':'one'}]
 if i==315:p['system_rules']=['rule'];p['seed_policy']={'mode':'fixed'}
 if i==316:p['dataset']=[{'x':1}];p['encoding']={'zero_required':True,'axis_min':0}
 if i==318:p['geodata']={'crs':'EPSG:4326','features':[]}
 if i in (319,320):p['evidence_sources']=['atlas']
 if i==321:p['dimensions']=[{'tolerance':.1}]
 if i==326:p['constraints']=['cost']
 if i==328:p['materials']=['silver']
 if i in (329,330):p['users']=['adult']
 if i==330:p['requirements']=['safe']
 if i in (331,332):p['requirements']=['safe']
 return p
BASE={'brief':'Build and test a concept','decision_owner':'design-team'}
def design_payload(fid):
 d=dict(BASE)
 if fid<335:d|={'requirements':[{'id':'r'}],'hazards':[{'id':'h','severity':3,'likelihood':2}],'controls':[]}
 else:d|={'gameplay_loops':[{'id':'loop'}],'content_nodes':[{'id':'level'}],'playtests':[{'completion_rate':.8}]}
 return d
from app.modules.m06_social_media_manager.creative import CREATIVE_SPECS,CREATIVE_METRIC_KEYS
from app.modules.m15_document_generator.creative_production_306_332 import plan,METRIC_NAMES
from app.modules.m15_document_generator.design_support_333_359 import design_support_333_359,DESIGN_METRIC_NAMES
import pytest

@pytest.mark.parametrize('row',range(288,306),ids=lambda r:f'row_{r}')
def test_rows_288_305_have_distinct_typed_evidence(row):
 slug=next(k for k,v in CREATIVE_SPECS.items() if v.row==row)
 client,repository=make_client();body=client.post(f'/api/v1/social-media-manager/creative/{slug}',json=CREATIVE_INPUT).json()
 e=repository.get_artifact(body['id']).evaluation['row_evidence']
 assert e['metric']['name']==CREATIVE_METRIC_KEYS[row] and isinstance(e['metric']['value'],int)
 assert e['metric']['unit']=='specified_items' and e['metric']['value_type']=='integer'
 assert e['mechanism'].endswith('.v1') and e['model']['provider_model']=='fake-model'
 assert e['evidence']['required_keys']==list(CREATIVE_SPECS[slug].section_keys) and e['external_effects']==[]

@pytest.mark.parametrize('row',range(306,333),ids=lambda r:f'row_{r}')
def test_rows_306_332_have_distinct_typed_evidence(row):
 out=plan(row,production_payload(row));e=out['row_evidence']
 assert e['metric']['name']==METRIC_NAMES[row] and isinstance(e['metric']['value'],int)
 assert e['model']['version']=='1.0.0' and e['evidence']['source_ids']==['brief-1'] and e['external_effects']==[]

@pytest.mark.parametrize('row',range(333,344),ids=lambda r:f'row_{r}')
def test_rows_333_343_have_distinct_typed_evidence(row):
 out=design_support_333_359(row,design_payload(row));e=out['row_evidence']
 assert e['metric']['name']==DESIGN_METRIC_NAMES[row] and isinstance(e['metric']['value'],(int,float))
 assert e['model']['version']=='1.0.0' and e['evidence']['decision_owner']=='design-team' and e['external_effects']==[]

def test_all_assigned_mechanisms_and_metric_names_are_unique():
 assert len(set(CREATIVE_METRIC_KEYS.values())|set(METRIC_NAMES.values())|set(DESIGN_METRIC_NAMES.values()))==56
