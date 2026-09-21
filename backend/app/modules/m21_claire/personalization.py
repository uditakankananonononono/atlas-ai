"""Consent-first persistent personalization for Claire."""
from __future__ import annotations
from datetime import datetime,timezone
import json,math,re
from sqlalchemy import JSON,Boolean,DateTime,Integer,String,Text,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
class DecisionRow(Base):
 __tablename__='m21_decisions';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');decision:Mapped[str]=mapped_column(Text);reason:Mapped[str]=mapped_column(Text);context:Mapped[str]=mapped_column(Text);embedding:Mapped[list]=mapped_column(JSON,default=list);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class DecisionOutcomeRow(Base):
 __tablename__='m21_decision_outcomes';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');decision_id:Mapped[int]=mapped_column(Integer,index=True);outcome:Mapped[str]=mapped_column(Text);rating:Mapped[str]=mapped_column(String(20));lesson:Mapped[str]=mapped_column(Text);evidence:Mapped[dict]=mapped_column(JSON,default=dict);observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class CorrectionRow(Base):
 __tablename__='m21_corrections';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');original:Mapped[str]=mapped_column(Text);correction:Mapped[str]=mapped_column(Text);context:Mapped[str]=mapped_column(Text);embedding:Mapped[list]=mapped_column(JSON,default=list);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ReasoningNoteRow(Base):
 __tablename__='m21_reasoning_notes';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');title:Mapped[str]=mapped_column(Text);owner_authored_note:Mapped[str]=mapped_column(Text);embedding:Mapped[list]=mapped_column(JSON,default=list);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class RankingRow(Base):
 __tablename__='m21_rankings';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');context:Mapped[str]=mapped_column(Text);options:Mapped[list]=mapped_column(JSON);ranking:Mapped[list]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class ReviewRow(Base):
 __tablename__='m21_weekly_reviews';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');artifact_id:Mapped[str]=mapped_column(String(200));rating:Mapped[str]=mapped_column(String(20));note:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class TelemetryConsentRow(Base):
 __tablename__='m21_telemetry_consent';tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True);enabled:Mapped[bool]=mapped_column(Boolean,default=False);scopes:Mapped[list]=mapped_column(JSON,default=list);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class TelemetryEventRow(Base):
 __tablename__='m21_telemetry_events';id:Mapped[int]=mapped_column(primary_key=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);actor_id:Mapped[str]=mapped_column(String(120),index=True,default='owner');kind:Mapped[str]=mapped_column(String(80));payload:Mapped[dict]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
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

# Row-specific owner controls for features-document rows 2-9.  These are
# deliberately separate operations rather than aliases around ``retrieve``.
# They expose only data belonging to the repository's tenant and actor.
def _public(row, excluded: set[str] | None = None) -> dict:
 excluded=(excluded or set())|{'_sa_instance_state','tenant_id','actor_id','embedding'}
 return {k:v for k,v in vars(row).items() if k not in excluded and not k.startswith('_')}

class ScopedPersonalizationRepository(PersonalizationRepository):
 """Actor-scoped personalization with portable export and hard deletion.

 ``PersonalizationRepository`` remains as the compatibility surface. New
 callers should provide the authenticated actor id and use this class.
 """
 def __init__(self,tenant_id:str,actor_id:str,session_factory:sessionmaker=SessionLocal):
  if not tenant_id.strip() or not actor_id.strip():raise ValueError('tenant_id and actor_id are required')
  super().__init__(tenant_id,session_factory);self.actor_id=actor_id
 def _owned(self,cls):
  # Legacy records predate actor_id. They are never silently adopted.
  return select(cls).where(cls.tenant_id==self.tenant_id,cls.actor_id==self.actor_id)
 def add_decision(self,decision:str,reason:str,context:str,embedding:list[float]):
  if not all(isinstance(x,str) and x.strip() for x in (decision,reason,context)):raise ValueError('decision, reason and context are required')
  if not embedding or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in embedding):raise ValueError('finite embedding values are required')
  with self.sessions.begin() as db:
   row=DecisionRow(tenant_id=self.tenant_id,actor_id=self.actor_id,decision=decision.strip(),reason=reason.strip(),context=context.strip(),embedding=list(map(float,embedding)));db.add(row);db.flush();return row.id
 def add_correction(self,original:str,correction:str,context:str,embedding:list[float]):
  if not original.strip() or not correction.strip() or original.strip()==correction.strip():raise ValueError('a non-empty changed correction is required')
  if not embedding:raise ValueError('embedding is required')
  with self.sessions.begin() as db:
   row=CorrectionRow(tenant_id=self.tenant_id,actor_id=self.actor_id,original=original.strip(),correction=correction.strip(),context=context.strip(),embedding=embedding);db.add(row);db.flush();return row.id
 def add_owner_reasoning(self,title:str,note:str,embedding:list[float],owner_confirmed:bool):
  if not owner_confirmed:raise PermissionError('reasoning note must be explicitly owner-authored')
  if not title.strip() or not note.strip() or not embedding:raise ValueError('title, note and embedding are required')
  with self.sessions.begin() as db:
   row=ReasoningNoteRow(tenant_id=self.tenant_id,actor_id=self.actor_id,title=title.strip(),owner_authored_note=note.strip(),embedding=embedding);db.add(row);db.flush();return row.id
 def retrieve_decisions(self,query_vector:list[float],limit:int=8):
  if not query_vector:raise ValueError('query vector is required')
  with self.sessions() as db:
   rows=list(db.scalars(self._owned(DecisionRow)));rows=[x for x in rows if x.embedding];rows.sort(key=lambda x:cosine(query_vector,x.embedding),reverse=True)
   return [{'decision_id':x.id,'decision':x.decision,'reason':x.reason,'context':x.context,'similarity':round(cosine(query_vector,x.embedding),4)} for x in rows[:limit]]
 def correction_examples(self,query_vector:list[float],limit:int=5):
  with self.sessions() as db:
   rows=list(db.scalars(self._owned(CorrectionRow)));rows=[x for x in rows if x.embedding];rows.sort(key=lambda x:cosine(query_vector,x.embedding),reverse=True)
   return [{'correction_id':x.id,'input':x.original,'preferred_output':x.correction,'context':x.context,'similarity':round(cosine(query_vector,x.embedding),4),'provenance':'owner_correction'} for x in rows[:limit]]
 def reasoning_templates(self,query_vector:list[float],limit:int=5):
  with self.sessions() as db:
   rows=list(db.scalars(self._owned(ReasoningNoteRow)));rows=[x for x in rows if x.embedding];rows.sort(key=lambda x:cosine(query_vector,x.embedding),reverse=True)
   return [{'note_id':x.id,'title':x.title,'owner_authored_note':x.owner_authored_note,'similarity':round(cosine(query_vector,x.embedding),4),'hidden_chain_of_thought':False} for x in rows[:limit]]
 def add_ranking(self,context:str,options:list[str],ranking:list[str]):
  if len(options)<2 or len(options)!=len(set(options)) or set(options)!=set(ranking):raise ValueError('ranking must order every distinct option exactly once')
  with self.sessions.begin() as db:
   row=RankingRow(tenant_id=self.tenant_id,actor_id=self.actor_id,context=context.strip(),options=options,ranking=ranking);db.add(row);db.flush();return row.id
 def preference_scores(self)->dict[str,float]:
  with self.sessions() as db: rows=list(db.scalars(self._owned(RankingRow)))
  scores:dict[str,float]={}
  for row in rows:
   n=len(row.ranking)
   for position,item in enumerate(row.ranking):scores[item]=scores.get(item,0.0)+(n-position)/n
  return dict(sorted(scores.items(),key=lambda x:(-x[1],x[0])))
 def add_weekly_review(self,artifact_id:str,rating:str,note:str):
  if rating not in {'good','bad','unclear'}:raise ValueError('rating must be good, bad or unclear')
  if not artifact_id.strip() or not note.strip():raise ValueError('artifact_id and note are required')
  with self.sessions.begin() as db:
   row=ReviewRow(tenant_id=self.tenant_id,actor_id=self.actor_id,artifact_id=artifact_id.strip(),rating=rating,note=note.strip());db.add(row);db.flush();return row.id
 def weekly_signal(self)->dict:
  with self.sessions() as db: rows=list(db.scalars(self._owned(ReviewRow)))
  counts={k:sum(x.rating==k for x in rows) for k in ('good','bad','unclear')}
  return {'review_count':len(rows),'ratings':counts,'requires_owner_approval_before_behavior_change':True,'notes':[x.note for x in rows]}
 def cognitive_twin_context(self,query_vector:list[float])->dict:
  return {'decisions':self.retrieve_decisions(query_vector,4),'corrections':self.correction_examples(query_vector,4),'reasoning_notes':self.reasoning_templates(query_vector,4),'preference_scores':self.preference_scores(),'provenance':'consented_owner_records','external_effects':[]}
 def export_data(self)->dict:
  classes=(DecisionRow,CorrectionRow,ReasoningNoteRow,RankingRow,ReviewRow,TelemetryEventRow)
  with self.sessions() as db:return {'tenant_id':self.tenant_id,'actor_id':self.actor_id,'records':{c.__tablename__:[_public(x) for x in db.scalars(self._owned(c))] for c in classes}}
 def delete_data(self)->dict:
  classes=(DecisionOutcomeRow,DecisionRow,CorrectionRow,ReasoningNoteRow,RankingRow,ReviewRow,TelemetryEventRow)
  counts={}
  with self.sessions.begin() as db:
   for cls in classes:
    rows=list(db.scalars(self._owned(cls)));counts[cls.__tablename__]=len(rows)
    for row in rows:db.delete(row)
  return {'deleted':counts,'tenant_id':self.tenant_id,'actor_id':self.actor_id}
