"""Persistent student-owned story projects and evolving BrandID."""
from datetime import datetime,timezone
from sqlalchemy import JSON,DateTime,Integer,String,Text,UniqueConstraint,func,select
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
  # Allocation contract: the next version is max(version)+1 computed inside
  # the transaction. A unique-(project_id,version) collision - two
  # concurrent allocations observing the same maximum - retries with a
  # recomputed number in a fresh transaction, bounded to three attempts,
  # then fails with a domain error. Integrity classification is
  # driver-identified (SQLite result codes, PostgreSQL SQLSTATE): a
  # recognized non-unique integrity error raises IntegrityWriteError on the
  # first attempt, an unclassifiable driver signal raises
  # UnclassifiedIntegrityError; neither is collision-labeled or retried.
  # A commit-time or post-commit failure raises CommitOutcomeUnknown: the
  # call failed while the version may have persisted; reconcile by listing
  # current versions before resubmitting. No automatic retry, compensation
  # or deduplication of the ambiguous case. Deterministic handler-path
  # contract only; no real-race closure claimed.
  from sqlalchemy.exc import IntegrityError as _IE
  from ._commit_contract import CommitOutcomeUnknown,IntegrityWriteError,UnclassifiedIntegrityError,classify_integrity_error
  last=None
  for _ in range(3):
   committed=False
   try:
    with self.sessions() as db:
     p=db.get(StoryProjectRow,project_id)
     if not p or p.tenant_id!=self.tenant_id:raise LookupError(project_id)
     current=db.scalar(select(func.max(StoryVersionRow.version)).where(StoryVersionRow.project_id==project_id));v=(current or 0)+1;db.add(StoryVersionRow(project_id=project_id,version=v,student_text=text,coach_feedback=feedback));db.flush()
     try:db.commit()
     except _IE:raise
     except Exception as exc:raise CommitOutcomeUnknown('story version commit outcome unknown; the version may have persisted; reconcile by listing current versions before resubmitting; no automatic retry, compensation or deduplication is performed') from exc
     committed=True
     return v
   except _IE as exc:
    # Cleanup errors after a returned commit are not write collisions.
    if committed:raise CommitOutcomeUnknown('story version call failed after a returned commit; the version persisted while the call failed; reconcile by listing current versions before resubmitting; no automatic retry, compensation or deduplication is performed') from exc
    kind=classify_integrity_error(exc)
    if kind=='unique':last=exc;continue
    if kind=='non_unique':raise IntegrityWriteError('story version write failed on a recognized non-collision integrity error; rolled back without write; not a version collision') from exc
    raise UnclassifiedIntegrityError('story version write failed on an integrity error this driver cannot classify; rolled back without write; identification covers SQLite and PostgreSQL only') from exc
   except CommitOutcomeUnknown:raise
   except Exception as exc:
    if committed:raise CommitOutcomeUnknown('story version call failed after a returned commit; the version persisted while the call failed; reconcile by listing current versions before resubmitting; no automatic retry, compensation or deduplication is performed') from exc
    raise
  raise ValueError('story version allocation collided repeatedly; resubmit the student text') from last
 def evolve_brand(self,values,patterns,strengths,evidence,_db=None):
  if not evidence:raise ValueError('BrandID requires student-supplied evidence')
  now=datetime.now(timezone.utc)
  def apply(db):
   r=db.get(BrandIdRow,self.tenant_id)
   if r is None:db.add(BrandIdRow(tenant_id=self.tenant_id,values=values,patterns=patterns,strengths=strengths,evidence=evidence,updated_at=now))
   else:r.values=values;r.patterns=patterns;r.strengths=strengths;r.evidence=evidence;r.updated_at=now
  if _db is not None:
   # Caller owns the transaction (e.g. interview answer): the brand update
   # commits or rolls back with the caller's writes.
   apply(_db)
  else:
   with self.sessions.begin() as db:apply(db)
  return {'values':values,'patterns':patterns,'strengths':strengths,'evidence':evidence,'living_profile':True}
