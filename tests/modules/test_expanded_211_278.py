import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m04_research_scientist.expanded_211_258 import ROWS as R4,run as m4
from app.modules.m04_research_scientist.routes import router as r4
from app.modules.m22_tools_hub.expanded_259_278 import ROWS as RT,run as tools
from app.modules.m22_tools_hub.routes import router as rt

def d4(row):
 p={'id':'p','title':'T','doi':'10/x','source':'PubMed'}
 if row in range(211,217):return {'query':'q','papers':[p]}
 return {217:{'paper':p,'sections':{'objective':'o','methods':'m','findings':'f','limitations':'l'}},218:{'papers':[p],'vectors':[[1,0]]},219:{'assignments':[{'paper_id':'p','cluster':0}]},220:{'topics':[{'topic':'x','evidence_count':1}]},221:{'topics':[{'topic':'a+b','evidence_count':0}]},222:{'observations':[{'hypothesis':'h','falsifier':'f','test':'t'}]},223:{'observations':[{'hypothesis':'h','falsifier':'f','test':'t'}]},224:{'paper':{'methods':'m','findings':'f'}},225:{'components':[{'components':['a','b'],'mechanism':'m','test':'t'}]},226:{'dataset':'d','experiment':'e'},227:{'dataset':'d','experiment':'e'},228:{'task':'t','code':'print(1)'},229:{'task':'t','code':'print(1)'},230:{'operation':'normalize','inputs':['adata']},231:{'image_digest':'sha256:x','command':['python'],'resource_limits':{'cpu':1}},232:{'results':[1]},233:{'data':{'x':[1]},'plot_spec':{'x':'x'}},234:{'sections':{'intro':'x'},'citations':['a']},235:{'manuscript':'m','journals':[{'name':'j','scope_fit':1}]},236:{'source_observations':[{'observation':'o'}]},237:{'source_observations':[{'observation':'o'}]},238:{'source_observations':[{'observation':'o'}]},239:{'question':'q','search_steps':['s']},240:{'operation':'run','inputs':['i']},241:{'operation':'dock','inputs':['i']},242:{'operation':'run','inputs':['i']},243:{'prizes':[{'name':'p','deadline':'d','source_url':'u'}]},244:{'winners':[{'attributes':['novel']}]},245:{'ideas':[{'scores':{'impact':2}}],'weights':{'impact':1}},246:{'fields':['a','b']},247:{'sections':['s'],'sources':['u']},248:{'operation':'predict','inputs':['seq']},249:{'operation':'workflow','inputs':['data']},250:{'operation':'view','inputs':['pdb']},251:{'tools':[{'source_url':'u','license':'MIT','version':'1'}]},252:{'sources':[{'url':'u','license_or_access_basis':'public'}]},253:{'requested_work':'book','legal_replacements':['library']},254:{'targets':[{'allowlisted':True,'terms_checked':True}]},255:{'workers':10,'benchmarks':['throughput']},256:{'outline':['x'],'page_target':40},257:{'submissions':[{'checks':{'eligible':True}}],'criteria':['eligible']},258:{'advice':[{'text':'x','anonymized':True}],'consent':{'research_use':True}}}[row]
def dt(row):
 return {259:{'candidates':[{'source_url':'u','observed_at':'t'}]},260:{'candidates':[{'source_url':'u','observed_at':'t'}]},261:{'candidates':[{'source_url':'u','observed_at':'t'}]},262:{'tool':{'name':'x','source_url':'u','publisher':'p','license':'MIT','version':'1'}},263:{'tool':'x','capabilities':['c']},264:{'artifact':'x','scan_findings':[]},265:{'tool':'x','sandbox_policy':{},'observations':[]},266:{'tool':'x','platform':'linux','tests':[{'passed':True}]},267:{'candidates':[{'scores':{'fit':1}}],'weights':{'fit':1}},268:{'tool':'x','adapter':'a','scopes':['read']},269:{'tool':'x','operations':['pip install x']},270:{'preview_hash':'h','reviewed_operations':['op'],'decision':'approve','reviewer':'u'},271:{'dependencies':[{'name':'x'}],'environment':'venv'},272:{'installed_changes':['x'],'rollback_steps':['remove']},273:{'dependencies':[{'name':'x','version':'1.0'}]},274:{'installed':[{'name':'x','version':'1'}],'available':[{'name':'x','version':'2'}]},275:{'content':'x','secret_indicators':['token']},276:{'techniques':[{'lawful':True,'authorized':True,'safe':True}]},277:{'expected':{'version':'1'},'observed':{'version':'1'}},278:{'events':[{'timestamp':'t','actor':'a','action':'scan','subject':'x'}]}}[row]

def test_exact_ranges():assert list(R4)==list(range(211,259)) and list(RT)==list(range(259,279))
@pytest.mark.parametrize('row',range(211,259))
def test_each_m4_row_substantive(row):
 o=m4(row,d4(row));assert o['row']==row and o['result'] and 'External collection' in o['boundary']
@pytest.mark.parametrize('row',range(259,279))
def test_each_tools_row_substantive(row):
 o=tools(row,dt(row));assert o['row']==row and o['result'] and 'does not authorize' in o['boundary']
@pytest.mark.parametrize('row',range(211,259))
def test_each_m4_row_negative(row):
 with pytest.raises((ValueError,KeyError,TypeError)):m4(row,{})
@pytest.mark.parametrize('row',range(259,279))
def test_each_tools_row_negative(row):
 with pytest.raises((ValueError,KeyError,TypeError)):tools(row,{})
def test_211_surveillance_deduplicates():
 d=d4(211);d['seen_ids']=['10/x'];assert m4(211,d)['result']['new_papers']==[]
def test_218_embedding_dimension_mismatch_rejected():
 with pytest.raises(ValueError):m4(218,{'papers':[1,2],'vectors':[[1],[1,2]]})
def test_220_gap_is_candidate_not_absence_proof():assert m4(220,d4(220))['result']['candidate_gaps'][0]['absence_not_proven']
def test_223_react_bounded():assert m4(223,d4(223))['result']['max_iterations']==5
def test_231_sandbox_never_executes():assert not m4(231,d4(231))['result']['executed']
def test_253_piracy_excluded():assert not m4(253,d4(253))['result']['piracy_used']
def test_254_only_allowlisted_terms_checked():assert len(m4(254,d4(254))['result']['adapters'])==1
def test_255_no_people_equivalence_claim():assert not m4(255,d4(255))['result']['billion_researcher_claim']
def test_264_high_scan_finding_blocks():
 d=dt(264);d['scan_findings']=[{'severity':'high'}];assert not tools(264,d)['result']['passed']
def test_269_install_preview_not_executed():assert not tools(269,dt(269))['result']['executed']
def test_270_exact_review_requires_reviewer():
 d=dt(270);d.pop('reviewer');assert not tools(270,d)['result']['approved']
def test_273_unpinned_detected():
 d=dt(273);d['dependencies']=[{'name':'x','version':'*'}];assert tools(273,d)['result']['unpinned']
def test_275_secret_content_not_retained():assert not tools(275,dt(275))['result']['content_retained']
def test_276_unsafe_hack_rejected():
 d=dt(276);d['techniques']=[{'lawful':False,'authorized':True,'safe':True}];assert tools(276,d)['result']['rejected']
def test_routes_mounted():
 a=FastAPI();a.include_router(r4);c=TestClient(a);assert c.post('/research-scientist/expanded-211-258/211',json=d4(211)).status_code==200
 b=FastAPI();b.include_router(rt);c=TestClient(b);assert c.post('/tools-hub/expanded-259-278/259',json=dt(259)).status_code==200
 assert c.post('/tools-hub/expanded-259-278/259',json={}).status_code==422
