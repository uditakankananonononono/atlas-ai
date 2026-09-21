from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m15_document_generator.creative_production_306_332 import *
S=[{'source_id':'brief-1','observed_at':datetime.now(timezone.utc).isoformat()}]
def payload(i):
 _,req,stages=SPECS[i];p={'sources':S,'decisions':{s:s+' decision' for s in stages}}
 for k in req:p[k]=k+' value'
 p['human_review']=True
 if i==306:p['tracks']=['vocal','music'];p['sample_rate']=48000
 if i==307:p['mix']='mix.wav';p['loudness_standard']={'integrated_lufs':-14,'true_peak_dbtp':-1}
 if i==310:p['episodes']=[{'title':'one'}]
 if i==313:p['speaker_layout']=[{'x':0,'y':0}]
 if i==314:p['inputs']=['motion'];p['outputs']=['light']
 if i==315:p['system_rules']=['rule'];p['seed_policy']={'mode':'fixed','seed':1}
 if i==316:p['dataset']=[{'x':1,'y':2}];p['encoding']={'zero_required':True,'axis_min':0}
 if i==317:p['facts']=['fact']
 if i==318:p['geodata']={'crs':'EPSG:4326','features':[]}
 if i in (319,320):p['evidence_sources']=['atlas']
 if i==321:p['dimensions']=[{'name':'width','value':10,'tolerance':.1}]
 if i==325:p['population']=['residents']
 if i==326:p['constraints']=['cost'];p['wearer']='adult';p['garment_type']='coat'
 if i==327:p['constraints']=['wash'];p['fiber_or_substrate']='cotton'
 if i==328:p['materials']=['silver'];p['wearer']='adult'
 if i in (329,330):p['users']=['adult'];p['constraints']=['cost'] if i==329 else p.get('constraints');p['requirements']=['safe'] if i==330 else p.get('requirements')
 if i==331:p['users']=['driver'];p['requirements']=['safe']
 if i==332:p['requirements']=['safe']
 return p
@pytest.mark.parametrize('i',range(306,333))
def test_exact_substantive_plan_per_row(i):
 p=payload(i);o=plan(i,p);assert o['row_id']==i and o['capability']==ROWS[i] and o['family']==SPECS[i][0] and len(o['workflow'])==len(SPECS[i][2]) and not o['open_stages'] and not o['rendered_or_fabricated'] and o['side_effects']==[]
def test_mixing_stages_are_domain_specific():assert SPECS[306][2]==['gain_staging','pan','eq','dynamics','spatial_fx','automation','reference_check']
def test_mastering_requires_lufs():
 p=payload(307);p['loudness_standard']={}
 with pytest.raises(CreativeError,match='missing required|integrated_lufs'):plan(307,p)
def test_foley_contains_sync_and_layers():assert {'sync','edit_layers'}<=set(SPECS[308][2])
def test_voice_direction_contains_consent():assert 'consent' in SPECS[309][2]
def test_podcast_includes_factcheck_and_publish_gate():assert {'fact_check','publish_approval'}<=set(SPECS[310][2])
def test_audiobook_includes_pronunciation_and_pickups():assert {'pronunciation_guide','pickup_log'}<=set(SPECS[311][2])
def test_radio_drama_integrates_cast_foley_soundscape():assert {'casting','foley','soundscape'}<=set(SPECS[312][2])
def test_installation_has_site_routing_safety():assert {'site_acoustics','routing','safety'}<=set(SPECS[313][2])
def test_interactive_art_has_state_privacy_accessibility():assert {'state_model','privacy','accessibility'}<=set(SPECS[314][2])
def test_generative_art_seed_must_be_structured():
 p=payload(315);p['seed_policy']='random'
 with pytest.raises(CreativeError,match='seed_policy'):plan(315,p)
def test_data_viz_rejects_truncated_required_zero_axis():
 p=payload(316);p['encoding']={'zero_required':True,'axis_min':3}
 with pytest.raises(CreativeError,match='axis_min'):plan(316,p)
def test_infographic_keeps_factcheck_sources_accessibility():assert {'fact_check','sources','accessibility'}<=set(SPECS[317][2])
def test_map_requires_crs():
 p=payload(318);p['geodata']={'features':[]}
 with pytest.raises(CreativeError,match='CRS'):plan(318,p)
def test_scientific_and_medical_distinct():assert SPECS[319][2]!=SPECS[320][2] and 'clinician_review' in SPECS[320][2]
def test_technical_drawing_rejects_negative_tolerance():
 p=payload(321);p['dimensions'][0]['tolerance']=-1
 with pytest.raises(CreativeError,match='tolerance'):plan(321,p)
def test_arch_rendering_has_truthfulness():assert 'truthfulness' in SPECS[322][2]
def test_built_environment_workflows_distinct():assert len({tuple(SPECS[i][2]) for i in range(323,326)})==3
def test_built_environment_requires_human_review():
 p=payload(325);p['human_review']=False
 with pytest.raises(CreativeError,match='human_review'):plan(325,p)
def test_fashion_textile_jewelry_furniture_distinct():assert len({tuple(SPECS[i][2]) for i in range(326,330)})==4
def test_industrial_has_lifecycle():assert 'lifecycle' in SPECS[330][2]
def test_automotive_has_crash_and_homologation():assert {'crash_constraints','homologation'}<=set(SPECS[331][2])
def test_aerospace_has_mass_stability_certification():assert {'mass_budget','stability_control','certification'}<=set(SPECS[332][2])
def test_source_required():
 p=payload(306);p['sources']=[]
 with pytest.raises(CreativeError,match='provenance'):plan(306,p)
def test_open_stage_truthful():
 p=payload(306);del p['decisions']['eq'];o=plan(306,p);assert o['open_stages']==['eq']
def test_exact_range_and_titles():assert set(ROWS)==set(range(306,333)) and ROWS[306]=='Mixing' and ROWS[332]=='Aerospace Design'
def test_mounted_route():
 r=TestClient(app).post('/api/v1/document-generator/creative-production-306-332/306',json=payload(306));assert r.status_code==200 and r.json()['capability']=='Mixing'
def test_unknown_route_negative():assert TestClient(app).post('/api/v1/document-generator/creative-production-306-332/305',json={}).status_code==422
def test_catalog_count():assert len(TestClient(app).get('/api/v1/document-generator/creative-production-306-332').json())==27
