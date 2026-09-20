from __future__ import annotations
from datetime import datetime
from sqlalchemy import JSON,Boolean,DateTime,Float,Integer,String,Text,UniqueConstraint,func,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import *
class EventRow(Base):
    __tablename__="m16_events";__table_args__=(UniqueConstraint("tenant_id","sequence",name="uq_m16_sequence"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));sequence:Mapped[int]=mapped_column(Integer);topic:Mapped[str]=mapped_column(String(120));aggregate_type:Mapped[str]=mapped_column(String(80));aggregate_id:Mapped[str]=mapped_column(String(200));payload:Mapped[dict]=mapped_column(JSON);occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class SnapshotRow(Base):
    __tablename__="m16_snapshots";tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);version:Mapped[int]=mapped_column(Integer);last_sequence:Mapped[int]=mapped_column(Integer);data:Mapped[dict]=mapped_column(JSON);generated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ApprovalRow(Base):
    __tablename__="m16_approvals";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_approval"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));module_id:Mapped[int]=mapped_column(Integer);action_type:Mapped[str]=mapped_column(String(120));title:Mapped[str]=mapped_column(String(500));summary:Mapped[str]=mapped_column(Text);risk:Mapped[str]=mapped_column(String(20));evidence:Mapped[dict]=mapped_column(JSON);proposed_payload:Mapped[dict]=mapped_column(JSON);state:Mapped[str]=mapped_column(String(20));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);reviewed_by:Mapped[str|None]=mapped_column(String(120),nullable=True);review_note:Mapped[str|None]=mapped_column(Text,nullable=True)
class CommandRow(Base):
    __tablename__="m16_commands";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120));id:Mapped[str]=mapped_column(String(36),index=True);utterance:Mapped[str]=mapped_column(Text);intent:Mapped[str]=mapped_column(String(120));parameters:Mapped[dict]=mapped_column(JSON);plan:Mapped[list]=mapped_column(JSON);read_only:Mapped[bool]=mapped_column(Boolean);confidence:Mapped[float]=mapped_column(Float);expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));executed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class AgentStatusRow(Base):
    __tablename__="m16_agent_status";__table_args__=(UniqueConstraint("tenant_id","agent_id",name="uq_m16_agent"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);module_id:Mapped[int]=mapped_column(Integer,index=True);agent_id:Mapped[str]=mapped_column(String(120));state:Mapped[str]=mapped_column(String(20));current_task:Mapped[str|None]=mapped_column(String(500),nullable=True);detail:Mapped[dict]=mapped_column(JSON);last_heartbeat:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class KpiPointRow(Base):
    __tablename__="m16_kpi_points";
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);kpi_id:Mapped[str]=mapped_column(String(80));window_hours:Mapped[int]=mapped_column(Integer);value:Mapped[float]=mapped_column(Float);recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
class KpiDefinitionRow(Base):
    __tablename__="m16_kpi_definitions";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_kpi_definition"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(80));label:Mapped[str]=mapped_column(String(120));unit:Mapped[str]=mapped_column(String(20));topics:Mapped[list]=mapped_column(JSON);window_hours:Mapped[int|None]=mapped_column(Integer,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
def _event(r):return Event(id=r.id,sequence=r.sequence,topic=r.topic,aggregate_type=r.aggregate_type,aggregate_id=r.aggregate_id,payload=r.payload,occurred_at=r.occurred_at)
def _approval(r):return Approval(id=r.id,module_id=r.module_id,action_type=r.action_type,title=r.title,summary=r.summary,risk=r.risk,evidence=r.evidence,proposed_payload=r.proposed_payload,state=ApprovalState(r.state),created_at=r.created_at,expires_at=r.expires_at,reviewed_at=r.reviewed_at)
def _command(r):return CommandPreview(id=r.id,utterance=r.utterance,intent=r.intent,parameters=r.parameters,plan=r.plan,read_only=r.read_only,confidence=r.confidence,expires_at=r.expires_at,created_at=r.created_at)
class SqlDashboardRepository:
    def __init__(self,tenant_id,actor_id,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.actor_id=actor_id;self.sessions=session_factory;Base.metadata.create_all(engine)
    def append_event(self,e:Event):
        with self.sessions.begin() as db:
            existing=db.scalar(select(EventRow).where(EventRow.tenant_id==self.tenant_id,EventRow.id==e.id))
            if existing:return _event(existing)
            max_seq=db.scalar(select(func.coalesce(func.max(EventRow.sequence),0)).where(EventRow.tenant_id==self.tenant_id));e.sequence=max_seq+1;db.add(EventRow(tenant_id=self.tenant_id,**e.model_dump()));return e
    def events_after(self,cursor,limit=500):
        with self.sessions() as db:return [_event(r) for r in db.scalars(select(EventRow).where(EventRow.tenant_id==self.tenant_id,EventRow.sequence>cursor).order_by(EventRow.sequence).limit(limit))]
    def snapshot(self):
        with self.sessions.begin() as db:
            r=db.get(SnapshotRow,self.tenant_id)
            if not r:r=SnapshotRow(tenant_id=self.tenant_id,version=0,last_sequence=0,data={"metrics":{},"timeline":[],"alerts":[],"freshness":{}},generated_at=datetime.utcnow());db.add(r);db.flush()
            return Snapshot(version=r.version,last_sequence=r.last_sequence,data=r.data,generated_at=r.generated_at)
    def pending_approvals(self):
        with self.sessions() as db:return [_approval(r) for r in db.scalars(select(ApprovalRow).where(ApprovalRow.tenant_id==self.tenant_id,ApprovalRow.state==ApprovalState.PENDING.value).order_by(ApprovalRow.created_at))]
    def save_approval(self,a:Approval):
        with self.sessions.begin() as db:db.add(ApprovalRow(tenant_id=self.tenant_id,reviewed_by=None,review_note=None,**a.model_dump(mode="python")))
        return a
    def decide(self,aid,state,note,at):
        with self.sessions.begin() as db:r=db.scalar(select(ApprovalRow).where(ApprovalRow.tenant_id==self.tenant_id,ApprovalRow.id==aid,ApprovalRow.state==ApprovalState.PENDING.value));
        if not r:return None
        with self.sessions.begin() as db:r=db.scalar(select(ApprovalRow).where(ApprovalRow.tenant_id==self.tenant_id,ApprovalRow.id==aid));r.state=state.value;r.reviewed_at=at;r.reviewed_by=self.actor_id;r.review_note=note;db.flush();return _approval(r)
    def save_command(self,c):
        with self.sessions.begin() as db:db.add(CommandRow(tenant_id=self.tenant_id,actor_id=self.actor_id,executed_at=None,**c.model_dump()))
        return c
    def get_command(self,cid):
        with self.sessions() as db:r=db.scalar(select(CommandRow).where(CommandRow.tenant_id==self.tenant_id,CommandRow.actor_id==self.actor_id,CommandRow.id==cid));return (r,_command(r)) if r else (None,None)
    def mark_command(self,cid,at):
        with self.sessions.begin() as db:r=db.scalar(select(CommandRow).where(CommandRow.tenant_id==self.tenant_id,CommandRow.actor_id==self.actor_id,CommandRow.id==cid));r.executed_at=at
    def heartbeat(self,data,at):
        with self.sessions.begin() as db:
            r=db.scalar(select(AgentStatusRow).where(AgentStatusRow.tenant_id==self.tenant_id,AgentStatusRow.agent_id==data.agent_id))
            if r:r.module_id=data.module_id;r.state=data.state.value;r.current_task=data.current_task;r.detail=data.detail;r.last_heartbeat=at
            else:db.add(AgentStatusRow(tenant_id=self.tenant_id,module_id=data.module_id,agent_id=data.agent_id,state=data.state.value,current_task=data.current_task,detail=data.detail,last_heartbeat=at))
        return AgentStatus(**data.model_dump(),last_heartbeat=at)
    def list_agents(self):
        with self.sessions() as db:return [AgentStatus(module_id=r.module_id,agent_id=r.agent_id,state=AgentState(r.state),current_task=r.current_task,detail=r.detail,last_heartbeat=r.last_heartbeat) for r in db.scalars(select(AgentStatusRow).where(AgentStatusRow.tenant_id==self.tenant_id).order_by(AgentStatusRow.module_id))]
    def approvals_reviewed_since(self,since):
        with self.sessions() as db:return [_approval(r) for r in db.scalars(select(ApprovalRow).where(ApprovalRow.tenant_id==self.tenant_id,ApprovalRow.reviewed_at.isnot(None),ApprovalRow.reviewed_at>=since).order_by(ApprovalRow.reviewed_at))]
    def events_between(self,start,end,limit=2000):
        with self.sessions() as db:return [_event(r) for r in db.scalars(select(EventRow).where(EventRow.tenant_id==self.tenant_id,EventRow.occurred_at>=start,EventRow.occurred_at<=end).order_by(EventRow.sequence).limit(limit))]
    def event_by_id(self,event_id):
        with self.sessions() as db:
            r=db.scalar(select(EventRow).where(EventRow.tenant_id==self.tenant_id,EventRow.id==event_id))
            return _event(r) if r else None
    def approval_by_id(self,approval_id):
        with self.sessions() as db:
            r=db.scalar(select(ApprovalRow).where(ApprovalRow.tenant_id==self.tenant_id,ApprovalRow.id==approval_id))
            return _approval(r) if r else None
    def update_snapshot(self,data,last_sequence):
        with self.sessions.begin() as db:
            r=db.get(SnapshotRow,self.tenant_id)
            if not r:r=SnapshotRow(tenant_id=self.tenant_id,version=0,last_sequence=0,data={},generated_at=datetime.utcnow());db.add(r);db.flush()
            assert last_sequence>=r.last_sequence,"snapshot projection cannot move backwards"
            r.data=data;r.last_sequence=last_sequence;r.version=r.version+1;r.generated_at=datetime.utcnow();db.flush()
            return Snapshot(version=r.version,last_sequence=r.last_sequence,data=r.data,generated_at=r.generated_at)
    def record_kpi_points(self,points,at):
        with self.sessions.begin() as db:
            for kpi_id,window_hours,value in points:db.add(KpiPointRow(tenant_id=self.tenant_id,kpi_id=kpi_id,window_hours=window_hours,value=float(value),recorded_at=at))
    def kpi_value_at_or_before(self,kpi_id,window_hours,moment):
        with self.sessions() as db:
            return db.scalar(select(KpiPointRow.value).where(KpiPointRow.tenant_id==self.tenant_id,KpiPointRow.kpi_id==kpi_id,KpiPointRow.window_hours==window_hours,KpiPointRow.recorded_at<=moment).order_by(KpiPointRow.recorded_at.desc(),KpiPointRow.pk.desc()).limit(1))
    def save_kpi_definition(self,d,at):
        with self.sessions.begin() as db:
            r=db.scalar(select(KpiDefinitionRow).where(KpiDefinitionRow.tenant_id==self.tenant_id,KpiDefinitionRow.id==d.id))
            if r:r.label=d.label;r.unit=d.unit;r.topics=list(d.topics);r.window_hours=d.window_hours
            else:db.add(KpiDefinitionRow(tenant_id=self.tenant_id,id=d.id,label=d.label,unit=d.unit,topics=list(d.topics),window_hours=d.window_hours,created_at=at))
        return KpiDefinitionOut(**d.model_dump(),created_at=at)
    def list_kpi_definitions(self):
        with self.sessions() as db:return [KpiDefinitionOut(id=r.id,label=r.label,unit=r.unit,topics=list(r.topics),window_hours=r.window_hours,created_at=r.created_at) for r in db.scalars(select(KpiDefinitionRow).where(KpiDefinitionRow.tenant_id==self.tenant_id).order_by(KpiDefinitionRow.id))]
    def delete_kpi_definition(self,kpi_id):
        with self.sessions.begin() as db:
            r=db.scalar(select(KpiDefinitionRow).where(KpiDefinitionRow.tenant_id==self.tenant_id,KpiDefinitionRow.id==kpi_id))
            if not r:return False
            db.delete(r);return True
