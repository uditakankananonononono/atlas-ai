import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.education import EducationError, capabilities, execute
from app.modules.m20_general_cognitive_worker.education_routes import router
SRC={"title":"Teaching evidence","url":"https://example.edu/evidence"}
def design(name="curriculum_design",**extra):
 p={"topic":"Fractions","learners":{"grade":5},"objectives":[{"id":"o1","statement":"Compare fractions"}],"assessments":[{"name":"exit ticket","objective_ids":["o1"]}],"duration_minutes":50,"source":SRC};p.update(extra);return execute(name,p)
def test_catalog_is_exact_and_complete():
 c=capabilities();assert len(c)==50 and [x['row_id'] for x in c]==list(range(1410,1460));assert c[0]['name']=='Curriculum Design' and c[-1]['name']=='Affect Detection'
@pytest.mark.parametrize('name', ['curriculum_design','assessment_design','lesson_planning','unit_planning','course_design','instructional_design','addie_model','sam_model','backward_design'])
def test_design_capabilities_align_objectives_assessment_and_time(name):
 o=design(name);assert o['result']['unassessed_objective_ids']==[] and sum(x['minutes'] for x in o['result']['sequence'])==50

def test_objectives_flag_unobservable_verbs_and_rubric_normalizes():
 o=design('learning_objective_writing',objectives=['Understand fractions']);assert o['result']['objective_quality']['needs_revision']==['obj-1']
 r=design('rubric_creation',criteria=[{'name':'reasoning','weight':3},{'name':'accuracy','weight':1}]);assert r['result']['normalized_weights'][0]['weight']==.75

def test_syllabus_has_policy_sections(): assert 'accessibility' in design('syllabus_creation')['result']['syllabus_sections']

def inclusion(name,**extra):
 p={'objectives':['Solve equations'],'learner_profile':{'prior_knowledge':'variable'},'supports':['worked examples'],'source':SRC};p.update(extra);return execute(name,p)
@pytest.mark.parametrize('name', ['universal_design_for_learning','differentiated_instruction','personalized_learning'])
def test_inclusive_design_preserves_choices(name): assert 'action_expression' in inclusion(name)['result']['choice_architecture']
def test_adaptive_thresholds_and_intelligent_tutor():
 assert inclusion('adaptive_learning',mastery=.4)['result']['adaptation']=='scaffold'
 assert 'select_hint_not_answer' in inclusion('intelligent_tutoring')['result']['tutor_loop']
def test_scaffolding_fades_and_zpd_is_difference():
 assert inclusion('scaffolding')['result']['fading_plan'][-1]['support']==0
 assert inclusion('zone_of_proximal_development',independent_skills=['a'],assisted_skills=['a','b'])['result']['zpd_candidates']==['b']
def test_cognitive_apprenticeship_has_full_cycle(): assert inclusion('cognitive_apprenticeship')['result']['apprenticeship_cycle'][0]=='modeling'

def pedagogy(name,**extra):
 p={'challenge':'Reduce school waste','objectives':['Evaluate evidence'],'source':SRC};p.update(extra);return execute(name,p)
@pytest.mark.parametrize('name', ['situated_learning','anchored_instruction','problem_based_learning','project_based_learning','inquiry_based_learning','discovery_learning','experiential_learning','cooperative_learning','collaborative_learning','peer_instruction'])
def test_pedagogies_produce_active_cycle_and_artifacts(name):
 o=pedagogy(name);assert len(o['result']['learning_cycle'])>=4 and o['result']['learner_artifacts']
def test_service_learning_requires_reciprocity(): assert 'reciprocity' in pedagogy('service_learning')['result']['community_safeguards']

def delivery(name): return execute(name,{'units':['Foundations','Application'],'constraints':{'bandwidth':'low'},'source':SRC})
@pytest.mark.parametrize('name',['flipped_classroom','blended_learning','online_learning','distance_education'])
def test_delivery_has_async_equivalent_and_accessibility(name):
 o=delivery(name);assert 'asynchronous_equivalent' in o['result']['continuity'] and 'captions_or_transcript' in o['result']['accessibility']
def test_mooc_micro_mobile_specifics():
 assert delivery('moocs')['result']['mooc_operations']['forum_moderation']
 assert delivery('microlearning')['result']['micro_units'][0]['target_minutes']<=10
 assert 'offline_resume' in delivery('mobile_learning')['result']['mobile_requirements']

def immersive(name,**extra):
 p={'objective':'Apply safety procedure','mechanic':'branching decision','alignment_rationale':'requires choosing each step','source':SRC};p.update(extra);return execute(name,p)
@pytest.mark.parametrize('name',['game_based_learning','simulation_based_learning'])
def test_game_and_simulation_align_mechanic_and_debrief(name):
 o=immersive(name);assert o['result']['alignment']['mechanic_practices_objective'] and len(o['result']['debrief'])==3
def test_gamification_is_noncoercive(): assert immersive('gamification')['result']['motivation_design']['avoids_coercive_rewards']
@pytest.mark.parametrize('name',['virtual_reality_learning','augmented_reality_learning','mixed_reality_learning'])
def test_xr_has_exit_and_2d_equivalent(name): assert 'accessible_2d_equivalent' in immersive(name)['result']['xr_safety']

def events(): return [{'learner_id':'p1','skill':'fractions','event_type':'attempt','correct':True,'duration_seconds':20},{'learner_id':'p1','skill':'fractions','event_type':'attempt','correct':False,'duration_seconds':40}]
def analytics(name,ev=None,**extra):
 p={'events':events() if ev is None else ev,'source':SRC};p.update(extra);return execute(name,p)
def test_ai_in_education_has_contestability():
 o=execute('artificial_intelligence_in_education',{'use_case':'practice hints','source':SRC});assert 'learner can contest recommendation' in o['result']['human_oversight']
def test_learning_analytics_uses_real_denominators():
 s=analytics('learning_analytics')['result']['summaries'][0];assert s['accuracy']==.5 and s['mean_duration_seconds']==30
def test_educational_data_mining_obeys_support_threshold():
 o=analytics('educational_data_mining',min_support=2);assert o['result']['frequent_patterns']==[{'event_type':'attempt','support':2}]
@pytest.mark.parametrize('name',['student_modeling','knowledge_tracing'])
def test_student_models_report_probability_not_grade(name):
 k=analytics(name)['result']['knowledge_state'][0];assert 0<=k['mastery_probability']<=1 and k['not_a_grade']
def test_affect_detection_only_accepts_non_diagnostic_signals():
 ev=[{'learner_id':'p','skill':'course','event_type':'self_report','value':'frustrated','confidence':.7},{'learner_id':'p','skill':'course','event_type':'camera_face','value':'sad'}]
 o=analytics('affect_detection',ev)['result'];assert len(o['affect_signals'])==1 and o['affect_signals'][0]['interpretation']=='uncertain' and 'facial emotion diagnosis' in o['prohibited']
def test_validation_rejects_missing_source_unknown_capability_and_bad_probability():
 with pytest.raises(EducationError): design('nope')
 with pytest.raises(EducationError): execute('curriculum_design',{'topic':'x'})
 with pytest.raises(EducationError): analytics('knowledge_tracing',prior_mastery=2)
def test_routes_mount_and_return_validation_errors():
 app=FastAPI();app.include_router(router,prefix='/api/modules/20');c=TestClient(app)
 assert len(c.get('/api/modules/20/education/capabilities').json())==50
 assert c.post('/api/modules/20/education/curriculum_design',json={'payload':{'topic':'x'}}).status_code==422
 assert c.post('/api/modules/20/education/curriculum_design',json={'payload':{'topic':'x','learners':{},'objectives':['Apply x'],'source':SRC}}).status_code==422

def _all_distinctive_results():
 results=[]
 for name in [x['key'] for x in capabilities()]:
  if name in {'curriculum_design','learning_objective_writing','assessment_design','rubric_creation','lesson_planning','unit_planning','course_design','syllabus_creation','instructional_design','addie_model','sam_model','backward_design'}:
   extra={'criteria':['accuracy']} if name=='rubric_creation' else {}
   out=design(name,**extra)
  elif name in {'universal_design_for_learning','differentiated_instruction','personalized_learning','adaptive_learning','intelligent_tutoring','scaffolding','zone_of_proximal_development','cognitive_apprenticeship'}:
   extra={'mastery':.4} if name=='adaptive_learning' else {}
   out=inclusion(name,**extra)
  elif name in {'situated_learning','anchored_instruction','problem_based_learning','project_based_learning','inquiry_based_learning','discovery_learning','experiential_learning','service_learning','cooperative_learning','collaborative_learning','peer_instruction'}: out=pedagogy(name)
  elif name in {'flipped_classroom','blended_learning','online_learning','distance_education','moocs','microlearning','mobile_learning'}:
   p={'units':['Foundations','Application'],'constraints':{'bandwidth':'low'},'source':SRC}
   if name=='moocs': p['cohort_scale']=1000
   out=execute(name,p)
  elif name in {'game_based_learning','gamification','simulation_based_learning','virtual_reality_learning','augmented_reality_learning','mixed_reality_learning'}: out=immersive(name)
  elif name=='artificial_intelligence_in_education': out=execute(name,{'use_case':'practice hints','source':SRC})
  else: out=analytics(name)
  results.append(out['result']['distinctive_computation'])
 return results

def test_every_education_row_has_unique_named_privacy_preserving_computation():
 results=_all_distinctive_results()
 assert len(results)==50 and len({x['name'] for x in results})==50
 assert all(x['educator_review_required'] and 'pseudonymous' in x['privacy'] for x in results)

def test_row_1425_adaptive_computation_changes_with_mastery():
 low=inclusion('adaptive_learning',mastery=.2)['result']['distinctive_computation']['value']
 high=inclusion('adaptive_learning',mastery=.8)['result']['distinctive_computation']['value']
 assert low != high

def test_row_1455_analytics_computation_changes_with_attempt_evidence():
 low=analytics('learning_analytics',events())['result']['distinctive_computation']['value']
 high=analytics('learning_analytics',[dict(events()[0]),dict(events()[0])])['result']['distinctive_computation']['value']
 assert low != high

def test_row_1459_affect_computation_ignores_camera_inference():
 allowed=[{'learner_id':'p','skill':'s','event_type':'self_report','value':'ok'}]
 mixed=allowed+[{'learner_id':'p','skill':'s','event_type':'camera_face','value':'sad'}]
 a=analytics('affect_detection',allowed)['result']; b=analytics('affect_detection',mixed)['result']
 assert len(a['affect_signals'])==len(b['affect_signals'])==1
 assert a['distinctive_computation']['value'] != b['distinctive_computation']['value']

# Exact row nodes reuse the substantive discriminating fixtures in the companion suite.
import importlib.util as _ilu
_ds=_ilu.spec_from_file_location('_atlas_discriminating',__file__.replace('test_m20_education_1410_1459.py','test_discriminating_1310_1459.py'));_dm=_ilu.module_from_spec(_ds);_ds.loader.exec_module(_dm)
_assert_row_moves=_dm.test_education_row_distinctive_value_moves_with_one_input
def test_1410_curriculum_design_distinctive_computation_moves():
 _assert_row_moves("curriculum_design",1410)
def test_1411_learning_objective_writing_distinctive_computation_moves():
 _assert_row_moves("learning_objective_writing",1411)
def test_1412_assessment_design_distinctive_computation_moves():
 _assert_row_moves("assessment_design",1412)
def test_1413_rubric_creation_distinctive_computation_moves():
 _assert_row_moves("rubric_creation",1413)
def test_1414_lesson_planning_distinctive_computation_moves():
 _assert_row_moves("lesson_planning",1414)
def test_1415_unit_planning_distinctive_computation_moves():
 _assert_row_moves("unit_planning",1415)
def test_1416_course_design_distinctive_computation_moves():
 _assert_row_moves("course_design",1416)
def test_1417_syllabus_creation_distinctive_computation_moves():
 _assert_row_moves("syllabus_creation",1417)
def test_1418_instructional_design_distinctive_computation_moves():
 _assert_row_moves("instructional_design",1418)
def test_1419_addie_model_distinctive_computation_moves():
 _assert_row_moves("addie_model",1419)
def test_1420_sam_model_distinctive_computation_moves():
 _assert_row_moves("sam_model",1420)
def test_1421_backward_design_distinctive_computation_moves():
 _assert_row_moves("backward_design",1421)
def test_1422_universal_design_for_learning_distinctive_computation_moves():
 _assert_row_moves("universal_design_for_learning",1422)
def test_1423_differentiated_instruction_distinctive_computation_moves():
 _assert_row_moves("differentiated_instruction",1423)
def test_1424_personalized_learning_distinctive_computation_moves():
 _assert_row_moves("personalized_learning",1424)
def test_1425_adaptive_learning_distinctive_computation_moves():
 _assert_row_moves("adaptive_learning",1425)
def test_1426_intelligent_tutoring_distinctive_computation_moves():
 _assert_row_moves("intelligent_tutoring",1426)
def test_1427_scaffolding_distinctive_computation_moves():
 _assert_row_moves("scaffolding",1427)
def test_1428_zone_of_proximal_development_distinctive_computation_moves():
 _assert_row_moves("zone_of_proximal_development",1428)
def test_1429_cognitive_apprenticeship_distinctive_computation_moves():
 _assert_row_moves("cognitive_apprenticeship",1429)
def test_1430_situated_learning_distinctive_computation_moves():
 _assert_row_moves("situated_learning",1430)
def test_1431_anchored_instruction_distinctive_computation_moves():
 _assert_row_moves("anchored_instruction",1431)
def test_1432_problem_based_learning_distinctive_computation_moves():
 _assert_row_moves("problem_based_learning",1432)
def test_1433_project_based_learning_distinctive_computation_moves():
 _assert_row_moves("project_based_learning",1433)
def test_1434_inquiry_based_learning_distinctive_computation_moves():
 _assert_row_moves("inquiry_based_learning",1434)
def test_1435_discovery_learning_distinctive_computation_moves():
 _assert_row_moves("discovery_learning",1435)
def test_1436_experiential_learning_distinctive_computation_moves():
 _assert_row_moves("experiential_learning",1436)
def test_1437_service_learning_distinctive_computation_moves():
 _assert_row_moves("service_learning",1437)
def test_1438_cooperative_learning_distinctive_computation_moves():
 _assert_row_moves("cooperative_learning",1438)
def test_1439_collaborative_learning_distinctive_computation_moves():
 _assert_row_moves("collaborative_learning",1439)
def test_1440_peer_instruction_distinctive_computation_moves():
 _assert_row_moves("peer_instruction",1440)
def test_1441_flipped_classroom_distinctive_computation_moves():
 _assert_row_moves("flipped_classroom",1441)
def test_1442_blended_learning_distinctive_computation_moves():
 _assert_row_moves("blended_learning",1442)
def test_1443_online_learning_distinctive_computation_moves():
 _assert_row_moves("online_learning",1443)
def test_1444_distance_education_distinctive_computation_moves():
 _assert_row_moves("distance_education",1444)
def test_1445_moocs_distinctive_computation_moves():
 _assert_row_moves("moocs",1445)
def test_1446_microlearning_distinctive_computation_moves():
 _assert_row_moves("microlearning",1446)
def test_1447_mobile_learning_distinctive_computation_moves():
 _assert_row_moves("mobile_learning",1447)
def test_1448_game_based_learning_distinctive_computation_moves():
 _assert_row_moves("game_based_learning",1448)
def test_1449_gamification_distinctive_computation_moves():
 _assert_row_moves("gamification",1449)
def test_1450_simulation_based_learning_distinctive_computation_moves():
 _assert_row_moves("simulation_based_learning",1450)
def test_1451_virtual_reality_learning_distinctive_computation_moves():
 _assert_row_moves("virtual_reality_learning",1451)
def test_1452_augmented_reality_learning_distinctive_computation_moves():
 _assert_row_moves("augmented_reality_learning",1452)
def test_1453_mixed_reality_learning_distinctive_computation_moves():
 _assert_row_moves("mixed_reality_learning",1453)
def test_1454_artificial_intelligence_in_education_distinctive_computation_moves():
 _assert_row_moves("artificial_intelligence_in_education",1454)
def test_1455_learning_analytics_distinctive_computation_moves():
 _assert_row_moves("learning_analytics",1455)
def test_1456_educational_data_mining_distinctive_computation_moves():
 _assert_row_moves("educational_data_mining",1456)
def test_1457_student_modeling_distinctive_computation_moves():
 _assert_row_moves("student_modeling",1457)
def test_1458_knowledge_tracing_distinctive_computation_moves():
 _assert_row_moves("knowledge_tracing",1458)
def test_1459_affect_detection_distinctive_computation_moves():
 _assert_row_moves("affect_detection",1459)
