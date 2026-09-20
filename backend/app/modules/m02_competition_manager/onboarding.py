"""Guided launch onboarding for owner application source documents."""
from datetime import datetime,timezone
from sqlalchemy import JSON,Boolean,DateTime,String,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class CorpusOnboardingRow(Base):
 __tablename__='m02_corpus_onboarding';tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);completed:Mapped[bool]=mapped_column(Boolean,default=False);skipped:Mapped[bool]=mapped_column(Boolean,default=False);document_types:Mapped[list]=mapped_column(JSON,default=list);source_ids:Mapped[list]=mapped_column(JSON,default=list);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class OnboardingService:
 REQUIRED=['writings','essays','activity_descriptions']
 def __init__(self,tenant_id,session_factory:sessionmaker=SessionLocal):self.tenant_id,self.sessions=tenant_id,session_factory;Base.metadata.create_all(engine)
 def launch_step(self):
  with self.sessions() as db:r=db.get(CorpusOnboardingRow,self.tenant_id)
  if r and (r.completed or r.skipped):return {'show':False,'completed':r.completed,'skipped':r.skipped}
  return {'show':True,'step':'application_source_corpus','title':'Add your source documents','prompt':'Connect or select your writings, essays, and activity descriptions so Atlas can ground application drafts in your own material.','requested_document_types':self.REQUIRED,'accepted_sources':['google_docs','google_sheets'],'optional':True,'skip_available':True,'next_action':'/api/v1/competition-manager/profile-corpus/google-docs'}
 def complete(self,document_types,source_ids):
  unknown=set(document_types)-set(self.REQUIRED)
  if unknown:raise ValueError(f'unknown document types: {sorted(unknown)}')
  if not source_ids:raise ValueError('at least one indexed source is required')
  now=datetime.now(timezone.utc)
  with self.sessions.begin() as db:
   r=db.get(CorpusOnboardingRow,self.tenant_id)
   if r is None:db.add(CorpusOnboardingRow(tenant_id=self.tenant_id,completed=True,skipped=False,document_types=document_types,source_ids=source_ids,updated_at=now))
   else:r.completed=True;r.skipped=False;r.document_types=document_types;r.source_ids=source_ids;r.updated_at=now
  return {'completed':True,'indexed_source_ids':source_ids,'application_pipeline_ready':True}
 def skip(self):
  now=datetime.now(timezone.utc)
  with self.sessions.begin() as db:
   r=db.get(CorpusOnboardingRow,self.tenant_id)
   if r is None:db.add(CorpusOnboardingRow(tenant_id=self.tenant_id,completed=False,skipped=True,document_types=[],source_ids=[],updated_at=now))
   else:r.skipped=True;r.updated_at=now
  return {'skipped':True,'warning':'Application drafting remains unavailable until owner source documents are indexed.'}
