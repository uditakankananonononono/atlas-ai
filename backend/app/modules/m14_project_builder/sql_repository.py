"""Durable tenant-scoped project storage with optimistic revisions."""
from __future__ import annotations
from sqlalchemy import JSON,Integer,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import Budget,ProjectPlan,ProjectView
class ProjectRow(Base):
 __tablename__="m14_projects";__table_args__=(UniqueConstraint("tenant_id","id"),)
 pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True)
 goal:Mapped[str]=mapped_column(Text);brief:Mapped[dict]=mapped_column(JSON);budget:Mapped[dict]=mapped_column(JSON);status:Mapped[str]=mapped_column(String(40),index=True);revision:Mapped[int]=mapped_column(Integer);plan:Mapped[dict|None]=mapped_column(JSON,nullable=True)
def _view(r):return ProjectView(id=r.id,tenant_id=r.tenant_id,goal=r.goal,brief=r.brief,budget=Budget.model_validate(r.budget),status=r.status,revision=r.revision,plan=ProjectPlan.model_validate(r.plan) if r.plan else None)
class SqlProjectRepository:
 def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
 def get(self,project_id:str):
  with self.sessions() as db:
   row=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==self.tenant_id,ProjectRow.id==project_id));return _view(row) if row else None
 def save(self,item:ProjectView,expected_revision:int|None=None):
  with self.sessions.begin() as db:
   row=db.scalar(select(ProjectRow).where(ProjectRow.tenant_id==self.tenant_id,ProjectRow.id==item.id))
   if row and expected_revision is not None and row.revision!=expected_revision:raise RuntimeError("project revision conflict")
   data=dict(tenant_id=self.tenant_id,id=item.id,goal=item.goal,brief=item.brief,budget=item.budget.model_dump(mode="json"),status=item.status,revision=item.revision,plan=item.plan.model_dump(mode="json") if item.plan else None)
   if row is None:row=ProjectRow(**data);db.add(row)
   else:
    for key,value in data.items():setattr(row,key,value)
   db.flush();return _view(row)
