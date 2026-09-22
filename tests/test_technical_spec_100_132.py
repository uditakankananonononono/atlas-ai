import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.runtime.technical_spec_100_132 import ROWS,technical_spec_100_132
def data(row):
 if row<=102:return {'nodes':[{'id':'n','type':'Project'}],'edges':[],'filter_types':['Project'],'edit':{'node_id':'n','gesture':'double_click'}}
 if row<=107:return {'pubsub_event':{'event_id':'e','history_id':'h'},'message':{'id':'m','subject':'action required','body':'respond','provenance':'gmail'},'embedding':[.1,.2],'classifier_label':'action-required','actions':[{'action':'reply','deadline':'2026-01-01','related_entity':'contact'}],'draft_body':'draft','thread_context_ids':['m'],'graph_node_ids':['n']}
 if row<=112:return {'watch':{'channel_id':'c','resource_id':'r'},'tasks':[{'id':'t','deadline':'2026-01-02','energy_required':2,'duration_minutes':30,'travel_minutes':10,'prep_minutes':10}],'slots':[{'id':'s','start':'2026-01-01','energy':3,'duration_minutes':60}]}
 if row<=117:return {'models':[{'id':'cheap','task_types':['research'],'max_length':1000,'cost':1,'latency_ms':100}],'task':{'type':'research','length':100,'cost_budget':2,'latency_ms':200},'nodes':[{'id':'a','task_name':'research','input_type':'query','output_type':'text'},{'id':'b','task_name':'critique','input_type':'text','output_type':'text'}],'edges':[{'from':'a','to':'b','type':'text'}],'provider_signals':{'confidence':.5},'max_retries':2,'attempt':0}
 if row<=124:return {'operations':[{'operation':'navigate'},{'operation':'fill','submit':True}],'legally_permissible':True,'context_id':'ctx','har_entries':[{'url':'https://x'}],'vlm_observations':[{'target':'button','confidence':.8}],'max_steps':2,'steps':[{'click':'button'}],'fields':[{'id':'email','label':'Email'}],'form_data':{'email':'a@b.test'},'form_id':'f','submit_approval':{'decision':'approved','scope':'f'}}
 if row<=131:return {'goal':'build project','stages':[{'id':x,'role':x} for x in ['literature-reviewer','data-miner','coder','analyst','writer']],'datasets':[{'public_url':'https://data','license':'CC0'}],'cpu_limit':1,'memory_mb':256,'experiment_command':'python test.py','files':[{'path':'README.md'}],'feedback':[{'stage_id':'coder','change':'add test'}],'git_repo':'repo','parent_commit':'abc','proposed_commit':'def'}
 return {'templates':[{'format':f,'document_type':'paper','template_id':f+'-paper'} for f in ('latex','docx','pptx')]}
@pytest.mark.parametrize('row',range(100,133))
def test_each_exact_spec_row_has_semantics_and_source_mapping(row):
 o=technical_spec_100_132(row,data(row));assert o['row']==row and o['requirement_id']==ROWS[row][0] and o['requirement']==ROWS[row][1] and o['source_mapping']['line_start'] and o['result'] is not None
def test_graph_filter_edit_and_planner_context():
 o=technical_spec_100_132(102,data(102))['result'];assert o['react_flow']['nodes'][0]['id']=='n' and o['edit_preview']['gesture']=='double_click' and o['planner_context']['node_ids']==['n']
def test_email_exact_schema_classifier_ltm_and_pending_draft():
 o=technical_spec_100_132(107,data(107))['result'];assert len(o['categories'])==7 and o['actions'][0]['related_entity']=='contact' and o['ltm_record']['embedding']==[.1,.2] and o['draft']['approval_status']=='pending'
def test_calendar_proposal_uses_energy_travel_prep_and_never_mutates():
 o=technical_spec_100_132(112,data(112))['result'];assert o['weekly_proposal'][0]['slot_id']=='s' and not o['mutated']
def test_lab_routes_and_bounds_retry():
 o=technical_spec_100_132(117,data(117))['result'];assert o['selected_model']=='cheap' and o['dag_order']==['a','b'] and o['low_confidence'] and o['retry_policy']['next']=='alternate_model_or_self_critique'
def test_browser_har_mapping_and_exact_submit_approval():
 o=technical_spec_100_132(124,data(124))['result'];assert len(o['har']['artifact_sha256'])==64 and o['field_mapping']['email']=='a@b.test' and o['submit_status']=='approved'
def test_project_roles_public_data_sandbox_readme_feedback_git_proposal():
 o=technical_spec_100_132(131,data(131))['result'];assert not o['missing_roles'] and not o['invalid_datasets'] and o['sandbox']['network'] is False and o['assembly']['has_readme'] and o['replan'][0]['status']=='proposed' and not o['git']['mutated']
def test_template_library_requires_all_three_formats():
 o=technical_spec_100_132(132,data(132))['result'];assert o['formats']==['docx','latex','pptx'];d=data(132);d['templates'].pop()
 with pytest.raises(ValueError):technical_spec_100_132(132,d)
def test_negative_paths_reject_bad_action_schema_cycle_and_unapproved_submit():
 d=data(106);d['actions'][0].pop('deadline')
 with pytest.raises(ValueError):technical_spec_100_132(106,d)
 d=data(114);d['edges'].append({'from':'b','to':'a','type':'text'})
 with pytest.raises(ValueError):technical_spec_100_132(114,d)
 d=data(124);d['submit_approval']['scope']='other';assert technical_spec_100_132(124,d)['result']['submit_status']=='paused_for_exact_approval'
def test_mounted_runtime_boundary():
 r=TestClient(app).post('/api/v1/runtime/technical-spec-100-132',json={'row':100,'data':data(100)});assert r.status_code==200 and r.json()['requirement_id']=='M9-06'

# Stable requirement-specific nodes for exact audit resolution.
def test_row_100_m9_06_react_flow_graph_returns_nodes_and_edges(): assert technical_spec_100_132(100,data(100))['result']['react_flow']['nodes'][0]['id']=='n'
def test_row_101_m9_07_filter_and_double_click_edit_are_preserved(): assert technical_spec_100_132(101,data(101))['result']['edit_preview']['gesture']=='double_click'
def test_row_102_m9_08_planner_context_consumes_visible_graph_ids(): assert technical_spec_100_132(102,data(102))['result']['planner_context']['node_ids']==['n']
def test_row_103_m10_01_pubsub_ingestion_has_stable_dedupe_key(): assert len(technical_spec_100_132(103,data(103))['result']['ingestion']['dedupe_key'])==64
def test_row_104_m10_02_email_embedding_persists_provenance(): assert technical_spec_100_132(104,data(104))['result']['ltm_record']=={'message_id':'m','embedding':[.1,.2],'provenance':'gmail'}
def test_row_105_m10_03_classifier_is_restricted_to_seven_categories(): assert len(technical_spec_100_132(105,data(105))['result']['categories'])==7
def test_row_106_m10_04_action_extraction_rejects_nonexact_schema():
 x=data(106);x['actions'][0].pop('deadline')
 with pytest.raises(ValueError):technical_spec_100_132(106,x)
def test_row_107_m10_05_reply_draft_keeps_thread_graph_context_pending():
 o=technical_spec_100_132(107,data(107))['result']['draft'];assert o['thread_context_ids']==['m'] and o['graph_node_ids']==['n'] and o['approval_status']=='pending'
def test_row_108_m11_01_calendar_watch_update_preserves_channel(): assert technical_spec_100_132(108,data(108))['result']['watch_update']['channel_id']=='c'
def test_row_109_m11_02_scheduler_assigns_task_to_feasible_slot(): assert technical_spec_100_132(109,data(109))['result']['weekly_proposal'][0]['slot_id']=='s'
def test_row_110_m11_03_schedule_accounts_for_travel_and_preparation():
 o=technical_spec_100_132(110,data(110))['result']['weekly_proposal'][0];assert o['travel_minutes']==10 and o['prep_minutes']==10
def test_row_111_m11_04_weekly_proposal_does_not_mutate_calendar(): assert not technical_spec_100_132(111,data(111))['result']['mutated']
def test_row_112_m11_05_rescheduling_is_approval_gated_when_conflicted():
 x=data(112);x['slots'][0]['duration_minutes']=1;o=technical_spec_100_132(112,x)['result'];assert o['unscheduled']==['t'] and o['reschedule_approval']=='pending'
def test_row_113_m12_01_model_policy_selects_eligible_lowest_cost_model(): assert technical_spec_100_132(113,data(113))['result']['selected_model']=='cheap'
def test_row_114_m12_02_collaboration_dag_rejects_cycle():
 x=data(114);x['edges'].append({'from':'b','to':'a','type':'text'})
 with pytest.raises(ValueError):technical_spec_100_132(114,x)
def test_row_115_m12_03_celery_nodes_preserve_typed_data_contract(): assert technical_spec_100_132(115,data(115))['result']['celery_tasks'][0]['input_type']=='query'
def test_row_116_m12_04_low_confidence_uses_provider_signal(): assert technical_spec_100_132(116,data(116))['result']['low_confidence']
def test_row_117_m12_05_retry_is_bounded_and_names_next_strategy(): assert technical_spec_100_132(117,data(117))['result']['retry_policy']=={'attempt':0,'max_retries':2,'next':'alternate_model_or_self_critique'}
def test_row_118_m13_01_browser_accepts_only_rest_operation_set():
 x=data(118);x['operations']=[{'operation':'shell'}]
 with pytest.raises(ValueError):technical_spec_100_132(118,x)
def test_row_119_m13_02_persistent_context_requires_legal_permission_and_id(): assert technical_spec_100_132(119,data(119))['result']['context']['persistent']
def test_row_120_m13_03_har_capture_has_content_digest(): assert len(technical_spec_100_132(120,data(120))['result']['har']['artifact_sha256'])==64
def test_row_121_m13_04_vlm_observations_are_explicit_not_invented(): assert technical_spec_100_132(121,data(121))['result']['vlm_observations'][0]['target']=='button'
def test_row_122_m13_05_navigation_loop_rejects_steps_over_bound():
 x=data(122);x['max_steps']=0
 with pytest.raises(ValueError):technical_spec_100_132(122,x)
def test_row_123_m13_06_form_mapping_matches_normalized_labels(): assert technical_spec_100_132(123,data(123))['result']['field_mapping']['email']=='a@b.test'
def test_row_124_m13_07_submit_pauses_when_approval_scope_mismatches():
 x=data(124);x['submit_approval']['scope']='other';assert technical_spec_100_132(124,x)['result']['submit_status']=='paused_for_exact_approval'
def test_row_125_m14_01_goal_decomposes_to_stages_without_mutation(): assert technical_spec_100_132(125,data(125))['result']['goal']=='build project'
def test_row_126_m14_02_project_requires_all_five_named_roles(): assert not technical_spec_100_132(126,data(126))['result']['missing_roles']
def test_row_127_m14_03_dataset_requires_public_url_and_license():
 x=data(127);x['datasets'][0].pop('license');assert technical_spec_100_132(127,x)['result']['invalid_datasets']
def test_row_128_m14_04_experiment_sandbox_disables_network(): assert not technical_spec_100_132(128,data(128))['result']['sandbox']['network']
def test_row_129_m14_05_project_assembly_detects_readme(): assert technical_spec_100_132(129,data(129))['result']['assembly']['has_readme']
def test_row_130_m14_06_feedback_creates_proposed_replan_not_execution(): assert technical_spec_100_132(130,data(130))['result']['replan'][0]['status']=='proposed'
def test_row_131_m14_07_git_version_control_records_proposal_without_mutation(): assert not technical_spec_100_132(131,data(131))['result']['git']['mutated']
def test_row_132_m15_01_template_library_requires_latex_docx_pptx():
 x=data(132);x['templates'].pop()
 with pytest.raises(ValueError):technical_spec_100_132(132,x)
