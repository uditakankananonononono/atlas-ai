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
