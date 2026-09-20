from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from typing import Any
import secrets,time
class RunStatus(str,Enum): RUNNING="running"; AWAITING_APPROVAL="awaiting_approval"; COMPLETE="complete"; FAILED="failed"
class ActionType(str,Enum): NAVIGATE="navigate"; CLICK="click"; FILL="fill"; EXTRACT="extract"; SCREENSHOT="screenshot"; SUBMIT="submit"
@dataclass
class AuditEvent:
    tenant_id:str; run_id:str; action:ActionType; payload:dict[str,Any]; occurred_at:float=field(default_factory=time.time)
@dataclass
class ApprovalRequest:
    id:str; tenant_id:str; run_id:str; action:ActionType; target:str; snapshot_path:str; form_values:dict[str,str]; digest:str; status:str="pending"
    @classmethod
    def pending(cls,**kwargs): return cls(id=secrets.token_urlsafe(18),status="pending",**kwargs)
