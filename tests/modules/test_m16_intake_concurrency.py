"""Pins for M16 intake/command races.

append_event retries a sequence-collision IntegrityError in a fresh
transaction (bounded at 3 attempts) and re-checks the event-id dedup inside
every attempt. mark_command claims a command with one conditional UPDATE, and
Service.execute claims before running the read executor, so a losing
concurrent execute never runs it. A failed executor leaves the command
claimed - retry means a fresh preview.

Establishes repository/service transaction behavior, not DB-vendor isolation
guarantees or whole-module concurrency acceptance.
"""
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.modules.m16_executive_dashboard.repository import EventRow,SqlDashboardRepository
from app.modules.m16_executive_dashboard.schemas import CommandPreview,Event
from app.modules.m16_executive_dashboard.service import Service
NOW=datetime(2026,10,7,12,0,tzinfo=timezone.utc)
def factory():
    e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(e)
    return sessionmaker(bind=e,expire_on_commit=False)
def event(eid):return Event(id=eid,sequence=0,topic="task.completed",aggregate_type="task",aggregate_id=f"a-{eid}",payload={},occurred_at=NOW)
class FailCommits:
    """Session factory whose first `fail_times` commits roll back, optionally run `on_conflict` (a concurrent intake winning the race), then raise the sequence-collision IntegrityError the loser would see."""
    def __init__(self,real,fail_times,on_conflict=None):self.real=real;self.fail_times=fail_times;self.attempts=0;self.on_conflict=on_conflict
    def begin(self):
        self.attempts+=1
        ctx=self.real.begin()
        if self.attempts<=self.fail_times:return _LosingCommit(ctx,self)
        return ctx
    def __call__(self):return self.real()
class _LosingCommit:
    def __init__(self,ctx,parent):self.ctx=ctx;self.parent=parent;self.db=None
    def __enter__(self):self.db=self.ctx.__enter__();return self.db
    def __exit__(self,exc_type,exc,tb):
        staged=[type(o).__name__ for o in self.db.new] if exc_type is None else []
        self.ctx.__exit__(Exception,Exception("roll back the conflicting attempt"),None)
        if exc_type is None:
            if self.parent.on_conflict:self.parent.on_conflict(staged)
            raise IntegrityError("INSERT INTO m16_events",{},Exception("UNIQUE constraint failed: m16_events.tenant_id, m16_events.sequence"))
        return False
def test_append_event_retries_sequence_collision_and_persists():
    flaky=FailCommits(factory(),fail_times=2)
    repo=SqlDashboardRepository("t","u",session_factory=flaky)
    saved=repo.append_event(event("e1"))
    assert saved.sequence==1 and flaky.attempts==3
    assert [e.id for e in repo.events_after(0)]==["e1"]
def test_append_event_retry_is_bounded():
    flaky=FailCommits(factory(),fail_times=10)
    repo=SqlDashboardRepository("t","u",session_factory=flaky)
    with pytest.raises(IntegrityError):repo.append_event(event("e1"))
    assert flaky.attempts==3
def test_append_event_retry_dedup_recheck_keeps_same_id_idempotent():
    real=factory()
    winner=SqlDashboardRepository("t","u",session_factory=real)
    staged_log=[]
    def concurrent_same_id_intake(staged):
        # The loser's first attempt staged an insert (its dedup check missed),
        # then this concurrent intake of the same id commits first.
        staged_log.append(staged)
        winner.append_event(event("e1"))
    flaky=FailCommits(real,fail_times=1,on_conflict=concurrent_same_id_intake)
    loser=SqlDashboardRepository("t","u",session_factory=flaky)
    saved=loser.append_event(event("e1"))
    assert staged_log==[["EventRow"]]  # the loser's dedup missed before the collision; the retry's re-check is what catches it
    assert saved.id=="e1" and saved.sequence==1
    assert [e.id for e in loser.events_after(0)]==["e1"]
def command(cid):
    now=datetime.now(timezone.utc)
    return CommandPreview(id=cid,utterance="show kpis",intent="show_kpis",parameters={},plan=[],read_only=True,confidence=0.9,expires_at=now+timedelta(minutes=5),created_at=now)
def test_mark_command_second_claim_loses_and_first_marker_survives():
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_command(command("c1"))
    first=datetime.now(timezone.utc)
    repo.mark_command("c1",first)
    with pytest.raises(RuntimeError,match="command already executed"):
        repo.mark_command("c1",datetime.now(timezone.utc))
    row,_=repo.get_command("c1")
    assert row.executed_at==first.replace(tzinfo=None)
def test_mark_command_scoped_to_own_tenant_and_actor():
    real=factory()
    mine=SqlDashboardRepository("t","u",session_factory=real)
    other=SqlDashboardRepository("t2","u2",session_factory=real)
    mine.save_command(command("c1"))
    with pytest.raises(RuntimeError,match="command already executed"):
        other.mark_command("c1",datetime.now(timezone.utc))
    row,_=mine.get_command("c1")
    assert row.executed_at is None
class StaleReadRepo:
    """Adds the read a concurrent execute took before the winner claimed: get_command reports executed_at=None while the stored row is already claimed."""
    def __init__(self,repo):self._repo=repo
    def get_command(self,cid):
        _,preview=self._repo.get_command(cid)
        return type("StaleRow",(),{"executed_at":None})(),preview
    def __getattr__(self,name):return getattr(self._repo,name)
def test_losing_concurrent_execute_never_runs_the_executor():
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_command(command("c1"))
    repo.mark_command("c1",datetime.now(timezone.utc))  # the winning execute claimed it
    calls=[]
    service=Service(StaleReadRepo(repo),executor=lambda intent,params:calls.append(intent) or {})
    with pytest.raises(RuntimeError,match="command already executed"):
        service.execute("c1")
    assert calls==[]
def test_failed_executor_leaves_command_claimed():
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_command(command("c1"))
    def boom(intent,params):raise ValueError("read failed")
    service=Service(repo,executor=boom)
    with pytest.raises(ValueError,match="read failed"):service.execute("c1")
    row,_=repo.get_command("c1")
    assert row.executed_at is not None  # claim-before-execute: retry means a fresh preview
def test_default_sqlite_execute_compares_expiry_without_typeerror():
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_command(command("c1"))
    service=Service(repo,executor=lambda intent,params:{"ok":True})
    assert service.execute("c1")["status"]=="completed"  # naive sqlite expiry read is coerced, no TypeError
def test_successful_execute_claims_then_runs_executor_once():
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_command(command("c1"))
    calls=[]
    service=Service(repo,executor=lambda intent,params:calls.append(intent) or {"ok":True})
    assert service.execute("c1")=={"status":"completed","result":{"ok":True}}
    assert calls==["show_kpis"]
    with pytest.raises(RuntimeError,match="command already executed"):service.execute("c1")
    assert calls==["show_kpis"]
def test_intake_preserves_offset_instants_and_rejects_naive():
    from pydantic import ValidationError
    from app.modules.m16_executive_dashboard.schemas import EventIn
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    service=Service(repo)
    # 15:00+05:30 is 09:30Z: the stored/read instant must stay 09:30Z, not be relabeled 15:00Z.
    service.intake(EventIn(topic="task.completed",aggregate_type="task",aggregate_id="a1",occurred_at=datetime(2026,10,7,15,0,tzinfo=timezone(timedelta(hours=5,minutes=30)))))
    (read,)=repo.events_after(0)
    assert read.occurred_at==datetime(2026,10,7,9,30,tzinfo=timezone.utc)
    with pytest.raises(ValidationError,match="timezone-aware"):
        EventIn(topic="task.completed",aggregate_type="task",aggregate_id="a2",occurred_at=datetime(2026,10,7,15,0))
def test_read_boundary_coercion_pins():
    from app.modules.m16_executive_dashboard.schemas import AgentHeartbeat,AgentState,Approval
    aware=datetime(2026,10,7,9,30,tzinfo=timezone.utc)
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_approval(Approval(id="ap1",module_id=16,action_type="send",title="t",summary="s",risk="medium",evidence={},proposed_payload={},created_at=aware,expires_at=aware+timedelta(hours=1)))
    assert repo.pending_approvals()[0].expires_at==aware+timedelta(hours=1)  # same instant, tz-attached
    repo.heartbeat(AgentHeartbeat(module_id=16,agent_id="w1",state=AgentState.RUNNING,current_task=None,detail={}),aware)
    assert repo.list_agents()[0].last_heartbeat==aware
    assert repo.snapshot().generated_at.tzinfo is not None
