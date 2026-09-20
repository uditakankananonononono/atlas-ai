"""Persistent student-owned story projects and evolving BrandID."""
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,Integer,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class StoryProjectRow(Base):
 __tablename__='m23_story_projects';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);title:Mapped[str]=mapped_column(String(500));track:Mapped[str]=mapped_column(String(20));opportunity:Mapped[dict]=mapped_column(JSON);status:Mapped[str]=mapped_column(String(30),default='active');created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class StoryVersionRow(Base):
 __tablename__='m23_story_versions';__table_args__=(UniqueConstraint('project_id','version'),);id:Mapped[int]=mapped_column(primary_key=True);project_id:Mapped[int]=mapped_column(Integer,index=True);version:Mapped[int]=mapped_column(Integer);student_text:Mapped[str]=mapped_column(Text);coach_feedback:Mapped[dict]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class BrandIdRow(Base):
 __tablename__='m23_brandids';tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);values:Mapped[list]=mapped_column(JSON);patterns:Mapped[list]=mapped_column(JSON);strengths:Mapped[list]=mapped_column(JSON);evidence:Mapped[list]=mapped_column(JSON);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class StoryRepository:
 def __init__(self,tenant_id,session_factory:sessionmaker=SessionLocal):self.tenant_id,self.sessions=tenant_id,session_factory;Base.metadata.create_all(engine)
 def project(self,title,track,opportunity):
  if track not in {'college','career'}:raise ValueError('track must be college or career')
  with self.sessions.begin() as db:r=StoryProjectRow(tenant_id=self.tenant_id,title=title,track=track,opportunity=opportunity);db.add(r);db.flush();return r.id
 def add_student_version(self,project_id,text,feedback):
  if not text.strip():raise ValueError('student-authored text is required')
  with self.sessions.begin() as db:
   p=db.get(StoryProjectRow,project_id)
   if not p or p.tenant_id!=self.tenant_id:raise LookupError(project_id)
   versions=list(db.scalars(select(StoryVersionRow).where(StoryVersionRow.project_id==project_id)));v=len(versions)+1;db.add(StoryVersionRow(project_id=project_id,version=v,student_text=text,coach_feedback=feedback));return v
 def evolve_brand(self,values,patterns,strengths,evidence):
  if not evidence:raise ValueError('BrandID requires student-supplied evidence')
  now=datetime.now(timezone.utc)
  with self.sessions.begin() as db:
   r=db.get(BrandIdRow,self.tenant_id)
   if r is None:db.add(BrandIdRow(tenant_id=self.tenant_id,values=values,patterns=patterns,strengths=strengths,evidence=evidence,updated_at=now))
   else:r.values=values;r.patterns=patterns;r.strengths=strengths;r.evidence=evidence;r.updated_at=now
  return {'values':values,'patterns':patterns,'strengths':strengths,'evidence':evidence,'living_profile':True}
