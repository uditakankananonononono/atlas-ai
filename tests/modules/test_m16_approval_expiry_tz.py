"""M16 approval expiry-in-write and offset-instant boundary (scratch, not yet run against real deps)."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
from app.modules.m16_executive_dashboard.schemas import Approval,ApprovalState
from app.modules.m16_executive_dashboard.service import Service

IST=timezone(timedelta(hours=5,minutes=30))

def _repo():
    return SqlDashboardRepository("tenant-"+uuid4().hex,"actor")

def _approval(expires_at,created_at=None):
    return Approval(id=str(uuid4()),module_id=16,action_type="x",title="t",summary="s",created_at=created_at or datetime.now(timezone.utc),expires_at=expires_at)

def test_decide_in_write_refuses_expired_even_if_precheck_was_stale():
    r=_repo();now=datetime.now(timezone.utc)
    a=_approval(now+timedelta(seconds=30));r.save_approval(a)
    # repository called directly at a time after expiry: the write itself refuses
    with pytest.raises(RuntimeError,match="approval expired"):
        r.decide(a.id,ApprovalState.APPROVED,None,now+timedelta(minutes=5))
    # state unchanged: still pending, nothing recorded as reviewed
    assert [p.id for p in r.pending_approvals()]==[a.id]
    assert r.approvals_reviewed_since(now-timedelta(hours=1))==[]

def test_decide_valid_before_expiry_still_works_and_loser_gets_none():
    r=_repo();now=datetime.now(timezone.utc)
    a=_approval(now+timedelta(hours=1));r.save_approval(a)
    won=r.decide(a.id,ApprovalState.APPROVED,"ok",now)
    assert won.state==ApprovalState.APPROVED
    assert r.decide(a.id,ApprovalState.REJECTED,"late",now) is None

def test_decide_without_expiry_and_unknown_id():
    r=_repo();now=datetime.now(timezone.utc)
    a=_approval(None);r.save_approval(a)
    assert r.decide(a.id,ApprovalState.REJECTED,None,now+timedelta(days=400)).state==ApprovalState.REJECTED
    assert r.decide("missing",ApprovalState.APPROVED,None,now) is None

def test_expiry_boundary_is_inclusive_like_service_precheck():
    r=_repo();t=datetime.now(timezone.utc).replace(microsecond=0)
    a=_approval(t);r.save_approval(a)
    assert r.decide(a.id,ApprovalState.APPROVED,None,t).state==ApprovalState.APPROVED

def test_service_decide_expired_keeps_410_contract():
    r=_repo();now=datetime.now(timezone.utc)
    a=_approval(now-timedelta(minutes=1));r.save_approval(a)
    svc=Service(r)
    from app.modules.m16_executive_dashboard.schemas import ApprovalDecision
    with pytest.raises(RuntimeError,match="approval expired"):svc.decide(a.id,ApprovalDecision(approve=True))

def test_offset_aware_expiry_keeps_its_instant():
    r=_repo();now=datetime.now(timezone.utc).replace(microsecond=0)
    # same instant as now+2h, written with a +05:30 offset
    exp=(now+timedelta(hours=2)).astimezone(IST)
    a=_approval(exp);r.save_approval(a)
    got=next(p for p in r.pending_approvals() if p.id==a.id)
    assert got.expires_at==now+timedelta(hours=2)
    assert a.expires_at.utcoffset()==timedelta(hours=5,minutes=30)  # caller object not mutated

def test_offset_aware_expiry_in_the_past_is_expired_not_shifted_into_future():
    r=_repo();now=datetime.now(timezone.utc)
    # 1 hour ago expressed in IST: unshifted wall clock would be 5.5h later and look like the future
    exp=(now-timedelta(hours=1)).astimezone(IST)
    a=_approval(exp);r.save_approval(a)
    with pytest.raises(RuntimeError,match="approval expired"):
        r.decide(a.id,ApprovalState.APPROVED,None,now)

def test_offset_aware_created_at_and_sweep():
    r=_repo();now=datetime.now(timezone.utc).replace(microsecond=0)
    a=_approval((now-timedelta(minutes=10)).astimezone(IST),created_at=(now-timedelta(hours=1)).astimezone(IST))
    r.save_approval(a)
    flipped=r.expire_approvals_before(now)
    assert [x.id for x in flipped]==[a.id]
    assert flipped[0].created_at==now-timedelta(hours=1)
