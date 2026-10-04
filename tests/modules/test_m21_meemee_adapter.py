import pytest as _pt
_pt.importorskip("meemee", reason="needs the separate Meemee repo: pip install '.[claire-adapter]' (meemee-agent @ 6b8c444); NOT run, not passed")
import pytest
from app.core.approvals import ApprovalStore
from app.core.models import ApprovalStatus
from app.modules.m20_general_cognitive_worker.service import Service as Cognitive
from app.modules.m21_claire.service import Service
from app.modules.m21_claire.meemee_local_client import MeemeeLocalClient, AdapterError
from app.modules.m21_claire.local_client_protocol import PairingService
from meemee.devices import DeviceRegistry
from meemee.device_simulator import StatefulDeviceSimulator

class Model:
 async def __call__(self,p,x):return {"steps":[]}

def rig(tmp_path, owner="tenant-a"):
 reg=DeviceRegistry(tmp_path/"d.db");p=reg.create_pairing(owner)
 caps={"write_file":{},"run_command":{}}
 paired=reg.pair(p["pairing_id"],p["code"],device_id="dev1",name="pc",capabilities=caps)
 calls=[]
 def wf(state,path,text):calls.append(path);state[path]=text;return {"bytes":len(text)}
 def rc(state,cmd):calls.append(cmd);return {"ran":cmd}
 sim=StatefulDeviceSimulator("dev1",paired["secret"],{"write_file":wf,"run_command":rc})
 ap=ApprovalStore();cl=MeemeeLocalClient(reg,owner,"dev1",sim.execute,ap,str(tmp_path/"d.db"))
 s=Service(Cognitive(ap,Model()),ap,local_client=cl);g=s.intake("organize",[],{})
 return reg,sim,ap,cl,s,g,calls

@pytest.mark.asyncio
async def test_low_risk_runs_idempotent_audited(tmp_path):
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 a={"id":"a1","kind":"write_file","arguments":{"path":"n.txt","text":"hi"},"idempotency_key":"k1"}
 r=await s.local_action(g.id,a);assert r["status"]=="completed" and r["result"]=={"bytes":2}
 r2=await s.local_action(g.id,a);assert r2["replayed"] and calls==["n.txt"]
 assert [e.phase for e in cl.chain.events][:2]==["issued","completed"]
 assert sim.snapshot()=={"n.txt":"hi"}

@pytest.mark.asyncio
async def test_high_risk_needs_matching_approval_once(tmp_path):
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 a={"id":"a2","kind":"run_command","arguments":{"cmd":"ls"},"idempotency_key":"k2"}
 req=await s.local_action(g.id,a);assert req.status.value=="pending" and not calls
 ap.decide(req.id,ApprovalStatus.APPROVED)
 # Service-created approvals carry no tenant_id (pre-existing m21 gap): adapter fails closed, not routed around
 with pytest.raises(AdapterError):await cl.execute(a,req.id)
 pv=await cl.preview(a);ok=_approve(ap,"tenant-a","run_command",pv)
 pend=_approve(ap,"tenant-a","run_command",pv)
 other=dict(a,arguments={"cmd":"rm x"},idempotency_key="k3")
 with pytest.raises(AdapterError):await cl.execute(other,ok.id)  # approval is for a different action
 r=await s.local_action(g.id,a,ok.id);assert r["result"]=={"ran":"ls"} and calls==["ls"]
 with pytest.raises(AdapterError):await cl.execute(dict(a,idempotency_key="k4"),ok.id)  # reuse

@pytest.mark.asyncio
async def test_owner_scope_revoke_undeclared(tmp_path):
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 bad=MeemeeLocalClient(reg,"tenant-b","dev1",sim.execute,ap,str(tmp_path/"d.db"))
 with pytest.raises(AdapterError):await bad.capabilities()
 with pytest.raises(ValueError):await s.local_action(g.id,{"kind":"click","idempotency_key":"z"})  # not granted
 reg.revoke("tenant-a","dev1")
 with pytest.raises(AdapterError):await s.local_action(g.id,{"kind":"write_file","arguments":{"path":"p","text":"t"},"idempotency_key":"k9"})

@pytest.mark.asyncio
async def test_changed_action_same_key_refused_and_audit_chain_persisted(tmp_path):
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 a={"id":"a1","kind":"write_file","arguments":{"path":"n","text":"1"},"idempotency_key":"k"}
 await cl.execute(a)
 with pytest.raises(AdapterError):await cl.execute(dict(a,arguments={"path":"n","text":"2"}))
 assert calls==["n"]
 cl2=MeemeeLocalClient(reg,"tenant-a","dev1",sim.execute,ap,str(tmp_path/"d.db"))
 assert [e.event_hash for e in cl2.chain.events]==[e.event_hash for e in cl.chain.events]
 await cl2.execute(dict(a,id="a9",idempotency_key="k2"))
 assert cl2.chain.events[-1].sequence==4 and cl2.chain.events[-1].previous_hash==cl2.chain.events[-2].event_hash
 assert PairingService  # protocol module still importable

@pytest.mark.asyncio
async def test_claim_without_command_fails_closed(tmp_path):
 import sqlite3
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 a={"id":"a1","kind":"write_file","arguments":{"path":"n","text":"1"},"idempotency_key":"k"}
 d=(await cl.preview(a))["digest"]
 c=sqlite3.connect(tmp_path/"d.db");c.execute("INSERT INTO claire_adapter_claims VALUES('tenant-a','dev1','k',?,NULL,NULL,'claimed','x')",(d,));c.commit()
 r=await cl.execute(a);assert r["status"]=="indeterminate" and calls==[]


def _approve(ap, owner, kind, preview, tenant_in_payload=True, decide_as=None):
 from app.core.models import ApprovalRequest
 payload={"preview":preview}
 if tenant_in_payload:payload["tenant_id"]=owner
 r=ap.put(ApprovalRequest(id="x",module_id=21,action_type=f"claire:{kind}",payload=payload),user_id=owner)
 ap.decide(r.id,ApprovalStatus.APPROVED,user_id=owner);return r

@pytest.mark.asyncio
async def test_multitenant_approval_adversarial(tmp_path):
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 a={"id":"a","kind":"run_command","arguments":{"cmd":"ls"},"idempotency_key":"k"}
 pv=await cl.preview(a)
 # tenant-z approves an identical preview; tenant-a's adapter must not accept it
 z=_approve(ap,"tenant-z","run_command",pv)
 with pytest.raises(AdapterError):await cl.execute(a,z.id)
 # approval owned by tenant-a but whose payload names another tenant
 bad=ap.put(__import__("app.core.models",fromlist=["ApprovalRequest"]).ApprovalRequest(id="x",module_id=21,action_type="claire:run_command",payload={"tenant_id":"tenant-z","preview":pv}),user_id="tenant-a")
 ap.decide(bad.id,ApprovalStatus.APPROVED,user_id="tenant-a")
 with pytest.raises(AdapterError):await cl.execute(a,bad.id)
 # approval with no tenant_id in payload (what Service.request_environment_change stores today) is refused
 none=_approve(ap,"tenant-a","run_command",pv,tenant_in_payload=False)
 with pytest.raises(AdapterError):await cl.execute(a,none.id)
 assert calls==[]
 ok=_approve(ap,"tenant-a","run_command",pv)
 assert (await cl.execute(a,ok.id))["status"]=="completed" and calls==["ls"]
 # tenant-a's approval cannot drive a tenant-b adapter on tenant-b's device
 p=reg.create_pairing("tenant-b");paired=reg.pair(p["pairing_id"],p["code"],device_id="devB",name="b",capabilities={"run_command":{}})
 simb=StatefulDeviceSimulator("devB",paired["secret"],{"run_command":lambda st,cmd:calls.append("B"+cmd)})
 clb=MeemeeLocalClient(reg,"tenant-b","devB",simb.execute,ap,str(tmp_path/"d.db"))
 ab=dict(a,idempotency_key="kb");pvb=await clb.preview(ab)
 fresh=_approve(ap,"tenant-a","run_command",pvb)
 with pytest.raises(AdapterError):await clb.execute(ab,fresh.id)
 assert calls==["ls"]
