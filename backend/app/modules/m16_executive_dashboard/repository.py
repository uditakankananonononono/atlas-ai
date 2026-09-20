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
class AlertRuleRow(Base):
    __tablename__="m16_alert_rules";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_alert_rule"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(80));kpi_id:Mapped[str]=mapped_column(String(80));comparator:Mapped[str]=mapped_column(String(8));threshold:Mapped[float]=mapped_column(Float);severity:Mapped[str]=mapped_column(String(20));message:Mapped[str|None]=mapped_column(String(300),nullable=True);cooldown_hours:Mapped[int]=mapped_column(Integer,default=1);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ViewPrefsRow(Base):
    __tablename__="m16_view_prefs";tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);layout:Mapped[dict]=mapped_column(JSON);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class WorkItemRow(Base):
    __tablename__="m16_work_items";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_work_item"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));title:Mapped[str]=mapped_column(String(300));item_type:Mapped[str]=mapped_column(String(40));status:Mapped[str]=mapped_column(String(20),index=True);estimate:Mapped[float|None]=mapped_column(Float,nullable=True);reach:Mapped[float|None]=mapped_column(Float,nullable=True);impact:Mapped[float|None]=mapped_column(Float,nullable=True);confidence:Mapped[float|None]=mapped_column(Float,nullable=True);effort:Mapped[float|None]=mapped_column(Float,nullable=True);value:Mapped[float|None]=mapped_column(Float,nullable=True);rank:Mapped[int]=mapped_column(Integer);sprint_id:Mapped[str|None]=mapped_column(String(36),nullable=True,index=True);roadmap_id:Mapped[str|None]=mapped_column(String(36),nullable=True,index=True);planned_start:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);planned_end:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class SprintRow(Base):
    __tablename__="m16_sprints";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_sprint"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));name:Mapped[str]=mapped_column(String(200));goal:Mapped[str]=mapped_column(Text);start:Mapped[datetime]=mapped_column(DateTime(timezone=True));end:Mapped[datetime]=mapped_column(DateTime(timezone=True));capacity_points:Mapped[float|None]=mapped_column(Float,nullable=True);status:Mapped[str]=mapped_column(String(20));closed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class CeremonyRow(Base):
    __tablename__="m16_ceremonies";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_ceremony"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));sprint_id:Mapped[str]=mapped_column(String(36),index=True);kind:Mapped[str]=mapped_column(String(20));scheduled_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));notes:Mapped[str]=mapped_column(Text);action_items:Mapped[list]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class RetrospectiveRow(Base):
    __tablename__="m16_retrospectives";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_retro"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));sprint_id:Mapped[str]=mapped_column(String(36),index=True);went_well:Mapped[list]=mapped_column(JSON);didnt_go_well:Mapped[list]=mapped_column(JSON);action_items:Mapped[list]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ExperimentRow(Base):
    __tablename__="m16_experiments";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_experiment"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));name:Mapped[str]=mapped_column(String(200));hypothesis:Mapped[str]=mapped_column(Text);metric:Mapped[str]=mapped_column(String(120));kind:Mapped[str]=mapped_column(String(20));variants:Mapped[list]=mapped_column(JSON);status:Mapped[str]=mapped_column(String(20));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class RoadmapRow(Base):
    __tablename__="m16_roadmaps";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_roadmap"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));name:Mapped[str]=mapped_column(String(200));horizon_start:Mapped[datetime]=mapped_column(DateTime(timezone=True));horizon_end:Mapped[datetime]=mapped_column(DateTime(timezone=True));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
def _work_item(r):return WorkItemOut(id=r.id,title=r.title,item_type=r.item_type,status=r.status,estimate=r.estimate,reach=r.reach,impact=r.impact,confidence=r.confidence,effort=r.effort,value=r.value,rank=r.rank,sprint_id=r.sprint_id,roadmap_id=r.roadmap_id,planned_start=r.planned_start,planned_end=r.planned_end,created_at=r.created_at,updated_at=r.updated_at,completed_at=r.completed_at)
def _sprint(r):return SprintOut(id=r.id,name=r.name,goal=r.goal,start=r.start,end=r.end,capacity_points=r.capacity_points,status=r.status,closed_at=r.closed_at)
def _experiment(r):return ExperimentOut(id=r.id,name=r.name,hypothesis=r.hypothesis,metric=r.metric,kind=r.kind,variants=[VariantOut(**v) for v in r.variants],status=r.status,created_at=r.created_at,updated_at=r.updated_at)
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
    def save_alert_rule(self,d,at):
        with self.sessions.begin() as db:
            r=db.scalar(select(AlertRuleRow).where(AlertRuleRow.tenant_id==self.tenant_id,AlertRuleRow.id==d.id))
            if r:r.kpi_id=d.kpi_id;r.comparator=d.comparator.value;r.threshold=d.threshold;r.severity=d.severity.value;r.message=d.message;r.cooldown_hours=d.cooldown_hours
            else:db.add(AlertRuleRow(tenant_id=self.tenant_id,id=d.id,kpi_id=d.kpi_id,comparator=d.comparator.value,threshold=d.threshold,severity=d.severity.value,message=d.message,cooldown_hours=d.cooldown_hours,created_at=at))
        return AlertRuleOut(**d.model_dump(),created_at=at)
    def list_alert_rules(self):
        with self.sessions() as db:return [AlertRuleOut(id=r.id,kpi_id=r.kpi_id,comparator=AlertComparator(r.comparator),threshold=r.threshold,severity=BlockerSeverity(r.severity),message=r.message,cooldown_hours=r.cooldown_hours,created_at=r.created_at) for r in db.scalars(select(AlertRuleRow).where(AlertRuleRow.tenant_id==self.tenant_id).order_by(AlertRuleRow.id))]
    def delete_alert_rule(self,rule_id):
        with self.sessions.begin() as db:
            r=db.scalar(select(AlertRuleRow).where(AlertRuleRow.tenant_id==self.tenant_id,AlertRuleRow.id==rule_id))
            if not r:return False
            db.delete(r);return True
    def expire_approvals_before(self,moment):
        with self.sessions.begin() as db:
            rows=db.scalars(select(ApprovalRow).where(ApprovalRow.tenant_id==self.tenant_id,ApprovalRow.state==ApprovalState.PENDING.value,ApprovalRow.expires_at.isnot(None),ApprovalRow.expires_at<moment)).all()
            for r in rows:r.state=ApprovalState.EXPIRED.value
            db.flush()
            return [_approval(r) for r in rows]
    def save_view(self,layout,at):
        with self.sessions.begin() as db:
            r=db.get(ViewPrefsRow,self.tenant_id)
            if r:r.layout=layout;r.updated_at=at
            else:db.add(ViewPrefsRow(tenant_id=self.tenant_id,layout=layout,updated_at=at))
    def get_view(self):
        with self.sessions() as db:
            r=db.get(ViewPrefsRow,self.tenant_id)
            return (dict(r.layout),r.updated_at) if r else (None,None)
    def save_work_item(self,item:WorkItemOut):
        with self.sessions.begin() as db:
            r=db.scalar(select(WorkItemRow).where(WorkItemRow.tenant_id==self.tenant_id,WorkItemRow.id==item.id))
            data=item.model_dump()
            if r:
                for k,v in data.items():setattr(r,k,v)
            else:db.add(WorkItemRow(tenant_id=self.tenant_id,**data))
        return item
    def get_work_item(self,item_id):
        with self.sessions() as db:
            r=db.scalar(select(WorkItemRow).where(WorkItemRow.tenant_id==self.tenant_id,WorkItemRow.id==item_id))
            return _work_item(r) if r else None
    def list_work_items(self,sprint_id=None,roadmap_id=None,status=None):
        with self.sessions() as db:
            q=select(WorkItemRow).where(WorkItemRow.tenant_id==self.tenant_id)
            if sprint_id is not None:q=q.where(WorkItemRow.sprint_id==sprint_id)
            if roadmap_id is not None:q=q.where(WorkItemRow.roadmap_id==roadmap_id)
            if status is not None:q=q.where(WorkItemRow.status==status)
            return [_work_item(r) for r in db.scalars(q.order_by(WorkItemRow.rank,WorkItemRow.created_at))]
    def delete_work_item(self,item_id):
        with self.sessions.begin() as db:
            r=db.scalar(select(WorkItemRow).where(WorkItemRow.tenant_id==self.tenant_id,WorkItemRow.id==item_id))
            if not r:return False
            db.delete(r);return True
    def save_sprint(self,sp:SprintOut):
        with self.sessions.begin() as db:
            r=db.scalar(select(SprintRow).where(SprintRow.tenant_id==self.tenant_id,SprintRow.id==sp.id))
            data=sp.model_dump()
            if r:
                for k,v in data.items():setattr(r,k,v)
            else:db.add(SprintRow(tenant_id=self.tenant_id,**data))
        return sp
    def get_sprint(self,sprint_id):
        with self.sessions() as db:
            r=db.scalar(select(SprintRow).where(SprintRow.tenant_id==self.tenant_id,SprintRow.id==sprint_id))
            return _sprint(r) if r else None
    def list_sprints(self):
        with self.sessions() as db:return [_sprint(r) for r in db.scalars(select(SprintRow).where(SprintRow.tenant_id==self.tenant_id).order_by(SprintRow.start))]
    def save_ceremony(self,c:CeremonyOut):
        with self.sessions.begin() as db:db.add(CeremonyRow(tenant_id=self.tenant_id,**c.model_dump()))
        return c
    def list_ceremonies(self,sprint_id=None):
        with self.sessions() as db:
            q=select(CeremonyRow).where(CeremonyRow.tenant_id==self.tenant_id)
            if sprint_id is not None:q=q.where(CeremonyRow.sprint_id==sprint_id)
            return [CeremonyOut(id=r.id,sprint_id=r.sprint_id,kind=r.kind,scheduled_at=r.scheduled_at,notes=r.notes,action_items=r.action_items,created_at=r.created_at) for r in db.scalars(q.order_by(CeremonyRow.scheduled_at))]
    def save_retrospective(self,retro:RetrospectiveOut):
        with self.sessions.begin() as db:db.add(RetrospectiveRow(tenant_id=self.tenant_id,**retro.model_dump()))
        return retro
    def list_retrospectives(self):
        with self.sessions() as db:return [RetrospectiveOut(id=r.id,sprint_id=r.sprint_id,went_well=r.went_well,didnt_go_well=r.didnt_go_well,action_items=r.action_items,created_at=r.created_at) for r in db.scalars(select(RetrospectiveRow).where(RetrospectiveRow.tenant_id==self.tenant_id).order_by(RetrospectiveRow.created_at))]
    def save_experiment(self,e:ExperimentOut):
        with self.sessions.begin() as db:
            r=db.scalar(select(ExperimentRow).where(ExperimentRow.tenant_id==self.tenant_id,ExperimentRow.id==e.id))
            data=e.model_dump()
            if r:
                for k,v in data.items():setattr(r,k,v)
            else:db.add(ExperimentRow(tenant_id=self.tenant_id,**data))
        return e
    def get_experiment(self,experiment_id):
        with self.sessions() as db:
            r=db.scalar(select(ExperimentRow).where(ExperimentRow.tenant_id==self.tenant_id,ExperimentRow.id==experiment_id))
            return _experiment(r) if r else None
    def save_analysis_job(self,j:AnalysisJobOut):
        with self.sessions.begin() as db:db.add(AnalysisJobRow(tenant_id=self.tenant_id,**j.model_dump()))
        return j
    def get_analysis_job(self,job_id):
        with self.sessions() as db:
            r=db.scalar(select(AnalysisJobRow).where(AnalysisJobRow.tenant_id==self.tenant_id,AnalysisJobRow.id==job_id))
            return _analysis_job(r) if r else None
    def list_analysis_jobs(self,method=None):
        with self.sessions() as db:
            q=select(AnalysisJobRow).where(AnalysisJobRow.tenant_id==self.tenant_id)
            if method:q=q.where(AnalysisJobRow.method==method)
            return [_analysis_job(r) for r in db.scalars(q.order_by(AnalysisJobRow.created_at.desc()).limit(200))]
    def list_experiments(self):
        with self.sessions() as db:return [_experiment(r) for r in db.scalars(select(ExperimentRow).where(ExperimentRow.tenant_id==self.tenant_id).order_by(ExperimentRow.created_at))]
    def save_roadmap(self,rm:RoadmapOut):
        with self.sessions.begin() as db:db.add(RoadmapRow(tenant_id=self.tenant_id,**rm.model_dump()))
        return rm
    def get_roadmap(self,roadmap_id):
        with self.sessions() as db:
            r=db.scalar(select(RoadmapRow).where(RoadmapRow.tenant_id==self.tenant_id,RoadmapRow.id==roadmap_id))
            return RoadmapOut(id=r.id,name=r.name,horizon_start=r.horizon_start,horizon_end=r.horizon_end,created_at=r.created_at) if r else None
    def list_roadmaps(self):
        with self.sessions() as db:return [RoadmapOut(id=r.id,name=r.name,horizon_start=r.horizon_start,horizon_end=r.horizon_end,created_at=r.created_at) for r in db.scalars(select(RoadmapRow).where(RoadmapRow.tenant_id==self.tenant_id).order_by(RoadmapRow.created_at))]
class AnalysisJobRow(Base):
    __tablename__="m16_analysis_jobs";__table_args__=(UniqueConstraint("tenant_id","id",name="uq_m16_analysis_job"),)
    pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36));method:Mapped[str]=mapped_column(String(60),index=True);feature_row:Mapped[int]=mapped_column(Integer);data:Mapped[dict]=mapped_column(JSON);params:Mapped[dict]=mapped_column(JSON);seed:Mapped[int]=mapped_column(Integer);status:Mapped[str]=mapped_column(String(20));output:Mapped[dict|None]=mapped_column(JSON,nullable=True);error:Mapped[str|None]=mapped_column(Text,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
def _analysis_job(r):
    return AnalysisJobOut(id=r.id,method=r.method,feature_row=r.feature_row,data=r.data,params=r.params,seed=r.seed,status=r.status,output=r.output,error=r.error,created_at=r.created_at,completed_at=r.completed_at)
