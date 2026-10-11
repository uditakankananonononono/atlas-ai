"""Bijective symbolic analogy constraints and explicit checked case reuse."""
import pytest
from app.modules.m20_general_cognitive_worker.learning_reasoning_810_859 import execute,LearningReasoningError
SRC={'title':'Cases','url':'https://example.org/cases'}
def analogy():return {'source':SRC,'analogy_source_features':{'a':'red','b':'round'},'analogy_target_features':{'x':'red','y':'round'},'analogy_correspondences':[{'source_feature':'a','target_feature':'x'},{'source_feature':'b','target_feature':'y'}],'candidate_inferences':[{'inference_id':'i','source_feature':'a','value':'red','source':'fixture:i'}],'target_constraints':[{'feature_id':'x','allowed_values':['red'],'source':'fixture:constraint'}]}
def case():return {'source':SRC,'case_bank':[{'case_id':'z','features':{'color':'red','shape':'round'},'proposed_action':'action-z','source':'fixture:z'},{'case_id':'a','features':{'color':'red','shape':'square'},'proposed_action':'action-a','source':'fixture:a'}],'case_target':{'features':{'color':'red','shape':'round'},'source':'fixture:target'},'case_feature_weights':{'color':1,'shape':2},'case_target_checks':None}
def run(method,p):return execute(method,p)['result']['analogy_check'if method=='analogical_reasoning'else 'case_reuse']

def test_analogy_mapping_and_constraint_checked_inference():
 r=run('analogical_reasoning',analogy());assert r['status']=='mapped' and r['mapping_complete'] is True
 assert r['unmapped_source_features']==r['unmapped_target_features']==[] and r['many_to_one_targets']==[]
 assert r['inference_reports']==[{'inference_id':'i','source_feature':'a','target_feature':'x','value':'red','source_value_matches':True,'target_constraints_present':True,'constraint_sources':['fixture:constraint'],'supported':True,'source':'fixture:i'}]
 assert r['source_truth_verified'] is False and r['general_analogy'] is None

def test_unmapped_many_to_one_and_constraint_failures_preserved():
 p=analogy();p['analogy_correspondences']=p['analogy_correspondences'][:1];r=run('analogical_reasoning',p);assert r['mapping_complete'] is False and r['unmapped_source_features']==['b'] and r['unmapped_target_features']==['y']
 p=analogy();p['analogy_correspondences'][1]['target_feature']='x';r=run('analogical_reasoning',p);assert r['many_to_one_targets']==['x'] and r['inference_reports'][0]['supported'] is False
 p=analogy();p['target_constraints'][0]['allowed_values']=['blue'];assert run('analogical_reasoning',p)['inference_reports'][0]['supported'] is False
 p=analogy();p['target_constraints']=[];assert run('analogical_reasoning',p)['inference_reports'][0]['supported'] is False

def test_case_rank_and_checks_before_adaptation():
 p=case();r=run('case_based_reasoning',p);assert [c['case_id']for c in r['ranked_cases']]==['z','a'] and [c['similarity']for c in r['ranked_cases']]==[1,pytest.approx(1/3)]
 assert r['status']=='awaiting_target_checks' and r['adapted_action'] is None
 p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'check','passed':True,'source':'fixture:check'}]};r=run('case_based_reasoning',p);assert r['status']=='checked_case_reuse' and r['adapted_action']=='action-z' and r['checks_passed'] is True and r['action_executed'] is False
 p['case_target_checks']['checks'][0]['passed']=False;r=run('case_based_reasoning',p);assert r['status']=='target_checks_failed' and r['adapted_action'] is None

def test_case_ties_and_nonbest_selection_explicit():
 p=case();p['case_bank'][0]['features']['shape']='square';assert [c['case_id']for c in run('case_based_reasoning',p)['ranked_cases']]==['a','z']
 p=case();p['case_target_checks']={'selected_case_id':'a','checks':[{'check_id':'c','passed':True,'source':'fixture'}]};assert run('case_based_reasoning',p)['adapted_action']=='action-a'

def test_invalid_map_reference_duplicate_source_and_inference():
 for value in [[{'source_feature':'unknown','target_feature':'x'}],analogy()['analogy_correspondences']*2]:
  p=analogy();p['analogy_correspondences']=value
  with pytest.raises(LearningReasoningError):run('analogical_reasoning',p)
 p=analogy();p['candidate_inferences'][0]['source_feature']='unknown'
 with pytest.raises(LearningReasoningError):run('analogical_reasoning',p)

def test_case_shape_refs_boolean_sources():
 for field,value in [('case_bank',[]),('case_feature_weights',{'color':0,'shape':1}),('case_target_checks',{'selected_case_id':'unknown','checks':[{'check_id':'c','passed':True,'source':'fixture'}]})]:
  p=case();p[field]=value
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)
 for key,value in [('passed',1),('source',''),('check_id','')]:
  p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'c','passed':True,'source':'fixture'}]};p['case_target_checks']['checks'][0][key]=value
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)

def test_mounted_auth_minimal_refusal_tenant(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);h=oidc_auth_headers('a','owner')
 for method,p in [('analogical_reasoning',analogy()),('case_based_reasoning',case())]:
  path='/api/v1/api/modules/20/learning-reasoning-810-859/'+method
  assert c.post(path,json={'payload':p}).status_code==401
  assert c.post(path,headers=h,json={'payload':p}).status_code==200
  assert c.post(path,headers=h,json={'payload':{'source':SRC}}).status_code==422
  assert c.post(path,headers=h,json={'payload':{**p,'resource_refs':[{'tenant_id':'b'}]}}).status_code==403

def test_inference_source_mismatch_and_mixed_checks():
 p=analogy();p['candidate_inferences'][0]['value']='blue';r=run('analogical_reasoning',p);assert r['inference_reports'][0]['source_value_matches'] is False and r['inference_reports'][0]['supported'] is False
 p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'yes','passed':True,'source':'fixture'},{'check_id':'no','passed':False,'source':'fixture'}]};r=run('case_based_reasoning',p);assert r['checks_passed'] is False and r['adapted_action'] is None

def test_exact_case_cap_weights_and_sources():
 p=case();p['case_bank']=[{**p['case_bank'][0],'case_id':str(i)}for i in range(256)];assert len(run('case_based_reasoning',p)['ranked_cases'])==256
 p['case_bank'].append({**p['case_bank'][0],'case_id':'256'})
 with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)
 for weight in [True,float('nan'),1000.1]:
  p=case();p['case_feature_weights']['color']=weight
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)
 for key in ['case_id','source','proposed_action']:
  p=case();p['case_bank'][0][key]=''
  with pytest.raises(LearningReasoningError):run('case_based_reasoning',p)

def test_full_boundaries_checks_echo_and_no_autoeffect():
 p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'c','passed':True,'source':'fixture'}]};r=run('case_based_reasoning',p)
 assert r['checks']==p['case_target_checks']['checks'] and r['source_truth_verified'] is False and r['target_source']=='fixture:target'
 assert r['boundary']=='Declared weighted exact feature case retrieval and supplied action reuse only after caller-recorded target checks. No invented adaptation, execution, semantic similarity or general case learning.'
 assert run('analogical_reasoning',analogy())['boundary']=='Explicit supplied symbolic correspondences and target allowed-value constraints only. Mapping gaps/many-to-one preserved; no semantic analogy discovery or independently verified inferences.'

def test_source_value_mismatch_not_masked_by_constraint():
 p=analogy();p['candidate_inferences'][0]['value']='blue';p['target_constraints'][0]['allowed_values']=['blue']
 r=run('analogical_reasoning',p)['inference_reports'][0]
 assert r['source_value_matches'] is False and r['target_constraints_present'] is True and r['supported'] is False

# Independent core calls preserve the exact failure, without wrapper conversion.
from app.modules.m20_general_cognitive_worker import analogy_cases as core
from copy import deepcopy

def exact_error(fn,p,message):
 with pytest.raises(ValueError) as exc:fn(p)
 assert str(exc.value)==message

@pytest.mark.parametrize('label',['analogy_source_features','analogy_target_features'])
def test_r2_feature_bounds(label):
 p=analogy();p[label]={str(i):'v' for i in range(64)}
 p['analogy_correspondences']=[];p['target_constraints']=[];p['candidate_inferences']=[]
 assert core.analogy(p)['status']=='mapping_gaps'
 p[label]['overflow']='v';exact_error(core.analogy,p,label+' requires1..64 feature dictionary')
 p[label]={};exact_error(core.analogy,p,label+' requires1..64 feature dictionary')

@pytest.mark.parametrize('field,cap',[('analogy_correspondences',64),('target_constraints',64),('candidate_inferences',256)])
def test_r2_analogy_row_caps(field,cap):
 p=analogy()
 if field=='analogy_correspondences':
  p['analogy_source_features']={str(i):'v' for i in range(64)};p['analogy_target_features']={'x':'v'}
  p[field]=[{'source_feature':str(i),'target_feature':'x'} for i in range(cap)]
  p['candidate_inferences']=[]
 elif field=='target_constraints':p[field]=[{'feature_id':'x','allowed_values':['red'],'source':str(i)} for i in range(cap)]
 else:p[field]=[{'inference_id':str(i),'source_feature':'a','value':'red','source':str(i)} for i in range(cap)]
 core.analogy(p)
 p[field].append({**p[field][0],**({'inference_id':'overflow'} if field=='candidate_inferences' else {})})
 exact_error(core.analogy,p,field+' requires bounded object list')

def test_r2_weight_and_check_bounds():
 p=case();p['case_feature_weights']={str(i):1 for i in range(64)};values={k:'v' for k in p['case_feature_weights']}
 p['case_target']['features']=values;p['case_bank']=[{**p['case_bank'][0],'features':values}]
 assert core.reuse(p)['ranked_cases'][0]['similarity']==1
 p['case_feature_weights']['overflow']=1
 exact_error(core.reuse,p,'case_feature_weights requires1..64 entries')
 p=case();p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':str(i),'passed':True,'source':'fixture'} for i in range(64)]}
 assert len(core.reuse(p)['checks'])==64
 p['case_target_checks']['checks'].append({'check_id':'overflow','passed':True,'source':'fixture'})
 exact_error(core.reuse,p,'checks requires bounded object list')
 p['case_target_checks']['checks']=[];exact_error(core.reuse,p,'checks requires bounded object list')

@pytest.mark.parametrize('change,message',[
 ('feature_key','analogy_source_features key requires bounded nonempty string'),
 ('feature_value','analogy_source_features value requires bounded nonempty string'),
 ('unknown_mapping','known feature references and unique source mapping required'),
 ('empty_allowed','allowed_values requires bounded text list'),
 ('unknown_constraint','unknown constraint feature'),
 ('duplicate_inference','unique inference IDs and known source features required'),
 ('unknown_inference','unique inference IDs and known source features required')])
def test_r2_analogy_validators(change,message):
 p=analogy()
 if change=='feature_key':p['analogy_source_features']={'':'red','b':'round'};p['analogy_correspondences'][0]['source_feature']='b'
 elif change=='feature_value':p['analogy_source_features']['a']=''
 elif change=='unknown_mapping':p['analogy_correspondences'][0]['source_feature']='unknown'
 elif change=='empty_allowed':p['target_constraints'][0]['allowed_values']=[]
 elif change=='unknown_constraint':p['target_constraints'][0]['feature_id']='unknown'
 elif change=='duplicate_inference':p['candidate_inferences'].append(deepcopy(p['candidate_inferences'][0]))
 else:p['candidate_inferences'][0]['source_feature']='unknown'
 exact_error(core.analogy,p,message)

@pytest.mark.parametrize('change,message',[
 ('target_schema','target features must cover exactly weighted schema'),
 ('duplicate_case','unique cases with exact weighted feature schema required'),
 ('case_schema','unique cases with exact weighted feature schema required'),
 ('target_source','target source requires bounded nonempty string'),
 ('duplicate_check','unique check IDs and boolean passed required')])
def test_r2_case_validators(change,message):
 p=case()
 if change=='target_schema':p['case_target']['features']['extra']='v'
 elif change=='duplicate_case':p['case_bank'].append(deepcopy(p['case_bank'][0]))
 elif change=='case_schema':p['case_bank'][0]['features']['extra']='v'
 elif change=='target_source':p['case_target']['source']=''
 else:p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':'dup','passed':True,'source':'fixture'},{'check_id':'dup','passed':True,'source':'fixture'}]}
 exact_error(core.reuse,p,message)

def test_r2_all_constraints_and_sorted_sources():
 p=analogy();p['target_constraints']=[{'feature_id':'x','allowed_values':['red'],'source':'z'},{'feature_id':'x','allowed_values':['blue'],'source':'a'}]
 r=core.analogy(p)['inference_reports'][0]
 assert r['supported'] is False and r['constraint_sources']==['a','z']
 p['target_constraints']=[];r=core.analogy(p)['inference_reports'][0]
 assert r['target_constraints_present'] is False

def test_r2_unmapped_target_and_many_to_one_independent():
 p=analogy();p['analogy_target_features']['extra']='v';r=core.analogy(p)
 assert r['mapping_complete'] is False and r['status']=='mapping_gaps' and r['unmapped_target_features']==['extra'] and r['inference_reports'][0]['supported'] is False
 p=analogy();p['analogy_target_features']={'x':'red'};p['analogy_correspondences'][1]['target_feature']='x';r=core.analogy(p)
 assert r['unmapped_source_features']==r['unmapped_target_features']==[]
 assert r['mapping_complete'] is False and r['status']=='mapping_gaps' and r['many_to_one_targets']==['x'] and r['inference_reports'][0]['supported'] is False

def test_r2_unsorted_mapping_outputs():
 p=analogy();p['analogy_source_features']={'z':'v','c':'v','b':'round','a':'red'}
 p['analogy_correspondences'].reverse();p['candidate_inferences']=[{**p['candidate_inferences'][0],'inference_id':i} for i in ['z','a']]
 r=core.analogy(p)
 assert r['unmapped_source_features']==['c','z']
 assert r['correspondences']==[{'source_feature':'a','target_feature':'x'},{'source_feature':'b','target_feature':'y'}]
 assert [i['inference_id'] for i in r['inference_reports']]==['a','z']

def test_r2_awaiting_and_sorted_checks_and_matches():
 p=case();r=core.reuse(p)
 assert r['selected_case_id'] is None and r['checks']==[] and r['checks_passed'] is None
 assert r['ranked_cases'][0]['matched_features']==['color','shape'] and r['ranked_cases'][1]['matched_features']==['color']
 p['case_target_checks']={'selected_case_id':'z','checks':[{'check_id':i,'passed':True,'source':i} for i in ['z','a']]}
 assert core.reuse(p)['checks']==[{'check_id':i,'passed':True,'source':i} for i in ['a','z']]

def test_r2_unmapped_source_sort_fixed_seed():
 import subprocess,sys,os,json
 p=analogy();p['analogy_source_features'].update({k:'v' for k in ['z','q','m','j','h','f','d','c']})
 code='import json;from app.modules.m20_general_cognitive_worker.analogy_cases import analogy;p=json.loads('+repr(json.dumps(p))+');assert analogy(p)["unmapped_source_features"]==["c","d","f","h","j","m","q","z"]'
 result=subprocess.run([sys.executable,'-c',code],env={**os.environ,'PYTHONHASHSEED':'0'},capture_output=True,text=True)
 assert result.returncode==0,result.stderr
