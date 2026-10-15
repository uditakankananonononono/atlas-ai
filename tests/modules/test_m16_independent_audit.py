from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
from app.modules.m16_executive_dashboard.schemas import Approval,ApprovalState

def test_offset_instant_decision_grid():
 t=datetime(2026,10,15,10,0,tzinfo=timezone.utc)
 for minutes in range(-720,841,60):
  for delta in [-1000000,-1,0,1,1000000]:
   r=SqlDashboardRepository(uuid4().hex,'actor');expiry=t.astimezone(timezone(timedelta(minutes=minutes)))
   a=Approval(id=uuid4().hex,module_id=16,action_type='x',title='t',summary='s',created_at=t,expires_at=expiry);r.save_approval(a)
   if delta>0:
    with pytest.raises(RuntimeError,match='approval expired'):r.decide(a.id,ApprovalState.APPROVED,None,t+timedelta(microseconds=delta))
    assert r.approval_by_id(a.id).state==ApprovalState.PENDING
   else:assert r.decide(a.id,ApprovalState.APPROVED,None,t+timedelta(microseconds=delta)).state==ApprovalState.APPROVED
   assert a.expires_at==expiry

def test_tenant_and_repeated_decisions():
 t=datetime(2026,10,15,tzinfo=timezone.utc);r=SqlDashboardRepository(uuid4().hex,'actor');a=Approval(id=uuid4().hex,module_id=16,action_type='x',title='t',summary='s',created_at=t,expires_at=t+timedelta(days=1));r.save_approval(a)
 other=SqlDashboardRepository(uuid4().hex,'other');assert other.decide(a.id,ApprovalState.APPROVED,None,t) is None
 assert r.approval_by_id(a.id).state==ApprovalState.PENDING
 assert r.decide(a.id,ApprovalState.REJECTED,'no',t).state==ApprovalState.REJECTED
 assert r.decide(a.id,ApprovalState.APPROVED,'yes',t) is None

def test_legacy_naive_dates_are_still_interpreted_as_utc():
 t=datetime(2026,10,15);r=SqlDashboardRepository(uuid4().hex,'actor');a=Approval(id=uuid4().hex,module_id=16,action_type='x',title='t',summary='s',created_at=t,expires_at=t);r.save_approval(a)
 assert r.approval_by_id(a.id).expires_at==t.replace(tzinfo=timezone.utc)
 assert r.decide(a.id,ApprovalState.APPROVED,None,t).state==ApprovalState.APPROVED

def test_decision_offset_uses_instant_not_wall_clock():
 t=datetime(2026,10,15,10,0,tzinfo=timezone.utc)
 for hours in [-8,5.5]:
  for delta in [-1,1]:
   r=SqlDashboardRepository(uuid4().hex,'actor');a=Approval(id=uuid4().hex,module_id=16,action_type='x',title='t',summary='s',created_at=t,expires_at=t);r.save_approval(a)
   decision=(t+timedelta(seconds=delta)).astimezone(timezone(timedelta(hours=hours)))
   if delta<0:assert r.decide(a.id,ApprovalState.APPROVED,None,decision).state==ApprovalState.APPROVED
   else:
    with pytest.raises(RuntimeError,match='approval expired'):r.decide(a.id,ApprovalState.APPROVED,None,decision)
