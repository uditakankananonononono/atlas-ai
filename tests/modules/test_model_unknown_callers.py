import asyncio
from types import SimpleNamespace
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from app.core.providers import ProviderError,ProviderOutcomeUnknown
from app.modules.m01_opportunity_discovery import routes as m01
from app.modules.m01_opportunity_discovery.schemas import DigestRequestIn
from app.modules.m06_social_media_manager.service import Service,Platform
from app.modules.m06_social_media_manager import routes as m06

@pytest.mark.parametrize('unknown',[True,False])
def test_digest_unknown_holds_no_approval_but_preflight_can_fallback(monkeypatch,unknown):
 filed=[]
 class Digest:
  def top_opportunities(self,**kwargs):return ['fixture']
  def render_digest(self,items):return 'deterministic fixture'
  def digest_prompt(self,items):return 'fixture'
  def digest_subject(self,items):return 'fixture'
  def propose_digest(self,**kwargs):filed.append(kwargs);return SimpleNamespace(id='ap',status=SimpleNamespace(value='pending'))
 async def fail(*args):raise ProviderOutcomeUnknown('fixture dispatched') if unknown else ProviderError('preflight missing key')
 monkeypatch.setattr(m01,'generate',fail)
 if unknown:
  with pytest.raises(HTTPException) as error:asyncio.run(m01.propose_digest(DigestRequestIn(use_llm=True),Digest()))
  assert error.value.status_code==409 and error.value.detail['state']=='unknown' and not filed
 else:
  result=asyncio.run(m01.propose_digest(DigestRequestIn(use_llm=True),Digest()));assert result.status=='pending' and len(filed)==1

@pytest.mark.parametrize('operation',['plan','analysis'])
def test_social_unknown_persists_no_plan_report_and_http_holds(operation):
 calls=[]
 async def fail(*args):calls.append('generation');raise ProviderOutcomeUnknown('fixture dispatched')
 class Metrics:
  async def fetch_engagement(self,*args):return {'fixture':1}
 svc=Service(approval_store=SimpleNamespace(),generate=fail,metrics_client=Metrics())
 if operation=='plan':
  with pytest.raises(ProviderOutcomeUnknown):asyncio.run(svc.create_plan('fixture',[Platform.INSTAGRAM]))
  assert not svc._repository.plans
  app=FastAPI();app.include_router(m06.router);app.dependency_overrides[m06.get_service]=lambda:svc
  response=TestClient(app).post('/social-media-manager/plans',json={'brief':'fixture','platforms':['instagram']})
  assert response.status_code==409 and response.json()['detail']['retry_allowed'] is False and not svc._repository.plans
 else:
  with pytest.raises(ProviderOutcomeUnknown):asyncio.run(svc.analyze_engagement(Platform.INSTAGRAM))
  assert not svc._repository.reports
 assert len(calls)==(2 if operation=='plan' else 1)
