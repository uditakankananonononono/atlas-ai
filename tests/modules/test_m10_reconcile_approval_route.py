"""Local isolated auth and saved-approval endpoint, no external effects."""
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m10_email_assistant.routes import router,get_service
from test_m10_email_assistant import make_service,raw_message


def test_reconciliation_route_uses_owner_scope_and_never_starts_unknown_model(tmp_path,monkeypatch,oidc_auth_headers):
 svc,repo,sink,client=make_service(tmp_path,tenant='tenant-a')
 repo.save_account(account_id='a',email_address='fixture@example.invalid',encrypted_refresh_token=svc.cipher.encrypt('rt'),history_id='100',watch_expiration=None)
 original=sink.put
 def put(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('fixture receipt lost')
 sink.put=put
 try:asyncio.run(svc._ingest_message('a',raw_message('g','Please reply',snippet='please reply')))
 except RuntimeError:pass
 row=repo.list_messages()[0]
 sink.matching_source_approvals=lambda **scope:[i for i,user in sink.items if user==scope['user_id']]
 app=FastAPI();app.include_router(router);app.dependency_overrides[get_service]=lambda:svc
 monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
 url=f'/email-assistant/accounts/a/draft-work/{row.id}/reconcile-approval'
 with TestClient(app) as http:
  assert http.post(url).status_code==401
  assert http.post(url,headers=oidc_auth_headers('tenant-b')).status_code==403
  assert http.post(url.replace('/accounts/a/','/accounts/other/'),headers=oidc_auth_headers('tenant-a')).status_code==404
  response=http.post(url,headers=oidc_auth_headers('tenant-a'))
  assert response.status_code==200,response.text
  assert response.json()['phase']=='complete' and response.json()['reconciled']
  assert len(sink.items)==1 and len(repo.list_drafts())==1
  assert http.post(url,headers=oidc_auth_headers('tenant-a')).json()['phase']=='complete'
  assert len(sink.items)==1 and len(repo.list_drafts())==1
 asyncio.run(client.aclose())


def test_reconcile_endpoint_cannot_restart_model_inflight_from_caller_receipt(tmp_path,monkeypatch,oidc_auth_headers):
 svc,repo,sink,client=make_service(tmp_path)
 repo.save_account(account_id='a',email_address='fixture@example.invalid',encrypted_refresh_token=svc.cipher.encrypt('rt'),history_id='100',watch_expiration=None)
 calls=[]
 async def generate(prompt,*args):
  if prompt.startswith('Extract action items'):return 'fixture','[]'
  calls.append('model');raise TimeoutError('fixture unknown')
 svc.llm_generate=generate
 try:asyncio.run(svc._ingest_message('a',raw_message('g','Please reply',snippet='please reply')))
 except TimeoutError:pass
 row=repo.list_messages()[0]
 app=FastAPI();app.include_router(router);app.dependency_overrides[get_service]=lambda:svc
 monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
 with TestClient(app) as http:
  response=http.post(f'/email-assistant/accounts/a/draft-work/{row.id}/reconcile-approval',headers=oidc_auth_headers('tenant-a'),json={'retry':True,'receipt':{'status':'sent'}})
  assert response.status_code==200 and response.json()['phase']=='model_inflight' and not response.json()['reconciled']
 assert calls==['model'] and sink.items==[] and repo.list_drafts()==[]
 asyncio.run(client.aclose())
