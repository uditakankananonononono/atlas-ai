import json,os,subprocess,sys
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_m25_verified_rehydration import src,NOW
from app.modules.m25_knowledge_copilot_training.schemas import IngestRequest
from app.modules.m25_knowledge_copilot_training.service_factory import *

@pytest.fixture
def root(tmp_path):tmp_path.chmod(0o700);return tmp_path

def setup(root):
    provision(root,'tenant','actor',known_new=True,allow_test_scratch=True)
    return KnowledgeServiceFactory(root,allow_test_scratch=True)

def test_actual_second_factory_process_restart(root):
    factory=setup(root)
    with factory.service('tenant','actor') as s:
        s.ingest(IngestRequest(source=src(),content='restart fact',mime_type='text/markdown',actor_id='actor'))
        expected=s.records['s1'].versions[0].created_at.isoformat()
    script='''import json,sys
from app.modules.m25_knowledge_copilot_training.service_factory import KnowledgeServiceFactory
f=KnowledgeServiceFactory(sys.argv[1],allow_test_scratch=True)
with f.service('tenant','actor') as s:
 v=s.records['s1'].versions[0]
 print(json.dumps({'hits':len(s.search('restart')),'mime':v.mime_type,'time':v.created_at.isoformat()}))
'''
    # Subprocess requires backend on PYTHONPATH; pytest pythonpath alone does not propagate.
    out=subprocess.run([sys.executable,'-c',script,str(root)],capture_output=True,text=True,check=True)
    assert json.loads(out.stdout)=={'hits':1,'mime':'text/markdown','time':expected}

def app_client(factory,monkeypatch):
    from app.modules.m25_knowledge_copilot_training import routes as r
    monkeypatch.setattr(r,'_factory',factory);monkeypatch.setenv('ATLAS_M25_DURABLE_ROOT',str(factory.root))
    app=FastAPI();app.include_router(r.router);return TestClient(app)

def test_identical_missing_lost_503_and_owner403(root,monkeypatch,oidc_auth_headers):
    f=setup(root);monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with app_client(f,monkeypatch) as c:
        foreign=c.get('/knowledge-copilot-training/export',headers=oidc_auth_headers('foreign','actor'))
        os.rmdir(root/'tenant')
        lost=c.get('/knowledge-copilot-training/export',headers=oidc_auth_headers('tenant','actor'))
        assert foreign.status_code==lost.status_code==503 and foreign.json()==lost.json()=={'detail':UNAVAILABLE}
    (root/'tenant').mkdir(mode=0o700)
    with app_client(f,monkeypatch) as c:
        assert c.get('/knowledge-copilot-training/export',headers=oidc_auth_headers('tenant','other')).status_code==403

def test_corruption_not_empty_success(root):
    f=setup(root)
    with f.service('tenant','actor') as s:s.ingest(IngestRequest(source=src(),content='fact',mime_type='text/plain',actor_id='actor'))
    (root/'tenant/s1/v1/source.bin').write_bytes(b'bad')
    fresh=KnowledgeServiceFactory(root,allow_test_scratch=True)
    with pytest.raises(ServiceUnavailable,match=UNAVAILABLE):
        with fresh.service('tenant','actor'):pass
    assert not fresh._services

def test_root_no_default_volatile_or_shared(root):
    for value in (None,str(root)):
        with pytest.raises(ServiceUnavailable):KnowledgeServiceFactory(value)
    root.chmod(0o755)
    with pytest.raises(ServiceUnavailable):KnowledgeServiceFactory(root,allow_test_scratch=True)

def test_profile_drift_and_existing_provision_refused(root):
    f=setup(root)
    with pytest.raises(ServiceUnavailable):provision(root,'tenant','actor',known_new=True,allow_test_scratch=True)
    p=next(root.glob('.m25-owner-*'));data=json.loads(p.read_text());data['profile']='other';p.write_text(json.dumps(data))
    with pytest.raises(ServiceUnavailable):
        with f.service('tenant','actor'):pass

def test_parallel_factory_one_publication(root):
    from concurrent.futures import ThreadPoolExecutor
    f=setup(root)
    def get(_):
        with f.service('tenant','actor') as s:return id(s)
    with ThreadPoolExecutor(max_workers=4) as pool:assert len(set(pool.map(get,range(8))))==1


def test_actual_routes_restore_append_scope_audio(root,monkeypatch,oidc_auth_headers):
    f=setup(root);provision(root,'foreign','other',known_new=True,allow_test_scratch=True)
    with f.service('tenant','actor') as s:s.ingest(IngestRequest(source=src(),content='restart fact',mime_type='text/markdown',actor_id='actor'))
    fresh=KnowledgeServiceFactory(root,allow_test_scratch=True)
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with app_client(fresh,monkeypatch) as c:
        own=oidc_auth_headers('tenant','actor');other=oidc_auth_headers('foreign','other')
        assert c.post('/knowledge-copilot-training/search',json={'query':'restart','limit':5},headers=own).json()[0]['text']=='restart fact'
        assert c.get('/knowledge-copilot-training/export',headers=other).json()['sources']==[]
        data=IngestRequest(source=src(),content='new fact',mime_type='text/plain',actor_id='actor').model_dump(mode='json')
        response=c.post('/knowledge-copilot-training/ingest',json=data,headers=own)
        assert response.status_code==200 and response.json()['version']==2
        data['mime_type']='audio/wav'
        response=c.post('/knowledge-copilot-training/ingest',json=data,headers=own)
        assert response.status_code==503 and response.json()=={'detail':UNAVAILABLE}


def test_no_root_config_identical_503(root,monkeypatch,oidc_auth_headers):
    from app.modules.m25_knowledge_copilot_training import routes as r
    monkeypatch.setattr(r,'_factory',None);monkeypatch.delenv('ATLAS_M25_DURABLE_ROOT',raising=False)
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        out=c.get('/knowledge-copilot-training/export',headers=oidc_auth_headers('tenant','actor'))
        assert out.status_code==503 and out.json()=={'detail':UNAVAILABLE}
    assert not (root/'tenant').exists()

@pytest.mark.parametrize('file,content',[('manifest.json','{'),('v1/segments.json','[]')])
def test_other_cold_corruption_refuses(root,file,content):
    f=setup(root)
    with f.service('tenant','actor') as s:s.ingest(IngestRequest(source=src(),content='fact',mime_type='text/plain',actor_id='actor'))
    (root/'tenant/s1'/file).write_text(content)
    fresh=KnowledgeServiceFactory(root,allow_test_scratch=True)
    with pytest.raises(ServiceUnavailable):
        with fresh.service('tenant','actor'):pass


def test_expired_consent_warm_and_cold_refuse(root):
    from datetime import datetime,timedelta,timezone
    source=src(expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    f=setup(root)
    with f.service('tenant','actor') as s:s.ingest(IngestRequest(source=source,content='fact',mime_type='text/plain',actor_id='actor'))
    with f.service('tenant','actor') as s:
        s.records['s1'].source.consent.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        s._persist_manifest(s.records['s1'])
    for factory in (f,KnowledgeServiceFactory(root,allow_test_scratch=True)):
        with pytest.raises(ServiceUnavailable):
            with factory.service('tenant','actor'):pass


def test_actual_http_root_outside_tmp(root,monkeypatch,oidc_auth_headers):
    import tempfile,shutil
    from app.modules.m25_knowledge_copilot_training import routes as r
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    path=Path(tempfile.mkdtemp(prefix='m25-root-',dir='/home/sandbox'))
    try:
        path.chmod(0o700);provision(path,'tenant','actor',known_new=True)
        monkeypatch.setattr(r,'_factory',None);monkeypatch.setenv('ATLAS_M25_DURABLE_ROOT',str(path))
        app=FastAPI();app.include_router(r.router)
        with TestClient(app) as c:
            headers=oidc_auth_headers('tenant','actor')
            data=IngestRequest(source=src(),content='durable route fact',mime_type='text/plain',actor_id='actor').model_dump(mode='json')
            assert c.post('/knowledge-copilot-training/ingest',json=data,headers=headers).status_code==200
        monkeypatch.setattr(r,'_factory',None)
        with TestClient(app) as c:
            out=c.post('/knowledge-copilot-training/search',json={'query':'durable','limit':5},headers=headers)
            assert out.status_code==200 and len(out.json())==1
        assert r._factory.root==path and not str(path).startswith('/tmp/')
    finally:shutil.rmtree(path)


def test_registry_missing_on_warm_cache_denies(root):
    f=setup(root)
    with f.service('tenant','actor'):pass
    next(root.glob('.m25-owner-*')).unlink()
    with pytest.raises(ServiceUnavailable):
        with f.service('tenant','actor'):pass


def test_workspace_symlink_refused_and_no_auto_adoption(root):
    provision(root,'tenant','actor',known_new=True,allow_test_scratch=True)
    os.rmdir(root/'tenant');(root/'target').mkdir(mode=0o700);(root/'tenant').symlink_to(root/'target')
    f=KnowledgeServiceFactory(root,allow_test_scratch=True)
    with pytest.raises(ServiceUnavailable):
        with f.service('tenant','actor'):pass
    legacy=root/'legacy';legacy.mkdir(mode=0o700)
    with pytest.raises(ServiceUnavailable):provision(root,'legacy','actor',known_new=True,allow_test_scratch=True)


def test_all_existing_endpoints_owner_narrowing(root,monkeypatch,oidc_auth_headers):
    f=setup(root);monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with app_client(f,monkeypatch) as c:
        headers=oidc_auth_headers('tenant','other')
        requests=[('GET','/export',None),('GET','/contradictions?subject=fact',None),('POST','/search',{'query':'fact','limit':1}),('POST','/claims/substantiate',[]),('DELETE','/sources/s1',None),('POST','/ingest',IngestRequest(source=src(),content='fact',mime_type='text/plain',actor_id='other').model_dump(mode='json'))]
        for method,path,data in requests:
            assert c.request(method,'/knowledge-copilot-training'+path,json=data,headers=headers).status_code==403


def test_actual_http_constructor_dotdot_into_tmp_refuses(root,monkeypatch,oidc_auth_headers):
    from app.modules.m25_knowledge_copilot_training import routes as r
    # Explicit administrative test setup only, HTTP never has scratch bypass.
    setup(root)
    alias='/home/sandbox/../..'+str(root)
    assert Path(alias).resolve()==root.resolve()
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    monkeypatch.setattr(r,'_factory',None);monkeypatch.setenv('ATLAS_M25_DURABLE_ROOT',alias)
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        out=c.get('/knowledge-copilot-training/export',headers=oidc_auth_headers('tenant','actor'))
        assert out.status_code==503 and out.json()=={'detail':UNAVAILABLE}
    assert r._factory is None
    with pytest.raises(ServiceUnavailable):provision(alias,'another','actor',known_new=True)


def private_run_path(monkeypatch):
    # Host-independent private 0700 /run fixture: simulate path metadata ONLY.
    # Production _root, factory dependency and HTTP handler are not mocked.
    from types import SimpleNamespace
    target=Path('/run/credentials/private-service')
    real_resolve=Path.resolve;real_symlink=Path.is_symlink;real_dir=Path.is_dir;real_stat=Path.stat
    def simulated(p):return p==target or p in target.parents
    monkeypatch.setattr(Path,'is_symlink',lambda self:False if simulated(self) else real_symlink(self))
    monkeypatch.setattr(Path,'resolve',lambda self,strict=False:target if self==target else real_resolve(self,strict=strict))
    monkeypatch.setattr(Path,'is_dir',lambda self:True if self==target else real_dir(self))
    monkeypatch.setattr(Path,'stat',lambda self,*a,**kw:SimpleNamespace(st_mode=0o40700) if self==target else real_stat(self,*a,**kw))
    return target


def test_private_run_0700_root_refused(monkeypatch):
    target=private_run_path(monkeypatch)
    with pytest.raises(ServiceUnavailable):KnowledgeServiceFactory(str(target))
    with pytest.raises(ServiceUnavailable):provision(str(target),'tenant','actor',known_new=True)


def test_actual_http_private_run_refuses_before_factory_cache(monkeypatch,oidc_auth_headers):
    from app.modules.m25_knowledge_copilot_training import routes as r
    target=private_run_path(monkeypatch)
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    monkeypatch.setenv('ATLAS_M25_DURABLE_ROOT',str(target));monkeypatch.setattr(r,'_factory',None)
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        response=c.get('/knowledge-copilot-training/export',headers=oidc_auth_headers('tenant','actor'))
        assert response.status_code==503 and response.json()=={'detail':UNAVAILABLE}
    assert r._factory is None
