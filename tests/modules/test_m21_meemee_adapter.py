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
 ap=ApprovalStore();cl=MeemeeLocalClient(reg,owner,"dev1",sim.execute,ap)
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
 with pytest.raises(AdapterError):await cl.execute(a,req.id)  # still pending
 ap.decide(req.id,ApprovalStatus.APPROVED)
 other=dict(a,arguments={"cmd":"rm x"},idempotency_key="k3")
 with pytest.raises(AdapterError):await cl.execute(other,req.id)  # approval is for a different action
 r=await s.local_action(g.id,a,req.id);assert r["result"]=={"ran":"ls"} and calls==["ls"]
 with pytest.raises(AdapterError):await cl.execute(dict(a,idempotency_key="k4"),req.id)  # reuse

@pytest.mark.asyncio
async def test_owner_scope_revoke_undeclared(tmp_path):
 reg,sim,ap,cl,s,g,calls=rig(tmp_path)
 bad=MeemeeLocalClient(reg,"tenant-b","dev1",sim.execute,ap)
 with pytest.raises(AdapterError):await bad.capabilities()
 with pytest.raises(ValueError):await s.local_action(g.id,{"kind":"click","idempotency_key":"z"})  # not granted
 reg.revoke("tenant-a","dev1")
 with pytest.raises(AdapterError):await s.local_action(g.id,{"kind":"write_file","arguments":{"path":"p","text":"t"},"idempotency_key":"k9"})
