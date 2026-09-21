import pytest
from fastapi.testclient import TestClient
from app.main import app
import app.technical_spec_34_66 as t
@pytest.fixture(autouse=True)
def clean():t.reset()
def test_34_hybrid_retrieval_semantic_keyword_filter():
 p={'query':'biology grant','query_vector':[1,0],'filters':{'kind':'grant'},'items':[{'id':'a','text':'biology grant','embedding':[1,0],'metadata':{'kind':'grant'}},{'id':'b','text':'biology','embedding':[0,1],'metadata':{'kind':'grant'}},{'id':'c','text':'biology grant','embedding':[1,0],'metadata':{'kind':'job'}}]};r=t.execute(34,p)['result'];assert [x['id'] for x in r['ranked']]==['a','b'] and r['ranked'][0]['semantic']==1
def test_35_typed_graph():assert t.execute(35,{'edges':[{'from':'project','to':'competition','type':'targets'}]})['result']['typed_edges'][0]['type']=='targets'
def test_35_rejects_untyped():
 with pytest.raises(t.SpecError):t.execute(35,{'edges':[{'from':'a','to':'b'}]})
@pytest.mark.parametrize('i',[36,37])
def test_36_37_recursive_planner_nodes(i):
 r=t.execute(i,{'goal':'apply','effort':{'task':3},'tools':{'task':['browser']},'deadlines':{'task':'2026-10-01'}})['result'];assert [x['type'] for x in r['nodes']]==['objective','milestone','task','subtask'] and r['nodes'][2]['effort']==3 and r['nodes'][2]['tools']==['browser']
def test_38_memory_triggered_refinement():assert t.execute(38,{'plan_id':'p','plan':{'goal':'g'},'memory_id':'m'})['result']['refined_from_memory']
def test_39_versioned_json():
 assert t.execute(39,{'plan_id':'p','plan':{'x':1}})['result']['version']==1 and t.execute(39,{'plan_id':'p','plan':{'x':2}})['result']['version']==2
def test_40_policy_model_route():assert t.execute(40,{'task_type':'code','policy':{'code':'deepseek','default':'mini'}})['result']['selected_model']=='deepseek'
def test_40_no_policy_negative():
 with pytest.raises(t.SpecError):t.execute(40,{'task_type':'x','policy':{}})
def test_41_exact_chain():
 c=[{'stage':x,'model':x,'output':x+' result'} for x in ['research','draft','critique','format']];assert t.execute(41,{'input':'q','chain':c})['result']['final']=='format result'
def test_41_wrong_chain_negative():
 with pytest.raises(t.SpecError):t.execute(41,{'chain':[]})
def test_42_recursive_merge():
 r=t.execute(42,{'results':[{'a':{'x':1},'tags':['a']},{'a':{'y':2},'tags':['a','b']} ]})['result']['merged'];assert r=={'a':{'x':1,'y':2},'tags':['a','b']}
def approval_payload():return {'user_id':'u','module':5,'action_type':'send','payload':{'to':'x'},'continuation_token':'token'}
@pytest.mark.parametrize('i',[43,44,46,47,48,51])
def test_approval_creation_contract_rows(i):
 r=t.execute(i,approval_payload())['result'];assert r['approval']['status']=='pending' and r['published_event']['type']=='approval_request' and r['worker_state']=='suspended' and not r['serialized_callback'] and r['sdk']=='request_approval'
def test_45_state_machine():
 aid=t.execute(43,approval_payload())['result']['approval']['id'];assert t.execute(45,{'approval_id':aid,'decision':'approved','approved_by':'owner'})['result']['approval']['approved_by']=='owner'
def test_45_cannot_redecide():
 aid=t.execute(43,approval_payload())['result']['approval']['id'];t.execute(45,{'approval_id':aid,'decision':'denied'});
 with pytest.raises(t.SpecError):t.execute(45,{'approval_id':aid,'decision':'approved'})
def test_49_single_use_release():
 aid=t.execute(43,approval_payload())['result']['approval']['id'];t.execute(45,{'approval_id':aid,'decision':'approved'});assert t.execute(49,{'approval_id':aid})['result']['released']
 with pytest.raises(t.SpecError):t.execute(49,{'approval_id':aid})
def test_50_immutable_audit_sequence():
 aid=t.execute(43,approval_payload())['result']['approval']['id'];t.execute(45,{'approval_id':aid,'decision':'denied'});assert [x['event'] for x in t.execute(50,{'approval_id':aid})['result']['audit']]==['created','denied']
def test_52_cosine_score():assert t.execute(52,{'profile_embedding':[1,0],'opportunity_embedding':[1,0]})['result']['match_score']==1
def test_53_logistic_impact():assert t.execute(53,{'features':{'wins':1},'coefficients':{'intercept':0,'wins':1}})['result']['expected_impact']==.731059
def test_54_persist_enriched():assert t.execute(54,{'opportunity':{'id':'o','match_score':.9,'expected_impact':.7}})['result']['persisted']['id']=='o'
def test_54_rejects_unenriched():
 with pytest.raises(t.SpecError):t.execute(54,{'opportunity':{'id':'o'}})
def test_55_strict_above_point8():assert not t.execute(55,{'match_score':.8})['result']['alert_emitted'] and t.execute(55,{'match_score':.8001})['result']['alert_emitted']
def test_56_digest_is_unsent_approval_draft():
 r=t.execute(56,{'matches':[{'id':'o'}]})['result'];assert not r['draft']['sent'] and r['approval_required']
def test_57_campaign_state():assert t.execute(57,{'goal':'find supervisor'})['result']['campaign']['status']=='draft'
def test_58_keyword_discovery():
 r=t.execute(58,{'keywords':['spatial'],'professors':[{'id':'a','keywords':['spatial']},{'id':'b','keywords':['ecology']}]})['result'];assert [x['id'] for x in r['matches']]==['a']
def test_59_impact_ranking():
 r=t.execute(59,{'professors':[{'id':'a','citation_count':10,'h_index':2},{'id':'b','citation_count':5,'h_index':1}]})['result'];assert r['ranked'][0]['id']=='a'
def test_60_grounded_personalization():assert t.execute(60,{'recent_work':{'title':'Atlas','url':'https://x'}})['result']['citation']=='https://x'
def test_60_requires_citation():
 with pytest.raises(t.SpecError):t.execute(60,{'recent_work':{'title':'x'}})
def test_61_exact_approval_delivery_contract():assert t.execute(61,{'approval_status':'approved','exact_recipient':'a@b','exact_message':'hi'})['result']['delivery_authorized']
def test_61_blocks_without_exact():
 with pytest.raises(t.SpecError):t.execute(61,{'approval_status':'approved'})
def test_62_thread_tracking_discloses_limits():
 r=t.execute(62,{'threads':[{'direction':'inbound'}]})['result'];assert r['reply_detected'] and len(r['limits'])==2
def test_63_window_validation():assert t.execute(63,{'window_days':7})['result']['configured']
def test_63_bad_window():
 with pytest.raises(t.SpecError):t.execute(63,{'window_days':0})
def test_64_followup_queue():assert t.execute(64,{'reply_detected':False})['result']['queued_for_approval']
def test_64_no_followup_after_reply():
 with pytest.raises(t.SpecError):t.execute(64,{'reply_detected':True})
def test_65_brief_intake():assert t.execute(65,{'goal':'update','audience':'students','platforms':['instagram'],'facts':['won']})['result']['brief']['facts']==['won']
def test_65_required_fields():
 with pytest.raises(t.SpecError):t.execute(65,{'goal':'x'})
def test_66_platform_strategy():
 r=t.execute(66,{'platforms':['Instagram','TikTok','Twitter']})['result'];assert [x['format'] for x in r['strategy']]==['carousel','60s_video_script','thread'] and not r['scheduled']
def test_all_source_mapping_preserved():
 for i,(rid,req,a,b) in t.ROWS.items():
  assert t.mapped(i,{})['source_mapping']=={'document':'technical-spec-line-by-line','line_start':a,'line_end':b} and t.mapped(i,{})['requirement_id']==rid
def test_exact_range_catalog():assert set(t.ROWS)==set(range(34,67))
def test_mounted_route():assert TestClient(app).post('/api/v1/technical-spec-34-66/52',json={'profile_embedding':[1,0],'opportunity_embedding':[1,0]}).status_code==200
def test_unknown_route():assert TestClient(app).post('/api/v1/technical-spec-34-66/33',json={}).status_code==422
def test_catalog_33():assert len(TestClient(app).get('/api/v1/technical-spec-34-66').json())==33
