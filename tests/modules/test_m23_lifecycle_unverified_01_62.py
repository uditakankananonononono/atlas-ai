import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m23_study_abroad.lifecycle_unverified_01_62 import ROWS,run
UNVERIFIED=[1,2,3,8,9,10,11,12,13,14,15,16,17,18,19,20,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62]
CASE={1:{'completed_stages':['identity']},2:{},3:{'institutions':[{'name':'X','rank':5,'official_source':'url'}]},8:{'identity_text':'Tai Ahom artist scientist'},9:{'records':[{'id':'a','theme':'science'},{'id':'b','theme':'art'}]},10:{'evidence':[{'detail':'built app','themes':['builder']}],'student_draft':'I learned by building.','prompt':'What matters?'},11:{'evidence':[{'detail':'x','themes':['growth']}],'student_draft':'I learned.','prompt':'Why?'},22:{'versions':[{'version':1,'text':'a'},{'version':2,'text':'b'}]},23:{'records':[{'id':'x','official_url':'u','checked_at':'now'}]},24:{'records':[{'id':'x','official_url':'u','checked_at':'now'}]},25:{'records':[{'id':'x','official_url':'u','checked_at':'now'}]},26:{'schools':[{'name':'A','fit':.8,'estimated_admit_probability':.2},{'name':'B','fit':.8,'estimated_admit_probability':.5},{'name':'C','fit':.7,'estimated_admit_probability':.8}]},32:{'module0_approval':True,'artifact':'application'},33:{'reviews':[{'issues':['a','b']},{'issues':['a']}]},34:{'profile_tags':['india','stem'],'scholarships':[{'id':'s','eligibility_tags':['india'],'official_url':'u'}]},35:{'profile_tags':['india','stem'],'scholarships':[{'id':'s','eligibility_tags':['india'],'official_url':'u'}]},36:{'tuition':100,'fees':10,'living':40,'aid':50,'years':2},37:{'forms':[{'name':'F','required_fields':['income'],'income':10}]},39:{'awards':[{'amount':100,'accepted':True},{'amount':50}]},40:{'sources':[{'type':'official','login_required':False},{'type':'private','login_required':True}]},41:{'evidence_quality':1,'expertise':.8,'recency':.9,'conflict_risk':.1},42:{'series':[{'value':10},{'value':15}]},43:{'events':[{'id':'e','official_url':'u','starts_at':'tomorrow'}]},44:{'events':[{'id':'e','official_url':'u','starts_at':'tomorrow'}]},45:{'items':[{'type':'deadline','source_verified':True}]},51:{'tenant_id':'a','records':[{'tenant_id':'a','id':1},{'tenant_id':'b','id':2}]},52:{'query':[1,0],'items':[{'id':'x','embedding':[1,0]}]},53:{'edges':[{'from':'school','to':'program'}]},54:{'schedules':[{'source':'official','cadence':'daily','enabled':True}]},55:{'collectors':[{'kind':'static','login_required':False},{'kind':'playwright','login_required':True}]},56:{'providers':[{'name':'a','healthy':True,'cost':1,'quality':.8}]},57:{'text':'Apply 2027-01-01 to Oxford University'},58:{'credentials':[{'id':'x','encrypted':True}],'audit_events':[{'id':'a'}]},59:{'achievements':[{'id':'x','fact':'won','evidence':'cert','source_module':4}]},60:{'language':'Assamese'},61:{'history':[{'applied':True,'won':True,'tags':['research']}]},62:{'pathways':[{'name':'graduate visa','official_url':'gov','estimated_cost':1}]}}
for r in range(12,21):
 if r not in CASE:CASE[r]={'evidence':[{'detail':'specific fact','themes':['fit']}],'student_draft':'I learned from research.','prompt':'Explain fit'}
for r in [27,28,29,30,31,38]:CASE[r]={'items':[{'id':'x','status':'open'}]}
for r in [46,47,48,49,50]:
 role=ROWS[r].replace('_agent','');CASE[r]={'tasks':[{'id':'x','role':role}]}
@pytest.mark.parametrize('row',UNVERIFIED)
def test_each_unverified_row_is_substantive(row):
 method=ROWS[row];r=run(method,CASE[row]);assert r['row']==row and r['method']==method and r['output'] and r['output']['method_limits']
def test_scale_and_lifecycle_invariants():
 assert run('destinations_55',{})['output']['count']==55
 x=run('end_to_end_lifecycle',CASE[1])['output'];assert len(x['stages'])==13 and x['next_stage']=='destination research'
def test_coaching_never_ghostwrites_and_submission_is_gated():
 assert not run('story_frameworks',CASE[10])['output']['final_prose_generated']
 assert not run('submission_approval',{'artifact':'x','module0_approval':False})['output']['submission_allowed']
def test_sources_tenant_and_collectors_enforce_boundaries():
 assert len(run('allowed_social_sources',CASE[40])['output']['blocked'])==1
 assert run('tenant_records',CASE[51])['output']['cross_tenant_rejected']==1
 assert len(run('collectors',CASE[55])['output']['blocked'])==1
def test_negative_paths_and_mounted_boundary():
 with pytest.raises(ValueError):run('draft_version_control',{'versions':[{'version':1},{'version':1}]})
 with pytest.raises(ValueError):run('multi_provider_ai',{'providers':[{'healthy':False}]})
 c=TestClient(app);h={'X-Tenant-ID':'m23','X-Actor-ID':'tester'}
 r=c.get('/api/v1/study-abroad/lifecycle-workbench/methods',headers=h);assert r.status_code==200 and len(r.json())==57
 r=c.post('/api/v1/study-abroad/lifecycle-workbench/analyze',headers=h,json={'method':'destinations_55','data':{}});assert r.status_code==200 and r.json()['output']['count']==55
 assert c.post('/api/v1/study-abroad/lifecycle-workbench/analyze',headers=h,json={'method':'bad'}).status_code==422
