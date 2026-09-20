"""Durable tenant-scoped project storage with optimistic revisions."""
from __future__ import annotations
from sqlalchemy import JSON,Integer,LargeBinary,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import ArtifactManifest,Budget,MilestoneView,ProjectPlan,ProjectView
class ProjectRow(Base):
 __tablename__="m14_projects";__table_args__=(UniqueConstraint("tenant_id","id"),)
 pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True)
 goal:Mapped[str]=mapped_column(Text);brief:Mapped[dict]=mapped_column(JSON);budget:Mapped[dict]=mapped_column(JSON);status:Mapped[str]=mapped_column(String(40),index=True);revision:Mapped[int]=mapped_column(Integer);plan:Mapped[dict|None]=mapped_column(JSON,nullable=True)
def _view(r):return ProjectView(id=r.id,tenant_id=r.tenant_id,goal=r.goal,brief=r.brief,budget=Budget.model_validate(r.budget),status=r.status,revision=r.revision,plan=ProjectPlan.model_validate(r.plan) if r.plan else None)
class MilestoneRow(Base):
 __tablename__="m14_milestones";__table_args__=(UniqueConstraint("tenant_id","project_id","milestone_id"),)
 pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True)
 project_id:Mapped[str]=mapped_column(String(36),index=True);milestone_id:Mapped[str]=mapped_column(String(160))
 data:Mapped[dict]=mapped_column(JSON)
def _milestone_view(r):return MilestoneView.model_validate(r.data)
class ArtifactRow(Base):
 __tablename__="m14_artifacts";__table_args__=(UniqueConstraint("tenant_id","project_id","id"),)
 pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True)
 project_id:Mapped[str]=mapped_column(String(36),index=True);id:Mapped[str]=mapped_column(String(36))
 manifest:Mapped[dict]=mapped_column(JSON);payload:Mapped[bytes]=mapped_column(LargeBinary)
def _manifest(r):return ArtifactManifest.model_validate(r.manifest)
class SqlProjectRepository:
 def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
 def get(self,project_id:str):
  with self.sessions() as db:
   row=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==self.tenant_id,ProjectRow.id==project_id));return _view(row) if row else None
 def list(self,limit:int=100):
  with self.sessions() as db:
   rows=db.scalars(select(ProjectRow).where(ProjectRow.tenant_id==self.tenant_id).order_by(ProjectRow.pk.desc()).limit(limit)).all();return [_view(r) for r in rows]
 def save(self,item:ProjectView,expected_revision:int|None=None):
  with self.sessions.begin() as db:
   row=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==self.tenant_id,ProjectRow.id==item.id))
   if row and expected_revision is not None and row.revision!=expected_revision:raise RuntimeError("project revision conflict")
   data=dict(tenant_id=self.tenant_id,id=item.id,goal=item.goal,brief=item.brief,budget=item.budget.model_dump(mode="json"),status=item.status,revision=item.revision,plan=item.plan.model_dump(mode="json") if item.plan else None)
   if row is None:row=ProjectRow(**data);db.add(row)
   else:
    for key,value in data.items():setattr(row,key,value)
   db.flush();return _view(row)
 def save_milestones(self,project_id:str,milestones:list[MilestoneView]):
  with self.sessions.begin() as db:
   for m in milestones:
    row=db.scalar(select(MilestoneRow).where(MilestoneRow.tenant_id==self.tenant_id,MilestoneRow.project_id==project_id,MilestoneRow.milestone_id==m.milestone_id))
    data=m.model_dump(mode="json")
    if row is None:db.add(MilestoneRow(tenant_id=self.tenant_id,project_id=project_id,milestone_id=m.milestone_id,data=data))
    else:row.data=data
   db.flush()
 def list_milestones(self,project_id:str):
  with self.sessions() as db:
   rows=db.scalars(select(MilestoneRow).where(MilestoneRow.tenant_id==self.tenant_id,MilestoneRow.project_id==project_id).order_by(MilestoneRow.pk)).all()
   return [_milestone_view(r) for r in rows]
 def save_artifact(self,project_id:str,manifest:ArtifactManifest,payload:bytes):
  with self.sessions.begin() as db:
   row=db.scalar(select(ArtifactRow).where(ArtifactRow.tenant_id==self.tenant_id,ArtifactRow.project_id==project_id,ArtifactRow.id==manifest.id))
   if row is not None:raise RuntimeError("artifact id already exists")
   db.add(ArtifactRow(tenant_id=self.tenant_id,project_id=project_id,id=manifest.id,manifest=manifest.model_dump(mode="json"),payload=payload));db.flush()
 def list_artifacts(self,project_id:str):
  with self.sessions() as db:
   rows=db.scalars(select(ArtifactRow).where(ArtifactRow.tenant_id==self.tenant_id,ArtifactRow.project_id==project_id).order_by(ArtifactRow.pk)).all()
   return [_manifest(r) for r in rows]
 def artifact_payloads(self,project_id:str):
  with self.sessions() as db:
   rows=db.scalars(select(ArtifactRow).where(ArtifactRow.tenant_id==self.tenant_id,ArtifactRow.project_id==project_id)).all()
   return {r.id:r.payload for r in rows}
