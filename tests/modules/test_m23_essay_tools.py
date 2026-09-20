from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_topic_and_outline_use_only_student_evidence_and_return_no_prose():
 evidence=[{"label":"Science club","description":"I restarted our community science club after the school lab closed.","values":["community","curiosity"]}]
 topic=client.post('/api/v1/study-abroad/essay-tools/topics',json={"prompt":"Describe your community contribution","evidence":evidence}).json()
 assert topic['candidates'][0]['label']=='Science club';assert topic['student_selects_topic'] is True;assert topic['generated_essay_prose'] is None
 outline=client.post('/api/v1/study-abroad/essay-tools/outline',json={"prompt":"Describe your community contribution","student_thesis":"I learned that access can be rebuilt collectively.","evidence":evidence}).json()
 assert outline['sections'][0]['student_evidence_options']==['Science club'];assert outline['generated_essay_prose'] is None

def test_hook_conclusion_and_clarity_are_coaching_only():
 hook=client.post('/api/v1/study-abroad/essay-tools/hook',json={"student_hook":"The locked laboratory door changed our science club.","evidence":["Our school laboratory closed and I restarted the club."]}).json()
 assert hook['supported_by_evidence'] is True and hook['replacement_hook'] is None
 conclusion=client.post('/api/v1/study-abroad/essay-tools/conclusion',json={"student_conclusion":"I now build access with my community.","thesis":"Community action can rebuild access."}).json()
 assert conclusion['checks']['student_authored'] is True and conclusion['replacement_conclusion'] is None
 clarity=client.post('/api/v1/study-abroad/essay-tools/clarity',json={"draft":"I organized the science club after our laboratory closed. I asked students what experiments they wanted and found donated supplies."}).json()
 assert clarity['revised_draft'] is None and clarity['guardrail']=='student-authored-final'
