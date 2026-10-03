"""Runtime HTTP test of own-document onboarding: paste -> status -> complete -> retrieve, offline, no paid calls."""
import os
import pytest
from sqlalchemy import create_engine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m02_competition_manager.profile_routes import router
P='/competition-manager/profile-corpus'
@pytest.fixture(autouse=True)
def isolated_db(tmp_path,monkeypatch):
    """Run against a per-test SQLite file so nothing lands in a repo-root or shared DB."""
    from app.core import database
    from app.modules.m02_competition_manager import onboarding,profile_corpus
    e=create_engine(f"sqlite:///{tmp_path/'own.db'}",connect_args={'check_same_thread':False})
    monkeypatch.setattr(onboarding,'engine',e);monkeypatch.setattr(profile_corpus,'engine',e)
    old=database.SessionLocal.kw.get('bind');database.SessionLocal.configure(bind=e)
    database.Base.metadata.create_all(e)
    yield
    database.SessionLocal.configure(bind=old)
    e.dispose()
def client():
    a=FastAPI();a.include_router(router);return TestClient(a)
def H(t):return {'x-atlas-tenant':t}
ESSAY="I taught myself Python by building a tide-prediction tool for my town's harbor and presented it at the school science fair."
def test_launch_prompt_paste_validate_complete_retrieve_and_tenant_isolation():
    c=client();t='own-doc-a'
    step=c.get(P+'/onboarding/launch-step',headers=H(t)).json();assert step['show'] and 'paste' in step['accepted_sources']
    r=c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'essays','title':'Harbor essay','text':ESSAY});assert r.status_code==200,r.text
    doc=r.json()['document'];assert doc['doc_type']=='essays' and r.json()['status']['missing_types']==['writings','activity_descriptions']
    assert r.json()['status']['complete'] is False and r.json()['status']['ready_for_drafting'] is True
    # fake ids / uncovered types are rejected
    assert c.post(P+'/onboarding/complete',headers=H(t),json={'document_types':['essays'],'source_ids':[99999]}).status_code==422
    assert c.post(P+'/onboarding/complete',headers=H(t),json={'document_types':['writings'],'source_ids':[doc['id']]}).status_code==422
    ok=c.post(P+'/onboarding/complete',headers=H(t),json={'document_types':['essays'],'source_ids':[doc['id']]});assert ok.status_code==200 and ok.json()['missing_types']==['writings','activity_descriptions']
    assert c.get(P+'/onboarding/launch-step',headers=H(t)).json()['show'] is False
    hits=c.post(P+'/retrieve',headers=H(t),json={'query':'what did you build with Python'}).json();assert hits[0]['title']=='Harbor essay'
    # another tenant sees nothing and cannot use this tenant's ids
    assert c.post(P+'/retrieve',headers=H('own-doc-b'),json={'query':'python harbor'}).json()==[]
    assert c.post(P+'/onboarding/complete',headers=H('own-doc-b'),json={'document_types':['essays'],'source_ids':[doc['id']]}).status_code==422
def test_bad_type_and_short_text_rejected_and_unavailable_model_is_honest(monkeypatch):
    c=client();t='own-doc-c'
    assert c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'college_records','title':'x','text':ESSAY}).status_code==422
    assert c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'essays','title':'x','text':'short'}).status_code==422
    monkeypatch.setenv('ATLAS_PROFILE_EMBEDDING_PROVIDER','openai');monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    r=c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'essays','title':'x','text':ESSAY})
    assert r.status_code==503 and 'unavailable' in r.json()['detail']   # server-configured hosted provider with no key: honest 503
    assert c.get(P+'/onboarding/status',headers=H(t)).json()['documents']==0
def test_integrated_application_reports_unavailable_model_instead_of_500_or_fake_draft(monkeypatch):
    from app.modules.m02_competition_manager.routes import router as cr
    monkeypatch.setenv('ATLAS_OLLAMA_URL','http://127.0.0.1:9');monkeypatch.setenv('ATLAS_OLLAMA_MODEL','tiny-test')
    a=FastAPI();a.include_router(cr);a.include_router(router);c=TestClient(a);t='own-doc-d'
    c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'essays','title':'E','text':ESSAY})
    r=c.post('/competition-manager/competitions/c1/integrated-application',headers=H(t),json={'official_url':'https://official.example','fields':[{'field':'impact','question':'What did you build?'}]})
    assert r.status_code==503 and 'nothing was drafted' in r.json()['detail'],r.text
def test_status_reports_model_not_configured_and_integrated_refuses_without_model(monkeypatch):
    monkeypatch.delenv('ATLAS_OLLAMA_MODEL',raising=False)
    from app.modules.m02_competition_manager.routes import router as cr
    a=FastAPI();a.include_router(cr);a.include_router(router);c=TestClient(a);t='own-doc-e'
    st=c.get(P+'/onboarding/status',headers=H(t)).json();assert st['drafting_model']['configured'] is False and st['indexing_leaves_machine'] is False
    r=c.post('/competition-manager/competitions/c1/integrated-application',headers=H(t),json={'official_url':'https://o.example','fields':[{'field':'f','question':'Why enter?'}]})
    assert r.status_code==503 and 'No local drafting model' in r.json()['detail']
def test_repaste_dedup_returns_matching_id_and_blank_input_rejected():
    c=client();t='own-doc-f';A=ESSAY;B=ESSAY+' Second paragraph about tides and data.'
    mk=lambda title,text:c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'essays','title':title,'text':text})
    a=mk('T',A).json()['document'];b=mk('T',B).json()['document'];a2=mk('T',A)
    assert a['id']!=b['id'] and a2.json()['document']['id']==a['id'] and a2.json()['created']==0
    assert len(c.get(P+'/onboarding/status',headers=H(t)).json()['documents_list'])==2
    assert mk('   ','x'*30).status_code==422 and mk('T',' '*40).status_code==422
    padded=mk('  P  ','  '+A+'  ').json()['document'];assert padded['title']=='P'
def test_client_cannot_pick_hosted_provider_and_bogus_provider_is_422_not_500(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','sk-test-should-never-be-used');monkeypatch.delenv('ATLAS_PROFILE_EMBEDDING_PROVIDER',raising=False)
    c=client();t='own-doc-g'
    assert c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'essays','title':'x','text':ESSAY,'embedding_provider':'openai'}).status_code==422  # extra field forbidden
    assert c.post(P+'/retrieve',headers=H(t),json={'query':'harbor','embedding_provider':'openai'}).status_code==422
    assert c.post(P+'/retrieve',headers=H(t),json={'query':'harbor','embedding_provider':'bogus'}).status_code==422
    assert c.post(P+'/retrieve',headers=H(t),json={'query':'harbor','embedding_provider':'lexical'}).status_code==200
def test_integrated_application_refuses_hosted_drafting_provider(monkeypatch):
    monkeypatch.delenv('ATLAS_ALLOW_HOSTED_DRAFTING',raising=False)
    from app.modules.m02_competition_manager.routes import router as cr
    a=FastAPI();a.include_router(cr);c=TestClient(a)
    r=c.post('/competition-manager/competitions/c1/integrated-application',headers=H('own-doc-h'),json={'official_url':'https://o.example','provider':'openai','fields':[{'field':'f','question':'Why enter?'}]})
    assert r.status_code==422 and 'Hosted drafting' in r.json()['detail']
def test_default_paste_makes_no_network_call_and_status_discloses_it(monkeypatch):
    import httpx
    def boom(*a,**k):raise AssertionError('network client used during offline paste')
    monkeypatch.setattr(httpx,'AsyncClient',boom);monkeypatch.delenv('ATLAS_PROFILE_EMBEDDING_PROVIDER',raising=False)
    c=client();t='own-doc-i'
    r=c.post(P+'/onboarding/documents',headers=H(t),json={'doc_type':'writings','title':'W','text':ESSAY});assert r.status_code==200,r.text
    assert c.post(P+'/retrieve',headers=H(t),json={'query':'harbor python'}).status_code==200
    # status probes the model server only when a model is configured; with none set it must not touch the network either
    monkeypatch.delenv('ATLAS_OLLAMA_MODEL',raising=False)
    st=c.get(P+'/onboarding/status',headers=H(t)).json()
    assert st['embedding_provider']=='lexical' and st['indexing_leaves_machine'] is False and 'not sent' in st['indexing_note']
