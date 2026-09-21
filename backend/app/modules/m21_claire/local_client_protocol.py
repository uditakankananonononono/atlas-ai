"""Optional capability endpoint for Claire, whose primary surface is inside Atlas."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime,timezone,timedelta
from typing import Any
import hashlib,hmac,json,secrets,uuid

@dataclass
class PairingChallenge:
 code:str;server_nonce:str;expires_at:datetime
@dataclass
class PairedDevice:
 id:str;name:str;certificate_fingerprint:str;capabilities:set[str];revoked:bool=False
@dataclass
class LocalAction:
 id:str;session_id:str;goal_id:str;kind:str;arguments:dict[str,Any];requires_approval:bool;idempotency_key:str
@dataclass
class AuditEvent:
 sequence:int;device_id:str;action_id:str;phase:str;payload:dict[str,Any];previous_hash:str;event_hash:str

class PairingService:
 """Reference handshake state; production issues pinned mTLS client certificates."""
 def __init__(self):self.pending={};self.devices={}
 def challenge(self,ttl_seconds:int=300):
  code=f"{secrets.randbelow(1_000_000):06d}";nonce=secrets.token_urlsafe(32);c=PairingChallenge(code,nonce,datetime.now(timezone.utc)+timedelta(seconds=ttl_seconds));self.pending[nonce]=c;return c
 def confirm(self,server_nonce:str,code:str,name:str,certificate_fingerprint:str,capabilities:set[str]):
  challenge=self.pending.pop(server_nonce)
  if challenge.expires_at<=datetime.now(timezone.utc):raise ValueError("pairing challenge expired")
  if not name.strip() or not certificate_fingerprint.strip():raise ValueError("device name and certificate fingerprint are required")
  if not capabilities:raise ValueError("at least one owner-granted capability is required")
  if not hmac.compare_digest(challenge.code,code):raise ValueError("pairing code mismatch")
  device=PairedDevice(str(uuid.uuid4()),name,certificate_fingerprint,capabilities);self.devices[device.id]=device;return device
 def revoke(self,device_id:str):self.devices[device_id].revoked=True

class AuditChain:
 def __init__(self,device_id:str):self.device_id=device_id;self.events=[]
 def append(self,action_id:str,phase:str,payload:dict[str,Any]):
  prev=self.events[-1].event_hash if self.events else "0"*64
  body=json.dumps({"sequence":len(self.events)+1,"device_id":self.device_id,"action_id":action_id,"phase":phase,"payload":payload,"previous_hash":prev},sort_keys=True,default=str)
  event=AuditEvent(len(self.events)+1,self.device_id,action_id,phase,payload,prev,hashlib.sha256(body.encode()).hexdigest());self.events.append(event);return event
