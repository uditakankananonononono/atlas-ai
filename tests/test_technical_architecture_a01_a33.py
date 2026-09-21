import pytest
from datetime import datetime,timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.runtime.technical_architecture_a01_a33 import *
from app.runtime.technical_architecture_routes_a01_a33 import router
def test_source_mapping_exact():assert [(x['requirement_id'],x['source_line_start']) for x in mapping()]==[(f'A{i:02}',5 if i<=6 else 6 if i<=8 else 7 if i<=11 else 8 if i<=13 else 9 if i<=15 else 10 if i<=17 else 11 if i<=20 else 12 if i<=24 else 13 if i==25 else 14 if i<=29 else 15 if i<=32 else 19) for i in range(1,34)]
def test_a01_a04_frontend_contract():
 m=FrontendContract().manifest();assert m['framework']=={'name':'Next.js','minimum_major':14,'router':'app','server_components':True};assert m['view']['minimum_major']==18;assert m['styling']['engine']=='Tailwind CSS';assert m['components']['system']=='shadcn/ui'
def test_a05_graph_validation_and_bad_edge():
 f=FrontendContract();assert f.validate_graph([{'id':'a'},{'id':'b'}],[{'source':'a','target':'b'}])['fit_view']
 with pytest.raises(ArchitectureError):f.validate_graph([{'id':'a'}],[{'source':'a','target':'x'}])
def test_a06_recharts_semantics():assert FrontendContract().chart([{'name':'x','value':1}])['aria_label']=='Dashboard metric chart'
def test_a07_backend_versions():
 m=BackendContract().manifest();assert m['python']=='>=3.12' and m['framework']=='FastAPI' and m['validation']=='Pydantic v2'
def test_a08_celery_redis_contract():assert BackendContract().task('scan',{})['result_backend']=='redis'
def test_a09_a11_data_contracts():
 m=BackendContract().manifest();assert m['database']=='PostgreSQL 16' and 'Supabase' in m['managed_targets'] and m['vector_store']=='ChromaDB'
 e=BackendContract().embedding('t','text',[.1,.2]);assert e['postgres_extension']=='vector' and e['vector_store_collection']=='ltm-t'
def test_a12_stream_ids_and_resume():
 b=EventBus();a=b.publish('events',{'x':1});b.publish('events',{'x':2});assert b.read('events',after=a['id'])==[{'id':'2-0','event':{'x':2}}]
def test_a13_rabbit_topic_binding():assert EventBus().binding('module.*','workers')['exchange_type']=='topic'
def test_a14_prompt_chain_and_missing_input():
 m=ModelOrchestrator();assert m.chain([{'name':'draft','requires':['topic'],'template':'About {topic}','output':'draft'}],{'topic':'AI'})['outputs']['draft']=='About AI'
 with pytest.raises(ArchitectureError):m.chain([{'name':'x','requires':['missing'],'template':'{missing}','output':'x'}],{})
def test_a15_model_routing_exact_catalog():
 m=ModelOrchestrator();assert m.route({'local_only':True})['model']=='llama-3.1-70b';assert set(m.MODELS)=={'openai','anthropic','gemini','deepseek','ollama'}
def test_a16_playwright_controlled_no_stealth():
 o=BrowserDocumentContract().browser();assert o['engine']=='Playwright' and not o['stealth_evasion'] and not o['credential_mass_scraping']
def test_a17_selenium_only_legacy():assert BrowserDocumentContract().browser(legacy=True)['engine']=='Selenium'
def test_a18_pymupdf():assert BrowserDocumentContract().document('application/pdf')['pipeline']==['PyMuPDF text and metadata']
def test_a19_ocr_pipeline():assert 'Tesseract OCR' in BrowserDocumentContract().document('application/pdf',scanned=True)['pipeline']
def test_a20_layout_parser():assert BrowserDocumentContract().document('text/html',layout=True)['preserve_blocks_tables_titles']
def test_a21_oauth_oidc_pkce_state_nonce():
 s=SecurityContract();assert s.oauth('google','https://app/cb','state','nonce')['pkce']
 with pytest.raises(ArchitectureError):s.oauth('google','http://app/cb','s','n')
def test_a22_jwt_lifecycle_signature_expiry():
 s=SecurityContract();issued=s.session('u','0123456789abcdef',ttl=10,now=100);assert s.verify(issued['token'],'0123456789abcdef',105)['sub']=='u'
 with pytest.raises(ArchitectureError):s.verify(issued['token'],'0123456789abcdef',111)
def test_a23_vault_never_returns_secret():assert not SecurityContract().vault_reference('secret/atlas','api_key')['secret_material_returned']
def test_a24_append_only_hash_chain_tamper_detection():
 a=AppendOnlyAudit();a.append('u','create','r');a.append('u','read','r');assert a.verify();a._events[0]['action']='tampered';assert not a.verify()
def test_a25_aware_scheduler_and_naive_rejected():
 s=SchedulerDeployment();assert s.schedule('x',datetime.now(timezone.utc),{})['scheduler']=='APScheduler'
 with pytest.raises(ArchitectureError):s.schedule('x',datetime.now(),{})
@pytest.mark.parametrize('kind,field',[('cloud_run','autoscaling'),('gke','health_probes'),('cloud_storage','signed_urls'),('cloud_sql','automated_backups')])
def test_a26_a29_deployment_targets(kind,field):assert field in SchedulerDeployment().target(kind)
def test_a30_auth_rate_limit():
 g=Gateway(limit=2);g.authorize('u',0);g.authorize('u',1)
 with pytest.raises(ArchitectureError):g.authorize('u',2)
 with pytest.raises(ArchitectureError):g.authorize('',100)
def test_a31_dispatch_to_celery():assert Gateway().dispatch('u','build',{'x':1})['queue']=='celery'
def test_a32_sse_wire_format():assert Gateway().sse('progress',{'pct':50},'1')=='id: 1\nevent: progress\ndata: {"pct":50}\n\n'
def test_a33_universal_ltm_ingest_and_hybrid_tenant_filter():
 l=UniversalLTM(lambda t:[1.0,2.0]);item=l.ingest('a',{'content':'grant research note','artifact_type':'note','source_uri':'doc://1','metadata':{'project':'p'},'origin':'generated'});l.ingest('b',{'content':'grant secret','artifact_type':'email','source_uri':'mail://1'});assert item['dense_index']=='ChromaDB' and item['metadata_store']=='PostgreSQL';assert len(l.search('a','grant',{'project':'p'}))==1 and not l.search('b','research')
 with pytest.raises(ArchitectureError):l.ingest('a',{'content':'','artifact_type':'x','source_uri':'x'})
def test_mounted_mapping_and_ltm_validation():
 app=FastAPI();app.include_router(router,prefix='/runtime');c=TestClient(app);assert len(c.get('/runtime/technical-architecture-a01-a33/mapping').json())==33;assert c.post('/runtime/technical-architecture-a01-a33/ltm/ingest',json={'tenant_id':'t','artifact':{}}).status_code==422
