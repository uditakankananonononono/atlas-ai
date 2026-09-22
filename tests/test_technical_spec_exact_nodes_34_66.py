"""Exact ledger nodes for rows 34-66, layered over the substantive behavior suite."""
import pytest
from app import technical_spec_34_66 as t

@pytest.fixture(autouse=True)
def reset(): t.reset()

def test_row_34_a34_hybrid_retrieval_combines_semantic_keyword_and_metadata():
 r=t.execute(34,{'query':'biology grant','query_vector':[1,0],'filters':{'kind':'grant'},'items':[{'id':'a','text':'biology grant','embedding':[1,0],'metadata':{'kind':'grant'}},{'id':'b','text':'biology','embedding':[0,1],'metadata':{'kind':'grant'}},{'id':'c','text':'biology grant','embedding':[1,0],'metadata':{'kind':'job'}}]})['result'];assert [x['id'] for x in r['ranked']]==['a','b']
def test_row_35_a35_typed_graph_rejects_untyped_edge():
 with pytest.raises(t.SpecError):t.execute(35,{'edges':[{'from':'a','to':'b'}]})
@pytest.mark.parametrize('row',[36,37])
def _planner(row): return t.execute(row,{'goal':'apply','effort':{'task':3},'tools':{'task':['browser']},'deadlines':{'task':'2026-10-01'}})['result']
def test_row_36_a36_recursive_planner_emits_four_node_levels(): assert [x['type'] for x in _planner(36)['nodes']]==['objective','milestone','task','subtask']
def test_row_37_a37_planner_assigns_effort_deadline_and_tools(): assert _planner(37)['nodes'][2]['effort']==3 and _planner(37)['nodes'][2]['tools']==['browser']
def test_row_38_a38_memory_update_triggers_refinement(): assert t.execute(38,{'plan_id':'p','plan':{'goal':'g'},'memory_id':'m'})['result']['refined_from_memory']
def test_row_39_a39_json_plan_versions_increment(): assert t.execute(39,{'plan_id':'p','plan':{'x':1}})['result']['version']==1 and t.execute(39,{'plan_id':'p','plan':{'x':2}})['result']['version']==2
def test_row_40_a40_policy_routes_task_or_fails_closed():
 assert t.execute(40,{'task_type':'code','policy':{'code':'deepseek'}})['result']['selected_model']=='deepseek'
 with pytest.raises(t.SpecError):t.execute(40,{'task_type':'x','policy':{}})
def test_row_41_a41_chain_requires_exact_research_draft_critique_format_order():
 c=[{'stage':x,'model':x,'output':x} for x in ['research','draft','critique','format']];assert t.execute(41,{'input':'q','chain':c})['result']['final']=='format'
def test_row_42_a42_recursive_merge_preserves_nested_values_and_dedupes_lists(): assert t.execute(42,{'results':[{'a':{'x':1},'tags':['a']},{'a':{'y':2},'tags':['a','b']}]})['result']['merged']=={'a':{'x':1,'y':2},'tags':['a','b']}
def ap():return {'user_id':'u','module':5,'action_type':'send','payload':{'to':'x'},'continuation_token':'token'}
def test_row_43_m0_01_approval_service_publishes_boundary_event(): assert t.execute(43,ap())['result']['published_event']['type']=='approval_request'
def test_row_44_m0_02_approval_request_persists_required_fields():
 a=t.execute(44,ap())['result']['approval'];assert {'id','user_id','module','action_type','payload','status','created_at'}<=set(a)
def test_row_45_m0_03_state_machine_rejects_second_decision():
 a=t.execute(43,ap())['result']['approval']['id'];t.execute(45,{'approval_id':a,'decision':'denied'})
 with pytest.raises(t.SpecError):t.execute(45,{'approval_id':a,'decision':'approved'})
def test_row_46_m0_04_approval_event_and_request_are_both_persisted():
 r=t.execute(46,ap())['result'];assert r['approval']['id']==r['published_event']['approval_id']
def test_row_47_m0_05_pending_request_has_dashboard_sse_event(): assert t.execute(47,ap())['result']['published_event']['type']=='approval_request'
def test_row_48_m0_06_worker_suspends_without_serialized_callback():
 r=t.execute(48,ap())['result'];assert r['worker_state']=='suspended' and not r['serialized_callback']
def test_row_49_m0_07_continuation_release_is_single_use():
 a=t.execute(43,ap())['result']['approval']['id'];t.execute(45,{'approval_id':a,'decision':'approved'});assert t.execute(49,{'approval_id':a})['result']['released']
 with pytest.raises(t.SpecError):t.execute(49,{'approval_id':a})
def test_row_50_m0_08_decision_audit_is_append_only_sequence():
 a=t.execute(43,ap())['result']['approval']['id'];t.execute(45,{'approval_id':a,'decision':'denied'});assert [x['event'] for x in t.execute(50,{'approval_id':a})['result']['audit']]==['created','denied']
def test_row_51_m0_09_effectful_module_uses_shared_approval_sdk(): assert t.execute(51,ap())['result']['sdk']=='request_approval'
def test_row_52_m1_01_cosine_match_score_exact(): assert t.execute(52,{'profile_embedding':[1,0],'opportunity_embedding':[1,0]})['result']['match_score']==1
def test_row_53_m1_02_expected_impact_uses_logistic_score(): assert t.execute(53,{'features':{'wins':1},'coefficients':{'intercept':0,'wins':1}})['result']['expected_impact']==.731059
def test_row_54_m1_03_rejects_unenriched_opportunity_persistence():
 with pytest.raises(t.SpecError):t.execute(54,{'opportunity':{'id':'o'}})
def test_row_55_m1_04_match_alert_threshold_is_strictly_above_point_eight(): assert not t.execute(55,{'match_score':.8})['result']['alert_emitted'] and t.execute(55,{'match_score':.8001})['result']['alert_emitted']
def test_row_56_m1_05_daily_digest_is_unsent_approval_draft():
 r=t.execute(56,{'matches':[{'id':'o'}]})['result'];assert not r['draft']['sent'] and r['approval_required']
def test_row_57_m5_01_campaign_intake_starts_in_draft_state(): assert t.execute(57,{'goal':'find supervisor'})['result']['campaign']['status']=='draft'
def test_row_58_m5_02_professor_discovery_matches_campaign_keywords(): assert [x['id'] for x in t.execute(58,{'keywords':['spatial'],'professors':[{'id':'a','keywords':['spatial']},{'id':'b','keywords':['ecology']}]})['result']['matches']]==['a']
def test_row_59_m5_03_professor_impact_ranking_uses_publication_metrics(): assert t.execute(59,{'professors':[{'id':'a','citation_count':10,'h_index':2},{'id':'b','citation_count':5,'h_index':1}]})['result']['ranked'][0]['id']=='a'
def test_row_60_m5_04_personalization_requires_recent_work_citation():
 with pytest.raises(t.SpecError):t.execute(60,{'recent_work':{'title':'x'}})
def test_row_61_m5_05_delivery_requires_exact_approval_recipient_and_message():
 with pytest.raises(t.SpecError):t.execute(61,{'approval_status':'approved'})
def test_row_62_m5_06_thread_tracking_detects_reply_and_discloses_limits():
 r=t.execute(62,{'threads':[{'direction':'inbound'}]})['result'];assert r['reply_detected'] and r['limits']
def test_row_63_m5_07_no_reply_window_must_be_positive():
 with pytest.raises(t.SpecError):t.execute(63,{'window_days':0})
def test_row_64_m5_08_followup_is_blocked_after_reply_otherwise_queued():
 assert t.execute(64,{'reply_detected':False})['result']['queued_for_approval']
 with pytest.raises(t.SpecError):t.execute(64,{'reply_detected':True})
def test_row_65_m6_01_content_brief_requires_goal_audience_and_platforms():
 with pytest.raises(t.SpecError):t.execute(65,{'goal':'x'})
def test_row_66_m6_02_platform_strategy_maps_formats_without_scheduling():
 r=t.execute(66,{'platforms':['Instagram','TikTok','Twitter']})['result'];assert [x['format'] for x in r['strategy']]==['carousel','60s_video_script','thread'] and not r['scheduled']
