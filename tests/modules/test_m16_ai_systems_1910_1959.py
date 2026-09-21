"""Focused executable evidence for each AI systems row 1910-1959."""
import pytest
from app.modules.m16_executive_dashboard import analysis
from app.modules.m16_executive_dashboard import ai_systems_1910_1959 as ai
GEN=({'prompt':'red fox forest','artifact_description':'red fox in a forest','quality_scores':[.8,.9],'provenance':'c2pa','watermark':True},{})
CASES={
'large_language_models':({'token_log_probabilities':[-.1,-.2,-.3],'context_window':10},{}),'multimodal_ai':({'modalities':['text','image'],'modality_scores':[.8,.6],'weights':[.4,.6]},{}),'vision_language_models':({'image_ids':['a','b'],'captions':['cat','dog'],'similarities':[.8,.3]},{'threshold':.5}),
'text_to_image_generation':GEN,'text_to_video_generation':GEN,'text_to_3d_generation':GEN,'text_to_audio_generation':GEN,'music_generation':GEN,'ai_art':GEN,
'voice_cloning':({'consent_verified':True,'provenance':'signed','watermark':True,'identity_similarity':.9},{}),'deepfakes':({'consent_verified':False,'provenance':None,'watermark':False,'identity_similarity':.95},{}),
'ai_writing':({'text':'A sourced claim. Another sentence.','sources':['s1'],'claims':['c1']},{}),'ai_coding':({'tests_passed':[10,5],'tests_total':[10,6],'static_analysis_issues':1,'dependency_scan_clean':True},{}),
'ai_agents':({'steps':[{'irreversible':False},{'irreversible':True,'approved':True}],'goal_completed':True},{}),'autonomous_agents':({'steps':[{'irreversible':False},{'irreversible':True,'approved':True}],'goal_completed':True},{}),
'multi_agent_systems':({'agents':['a','b'],'delegations':[{'from':'a','to':'b'}]},{}),'agent_communication':({'messages':[{'sender':'a','recipient':'b','type':'request','correlation_id':'1'}]},{}),'agent_coordination':({'tasks':[{'id':'a','owner':'x','depends_on':[]},{'id':'b','owner':'y','depends_on':['a']}]},{}),'agent_negotiation':({'offers':['x','y'],'utilities':[.4,.8]},{'reservation_utility':.5}),'agent_learning':({'before_scores':[.5,.6],'after_scores':[.7,.55]},{}),
'reinforcement_learning_from_human_feedback':({'chosen_rewards':[1,2,3],'rejected_rewards':[0,1,2]},{}),'constitutional_ai':({'principles':['safe','honest'],'critiques':['c1','c2'],'revisions':['r1','r2']},{}),'ai_alignment':({'intended_scores':[1,.5],'observed_scores':[.9,.4]},{'tolerance':.11}),'ai_safety':({'hazard_severity':[3,2],'hazard_likelihood':[.2,.1],'detectability':[1,2]},{'threshold':.5}),'ai_ethics':({'principles':['privacy','fairness'],'evidence':{'privacy':'doc'}},{}),
'explainable_ai':({'feature_names':['age','income'],'feature_importance':[.2,.8]},{}),'interpretable_ai':({'feature_names':['age','income'],'feature_importance':[.2,.8]},{}),'fair_ai':({'groups':['a','a','b','b'],'selected':[1,0,1,1],'positive_labels':[1,1,1,1]},{}),
'responsible_ai':({'dimensions':['safety','fairness'],'scores':[.9,.8],'weights':[1,1]},{'threshold':.7}),'trustworthy_ai':({'dimensions':['reliability','privacy'],'scores':[.8,.9],'weights':[1,2]},{'threshold':.7}),
'ai_governance':({'requirements':['owner','risk'],'evidence':{'owner':'x','risk':'y'}},{}),'ai_regulation':({'requirements':['notice','records'],'evidence':{'notice':'x'}},{}),'ai_policy':({'requirements':['scope'],'evidence':{'scope':'x'}},{}),'ai_standards':({'requirements':['test','document'],'evidence':{'test':'x','document':'y'}},{}),'ai_certification':({'requirements':['audit'],'evidence':{'audit':'report'}},{}),
'ai_auditing':({'controls':[{'id':'c1','result':'pass','evidence':'x'},{'id':'c2','result':'fail','evidence':'y'}]},{}),'ai_testing':({'expected':[1,2],'actual':[1,2],'independent_evidence':True},{}),'ai_verification':({'expected':['a','b'],'actual':['a','b'],'independent_evidence':True},{}),'ai_validation':({'expected':[True,False],'actual':[True,False],'independent_evidence':True},{}),'ai_assurance':({'expected':[1,2],'actual':[1,2],'critical_indices':[0],'independent_evidence':True},{}),
'foundation_models':({'tasks':['a','b'],'scores':[.8,.7],'baselines':[.5,.6]},{}),'pre_trained_models':({'tasks':['a','b'],'scores':[.8,.7],'baselines':[.5,.6]},{}),'fine_tuning':({'before_scores':[.5,.6],'after_scores':[.8,.7],'retained_base_scores':[.48,.59]},{}),'transfer_learning':({'scratch_scores':[.5,.6],'transfer_scores':[.7,.7],'scratch_examples':[100,100],'transfer_examples':[20,25]},{}),
'few_shot_learning':({'predictions':['a','b'],'targets':['a','c'],'shots':3,'prompt_tokens':50},{}),'zero_shot_learning':({'predictions':['a','b'],'targets':['a','b'],'shots':0},{}),'in_context_learning':({'predictions':[1,2],'targets':[1,2],'shots':2},{}),'prompt_engineering':({'variants':['short','long'],'scores':[.8,.9],'token_counts':[10,100]},{'token_penalty':.002}),'chain_of_thought':({'steps':['identify','calculate'],'final_answer':4,'expected_answer':4,'step_verifications':[True,True]},{'return_trace':False}),'tree_of_thought':({'nodes':[{'id':'root','parent':None,'score':0},{'id':'a','parent':'root','score':.7},{'id':'b','parent':'root','score':.9}]},{})}
@pytest.mark.parametrize('method,row',ai.ROWS.items())
def test_each_row_is_mounted_and_substantive(method,row):
 data,params=CASES[method];r=analysis.run(method,data,params,seed=3)
 assert r['feature_row']==row and r['method']==method and r['inputs']['data']==data
 assert isinstance(r['output'],dict) and r['output']
def test_identity_media_requires_consent_provenance_and_watermark():
 ok=analysis.run('voice_cloning',*CASES['voice_cloning'])['output'];bad=analysis.run('deepfakes',*CASES['deepfakes'])['output']
 assert ok['release_allowed'] and not bad['release_allowed'] and set(bad['risk_flags'])=={'missing_consent','missing_provenance','missing_watermark'}
def test_agent_and_governance_gates_are_real():
 unsafe=analysis.run('autonomous_agents',{'steps':[{'irreversible':True,'approved':False}]})['output'];assert not unsafe['safe_to_execute']
 reg=analysis.run('ai_regulation',*CASES['ai_regulation'])['output'];assert reg['decision']=='evidence_incomplete' and reg['gaps']==['records']
def test_learning_and_reasoning_metrics():
 llm=analysis.run('large_language_models',*CASES['large_language_models'])['output'];assert llm['perplexity']>1
 r=analysis.run('tree_of_thought',*CASES['tree_of_thought'])['output'];assert r['best_leaf_id']=='b' and r['best_path']==['root','b']
 z=analysis.run('zero_shot_learning',*CASES['zero_shot_learning'])['output'];assert z['shots']==0 and z['accuracy']==1
def test_invalid_inputs_fail_loudly():
 with pytest.raises(ValueError):analysis.run('zero_shot_learning',{'predictions':[1],'targets':[1],'shots':1})
 with pytest.raises(ValueError):analysis.run('ai_coding',{'tests_passed':[2],'tests_total':[1]})
 with pytest.raises(ValueError):analysis.run('fair_ai',{'groups':['a'],'selected':[1,0],'positive_labels':[1]})
