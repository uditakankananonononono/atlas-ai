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

def test_interleaved_save_with_same_expected_version_has_exactly_one_winner(tmp_path):
    # A worker thread reads version 1 and is parked at its write statement
    # while the main thread completes a full save that moves the idea to
    # version 2. The worker's save must then lose: its expected_version=1 is
    # stale at write time even though it was fresh at read time. A
    # read-then-write version check cannot guard this interleaving; only an
    # atomic conditional claim can. WAL keeps the parked reader from blocking
    # the first writer's commit so the interleaving is deterministic. On
    # read-then-write code this pin fails: the stale writer's plain UPDATE
    # either silently overwrites (journal_mode=delete) or dies with a snapshot
    # lock error (WAL) - never an honest version conflict.
    import itertools, threading
    from sqlalchemy import event
    engine = create_engine(f"sqlite:///{tmp_path/'race.db'}", connect_args={"timeout": 30})
    with engine.connect() as setup_conn:
        setup_conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    service = LedgerService(SqlIdeaRepository("tenant-race", sessions), "actor-r")
    x = service.create_idea(idea())

    release_first_update = threading.Event()
    worker_parked = threading.Event()
    update_count = itertools.count()
    count_lock = threading.Lock()

    @event.listens_for(engine, "before_cursor_execute")
    def hold_first_update(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE") and "m19_ideas" in statement:
            with count_lock:
                n = next(update_count)
            if n == 0:
                worker_parked.set()
                release_first_update.wait(25)

    def bumped():
        updated = service._idea(x.id)
        updated.stage = IdeaStage.DISCOVERY
        updated.version += 1
        updated.updated_at = datetime.now(timezone.utc)
        return updated

    worker_out = []
    def attempt():
        try:
            service.repository.save_idea(bumped(), expected_version=1)
            worker_out.append("saved")
        except RuntimeError:
            worker_out.append("conflict")

    worker = threading.Thread(target=attempt)
    worker.start()
    assert worker_parked.wait(10), "worker did not reach its write statement"
    main_out = []
    try:
        service.repository.save_idea(bumped(), expected_version=1)
        main_out.append("saved")
    except RuntimeError:
        main_out.append("conflict")
    release_first_update.set()
    worker.join(30)
    outcomes = sorted(worker_out + main_out)
    assert outcomes == ["conflict", "saved"], outcomes
    assert service.repository.get_idea(x.id).version == 2
