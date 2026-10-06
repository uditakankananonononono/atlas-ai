"""Actual mounted-app route canaries, signed owners, no dependency override."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker import routes
from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
from app.modules.m20_general_cognitive_worker.metacognition import PromptTemplate
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import ApprovalGateDecision

BASE='/api/v1/api/modules/20/meta/improvement/proposals'

@pytest.fixture
def bound(monkeypatch,oidc_auth_headers):
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setattr(routes,'_services',{})
 monkeypatch.setattr(routes,'_service',None)
 services={}
 for owner in ('a','b'):
  s=CognitiveWorkerService(approval_gate=InMemoryApprovalGate())
  s.prompt_registry.register(PromptTemplate(name='orient',content=owner+'-v1'))
  routes.bind_service(s,tenant_id=owner);services[owner]=s
 return TestClient(app),services,oidc_auth_headers('a'),oidc_auth_headers('b')

def propose(c,h,text='reviewed-v2'):
 r=c.post(BASE,headers=h,json={'target_name':'orient','proposed_content':text})
 assert r.status_code==201,r.text
 return r.json()

def apply(c,h,p,token=None):
 return c.post(BASE+'/'+p['proposal_id']+'/apply',headers=h,json={'approved':True,'approval_id':token or p['approval_id']})

def test_mounted_route_pending_foreign_and_cross_owner_rejected_then_exact_once(bound):
 c,ss,a,b=bound;p=propose(c,a);other=propose(c,a,'other')
 assert apply(c,a,p).status_code==403
 ss['a'].safety.approvals.decide(other['approval_id'],ApprovalGateDecision.APPROVED)
 assert apply(c,a,p,other['approval_id']).status_code==403
 assert apply(c,b,p).status_code==404
 assert ss['a'].prompt_registry.get('orient').content=='a-v1'
 assert ss['b'].prompt_registry.get('orient').content=='b-v1'
 ss['a'].safety.approvals.decide(p['approval_id'],ApprovalGateDecision.APPROVED)
 r=apply(c,a,p);assert r.status_code==200,r.text
 assert ss['a'].prompt_registry.get('orient').content=='reviewed-v2'
 assert apply(c,a,p).status_code==403
 assert apply(c,a,other).status_code==403
 assert ss['a'].prompt_registry.get('orient').version==2

@pytest.mark.parametrize('attack',['proposal_content','proposal_token','target_content','target_kind'])
def test_mounted_route_snapshot_and_stale_target_checks(bound,attack):
 c,ss,a,b=bound;p=propose(c,a);s=ss['a']
 s.safety.approvals.decide(p['approval_id'],ApprovalGateDecision.APPROVED)
 if attack=='proposal_content':s.improvement.proposals[p['proposal_id']].proposed_content='unreviewed'
 if attack=='proposal_token':s.improvement.proposals[p['proposal_id']].approval_id='forged'
 if attack=='target_content':s.prompt_registry.get('orient').content='newer-current'
 if attack=='target_kind':s.prompt_registry.get('orient').kind='algorithm_parameter'
 assert apply(c,a,p).status_code==403
 assert s.prompt_registry.get('orient').version==1
 assert s.prompt_registry.get('orient').content!='unreviewed'

def test_mounted_route_unauthenticated_request_never_applies(bound):
 c,ss,a,b=bound;p=propose(c,a)
 ss['a'].safety.approvals.decide(p['approval_id'],ApprovalGateDecision.APPROVED)
 assert apply(c,{},p).status_code==401
 assert ss['a'].prompt_registry.get('orient').content=='a-v1'
