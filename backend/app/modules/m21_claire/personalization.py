"""Consent-first persistent personalization for Claire."""
from __future__ import annotations
from datetime import datetime,timezone
import json,math,re
from sqlalchemy import JSON,Boolean,DateTime,Integer,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class DecisionRow(Base):
 __tablename__='m21_decisions';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);decision:Mapped[str]=mapped_column(Text);reason:Mapped[str]=mapped_column(Text);context:Mapped[str]=mapped_column(Text);embedding:Mapped[list]=mapped_column(JSON,default=list);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class DecisionOutcomeRow(Base):
 __tablename__='m21_decision_outcomes';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);decision_id:Mapped[int]=mapped_column(Integer,index=True);outcome:Mapped[str]=mapped_column(Text);rating:Mapped[str]=mapped_column(String(20));lesson:Mapped[str]=mapped_column(Text);evidence:Mapped[dict]=mapped_column(JSON,default=dict);observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class CorrectionRow(Base):
 __tablename__='m21_corrections';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);original:Mapped[str]=mapped_column(Text);correction:Mapped[str]=mapped_column(Text);context:Mapped[str]=mapped_column(Text);embedding:Mapped[list]=mapped_column(JSON,default=list);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ReasoningNoteRow(Base):
 __tablename__='m21_reasoning_notes';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);title:Mapped[str]=mapped_column(Text);owner_authored_note:Mapped[str]=mapped_column(Text);embedding:Mapped[list]=mapped_column(JSON,default=list);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class RankingRow(Base):
 __tablename__='m21_rankings';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);context:Mapped[str]=mapped_column(Text);options:Mapped[list]=mapped_column(JSON);ranking:Mapped[list]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ReviewRow(Base):
 __tablename__='m21_weekly_reviews';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);artifact_id:Mapped[str]=mapped_column(String(200));rating:Mapped[str]=mapped_column(String(20));note:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class TelemetryConsentRow(Base):
 __tablename__='m21_telemetry_consent';tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);enabled:Mapped[bool]=mapped_column(Boolean,default=False);scopes:Mapped[list]=mapped_column(JSON,default=list);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class TelemetryEventRow(Base):
 __tablename__='m21_telemetry_events';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);kind:Mapped[str]=mapped_column(String(80));payload:Mapped[dict]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
def cosine(a,b):
 n=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b));return 0 if not n else sum(x*y for x,y in zip(a,b))/n
class PersonalizationRepository:
 def __init__(self,tenant_id,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
 def add(self,kind,data,embedding=None):
  cls={'decision':DecisionRow,'correction':CorrectionRow,'reasoning_note':ReasoningNoteRow,'ranking':RankingRow,'review':ReviewRow}[kind]
  with self.sessions.begin() as db:row=cls(tenant_id=self.tenant_id,embedding=embedding or [],**data) if hasattr(cls,'embedding') else cls(tenant_id=self.tenant_id,**data);db.add(row);db.flush();return row.id
 def retrieve(self,query_vector,limit=8):
  with self.sessions() as db:
   rows=[*db.scalars(select(DecisionRow).where(DecisionRow.tenant_id==self.tenant_id)),*db.scalars(select(CorrectionRow).where(CorrectionRow.tenant_id==self.tenant_id)),*db.scalars(select(ReasoningNoteRow).where(ReasoningNoteRow.tenant_id==self.tenant_id))]
   rows=[r for r in rows if r.embedding];rows.sort(key=lambda r:cosine(query_vector,r.embedding),reverse=True)
   result=[]
   for r in rows[:limit]:
    content={k:v for k,v in vars(r).items() if not k.startswith('_') and k not in {'embedding','tenant_id'}}
    if isinstance(r,DecisionRow):
     outcomes=list(db.scalars(select(DecisionOutcomeRow).where(DecisionOutcomeRow.tenant_id==self.tenant_id,DecisionOutcomeRow.decision_id==r.id).order_by(DecisionOutcomeRow.observed_at.desc())))
     content['outcomes']=[{'outcome':x.outcome,'rating':x.rating,'lesson':x.lesson,'evidence':x.evidence,'observed_at':x.observed_at} for x in outcomes]
    result.append({'kind':r.__tablename__,'id':r.id,'score':round(cosine(query_vector,r.embedding),4),'content':content})
   return result
 def add_decision_outcome(self,decision_id,data):
  with self.sessions.begin() as db:
   decision=db.get(DecisionRow,decision_id)
   if decision is None or decision.tenant_id!=self.tenant_id:raise KeyError('decision not found')
   row=DecisionOutcomeRow(tenant_id=self.tenant_id,decision_id=decision_id,**data);db.add(row);db.flush();return row.id
 def decision_history(self,decision_id):
  with self.sessions() as db:
   decision=db.get(DecisionRow,decision_id)
   if decision is None or decision.tenant_id!=self.tenant_id:raise KeyError('decision not found')
   outcomes=list(db.scalars(select(DecisionOutcomeRow).where(DecisionOutcomeRow.tenant_id==self.tenant_id,DecisionOutcomeRow.decision_id==decision_id).order_by(DecisionOutcomeRow.observed_at)))
   return {'decision':{'id':decision.id,'decision':decision.decision,'reason':decision.reason,'context':decision.context,'created_at':decision.created_at},'outcomes':[{'id':x.id,'outcome':x.outcome,'rating':x.rating,'lesson':x.lesson,'evidence':x.evidence,'observed_at':x.observed_at} for x in outcomes]}
 def set_telemetry_consent(self,enabled,scopes):
  now=datetime.now(timezone.utc)
  with self.sessions.begin() as db:
   row=db.get(TelemetryConsentRow,self.tenant_id)
   if row is None:db.add(TelemetryConsentRow(tenant_id=self.tenant_id,enabled=enabled,scopes=scopes,updated_at=now))
   else:row.enabled=enabled;row.scopes=scopes;row.updated_at=now
 def log_telemetry(self,kind,payload):
  with self.sessions.begin() as db:
   consent=db.get(TelemetryConsentRow,self.tenant_id)
   if not consent or not consent.enabled or kind not in consent.scopes:raise PermissionError('telemetry scope is not enabled by owner')
   row=TelemetryEventRow(tenant_id=self.tenant_id,kind=kind,payload=payload);db.add(row);db.flush();return row.id
