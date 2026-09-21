import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.education import EducationError, capabilities, execute
from app.modules.m20_general_cognitive_worker.education_routes import router
SRC={"title":"Teaching evidence","url":"https://example.edu/evidence"}
def design(name="curriculum_design",**extra):
 p={"topic":"Fractions","learners":{"grade":5},"objectives":[{"id":"o1","statement":"Compare fractions"}],"assessments":[{"name":"exit ticket","objective_ids":["o1"]}],"duration_minutes":50,"source":SRC};p.update(extra);return execute(name,p,tenant_id="tenant-a",actor_id="teacher-a")
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
 p={'objectives':['Solve equations'],'learner_profile':{'prior_knowledge':'variable'},'supports':['worked examples'],'source':SRC};p.update(extra);return execute(name,p,tenant_id="tenant-a",actor_id="teacher-a")
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
 p={'challenge':'Reduce school waste','objectives':['Evaluate evidence'],'source':SRC};p.update(extra);return execute(name,p,tenant_id="tenant-a",actor_id="teacher-a")
@pytest.mark.parametrize('name', ['situated_learning','anchored_instruction','problem_based_learning','project_based_learning','inquiry_based_learning','discovery_learning','experiential_learning','cooperative_learning','collaborative_learning','peer_instruction'])
def test_pedagogies_produce_active_cycle_and_artifacts(name):
 o=pedagogy(name);assert len(o['result']['learning_cycle'])>=4 and o['result']['learner_artifacts']
def test_service_learning_requires_reciprocity(): assert 'reciprocity' in pedagogy('service_learning')['result']['community_safeguards']

def delivery(name): return execute(name,{'units':['Foundations','Application'],'constraints':{'bandwidth':'low'},'source':SRC},tenant_id='tenant-a',actor_id='teacher-a')
@pytest.mark.parametrize('name',['flipped_classroom','blended_learning','online_learning','distance_education'])
def test_delivery_has_async_equivalent_and_accessibility(name):
 o=delivery(name);assert 'asynchronous_equivalent' in o['result']['continuity'] and 'captions_or_transcript' in o['result']['accessibility']
def test_mooc_micro_mobile_specifics():
 assert delivery('moocs')['result']['mooc_operations']['forum_moderation']
 assert delivery('microlearning')['result']['micro_units'][0]['target_minutes']<=10
 assert 'offline_resume' in delivery('mobile_learning')['result']['mobile_requirements']

def immersive(name,**extra):
 p={'objective':'Apply safety procedure','mechanic':'branching decision','alignment_rationale':'requires choosing each step','source':SRC};p.update(extra);return execute(name,p,tenant_id="tenant-a",actor_id="teacher-a")
@pytest.mark.parametrize('name',['game_based_learning','simulation_based_learning'])
def test_game_and_simulation_align_mechanic_and_debrief(name):
 o=immersive(name);assert o['result']['alignment']['mechanic_practices_objective'] and len(o['result']['debrief'])==3
def test_gamification_is_noncoercive(): assert immersive('gamification')['result']['motivation_design']['avoids_coercive_rewards']
@pytest.mark.parametrize('name',['virtual_reality_learning','augmented_reality_learning','mixed_reality_learning'])
def test_xr_has_exit_and_2d_equivalent(name): assert 'accessible_2d_equivalent' in immersive(name)['result']['xr_safety']

def events(): return [{'learner_id':'p1','skill':'fractions','event_type':'attempt','correct':True,'duration_seconds':20},{'learner_id':'p1','skill':'fractions','event_type':'attempt','correct':False,'duration_seconds':40}]
def analytics(name,ev=None,**extra):
 p={'events':events() if ev is None else ev,'source':SRC};p.update(extra);return execute(name,p,tenant_id="tenant-a",actor_id="teacher-a")
def test_ai_in_education_has_contestability():
 o=execute('artificial_intelligence_in_education',{'use_case':'practice hints','source':SRC},tenant_id='tenant-a',actor_id='teacher-a');assert 'learner can contest recommendation' in o['result']['human_oversight']
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
 with pytest.raises(EducationError): execute('curriculum_design',{'topic':'x'},tenant_id='tenant-a',actor_id='teacher-a')
 with pytest.raises(EducationError): analytics('knowledge_tracing',prior_mastery=2)
def test_routes_mount_and_return_validation_errors():
 app=FastAPI();app.include_router(router,prefix='/api/modules/20');c=TestClient(app);h={'X-Tenant-ID':'tenant-a','X-Actor-ID':'teacher-a'}
 assert len(c.get('/api/modules/20/education/capabilities').json())==50
 assert c.post('/api/modules/20/education/curriculum_design',headers=h,json={'payload':{'topic':'x'}}).status_code==422
 assert c.post('/api/modules/20/education/curriculum_design',headers=h,json={'payload':{'topic':'x','learners':{},'objectives':['Apply x'],'source':SRC}}).status_code==422


def test_every_education_row_requires_teacher_review_and_private_scope():
    samples = {
        "design": ("curriculum_design", {"topic":"Fractions","learners":{"grade":5},"objectives":["Compare fractions"],"source":SRC}),
        "inclusion": ("universal_design_for_learning", {"objectives":["Solve equations"],"learner_profile":{"prior":"algebra"},"source":SRC}),
        "pedagogy": ("situated_learning", {"challenge":"Reduce waste","objectives":["Evaluate evidence"],"source":SRC}),
        "delivery": ("online_learning", {"units":["Unit 1"],"source":SRC}),
        "immersive": ("game_based_learning", {"objective":"Apply procedure","mechanic":"branching","source":SRC}),
        "analytics": ("learning_analytics", {"events":[{"learner_id":"learner-7","skill":"fractions","event_type":"attempt","correct":True}],"source":SRC}),
    }
    for name,payload in samples.values():
        out=execute(name,payload,tenant_id="district-1",actor_id="teacher-9")
        assert out["teacher_review"]["status"]=="pending"
        assert out["teacher_review"]["release_blocked"] is True
        assert out["privacy"]=={"tenant_id":"district-1","actor_id":"teacher-9","learner_identifiers":"pseudonymous_only","contact_information_rejected":True,"cross_tenant_reuse":False}

def test_education_rejects_contact_information_as_learner_identifier():
    with pytest.raises(EducationError,match="pseudonymous"):
        analytics("learning_analytics",[{"learner_id":"student@example.edu","skill":"fractions","event_type":"attempt"}])

def test_education_route_requires_scope_and_rejects_scope_mismatch():
    app=FastAPI();app.include_router(router,prefix='/api/modules/20');c=TestClient(app)
    body={"payload":{"topic":"x","learners":{"grade":5},"objectives":["Apply x"],"source":SRC}}
    assert c.post('/api/modules/20/education/curriculum_design',json=body).status_code==422
    h={"X-Tenant-ID":"tenant-a","X-Actor-ID":"teacher-a"}
    body["payload"]["tenant_id"]="tenant-b"
    assert c.post('/api/modules/20/education/curriculum_design',headers=h,json=body).status_code==422
