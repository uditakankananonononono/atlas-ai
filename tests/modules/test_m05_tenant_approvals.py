from datetime import datetime, timezone
from app.modules.m05_outreach_manager.service import Service, InMemoryContactRepository
from app.modules.m05_outreach_manager.campaigns import CampaignService, InMemoryCampaignRepository
from app.modules.m05_outreach_manager.schemas import ContactCreate
class A:
 def __init__(s):s.items=[]
 def put(s,x,*,user_id=None):s.items.append(x);return x

def test_original_send_proposal_carries_tenant():
 a=A();contacts=InMemoryContactRepository();svc=Service(contacts,a,None,tenant_id='t1');c=svc.create_contact(ContactCreate(project_id='p',name='Ada',email='ada@example.org'));d=type('D',(),{'contact_id':c.id,'subject':'Hi','body':'Body','id':'d1'})();assert svc.propose_send(d).payload['tenant_id']=='t1'

def test_campaign_send_approval_carries_tenant():
 a=A();contacts=InMemoryContactRepository();campaigns=InMemoryCampaignRepository();c=Service(contacts,a,None,tenant_id='t1').create_contact(ContactCreate(project_id='p',name='Ada',email='ada@example.org'));svc=CampaignService(campaigns,contacts,a,tenant_id='t1');camp=svc.create_campaign(project_id='p',name='n',goal='goal');m=svc.add_draft(camp.id,c.id,subject='Hi',body='Body');assert svc.submit_for_approval(m.id).payload['tenant_id']=='t1'
