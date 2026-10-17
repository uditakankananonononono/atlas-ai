"""Durable tenant-scoped idea runs for Module 19.
Replaces the process-local run map: tenant-scoped rows, append-only events, optimistic
version checks, budget reservation as a conditional update (CAS), and queue priority.
Expired or unknown work is never silently retried (durable_jobs.py semantics)."""
from __future__ import annotations
import math
from datetime import datetime,timezone
from sqlalchemy import DateTime,Float,Integer,JSON,String,select,update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import RunOut,Stage

def _now():return datetime.now(timezone.utc)

class RunRow(Base):
    __tablename__="m19_runs"
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True,unique=True);state:Mapped[str]=mapped_column(String(30));stage:Mapped[str]=mapped_column(String(30),index=True);payload:Mapped[dict]=mapped_column(JSON);spent:Mapped[float]=mapped_column(Float);reserved:Mapped[float]=mapped_column(Float);budget_cap:Mapped[float]=mapped_column(Float);priority:Mapped[int]=mapped_column(Integer);version:Mapped[int]=mapped_column(Integer);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class RunEventRow(Base):
    __tablename__="m19_run_events"
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);run_id:Mapped[str]=mapped_column(String(36),index=True);kind:Mapped[str]=mapped_column(String(40));version:Mapped[int]=mapped_column(Integer);payload:Mapped[dict]=mapped_column(JSON);at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

def _run(r):return RunOut.model_validate({**r.payload,"id":r.id,"state":r.state,"stage":r.stage,"spent":r.spent,"reserved":r.reserved,"budget_cap":r.budget_cap})
def _payload(x):return x.model_dump(mode="json",exclude={"id","state","stage","spent","reserved","budget_cap"})

class SqlRunStore:
    def __init__(self,session_factory:sessionmaker=SessionLocal):self.sessions=session_factory;Base.metadata.create_all(engine)
    def create(self,tenant_id:str,run:RunOut,priority:int=0)->RunOut:
        at=_now();row=RunRow(tenant_id=tenant_id,id=run.id,state=run.state,stage=run.stage.value,payload=_payload(run),spent=run.spent,reserved=run.reserved,budget_cap=run.budget_cap,priority=priority,version=1,created_at=at,updated_at=at)
        try:
            with self.sessions.begin() as db:
                db.add(row);db.add(RunEventRow(tenant_id=tenant_id,run_id=run.id,kind="created",version=1,payload={},at=at))
        except IntegrityError:raise RuntimeError("run id unavailable") from None
        return run
    def get(self,tenant_id:str,run_id:str)->RunOut|None:
        with self.sessions() as db:
            r=db.scalar(select(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id));return _run(r) if r else None
    def list_events(self,tenant_id:str,run_id:str)->list[RunEventRow]:
        with self.sessions() as db:return [r for r in db.scalars(select(RunEventRow).where(RunEventRow.tenant_id==tenant_id,RunEventRow.run_id==run_id).order_by(RunEventRow.pk))]
    def reserve_budget(self,tenant_id:str,run_id:str,cost:float,new_state:str,new_stage:Stage,expected_stages:list[Stage]|None=None)->RunOut:
        """CAS: reserve only while spent+reserved+cost<=budget_cap AND (when given) the current
        stage is one of expected_stages; one conditional statement. Optimistic expected-stage check."""
        if not math.isfinite(cost) or cost<0:raise ValueError("cost must be finite and non-negative")
        conds=[RunRow.tenant_id==tenant_id,RunRow.id==run_id,RunRow.spent+RunRow.reserved+cost<=RunRow.budget_cap]
        if expected_stages is not None:conds.append(RunRow.stage.in_([s.value for s in expected_stages]))
        with self.sessions.begin() as db:
            res=db.execute(update(RunRow).where(*conds).values(reserved=RunRow.reserved+cost,state=new_state,stage=new_stage.value,version=RunRow.version+1,updated_at=_now()).execution_options(synchronize_session=False)).rowcount
            if res!=1:
                r=db.scalar(select(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id))
                if r is None:raise KeyError(run_id)
                if expected_stages is not None and r.stage not in [s.value for s in expected_stages]:raise ValueError(f"expected stage {[s.value for s in expected_stages]}, found {r.stage}")
                raise ValueError("budget cap exceeded")
            r=db.scalar(select(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id))
            db.add(RunEventRow(tenant_id=tenant_id,run_id=run_id,kind="budget_reserved",version=r.version,payload={"cost":cost},at=_now()))
            return _run(r)
    def next_queued(self,tenant_id:str,state:str="queued")->RunOut|None:
        """Queue-priority selector: highest priority first, FIFO tiebreak (created_at, id).
        Read-only selector; no worker or lease semantics are implied."""
        with self.sessions() as db:
            r=db.scalar(select(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.state==state).order_by(RunRow.priority.desc(),RunRow.created_at,RunRow.id).limit(1));return _run(r) if r else None
    def release_budget(self,tenant_id:str,run_id:str,cost:float,expected_version:int,new_state:str,new_stage:Stage)->RunOut:
        """Explicit grounded release only - never called automatically on unknown outcomes.
        Conditional on expected_version and reserved>=cost; version bump and event are atomic."""
        if not math.isfinite(cost) or cost<0:raise ValueError("cost must be finite and non-negative")
        with self.sessions.begin() as db:
            res=db.execute(update(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id,RunRow.version==expected_version,RunRow.reserved>=cost).values(reserved=RunRow.reserved-cost,state=new_state,stage=new_stage.value,version=expected_version+1,updated_at=_now()).execution_options(synchronize_session=False)).rowcount
            if res!=1:
                if db.scalar(select(RunRow.pk).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id)) is None:raise LookupError(run_id)
                raise RuntimeError("run changed or insufficient reservation; refresh before retrying")
            r=db.scalar(select(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id))
            db.add(RunEventRow(tenant_id=tenant_id,run_id=run_id,kind="budget_released",version=r.version,payload={"cost":cost},at=_now()))
            return _run(r)
    def transition(self,tenant_id:str,run_id:str,expected_version:int,changes:dict,event_kind:str)->RunOut:
        """Optimistic expected-version conditional update plus one append-only event, atomically."""
        with self.sessions.begin() as db:
            res=db.execute(update(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id,RunRow.version==expected_version).values(**changes,version=expected_version+1,updated_at=_now()).execution_options(synchronize_session=False)).rowcount
            if res!=1:
                if db.scalar(select(RunRow.pk).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id)) is None:raise LookupError(run_id)
                raise RuntimeError("run changed; refresh before retrying")
            r=db.scalar(select(RunRow).where(RunRow.tenant_id==tenant_id,RunRow.id==run_id))
            db.add(RunEventRow(tenant_id=tenant_id,run_id=run_id,kind=event_kind,version=r.version,payload={},at=_now()))
            return _run(r)

class InMemoryRunStore:
    """Explicit test-injection double for the SqlRunStore surface. Never the production default."""
    def __init__(self):from threading import RLock;self._lock=RLock();self._runs={};self._events={};self._prio={}
    def create(self,tenant_id,run,priority=0):
        with self._lock:
            if (tenant_id,run.id) in self._runs:raise RuntimeError("run id unavailable")
            self._runs[(tenant_id,run.id)]=run.model_copy(deep=True);self._events.setdefault((tenant_id,run.id),[("created",1)]);self._prio[(tenant_id,run.id)]=priority;return run
    def get(self,tenant_id,run_id):
        with self._lock:return self._runs.get((tenant_id,run_id))
    def list_events(self,tenant_id,run_id):
        with self._lock:return list(self._events.get((tenant_id,run_id),[]))
    def release_budget(self,tenant_id,run_id,cost,expected_version,new_state,new_stage):
        with self._lock:
            run=self._runs.get((tenant_id,run_id))
            if run is None:raise LookupError(run_id)
            if not (cost==cost) or cost in (float("inf"),float("-inf")) or cost<0:raise ValueError("cost must be finite and non-negative")
            if run.reserved<cost:raise RuntimeError("insufficient reservation")
            run.reserved-=cost;run.state=new_state;run.stage=new_stage
            self._events.setdefault((tenant_id,run_id),[]).append(("budget_released",len(self._events.get((tenant_id,run_id),[]))+1));return run
    def reserve_budget(self,tenant_id,run_id,cost,new_state,new_stage,expected_stages=None):
        with self._lock:
            run=self._runs.get((tenant_id,run_id))
            if run is None:raise KeyError(run_id)
            if not (cost==cost) or cost in (float("inf"),float("-inf")) or cost<0:raise ValueError("cost must be finite and non-negative")
            if expected_stages is not None and run.stage not in expected_stages:raise ValueError("expected stage mismatch")
            if run.spent+run.reserved+cost>run.budget_cap:raise ValueError("budget cap exceeded")
            run.reserved+=cost;run.state=new_state;run.stage=new_stage
            self._events.setdefault((tenant_id,run_id),[]).append(("budget_reserved",len(self._events.get((tenant_id,run_id),[]))+1));return run
    def next_queued(self,tenant_id,state="queued"):
        with self._lock:
            xs=[r for (t,_),r in self._runs.items() if t==tenant_id and r.state==state]
            xs.sort(key=lambda r:-self._prio.get((tenant_id,r.id),0));return xs[0] if xs else None
    def transition(self,tenant_id,run_id,expected_version,changes,event_kind):raise NotImplementedError("test double covers create/get/reserve/release only")
