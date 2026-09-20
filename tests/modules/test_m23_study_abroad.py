from app.modules.m23_study_abroad.service import Service
from app.modules.m23_study_abroad.schemas import *
def profile():return StudentProfileIn(values=['curiosity'],turning_points=['Built a community lab'],strengths=['systems thinking'],academics={'gpa':3.8},finances={'annual_budget_usd':30000},goals=['study computer science'])
def test_identity_uses_student_supplied_evidence_and_fit_is_explainable():
 s=Service();v=s.identity_vector(profile());assert v['source']=='student_supplied' and 'systems' in v['patterns']
 u=UniversityIn(id='u',name='U',country='US',programs=['Computer Science'],annual_tuition_usd=20000,official_url='https://u.example/admissions')
 fit=s.fit(profile(),[u])[0];assert fit['score']==1 and fit['evidence']=={'program_match':1,'budget_fit':1}
def test_essay_system_is_coaching_only_and_never_returns_final_prose():
 x=EssayCoachingIn(prompt='Describe growth',student_draft='Since I was young, I have cared about systems. Building a community lab changed my thinking.',system='common_app',identity_evidence=['community lab'])
 out=Service().coach_essay(x);assert out.final_prose is None and out.guardrail=='student-authored-final' and out.questions and 'since i was young' in out.critique['cliches']
