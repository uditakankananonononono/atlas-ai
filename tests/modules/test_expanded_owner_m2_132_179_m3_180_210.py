from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m02_competition_manager.expanded_owner_132_179 import ROWS as M2,PROFILES as P2,ExpandedM2Error,run as run2
from app.modules.m03_grant_writer.expanded_owner_180_210 import ROWS as M3,PROFILES as P3,ExpandedM3Error,run as run3
S=[{'source_id':'owner-or-official-1','observed_at':datetime.now(timezone.utc).isoformat()}]
def p2(i):
 _,req,stages=P2[i];p={'sources':S,'evidence':{x:x+' evidence' for x in stages}}
 for k in req:p[k]=k+' value'
 if i==149:p['passes_per_model']=50;p['models']=['a'];p['draft']='d'
 if i in (151,):p['fields']={'name':'owner fact'};p['approved_preview']='preview'
 if i in (153,):p['fields']=['essay'];p['activity_facts']=['founded club'];p['claims']=['founded club']
 if i==154:p['draft']='I founded club';p['activity_facts']=['founded club'];p['claims']=['founded club']
 if i in (156,158):p['recipient']='official@example';p['exact_message']='hello'
 if i==166:p['exact_fields']={'name':'x'};p['screenshot']='shot';p['recipient_site']='site'
 if i==177:p['fact_map']=['founded club'];p['draft']='founded club';p['claims']=['founded club']
 if i==178:p['parts']=['a','b']
 return p
def p3(i):
 _,req,stages=P3[i];p={'sources':S,'workflow_evidence':{x:x+' evidence' for x in stages}}
 for k in req:p[k]=k+' value'
 if i in (180,):p['document_ids']=['d']
 if i==181:p['spreadsheet_ids']=['s'];p['ranges']=['A1']
 if i in (183,184):p['public_sources']=['url']
 if i==185:p['seed_fields']=['field'];p['target']=500000
 if i==186:p['queries']=['q'];p['public_sources']=['url']
 if i in (187,):p['documents']=['doc']
 if i==188:p['companies']=['c'];p['evidence']=['e']
 if i in (189,):p['stories']=['s']
 if i==190:p['cases']=['c']
 if i==191:p['markets']=['m']
 if i==192:p['securities']=['x'];p['sources']=S
 if i==193:p['variables']=['v'];p['target']=1000000
 if i==194:p['guidelines']=['g'];p['model']='Gemini'
 if i in (197,):p['databases']=['db']
 if i==198:p['award_records']=['a'];p['target']=1000
 if i==199:p['call']='c';p['applicant_facts']=['f'];p['model']='Claude'
 if i==200:p['proposal']='p';p['criteria']=['clarity','impact','feasibility'];p['model']='GPT-4'
 if i==201:p['proposal']='p';p['critique']=['c']
 if i==202:p['document']='d';p['styles']={'h':'x'}
 if i==203:p['document']='d';p['layout']={'page':'A4'}
 if i==204:p['categories']=['people'];p['rules']=['r']
 if i==205:p['items']=['role'];p['sources']=S
 if i==206:p['line_items']=[{'quantity':2,'unit_rate':5}];p['currency']='USD'
 if i==207:p['proposal']='p';p['funded_proposals']=['f']
 if i==208:p['proposal']='p';p['references']=['r']
 if i==209:p['needs']=['n'];p['candidates']=['c']
 if i==210:p['parts']=[f'p{x}' for x in range(20)]
 return p
@pytest.mark.parametrize('i',range(132,180))
def test_every_m2_row_exact_and_substantive(i):
 o=run2(i,p2(i));assert o['row_id']==i and o['requirement']==M2[i] and o['mode']==P2[i][0] and len(o['workflow'])==len(P2[i][2]) and not o['pending'] and o['external_effects']==[]
@pytest.mark.parametrize('i',range(180,211))
def test_every_m3_row_exact_and_substantive(i):
 o=run3(i,p3(i));assert o['row_id']==i and o['requirement']==M3[i] and o['mode']==P3[i][0] and len(o['workflow'])==len(P3[i][2]) and not o['pending'] and o['external_effects']==[]
def test_149_exact_50_pass_target():
 p=p2(149);p['passes_per_model']=49
 with pytest.raises(ExpandedM2Error,match='50'):run2(149,p)
@pytest.mark.parametrize('i',[151,156,158,166])
def test_exact_review_rows_block_execution(i):
 p=p2(i);p['execute']=True
 with pytest.raises(ExpandedM2Error,match='blocked'):run2(i,p)
def test_grounded_draft_flags_unsupported_claim():
 p=p2(153);p['claims']=['won Nobel'];assert run2(153,p)['unsupported_claims']==['won Nobel']
def test_m2_provenance_required():
 p=p2(132);p['sources']=[]
 with pytest.raises(ExpandedM2Error,match='provenance'):run2(132,p)
@pytest.mark.parametrize('i,target,bad',[(185,500000,5),(193,1000000,5),(198,1000,999)])
def test_m3_scale_targets_are_exact_or_minimum(i,target,bad):
 p=p3(i);p['target']=bad
 with pytest.raises(ExpandedM3Error):run3(i,p)
def test_targets_report_honest_gap():
 o=run3(185,p3(185));assert o['metrics']=={'target':500000,'actual':1,'gap':499999,'target_met':False}
def test_twenty_part_workflow_exact():
 p=p3(210);p['parts']=p['parts'][:19]
 with pytest.raises(ExpandedM3Error,match='twenty'):run3(210,p)
def test_budget_table_math():assert run3(206,p3(206))['metrics']['subtotal']==10
def test_m3_provenance_required():
 p=p3(195);p['sources']=[]
 with pytest.raises(ExpandedM3Error,match='provenance'):run3(195,p)
def test_exact_ranges_titles():assert len(M2)==48 and len(M3)==31 and M2[132]=='Official rules-page capture' and M3[210]=='Twenty-part grant workflow target'
def test_m2_mounted():
 r=TestClient(app).post('/api/v1/competition-manager/expanded-owner-132-179/132',json=p2(132));assert r.status_code==200 and r.json()['row_id']==132
def test_m3_mounted():
 r=TestClient(app).post('/api/v1/grant-writer/expanded-owner-180-210/210',json=p3(210));assert r.status_code==200 and r.json()['row_id']==210
def test_unknown_routes_negative():
 c=TestClient(app);assert c.post('/api/v1/competition-manager/expanded-owner-132-179/131',json={}).status_code==422 and c.post('/api/v1/grant-writer/expanded-owner-180-210/211',json={}).status_code==422
def test_catalog_counts():
 c=TestClient(app);assert len(c.get('/api/v1/competition-manager/expanded-owner-132-179').json())==48 and len(c.get('/api/v1/grant-writer/expanded-owner-180-210').json())==31
