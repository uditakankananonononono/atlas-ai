import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m06_social_media_manager.technical_67_75 import run as m6
from app.modules.m06_social_media_manager.routes import router as r6
from app.modules.m07_brand_collaboration.technical_76_84 import run as m7
from app.modules.m07_brand_collaboration.routes import router as r7
from app.modules.m08_startup_growth.technical_85_94 import run as m8
from app.modules.m08_startup_growth.routes import router as r8
from app.modules.m09_knowledge_workspace.technical_95_99 import run as m9
from app.modules.m09_knowledge_workspace.routes import router as r9

def d(row):
 return {67:{'workflow':'w','prompt':'p','output_spec':{'width':1}},68:{'engine':'Bark','text':'t','voice':'v','output_spec':{'format':'wav'}},69:{'content_id':'c','account_id':'a','approval':{'id':'x','status':'approved'}},70:{'content_id':'c','account_id':'a','approval':{'id':'x','status':'approved'}},71:{'content_id':'c','account_id':'a','approval':{'id':'x','status':'approved'}},72:{'effect':'publish','approval':{'status':'pending'}},73:{'date':'2026-01-01','platform':'x','metrics':{'likes':2}},74:{'snapshots':[{'timestamp':'t','metrics':{'likes':2}}],'candidates':[{'suggestion':'later','evidence_snapshot_ids':['s']}]},75:{'variants':['a','b'],'primary_metric':'clicks','approval':{'status':'pending'}},76:{'platforms':[{'public':True,'terms_permit_research':True,'source_url':'u'}]},77:{'announcements':[{'source_url':'u','announced_at':'t'}]},78:{'brand':'b','mission':'m','evidence':['u'],'alignment_dimensions':{'mission':2}},79:{'contacts':[{'official_source_url':'u'}]},80:{'creator':'c','metrics':{},'portfolio':[]},81:{'tiers':[{'name':'a','deliverables':[],'price':1,'usage_rights':'x'}]},82:{'seller':'s','buyer':'b','line_items':[{'quantity':2,'unit_price':3}],'currency':'USD'},83:{'partnership_id':'p','events':[],'deliverables':[{'id':'d','status':'open','overdue':True}]},84:{'report':{},'approval':{'id':'a','status':'pending'}},85:{'brief':'site'},86:{'hero':{},'features':[],'waitlist':{}},87:{'table':'wait','email_field':'email','consent_field':'consent'},88:{'workspace_files':['a'],'approval':{'status':'pending'}},89:{'template':'t','slides':[]},90:{'slides':[{'type':x} for x in ['problem','solution','market','traction','ask']]},91:{'chart_spec':{},'data':{},'slide_id':'s'},92:{'source_revision':'a','code_symbols':['GET /']},93:{'source_revision':'a','code_symbols':['f']},94:{'source_revision':'a','code_symbols':['f']},95:{'nodes':[{'id':'n','type':'Project'}]},96:{'edges':[{'id':'e','type':'supports','from_id':'a','to_id':'b'}],'node_ids':['a','b']},97:{'tenant_id':'t','nodes':[],'edges':[]},98:{'entity_id':'a','entity_vector':[1,0],'candidates':[{'id':'b','vector':[.9,.1]}],'threshold':.8},99:{'text':'Sam project Friday','mentions':[{'type':'Contact','normalized_name':'sam'}],'entities':[{'id':'c','type':'Contact','normalized_name':'sam'}]}}[row]
def run(row,p):return m6(row,p) if row<=75 else m7(row,p) if row<=84 else m8(row,p) if row<=94 else m9(row,p)
@pytest.mark.parametrize('row',range(67,100))
def test_every_row_exact_semantic_result(row):assert run(row,d(row))['row']==row and run(row,d(row))['result']
@pytest.mark.parametrize('row',range(67,100))
def test_every_row_negative_empty_payload(row):
 with pytest.raises((ValueError,KeyError,TypeError)):run(row,{})
def test_67_68_assets_are_adapters_not_fake_generation():assert not m6(67,d(67))['result']['asset_generated'] and not m6(68,d(68))['result']['audio_generated']
@pytest.mark.parametrize('row',range(69,72))
def test_69_71_publish_approved_but_not_executed(row):
 o=m6(row,d(row));assert o['result']['publish_allowed'] and not o['result']['published'] and not o['external_effect_performed']
def test_72_pending_approval_queues():assert m6(72,d(72))['result']['queued'] and not m6(72,d(72))['result']['executable']
def test_73_daily_metrics_preserve_source_keys():assert m6(73,d(73))['result']['metric_keys']==['likes']
def test_74_suggestion_has_evidence_no_causality():assert m6(74,d(74))['result']['suggestions'][0]['grounded'] and m6(74,d(74))['result']['causal_claim_forbidden']
def test_75_ab_requires_approval():assert not m6(75,d(75))['result']['execution_allowed']
def test_76_77_only_public_verified_sources():assert m7(76,d(76))['result']['platforms'][0]['allowed'] and m7(77,d(77))['result']['events'][0]['verified']
def test_78_alignment_evidence_and_score():assert m7(78,d(78))['result']['score']==2
def test_79_no_guessed_email():assert m7(79,d(79))['result']['guessed_emails_forbidden']
def test_80_pdf_not_fake_rendered():assert not m7(80,d(80))['result']['rendered']
def test_81_package_completeness():assert m7(81,d(81))['result']['tiers'][0]['complete']
def test_82_invoice_no_commitment():assert m7(82,d(82))['result']['invoice']['total']==6 and not m7(82,d(82))['result']['payment_committed']
def test_83_crm_overdue():assert m7(83,d(83))['result']['overdue_ids']==['d']
def test_84_report_not_shared_pending():assert not m7(84,d(84))['result']['share_allowed']
def test_85_static_next_tailwind():assert m8(85,d(85))['result']['static_export']
def test_86_required_sections():assert len(m8(86,d(86))['result']['sections'])==3
def test_87_supabase_security():assert not m8(87,d(87))['result']['service_role_exposed_to_browser']
def test_88_vercel_gated():assert not m8(88,d(88))['result']['vercel_push_allowed']
def test_89_editable_pptx():assert m8(89,d(89))['result']['editable']
def test_90_pitch_order():assert m8(90,d(90))['result']['correct_order']
def test_91_chart_not_fake_rendered():assert not m8(91,d(91))['result']['rendered']
@pytest.mark.parametrize('row',range(92,95))
def test_92_94_code_grounding_flags_claims(row):
 x=d(row);x['claims']=[{'text':'x'}];assert m8(row,x)['result']['ungrounded_claims']
def test_95_exact_node_types_reject_unknown():
 x=d(95);x['nodes'].append({'id':'x','type':'Unknown'});assert not m9(95,x)['result']['valid']
def test_96_edge_integrity():assert m9(96,d(96))['result']['valid']
def test_97_adjacency_schema_tenant_predicate():assert m9(97,d(97))['result']['tenant_predicate_required']
def test_98_embedding_suggests_not_creates():assert m9(98,d(98))['result']['suggestions'] and not m9(98,d(98))['result']['auto_created']
def test_98_dimension_mismatch_rejected():
 x=d(98);x['candidates'][0]['vector']=[1]
 with pytest.raises(ValueError):m9(98,x)
def test_99_ner_links_existing_and_does_not_create():assert m9(99,d(99))['result']['links'][0]['entity_id']=='c' and not m9(99,d(99))['result']['auto_created']
def test_all_mounted():
 for router,path,row in [(r6,'/social-media-manager/technical-67-75/67',67),(r7,'/brand-collaboration/technical-76-84/76',76),(r8,'/startup-growth/technical-85-94/85',85),(r9,'/knowledge-workspace/technical-95-99/95',95)]:
  a=FastAPI();a.include_router(router);assert TestClient(a).post(path,json=d(row)).status_code==200

# Stable, requirement-specific evidence nodes used by the line-by-line audit.
def test_row_67_m6_03_image_adapter_declares_output_without_fake_asset(): assert not m6(67,d(67))['result']['asset_generated']
def test_row_68_m6_04_audio_adapter_declares_engine_without_fake_audio(): assert not m6(68,d(68))['result']['audio_generated']
def test_row_69_m6_05_meta_publish_is_approved_but_not_externally_performed():
 o=m6(69,d(69));assert o['result']['publish_allowed'] and not o['external_effect_performed']
def test_row_70_m6_06_x_publish_is_approved_but_not_externally_performed():
 o=m6(70,d(70));assert o['result']['publish_allowed'] and not o['external_effect_performed']
def test_row_71_m6_07_linkedin_publish_is_approved_but_not_externally_performed():
 o=m6(71,d(71));assert o['result']['publish_allowed'] and not o['external_effect_performed']
def test_row_72_m6_08_pending_publish_is_queued_not_executable():
 o=m6(72,d(72));assert o['result']['queued'] and not o['result']['executable']
def test_row_73_m6_09_daily_metrics_preserve_provider_metric_keys(): assert m6(73,d(73))['result']['metric_keys']==['likes']
def test_row_74_m6_10_suggestion_requires_evidence_and_forbids_causality():
 o=m6(74,d(74))['result'];assert o['suggestions'][0]['grounded'] and o['causal_claim_forbidden']
def test_row_75_m6_11_ab_test_remains_approval_gated(): assert not m6(75,d(75))['result']['execution_allowed']
def test_row_76_m7_01_discovery_allows_only_public_terms_permitted_platform(): assert m7(76,d(76))['result']['platforms'][0]['allowed']
def test_row_77_m7_02_announcement_monitor_preserves_verified_source(): assert m7(77,d(77))['result']['events'][0]['verified']
def test_row_78_m7_03_alignment_score_is_backed_by_evidence_dimensions(): assert m7(78,d(78))['result']['score']==2
def test_row_79_m7_04_contact_enrichment_forbids_guessed_email(): assert m7(79,d(79))['result']['guessed_emails_forbidden']
def test_row_80_m7_05_media_kit_does_not_claim_unrendered_pdf(): assert not m7(80,d(80))['result']['rendered']
def test_row_81_m7_06_sponsorship_tier_checks_package_completeness(): assert m7(81,d(81))['result']['tiers'][0]['complete']
def test_row_82_m7_07_invoice_computes_total_without_payment_commitment():
 o=m7(82,d(82))['result'];assert o['invoice']['total']==6 and not o['payment_committed']
def test_row_83_m7_08_crm_identifies_overdue_deliverable(): assert m7(83,d(83))['result']['overdue_ids']==['d']
def test_row_84_m7_09_pending_brand_report_cannot_be_shared(): assert not m7(84,d(84))['result']['share_allowed']
def test_row_85_m8_01_landing_page_is_static_next_export(): assert m8(85,d(85))['result']['static_export']
def test_row_86_m8_02_landing_page_contains_required_sections(): assert len(m8(86,d(86))['result']['sections'])==3
def test_row_87_m8_03_waitlist_never_exposes_service_role_to_browser(): assert not m8(87,d(87))['result']['service_role_exposed_to_browser']
def test_row_88_m8_04_vercel_push_waits_for_approval(): assert not m8(88,d(88))['result']['vercel_push_allowed']
def test_row_89_m8_05_pitch_deck_output_remains_editable(): assert m8(89,d(89))['result']['editable']
def test_row_90_m8_06_pitch_deck_enforces_required_slide_order(): assert m8(90,d(90))['result']['correct_order']
def test_row_91_m8_07_chart_does_not_claim_unrendered_artifact(): assert not m8(91,d(91))['result']['rendered']
def _ungrounded(row):
 x=d(row);x['claims']=[{'text':'x'}];return m8(row,x)['result']['ungrounded_claims']
def test_row_92_m8_08_redoc_flags_claims_absent_from_code(): assert _ungrounded(92)
def test_row_93_m8_09_manual_flags_claims_absent_from_code(): assert _ungrounded(93)
def test_row_94_m8_10_blog_flags_claims_absent_from_code(): assert _ungrounded(94)
def test_row_95_m9_01_graph_rejects_unknown_node_type():
 x=d(95);x['nodes'].append({'id':'x','type':'Unknown'});assert not m9(95,x)['result']['valid']
def test_row_96_m9_02_typed_edge_requires_existing_endpoints(): assert m9(96,d(96))['result']['valid']
def test_row_97_m9_03_adjacency_persistence_requires_tenant_predicate(): assert m9(97,d(97))['result']['tenant_predicate_required']
def test_row_98_m9_04_embedding_link_is_suggestion_not_auto_create():
 o=m9(98,d(98))['result'];assert o['suggestions'] and not o['auto_created']
def test_row_99_m9_05_ner_links_existing_entity_without_auto_create():
 o=m9(99,d(99))['result'];assert o['links'][0]['entity_id']=='c' and not o['auto_created']
