import pytest
from fastapi.testclient import TestClient
from app.auth.context import TenantContext
from app.main import app
from app.modules.m20_general_cognitive_worker.agi_routes import get_agi_service, router
from app.modules.m20_general_cognitive_worker.agi_service import AGIRuntimeService, ModuleZeroGCWApprovalGate
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import ApprovalGateDecision, ApprovalGateRequest, Risk


class Center:
    def __init__(self): self.rows={}
    def submit(self,**kw): self.rows['id']={"id":"id","user_id":kw['user_id'],"status":"pending",**kw}; return self.rows['id']
    def get(self,key): return self.rows[key]


def test_module_zero_adapter_preserves_tenant_and_effect_payload():
    center=Center(); gate=ModuleZeroGCWApprovalGate('tenant-a',center)
    rid=gate.request(ApprovalGateRequest(action_type='activate_autonomous_goal',summary='goal',risk=Risk.EXTERNAL,payload={'proposal_id':'p'}))
    row=center.rows[rid]
    assert row['user_id']=='tenant-a' and row['payload']['proposal_id']=='p'
    assert gate.decision(rid)==ApprovalGateDecision.PENDING
    row['status']='approved'
    assert gate.decision(rid)==ApprovalGateDecision.APPROVED
    row['user_id']='tenant-b'
    assert gate.decision(rid)==ApprovalGateDecision.PENDING


def test_tenant_service_persists_world_and_provenance(tmp_path):
    gate=InMemoryApprovalGate(); first=AGIRuntimeService('t',data_dir=str(tmp_path),approval_gate=gate)
    first.world.observe(subject='x',predicate='value',value=1,source='test')
    second=AGIRuntimeService('t',data_dir=str(tmp_path),approval_gate=gate)
    assert second.world.hypotheses('x','value')[0]['value']==1
    report=second.evaluate_transfer(strategy='sum_items',cases=[
      {'id':'a','domain':'math','problem':{'items':[1,2]},'expected':3},
      {'id':'b','domain':'ops','problem':{'items':[2,3]},'expected':5,'source_domain':'math'}])
    assert report['accuracy']==1 and second.events.get('t',report['provenance_event_id'])


def test_authenticated_routes_expose_world_goal_and_evaluation(tmp_path):
    gate=InMemoryApprovalGate(); service=AGIRuntimeService('tenant',data_dir=str(tmp_path),approval_gate=gate)
    app.dependency_overrides[get_agi_service]=lambda:service
    client=TestClient(app)
    try:
      assert client.post('/api/v1/agi-runtime/world/evidence',json={'subject':'launch','predicate':'date','value':'Mon','source':'a'}).status_code==201
      client.post('/api/v1/agi-runtime/world/evidence',json={'subject':'launch','predicate':'date','value':'Tue','source':'b'})
      proposal=client.post('/api/v1/agi-runtime/goals/proposals',json={'mission':'ship safely'}).json()[0]
      approval=client.post(f"/api/v1/agi-runtime/goals/{proposal['id']}/request-activation").json()['approval_id']
      assert client.post(f"/api/v1/agi-runtime/goals/{proposal['id']}/activate",json={'approval_id':approval}).status_code==403
      gate.decide(approval,ApprovalGateDecision.APPROVED)
      assert client.post(f"/api/v1/agi-runtime/goals/{proposal['id']}/activate",json={'approval_id':approval}).status_code==200
      evaluation=client.post('/api/v1/agi-runtime/evaluations/cross-domain',json={'strategy':'sum_items','cases':[{'id':'a','domain':'math','problem':{'items':[1]},'expected':1},{'id':'b','domain':'ops','problem':{'items':[2]},'expected':2,'source_domain':'math'}]})
      assert evaluation.status_code==201 and evaluation.json()['worst_domain_accuracy']==1
    finally: app.dependency_overrides.clear()
