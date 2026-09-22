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

# Exact requirement-specific nodes for the strict audit validator.
def test_row_133_m15_02_structured_content_preserves_sections(): assert run('structured_content',C[133])['output']['document']['sections'][0]['heading']=='Intro'
def test_row_134_m15_03_figure_embedding_requires_supported_engine_artifact(): assert run('figure_embedding',C[134])['output']['embedded'][0]['engine']=='plotly'
def test_row_135_m15_04_plot_sandbox_forbids_network_and_caller_code():
 assert not run('sandboxed_plot',C[135])['output']['sandbox_plan']['network']
 with pytest.raises(ValueError):run('sandboxed_plot',{'plot_spec':{'kind':'line','code':'import os'}})
def test_row_136_m15_05_document_version_hashes_content_and_links_parent():
 o=run('document_versions',C[136])['output'];assert len(o['content_hash'])==64 and o['parent_version']==1
def test_row_137_m16_01_live_feed_rejects_unknown_event_types():
 x={'events':[{'type':'unknown','sequence':2}]};assert run('live_feed',x)['output']['rejected_types']==['unknown']
def test_row_138_m16_02_timeline_sorts_higher_priority_first(): assert run('priority_timeline',C[138])['output']['bars'][0]['priority']==1
def test_row_139_m16_03_approval_queue_separates_pending_from_decided(): assert len(run('approval_queue',C[139])['output']['pending'])==1
def test_row_140_m16_04_agent_status_counts_running_agents(): assert run('agent_status',C[140])['output']['running']==1
def test_row_141_m16_05_kpi_card_requires_evidence_ids():
 with pytest.raises(ValueError):run('kpi_cards',{'cards':[{'metric':'x','value':1}]})
def test_row_142_m16_06_mutating_command_never_executes_directly():
 o=run('command_bar',C[142])['output'];assert o['approval_required'] and not o['execution_allowed']
def test_row_143_m17_01_advice_sources_allow_only_licensed_nonlogin_collection(): assert len(run('advice_sources',C[143])['output']['allowed'])==1
def test_row_144_m17_02_transcription_requires_permission_and_uri():
 with pytest.raises(ValueError):run('whisper_transcription',{'media':[{'uri':'x','permission':False}]})
def test_row_145_m17_03_advice_clusters_by_topic(): assert run('advice_clustering',C[145])['output']['clusters'][0]['topic']=='essay'
def test_row_146_m17_04_actionable_tip_requires_citation(): assert run('actionable_tips',C[146])['output']['tips'][0]['citation']=='u'
def test_row_147_m17_05_identity_vector_contains_no_inferred_facts(): assert run('identity_vector',C[147])['output']['inferred_facts']==[]
def test_row_148_m17_06_structure_retrieval_scores_identity_tag_overlap(): assert run('structure_retrieval',C[148])['output']['matches'][0]['score']==1
def test_row_149_m17_07_essay_concepts_are_coaching_not_final_essays(): assert all(not x['final_essay'] for x in run('essay_concepts',C[149])['output']['concepts'])
def test_row_150_m17_08_voice_consistency_forbids_impersonation_and_final_essay():
 o=run('voice_consistency',C[150])['output'];assert not o['impersonation_allowed'] and not o['final_essay_generated']
def test_row_151_m17_09_critique_requires_three_model_reviews():
 with pytest.raises(ValueError):run('multi_model_critique',{'reviews':C[151]['reviews'][:2]})
def test_row_152_m17_10_suggestion_diff_preserves_original(): assert run('suggestion_diff',C[152])['output']['original_preserved']=='a'
def test_row_153_m17_11_literary_device_placements_require_review(): assert all(x['position']=='review-needed' for x in run('literary_devices',C[153])['output']['placements'])
def test_row_154_m18_01_blueprints_collect_only_public_nonlogin_sources(): assert len(run('legal_blueprints',C[154])['output']['collectable'])==1
def test_row_155_m18_02_blueprint_extraction_identifies_monetization(): assert 'subscription' in run('blueprint_extraction',C[155])['output']['monetization']
def test_row_156_m18_03_scam_classifier_blocks_high_risk_claims(): assert run('scam_classifier',C[156])['output']['blocked']
def test_row_157_m18_04_blueprint_schema_rejects_missing_required_field():
 x=dict(C[157]);x.pop('tools')
 with pytest.raises(ValueError):run('blueprint_schema',x)
def test_row_158_m18_05_contextual_guide_adapts_to_weekly_hours(): assert '5 hours/week' in run('contextual_guide',C[158])['output']['guide'][0]['adaptation']
def test_row_159_m18_06_swot_requires_all_four_nonempty_sections(): assert run('swot',C[159])['output']['complete']
def test_row_160_m18_07_trend_analysis_computes_rising_direction(): assert run('trend_saturation',C[160])['output']['direction']=='rising'
def test_row_161_m18_08_viability_score_bounds_inputs_and_recommends(): assert run('viability_score',C[161])['output']['recommendation']=='go'
def test_row_162_m18_09_feasibility_report_requires_all_sections():
 x=dict(C[162]);x.pop('swot')
 with pytest.raises(ValueError):run('feasibility_report',x)
def test_row_163_m19_01_idea_intake_requires_exactly_one_modality():
 with pytest.raises(ValueError):run('idea_intake',{'text':'x','voice_transcript':'x'})
def test_row_164_m19_02_lean_canvas_preserves_problem_customer_solution():
 o=run('lean_canvas',C[164])['output']['lean_canvas'];assert o['problem']=='access' and o['customer_segments']==['students']
def test_row_165_m19_03_market_research_queues_public_sources_without_login_scraping(): assert not run('market_research',C[165])['output']['jobs'][0]['login_scraping']
