import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.technical_spec_0133_0165 import META,run
C={133:{'sections':[{'heading':'Intro','paragraphs':['x'],'bullets':['a'],'figure_captions':['f']}]},134:{'figures':[{'engine':'plotly','artifact_uri':'file://x','caption':'c'}]},135:{'plot_spec':{'kind':'line','x':[1,2],'y':[2,3]}},136:{'previous':'a','current':'b','version':2},137:{'events':[{'type':'task_progress','sequence':1}]},138:{'tasks':[{'id':'t','start':'2026-01-01','end':'2026-01-02','priority':1}]},139:{'approvals':[{'id':'a','status':'pending'}]},140:{'agents':[{'id':'a','state':'running'}]},141:{'cards':[{'metric':'wins','value':2,'evidence_ids':['e1']}]},142:{'command':'Apply to grant'},143:{'sources':[{'url':'u','official_or_licensed':True,'login_scrape':False}]},144:{'media':[{'uri':'file://a','permission':True}]},145:{'advice':[{'id':'a','topic':'essay'}]},146:{'advice':[{'id':'a','tip':'revise','source_url':'u'}]},147:{'user_facts':[{'dimension':'identity','fact':'artist'}]},148:{'identity_tags':['artist'],'structures':[{'id':'s','tags':['artist'],'source_url':'u'}]},149:{'evidence':[{'theme':'heritage','fact':'grandmother wove dress','metaphor':'thread'}],'count':5},150:{'user_samples':['short clear words'],'draft':'clear words'},151:{'reviews':[{'dimension':'narrative','issues':[]},{'dimension':'grammar','issues':[]},{'dimension':'cliche','issues':['journey']}]},152:{'original':'a','suggested':'b'},153:{'draft':'A scene.'},154:{'sources':[{'url':'u','public':True,'login_required':False}]},155:{'text':'1. Make product\n2. Sell subscription','known_tools':['Canva']},156:{'claims':['guaranteed income','act now'],'upfront_fee':True,'verifiable_identity':False},157:{'steps':['a'],'tools':['x'],'complexity':'low','time_to_first_dollar':'30d','automation_level':.5,'source_urls':['u']},158:{'blueprint':{'steps':['a']},'user_context':{'weekly_hours':5,'constraints':['budget']}},159:{'strengths':['skill'],'weaknesses':['time'],'opportunities':['demand'],'threats':['competition']},160:{'trend_points':[10,20,30]},161:{'saturation':.2,'barrier':.3,'demand':.9},162:{'blueprint':{},'swot':{},'saturation':.2,'viability':.7,'evidence_urls':['u']},163:{'text':'AI tutor for villages'},164:{'idea':'AI tutor','problem':'access','customers':['students'],'solution':'offline tutor'},165:{'queries':['AI tutor competitors','education apps'],'concurrent_limit':2}}
@pytest.mark.parametrize('row',range(133,166))
def test_each_exact_row_semantic_and_source_mapped(row):
 method=META[row][3];r=run(method,C[row]);assert r['row']==row and r['requirement_id']==META[row][0] and r['source_line_start']==META[row][1] and r['source_line_end']==META[row][2] and r['output'] and r['output']['method_limits']
def test_sandbox_approval_provenance_and_coaching_boundaries():
 assert not run('sandboxed_plot',C[135])['output']['sandbox_plan']['network']
 assert run('command_bar',C[142])['output']['approval_required'] and not run('command_bar',C[142])['output']['execution_allowed']
 assert run('essay_concepts',C[149])['output']['count']==5 and all(not x['final_essay'] for x in run('essay_concepts',C[149])['output']['concepts'])
 assert run('legal_blueprints',C[154])['output']['blocked']==[]
def test_negative_paths_and_mounted_boundary():
 with pytest.raises(ValueError):run('sandboxed_plot',{'plot_spec':{'kind':'line','code':'import os'}})
 with pytest.raises(ValueError):run('kpi_cards',{'cards':[{'metric':'x','value':1}]})
 with pytest.raises(ValueError):run('idea_intake',{'text':'x','voice_transcript':'x'})
 c=TestClient(app);h={'X-Tenant-ID':'spec','X-Actor-ID':'tester'}
 r=c.get('/api/v1/api/modules/20/technical-spec-133-165/methods',headers=h);assert r.status_code==200 and len(r.json())==33
 r=c.post('/api/v1/api/modules/20/technical-spec-133-165/analyze',headers=h,json={'method':'viability_score','data':C[161]});assert r.status_code==200 and r.json()['row']==161
 assert c.post('/api/v1/api/modules/20/technical-spec-133-165/analyze',headers=h,json={'method':'bad'}).status_code==422
