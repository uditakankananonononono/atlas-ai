"""Synthetic assets only: no real weights, download or accuracy validation."""
import base64
import json
import pytest
from fastapi import HTTPException
from app.ingest.asr_provisioning import config_from_env, main
from app.ingest.offline_asr import ASRError
from app.modules.m25_knowledge_copilot_training import routes
from app.modules.m25_knowledge_copilot_training.service_factory import KnowledgeServiceFactory, provision, ServiceUnavailable
from app.auth.context import TenantContext
from test_offline_asr import config, model, wav
from test_m25_verified_rehydration import src


def test_env_disabled_and_invalid(config):
    assert config_from_env({}) is None
    assert config_from_env({'ATLAS_ASR_ENABLED':'true','ATLAS_ASR_MODEL_DIR':'remote'}) is None
    with pytest.raises(ASRError):config_from_env({'ATLAS_ASR_ENABLED':'1'})
    with pytest.raises(ASRError):config_from_env({'ATLAS_ASR_ENABLED':'1','ATLAS_ASR_MODEL_DIR':'remote'})
    assert config_from_env({'ATLAS_ASR_ENABLED':'1','ATLAS_ASR_MODEL_DIR':str(config.model_dir)}) == config


def test_cli_verify_and_invalid(config,capsys):
    assert main(['--model-dir',str(config.model_dir)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['model_identity']==config.identity() and result['assets_verified'] is True
    assert result['real_inference_verified'] is False and result['accuracy_verified'] is False
    assert main(['--model-dir','hub/model'])==1
    assert 'hub/model' not in capsys.readouterr().out
    assert main(['--model-dir',str(config.model_dir),'--tenant','a'])==1


def test_cli_provision_uses_explicit_known_new(config,monkeypatch,capsys):
    import app.modules.m25_knowledge_copilot_training.service_factory as factory
    calls=[]
    monkeypatch.setattr(factory,'provision',lambda *a,**kw:calls.append((a,kw)))
    args=['--model-dir',str(config.model_dir),'--m25-root','/private/root','--tenant','t','--owner','o']
    assert main(args)==1 and not calls
    assert main(args+['--known-new'])==0
    assert calls==[(('/private/root','t','o'),{'known_new':True,'asr_config':config})]


def test_http_factory_audio_and_restart(config,model,tmp_path,monkeypatch):
    root=tmp_path/'root';root.mkdir(mode=0o700)
    provision(root,'tenant','owner',known_new=True,asr_config=config,allow_test_scratch=True)
    monkeypatch.setattr(routes,'_factory',None)
    real=KnowledgeServiceFactory
    monkeypatch.setattr(routes,'KnowledgeServiceFactory',lambda r,**kw:real(r,allow_test_scratch=True,**kw))
    monkeypatch.setenv('ATLAS_M25_DURABLE_ROOT',str(root))
    monkeypatch.setenv('ATLAS_ASR_ENABLED','1')
    monkeypatch.setenv('ATLAS_ASR_MODEL_DIR',str(config.model_dir))
    data=routes.AudioIngestRequest(source=src(),actor_id='owner',audio_base64=base64.b64encode(wav()).decode())
    def ingest():
        gen=routes.get_service(TenantContext('tenant','owner'))
        try:return routes.ingest_audio(data,next(gen))
        finally:gen.close()
    result=ingest()
    assert result['segments']==1 and model.loads[0][1]['local_files_only'] is True
    monkeypatch.setattr(routes,'_factory',None)
    gen=routes.get_service(TenantContext('tenant','owner'))
    try:
        service=next(gen)
        assert service.records
        with pytest.raises(HTTPException) as exc:routes.ingest_audio(data.model_copy(update={'audio_base64':'%%%'}),service)
        assert exc.value.status_code==422
        with pytest.raises(HTTPException):routes.ingest_audio(data.model_copy(update={'actor_id':'other'}),service)
    finally:gen.close()
    monkeypatch.setenv('ATLAS_ASR_MODEL_SIZE','base')
    with pytest.raises(HTTPException) as exc:next(routes.get_service(TenantContext('tenant','owner')))
    assert exc.value.status_code==503


def test_old_registry_not_upgraded(config,tmp_path):
    root=tmp_path/'root';root.mkdir(mode=0o700)
    provision(root,'t','o',known_new=True,allow_test_scratch=True)
    factory=KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config)
    with pytest.raises(ServiceUnavailable):
        with factory.service('t','o'):pass


def test_authenticated_http_audio(config,model,tmp_path,monkeypatch,oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    root=tmp_path/'http';root.mkdir(mode=0o700)
    provision(root,'tenant','owner',known_new=True,asr_config=config,allow_test_scratch=True)
    monkeypatch.setattr(routes,'_factory',None)
    real=KnowledgeServiceFactory
    monkeypatch.setattr(routes,'KnowledgeServiceFactory',lambda r,**kw:real(r,allow_test_scratch=True,**kw))
    monkeypatch.setenv('ATLAS_M25_DURABLE_ROOT',str(root))
    monkeypatch.setenv('ATLAS_ASR_ENABLED','1')
    monkeypatch.setenv('ATLAS_ASR_MODEL_DIR',str(config.model_dir))
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH',raising=False)
    app=FastAPI();app.include_router(routes.router)
    c=TestClient(app)
    body={'source':src().model_dump(mode='json'),'actor_id':'owner','audio_base64':base64.b64encode(wav()).decode()}
    url='/knowledge-copilot-training/ingest-audio'
    assert c.post(url,json=body).status_code==401
    wrong=oidc_auth_headers(tenant='tenant',subject='other')
    assert c.post(url,json=body,headers=wrong).status_code==403
    h=oidc_auth_headers(tenant='tenant',subject='owner')
    assert c.post(url,json={**body,'audio_base64':'%'},headers=h).status_code==422
    assert c.post(url,json={**body,'audio_base64':base64.b64encode(b'x'*20001).decode()},headers=h).status_code==422
    assert c.post(url,json=body,headers=h).status_code==200
    monkeypatch.delenv('ATLAS_ASR_ENABLED')
    assert c.post(url,json=body,headers=h).status_code==503
