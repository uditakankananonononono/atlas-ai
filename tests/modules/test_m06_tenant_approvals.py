from app.modules.m06_social_media_manager.service import Service,MemorySocialRepository
class A:
 def __init__(s):s.items=[]
 def put(s,x,*,user_id=None):s.items.append((x,user_id));return x
async def gen(*args):return 'm','x'
def test_central_approval_boundary_adds_tenant():
 a=A();svc=Service(approval_store=a,generate=gen,repository=MemorySocialRepository(),tenant_id='t1');request=svc._file_approval(action_type='publish',payload={'plan_id':'p'});assert request.payload=={'tenant_id':'t1','plan_id':'p'};assert a.items[0][1]=='t1'
def test_empty_tenant_fails_closed():
 try:Service(approval_store=A(),generate=gen,repository=MemorySocialRepository(),tenant_id=' ')
 except ValueError as e:assert 'tenant_id' in str(e)
 else:raise AssertionError


def test_runtime_lookup_requires_exact_reviewed_content_media_and_account(monkeypatch):
 from datetime import datetime,timezone
 from types import SimpleNamespace
 from app.modules.m06_social_media_manager.routes import _ApprovalCenterLookup
 from app.modules.m06_social_media_manager.scheduler import ScheduleEntry
 from app.modules.m06_social_media_manager.models import Platform
 from app.core import approvals as module
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='reviewed',publish_at=datetime.now(timezone.utc),approval_id='a',status='approved')
 payload={'tenant_id':'t','schedule_id':'s','plan_id':'p','platform':'twitter','format':'thread','copy':'reviewed','publish_at':entry.publish_at.isoformat(),'sponsored':False,'media_urls':[],'alt_texts':[],'thread_chunks':[],'link':None,'account_id':'fixture-account'}
 request=SimpleNamespace(status='approved',action_type='schedule_post',payload=payload)
 class Store:
  def get(self,*args,**kwargs):return request
 monkeypatch.setattr(module,'approvals',Store())
 lookup=_ApprovalCenterLookup('t')
 assert lookup.authorizes(entry,account_id='fixture-account')
 for key,value in [('copy','changed'),('media_urls',['https://fixture.invalid/image']),('account_id','other'),('tenant_id','other'),('schedule_id','other')]:
  previous=payload[key];payload[key]=value
  assert not lookup.authorizes(entry,account_id='fixture-account')
  payload[key]=previous
 assert not lookup.authorizes(entry,account_id=None)
 del payload['media_urls']
 assert not lookup.authorizes(entry,account_id='fixture-account')
