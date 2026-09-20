from datetime import datetime,timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m19_idea_incubator.repository import SqlIdeaRepository
from app.modules.m19_idea_incubator.schemas import *
from app.modules.m19_idea_incubator.ledger import LedgerService

def setup():
 engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);sessions=sessionmaker(engine)
 return LedgerService(SqlIdeaRepository("tenant-a",sessions),"actor-a"),LedgerService(SqlIdeaRepository("tenant-b",sessions),"actor-b")
def idea():return IdeaCreate(title="Idea",problem="Problem",proposed_solution="Solution")
def evidence():return EvidenceCreate(kind=EvidenceKind.MARKET_DATA,claim="Demand",source="study",polarity=EvidencePolarity.SUPPORTS,strength=.8,confidence=.7,observed_at=datetime.now(timezone.utc))
def feasibility():
 d=DimensionScore(score=80,confidence=.8)
 return FeasibilityTestCreate(desirability=d,technical=d,viability=d,strategic_fit=d,compliance=d)
def experiment():return ExperimentCreate(name="Pilot",hypothesis="Converts",method="Run pilot",metric="conversion",target=10)

def test_sql_repository_roundtrips_all_ledger_entities():
 a,_=setup();x=a.create_idea(idea());a.add_evidence(x.id,evidence());a.test_feasibility(x.id,feasibility());e=a.create_experiment(x.id,experiment());a.decide(x.id,DecisionCreate(to_stage=IdeaStage.DISCOVERY,rationale="Explore"));d=a.dossier(x.id)
 assert d.idea.title=="Idea";assert len(d.evidence)==1;assert len(d.feasibility_tests)==1;assert d.experiments[0].id==e.id;assert d.decisions[0].actor_id=="actor-a"

def test_sql_repository_enforces_tenant_isolation():
 a,b=setup();x=a.create_idea(idea());assert b.repository.get_idea(x.id) is None;assert b.list_ideas()==[]

def test_sql_repository_optimistic_version_conflict():
 a,_=setup();x=a.create_idea(idea());stale=a._idea(x.id);a.decide(x.id,DecisionCreate(to_stage=IdeaStage.DISCOVERY,rationale="Explore",expected_version=1));stale.title="late writer"
 import pytest
 with pytest.raises(RuntimeError,match="changed"):a.repository.save_idea(stale,expected_version=1)
