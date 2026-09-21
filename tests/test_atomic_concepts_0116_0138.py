import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.runtime.atomic_concepts_0116_0138 import execute

def test_116_data_sharing_fair_compliance():
 x=execute('125.1',{'persistent_identifier':'doi:x','license':'CC-BY','metadata':{'title':'dataset'},'repository':'zenodo','access_conditions':'open','provenance':'lab'});assert x['compliant'] and x['fair_data_checklist']['license']
def test_117_code_sharing_reproducibility():
 x=execute('125.2',{'repository_url':'https://x','license':'MIT','version_tag':'v1','environment_lock':'lock','readme':'r','tests':'t'});assert x['reproducibility_ready']
def test_118_title_candidates_are_specific_not_clickbait():
 x=execute('131.1',{'main_finding':'Treatment reduced symptoms','population':'120 adults','design':'RCT'});assert len(x['candidates'])==3 and x['clickbait_forbidden']
def test_119_title_accuracy_finds_unsupported_claim():
 x=execute('131.2',{'title':'X cures Y','title_claims':['cures'],'supported_claims':['associated'],'design':'cohort'});assert x['unsupported_claims']==['cures'] and not x['accurate'] and not x['causal_language_allowed']
def test_120_value_function_td_learning(): assert execute('162.1',{'rewards':[1,0],'values':[0],'gamma':.9,'alpha':.5})['updated_value']>0
def test_121_policy_learning_normalizes_actor_probabilities():
 x=execute('162.2',{'rewards':[1],'values':[0],'actions':['a','b'],'action_probabilities':[.5,.5],'chosen_index':0});assert sum(x['updated_policy'].values())==pytest.approx(1) and x['updated_policy']['a']>.5
def test_122_tension_creation_has_causal_escalation():
 x=execute('267.1',{'scene':'escape','stakes':'family','time_pressure':'sunrise','uncertainty':'route','complication':'bridge falls'});assert [b['beat'] for b in x['tension_beats']]==['goal','stakes','uncertainty','clock','complication']
def test_123_tension_release_keeps_consequence(): assert execute('267.2',{'scene':'x','stakes':'y','resolved_question':'door opens'})['catharsis_without_erasing_consequence']
def test_124_trope_expectation_preserves_core_pleasure(): assert execute('271.1',{'trope':'mentor','audience_promise':'growth','core_pleasure':'wisdom','conventional_beats':['lesson']})['core_pleasure_to_preserve']=='wisdom'
def test_125_trope_subversion_is_seeded_not_shock_only(): assert execute('271.2',{'trope':'mentor','audience_promise':'growth','subversion':'student teaches','seeded_evidence':['mentor listens']})['shock_only'] is False
def test_126_lyric_meter_reports_estimated_syllables(): assert len(execute('274.1',{'lines':['Light in the sky','Night passing by'],'target_syllables':4})['estimated_syllables'])==2
def test_127_lyric_rhyme_checks_scheme(): assert execute('274.2',{'lines':['bright light','soft night'],'scheme':'AA'})['scheme_satisfied']
def test_128_squash_preserves_volume_proxy(): assert execute('295.1',{'volume':1,'scale_y':.25})['scale_x']==2
def test_129_stretch_preserves_volume_proxy(): assert execute('295.2',{'volume':1,'scale_y':4})['scale_x']==.5
def test_130_anticipation_has_opposing_pre_action(): assert execute('295.3',{'volume':1,'pre_action_pose':'back','action_pose':'forward'})['opposing_direction']
def test_131_beat_programming_returns_onset_grid(): assert execute('304.1',{'bpm':120,'steps':8,'pattern':[1,0,0,0,1,0,0,0]})['onsets']==[0,4]
def test_132_groove_programming_has_microtiming(): assert execute('304.2',{'bpm':120,'steps':8,'swing':.6})['microtiming_offsets'][1]>0
def test_133_visual_aesthetics_checks_data_ink_not_decoration(): assert execute('316.1',{'chart':{'marks':10,'decorations':10,'palette':['x'],'title':'t'}})['aesthetic_checks']['data_ink_ratio_proxy']==.5
def test_134_visual_clarity_checks_accessible_redundancy(): assert execute('316.2',{'chart':{'marks':10,'title':'t','encodings':{'x':'date','y':'value'},'units':'kg','redundant_encoding':True,'uncertainty':'CI'}})['clarity_checks']['color_not_only_channel']
def test_135_anatomical_plan_has_orientation_and_sources(): assert len(execute('320.1',{'references':[{'id':'atlas'}],'view':'anterior','structures':['heart']})['orientation_labels'])==4
def test_136_procedure_plan_is_not_surgical_instruction(): assert execute('320.2',{'references':[{'id':'guide'}],'steps':['incision'],'hazards':['bleeding']})['not_surgical_instruction']
def test_137_aircraft_support_uses_trade_and_verification_not_flight_claim():
 x=execute('332.1',{'mission':'trainer','requirements':{'range_km':500}});assert 'wing loading' in x['trade_studies'] and not x['flightworthy_claim']
def test_138_spacecraft_support_uses_budgets_and_no_launch_claim():
 x=execute('332.2',{'mission':'earth imaging','requirements':{'resolution_m':5}});assert 'delta-v' in x['budgets'] and not x['launch_ready_claim']
def test_negative_paths_reject_incomplete_or_invalid_inputs():
 with pytest.raises(ValueError):execute('131.1',{})
 with pytest.raises(ValueError):execute('162.2',{'rewards':[1],'actions':['a'],'action_probabilities':[]})
 with pytest.raises(ValueError):execute('304.1',{'bpm':2,'steps':8})
 with pytest.raises(ValueError):execute('320.1',{'references':[]})
 with pytest.raises(ValueError):execute('332.1',{'requirements':{}})
def test_mounted_boundary_and_http_failure():
 c=TestClient(app);base='/api/v1/runtime/atomic-concepts-116-138';assert len(c.get(base+'/capabilities').json())==23
 r=c.post(base+'/execute',json={'atomic_row_id':'332.2','data':{'mission':'m','requirements':{'r':1}}});assert r.status_code==200 and not r.json()['launch_ready_claim']
 assert c.post(base+'/execute',json={'atomic_row_id':'bad','data':{}}).status_code==422
