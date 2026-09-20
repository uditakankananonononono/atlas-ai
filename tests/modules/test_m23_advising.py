from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
H={"x-atlas-tenant":"advising-a","x-atlas-actor":"student"}
PROFILE={"values":["community"],"strengths":["analysis"],"interests":["biology","health"],"goals":["public health"]}

def test_major_mentor_is_evidence_explainable_and_persistent():
 r=client.post('/api/v1/study-abroad/major-mentor',headers=H,json={"profile":PROFILE,"majors":[{"id":"bio","name":"Biology","themes":["biology"],"skills":["analysis"],"careers":["health"]},{"id":"art","name":"Art","themes":["drawing"],"skills":[],"careers":[]}]}).json()
 assert r['recommendations'][0]['id']=='bio';assert set(r['recommendations'][0]['matched_evidence'])=={'analysis','biology','health'}
 hist=client.get('/api/v1/study-abroad/advising-history?kind=major_mentor',headers=H).json();assert hist[0]['id']==r['id']
 assert client.get('/api/v1/study-abroad/advising-history',headers={"x-atlas-tenant":"advising-b"}).json()==[]

def test_school_match_is_official_url_grounded_not_admission_prediction():
 r=client.post('/api/v1/study-abroad/school-match',headers=H,json={"profile":{**PROFILE,"annual_budget_usd":30000},"schools":[{"id":"s1","name":"School One","programs":["public health","biology"],"annual_cost_usd":25000,"official_url":"https://example.edu/programs"}]}).json()
 assert r['matches'][0]['affordable'] is True and r['matches'][0]['official_url']=='https://example.edu/programs';assert r['not_an_admission_prediction'] is True

def test_activity_plan_respects_capacity_and_uses_supplied_activities_only():
 activities=[{"id":"clinic","name":"Clinic volunteer","themes":["health","community"],"hours_per_week":3,"milestone":"Complete orientation"},{"id":"lab","name":"Lab club","themes":["biology"],"hours_per_week":4}]
 r=client.post('/api/v1/study-abroad/activity-plan',headers=H,json={"profile":PROFILE,"activities":activities,"weekly_hours":5}).json()
 assert r['scheduled_hours']<=5 and r['invented_activities'] is False;assert {x['id'] for x in r['plan']} <= {'clinic','lab'}

def test_passion_project_picker_filters_constraints_and_preserves_student_choice():
 ideas=[{"id":"map","title":"Map local health access","themes":["health","community"],"hours_per_week":3,"budget_usd":10,"first_experiment":"Interview a clinic"},{"id":"device","title":"Build a medical device","themes":["health"],"hours_per_week":20,"budget_usd":5000}]
 r=client.post('/api/v1/study-abroad/passion-projects',headers=H,json={"profile":PROFILE,"constraints":{"max_hours_per_week":5,"max_budget_usd":50},"ideas":ideas}).json()
 assert r['ideas'][0]['id']=='map' and r['ideas'][0]['feasible'] is True;assert r['ideas'][1]['feasible'] is False;assert r['student_must_choose_and_author'] is True
