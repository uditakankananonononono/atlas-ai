"""Pins for M16 intake/command races.

The append_event retry is bounded (exactly 3 attempts) and re-checks the
event-id dedup inside every attempt, so a concurrent intake of the same id
stays idempotent. mark_command claims a command with one conditional UPDATE:
a second claim loses instead of overwriting the first execution marker.

Establishes transaction/retry behavior of the repository, not DB-vendor
isolation guarantees or whole-module concurrency acceptance.
"""
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository
from app.modules.m16_executive_dashboard.schemas import CommandPreview,Event
NOW=datetime(2026,10,7,12,0,tzinfo=timezone.utc)
def factory():
    e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(e)
    return sessionmaker(bind=e,expire_on_commit=False)
def event(eid):return Event(id=eid,sequence=0,topic="task.completed",aggregate_type="task",aggregate_id=f"a-{eid}",payload={},occurred_at=NOW)
class FailCommits:
    """Session factory whose first `fail_times` commits raise the sequence-collision IntegrityError a concurrent intake would cause."""
    def __init__(self,real,fail_times):self.real=real;self.fail_times=fail_times;self.attempts=0
    def begin(self):
        self.attempts+=1
        ctx=self.real.begin()
        if self.attempts<=self.fail_times:return _RaiseOnCommit(ctx)
        return ctx
    def __call__(self):return self.real()
class _RaiseOnCommit:
    def __init__(self,ctx):self.ctx=ctx
    def __enter__(self):return self.ctx.__enter__()
    def __exit__(self,exc_type,exc,tb):
        self.ctx.__exit__(Exception,Exception("roll back the conflicting attempt"),None)
        if exc_type is None:raise IntegrityError("INSERT INTO m16_events",{},Exception("UNIQUE constraint failed: m16_events.tenant_id, m16_events.sequence"))
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
    real=factory();flaky=FailCommits(real,fail_times=1)
    repo=SqlDashboardRepository("t","u",session_factory=flaky)
    winner=SqlDashboardRepository("t","u",session_factory=real)
    # The concurrent intake of the same id commits first; the wrapper fails the
    # loser's first commit, so the retry's dedup re-check must return the
    # winner's event instead of inserting a duplicate row.
    saved_by_winner=winner.append_event(event("e1"))
    saved=repo.append_event(event("e1"))
    assert flaky.attempts==2
    assert saved.id=="e1" and saved.sequence==saved_by_winner.sequence
    assert len(repo.events_after(0))==1
def command(cid):return CommandPreview(id=cid,utterance="show kpis",intent="show_kpis",parameters={},plan=[],read_only=True,confidence=0.9,expires_at=NOW+timedelta(minutes=5),created_at=NOW)
def test_mark_command_second_claim_loses_and_first_marker_survives():
    repo=SqlDashboardRepository("t","u",session_factory=factory())
    repo.save_command(command("c1"))
    first=NOW+timedelta(seconds=1)
    repo.mark_command("c1",first)
    with pytest.raises(RuntimeError,match="command already executed"):
        repo.mark_command("c1",NOW+timedelta(seconds=2))
    row,_=repo.get_command("c1")
    assert row.executed_at==first.replace(tzinfo=None)
def test_mark_command_scoped_to_own_tenant_and_actor():
    real=factory()
    mine=SqlDashboardRepository("t","u",session_factory=real)
    other=SqlDashboardRepository("t2","u2",session_factory=real)
    mine.save_command(command("c1"))
    with pytest.raises(RuntimeError,match="command already executed"):
        other.mark_command("c1",NOW)
    row,_=mine.get_command("c1")
    assert row.executed_at is None
