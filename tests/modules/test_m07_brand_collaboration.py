from datetime import date,datetime,timezone
from app.modules.m07_brand_collaboration.schemas import BrandDiscoveryIn,MediaKitIn,PartnershipEventIn,ReportIn
from app.modules.m07_brand_collaboration.service import Service
class Repo:
 def __init__(s):s.tenant_id="tenant-test";s.b={};s.a={};s.e=[]
 def add_brand(s,**d):s.b[d['id']]=type('R',(),d)
 def brand(s,i):return s.b.get(i)
 def add_artifact(s,**d):s.a[d['id']]=type('R',(),d)
 def artifact(s,i):return s.a.get(i)
 def add_event(s,**d):s.e.append(type('R',(),d))
 def events(s,i):return [x for x in s.e if x.brand_id==i]
class Approvals:
 def __init__(s):s.items=[]
 def put(s,x,*,user_id=None):s.items.append((x,user_id));return x
def test_full_brand_flow_is_gated():
 r=Repo();a=Approvals();svc=Service(r,a);b=svc.discover(BrandDiscoveryIn(name='Acme',mission='girls science access',public_url='https://acme.test'), 'science access for girls')
 assert b.alignment_score>0
 kit=svc.media_kit(MediaKitIn(brand_id=b.id,creator_name='Ada',creator_mission='science access',metrics={'reach':100}))
 svc.log_event(PartnershipEventIn(brand_id=b.id,kind='deal',occurred_at=datetime.now(timezone.utc),data={'stage':'won'}))
 report=svc.report(ReportIn(brand_id=b.id,period_start=date(2026,1,1),period_end=date(2026,1,31),metrics={'views':50}))
 proposal=svc.propose_send(report.id,'brand@example.test');assert proposal.status=='pending' and len(a.items)==1 and kit.sha256

def test_send_approval_preserves_tenant_boundary():
 r=Repo();a=Approvals();svc=Service(r,a);b=svc.discover(BrandDiscoveryIn(name='Acme',mission='science',public_url='https://acme.test'),'science')
 art=svc.media_kit(MediaKitIn(brand_id=b.id,creator_name='Ada',creator_mission='science',metrics={}))
 assert svc.propose_send(art.id,'brand@example.test').payload['tenant_id']=='tenant-test'
 assert a.items[-1][1]=='tenant-test'
