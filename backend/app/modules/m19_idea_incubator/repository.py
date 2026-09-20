"""Tenant-scoped persistence and an in-memory test repository for Module 19."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from threading import RLock
from sqlalchemy import JSON,DateTime,Float,Integer,String,Text,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .schemas import *

class IdeaRow(Base):
    __tablename__="m19_ideas";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True,unique=True);title:Mapped[str]=mapped_column(String(180));problem:Mapped[str]=mapped_column(Text);proposed_solution:Mapped[str]=mapped_column(Text);tags:Mapped[list]=mapped_column(JSON);metadata_json:Mapped[dict]=mapped_column(JSON);stage:Mapped[str]=mapped_column(String(30),index=True);version:Mapped[int]=mapped_column(Integer);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class EvidenceRow(Base):
    __tablename__="m19_evidence";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),index=True,unique=True);idea_id:Mapped[str]=mapped_column(String(36),index=True);kind:Mapped[str]=mapped_column(String(30));claim:Mapped[str]=mapped_column(Text);source:Mapped[str]=mapped_column(Text);polarity:Mapped[str]=mapped_column(String(20));strength:Mapped[float]=mapped_column(Float);confidence:Mapped[float]=mapped_column(Float);observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));metadata_json:Mapped[dict]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class FeasibilityRow(Base):
    __tablename__="m19_feasibility_tests";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),unique=True);idea_id:Mapped[str]=mapped_column(String(36),index=True);payload:Mapped[dict]=mapped_column(JSON);weighted_score:Mapped[float]=mapped_column(Float);weighted_confidence:Mapped[float]=mapped_column(Float);outcome:Mapped[str]=mapped_column(String(20));tested_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class ExperimentRow(Base):
    __tablename__="m19_experiments";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),unique=True);idea_id:Mapped[str]=mapped_column(String(36),index=True);payload:Mapped[dict]=mapped_column(JSON);status:Mapped[str]=mapped_column(String(20));observed_value:Mapped[float|None]=mapped_column(Float,nullable=True);learnings:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
class DecisionRow(Base):
    __tablename__="m19_decisions";pk:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);id:Mapped[str]=mapped_column(String(36),unique=True);idea_id:Mapped[str]=mapped_column(String(36),index=True);from_stage:Mapped[str]=mapped_column(String(30));to_stage:Mapped[str]=mapped_column(String(30));rationale:Mapped[str]=mapped_column(Text);actor_id:Mapped[str]=mapped_column(String(120));metadata_json:Mapped[dict]=mapped_column(JSON);decided_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));idea_version:Mapped[int]=mapped_column(Integer)

def _idea(r):return Idea(id=r.id,title=r.title,problem=r.problem,proposed_solution=r.proposed_solution,tags=r.tags,metadata=r.metadata_json,stage=IdeaStage(r.stage),version=r.version,created_at=r.created_at,updated_at=r.updated_at)
def _evidence(r):return Evidence(id=r.id,idea_id=r.idea_id,kind=EvidenceKind(r.kind),claim=r.claim,source=r.source,polarity=EvidencePolarity(r.polarity),strength=r.strength,confidence=r.confidence,observed_at=r.observed_at,metadata=r.metadata_json,created_at=r.created_at)
def _feasibility(r):return FeasibilityTest.model_validate({**r.payload,"id":r.id,"idea_id":r.idea_id,"weighted_score":r.weighted_score,"weighted_confidence":r.weighted_confidence,"outcome":r.outcome,"tested_at":r.tested_at})
def _experiment(r):return Experiment.model_validate({**r.payload,"id":r.id,"idea_id":r.idea_id,"status":r.status,"observed_value":r.observed_value,"learnings":r.learnings,"created_at":r.created_at,"updated_at":r.updated_at})
def _decision(r):return Decision(id=r.id,idea_id=r.idea_id,from_stage=IdeaStage(r.from_stage),to_stage=IdeaStage(r.to_stage),rationale=r.rationale,actor_id=r.actor_id,metadata=r.metadata_json,decided_at=r.decided_at,idea_version=r.idea_version)

class SqlIdeaRepository:
    def __init__(self,tenant_id:str,session_factory:sessionmaker=SessionLocal):self.tenant_id=tenant_id;self.sessions=session_factory;Base.metadata.create_all(engine)
    def save_idea(self,x,expected_version=None):
        with self.sessions.begin() as db:
            r=db.scalar(select(IdeaRow).where(IdeaRow.tenant_id==self.tenant_id,IdeaRow.id==x.id))
            if r and expected_version is not None and r.version!=expected_version:raise RuntimeError("idea changed; refresh before deciding")
            if r is None:r=IdeaRow(tenant_id=self.tenant_id,id=x.id);db.add(r)
            for k,v in {"title":x.title,"problem":x.problem,"proposed_solution":x.proposed_solution,"tags":x.tags,"metadata_json":x.metadata,"stage":x.stage.value,"version":x.version,"created_at":x.created_at,"updated_at":x.updated_at}.items():setattr(r,k,v)
        return x
    def get_idea(self,i):
        with self.sessions() as db:r=db.scalar(select(IdeaRow).where(IdeaRow.tenant_id==self.tenant_id,IdeaRow.id==i));return _idea(r) if r else None
    def list_ideas(self):
        with self.sessions() as db:return [_idea(r) for r in db.scalars(select(IdeaRow).where(IdeaRow.tenant_id==self.tenant_id).order_by(IdeaRow.created_at))]
    def _add(self,row):
        with self.sessions.begin() as db:db.add(row)
    def add_evidence(self,x):self._add(EvidenceRow(tenant_id=self.tenant_id,id=x.id,idea_id=x.idea_id,kind=x.kind.value,claim=x.claim,source=x.source,polarity=x.polarity.value,strength=x.strength,confidence=x.confidence,observed_at=x.observed_at,metadata_json=x.metadata,created_at=x.created_at));return x
    def list_evidence(self,i):
        with self.sessions() as db:return [_evidence(r) for r in db.scalars(select(EvidenceRow).where(EvidenceRow.tenant_id==self.tenant_id,EvidenceRow.idea_id==i).order_by(EvidenceRow.created_at))]
    def add_test(self,x):self._add(FeasibilityRow(tenant_id=self.tenant_id,id=x.id,idea_id=x.idea_id,payload=x.model_dump(mode="json",exclude={"id","idea_id","weighted_score","weighted_confidence","outcome","tested_at"}),weighted_score=x.weighted_score,weighted_confidence=x.weighted_confidence,outcome=x.outcome.value,tested_at=x.tested_at));return x
    def list_tests(self,i):
        with self.sessions() as db:return [_feasibility(r) for r in db.scalars(select(FeasibilityRow).where(FeasibilityRow.tenant_id==self.tenant_id,FeasibilityRow.idea_id==i).order_by(FeasibilityRow.tested_at))]
    def save_experiment(self,x):
        with self.sessions.begin() as db:
            r=db.scalar(select(ExperimentRow).where(ExperimentRow.tenant_id==self.tenant_id,ExperimentRow.id==x.id))
            if r is None:r=ExperimentRow(tenant_id=self.tenant_id,id=x.id,idea_id=x.idea_id,created_at=x.created_at);db.add(r)
            r.payload=x.model_dump(mode="json",exclude={"id","idea_id","status","observed_value","learnings","created_at","updated_at"});r.status=x.status.value;r.observed_value=x.observed_value;r.learnings=x.learnings;r.updated_at=x.updated_at
        return x
    def list_experiments(self,i):
        with self.sessions() as db:return [_experiment(r) for r in db.scalars(select(ExperimentRow).where(ExperimentRow.tenant_id==self.tenant_id,ExperimentRow.idea_id==i).order_by(ExperimentRow.created_at))]
    def add_decision(self,x):self._add(DecisionRow(tenant_id=self.tenant_id,id=x.id,idea_id=x.idea_id,from_stage=x.from_stage.value,to_stage=x.to_stage.value,rationale=x.rationale,actor_id=x.actor_id,metadata_json=x.metadata,decided_at=x.decided_at,idea_version=x.idea_version));return x
    def list_decisions(self,i):
        with self.sessions() as db:return [_decision(r) for r in db.scalars(select(DecisionRow).where(DecisionRow.tenant_id==self.tenant_id,DecisionRow.idea_id==i).order_by(DecisionRow.decided_at))]

class MemoryIdeaRepository:
    def __init__(self):self.lock=RLock();self.ideas={};self.evidence={};self.tests={};self.experiments={};self.decisions={}
    def save_idea(self,x,expected_version=None):
        with self.lock:
            old=self.ideas.get(x.id)
            if old and expected_version is not None and old.version!=expected_version:raise RuntimeError("idea changed; refresh before deciding")
            self.ideas[x.id]=deepcopy(x);return deepcopy(x)
    def get_idea(self,i):return deepcopy(self.ideas.get(i))
    def list_ideas(self):return deepcopy(list(self.ideas.values()))
    def _add(self,store,x):store.setdefault(x.idea_id,[]).append(deepcopy(x));return deepcopy(x)
    def add_evidence(self,x):return self._add(self.evidence,x)
    def list_evidence(self,i):return deepcopy(self.evidence.get(i,[]))
    def add_test(self,x):return self._add(self.tests,x)
    def list_tests(self,i):return deepcopy(self.tests.get(i,[]))
    def save_experiment(self,x):
        items=self.experiments.setdefault(x.idea_id,[])
        for n,item in enumerate(items):
            if item.id==x.id:items[n]=deepcopy(x);return deepcopy(x)
        items.append(deepcopy(x));return deepcopy(x)
    def list_experiments(self,i):return deepcopy(self.experiments.get(i,[]))
    def add_decision(self,x):return self._add(self.decisions,x)
    def list_decisions(self,i):return deepcopy(self.decisions.get(i,[]))
