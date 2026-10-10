"""Real PG immutable captured rankings, never reconstruction or history backfill."""
from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.auth.context import TenantContext
from app.modules.m19_idea_incubator.repository import IdeaRow,EvidenceRow,FeasibilityRow,ExperimentRow
from app.modules.m19_idea_incubator.snapshots import SnapshotService,SnapshotRow,SnapshotCounterRow,SnapshotError
from app.modules.m19_idea_incubator.schemas import Idea,IdeaStage,Evidence,EvidenceKind,EvidencePolarity
T0=datetime(2026,6,1,tzinfo=timezone.utc)
ASOF=datetime(2026,9,1,tzinfo=timezone.utc)
OWNER=TenantContext('a','owner',frozenset())
FOREIGN=TenantContext('b','other',frozenset())
PARAMS={'as_of':ASOF,'half_life_days':90.0,'include_terminal':False,'limit':None,'stale_experiment_policy':'exclude'}

@pytest.fixture
def env(tmp_path):
    import pgserver
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    sessions=sessionmaker(engine,expire_on_commit=False)
    for row in (IdeaRow,EvidenceRow,FeasibilityRow,ExperimentRow,SnapshotCounterRow,SnapshotRow):row.__table__.create(engine)
    with sessions.begin() as db:
        db.add(IdeaRow(tenant_id='a',id='i',title='idea',problem='p',proposed_solution='s',tags=[],metadata_json={},stage='validation',version=1,created_at=T0,updated_at=T0))
        for id,observed in [('e',T0),('future',ASOF+timedelta(days=1))]:
            db.add(EvidenceRow(tenant_id='a',id=id,idea_id='i',kind='other',claim='claim-'+id,source='source',polarity='supports',strength=.8,confidence=.5,observed_at=observed,created_at=observed,metadata_json={'unknown':None}))
    yield SnapshotService(sessions,code_version='test-code-sha'),sessions,engine
    engine.dispose()


def test_capture_read_restart_full_excluded_and_current_divergence(env):
    svc,sessions,_=env
    assert svc.find(OWNER,**PARAMS)['snapshot_available'] is False
    captured=svc.capture(OWNER,**PARAMS)
    assert captured['schema_version']==1 and captured['revision']==1
    assert captured['census_scope']=='visited_rows_only' and captured['consistent_read'] is True
    assert captured['source_state_caveat'] and captured['reconstruction_claimed'] is False
    assert captured['included']['ideas'][0]['id']=='i'
    assert captured['excluded'][0]['row']['claim']=='claim-future'
    assert captured['excluded'][0]['row']['metadata']['unknown'] is None
    assert len(captured['content_hash'])==64
    with sessions.begin() as db:db.scalar(select(EvidenceRow).where(EvidenceRow.id=='e')).claim='changed'
    fresh=SnapshotService(sessions,code_version='test-code-sha')
    assert fresh.get(OWNER,captured['snapshot_id'])==captured
    assert fresh.find(OWNER,**PARAMS)['snapshot']==captured
    assert fresh.live(OWNER,**PARAMS)['label']=='current_filter'
    assert fresh.compare(OWNER,captured['snapshot_id'])['diverged'] is True
    assert fresh.capture(OWNER,**PARAMS)['revision']==2


def test_tenant_owner_and_schema_hash_fail_closed(env):
    svc,sessions,_=env;s=svc.capture(OWNER,**PARAMS)
    for ctx in (FOREIGN,TenantContext('a','different-owner',frozenset())):
        with pytest.raises(SnapshotError):svc.get(ctx,s['snapshot_id'])
    with sessions.begin() as db:
        row=db.get(SnapshotRow,s['snapshot_id']);row.payload={**row.payload,'schema_version':99}
    with pytest.raises(SnapshotError):svc.get(OWNER,s['snapshot_id'])


def test_unsupported_sqlite_refuses_capture_live_filter_still_works(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'sqlite.db'));sessions=sessionmaker(engine)
    for row in (IdeaRow,EvidenceRow,FeasibilityRow,ExperimentRow,SnapshotCounterRow,SnapshotRow):row.__table__.create(engine)
    svc=SnapshotService(sessions,code_version='test')
    with pytest.raises(SnapshotError,match='REPEATABLE READ'):svc.capture(OWNER,**PARAMS)
    assert svc.live(OWNER,**PARAMS)['result']['ranking']['ranked']==[]
    engine.dispose()


def test_record_capacity_no_eviction_and_lower_only(env):
    _,sessions,_=env
    with pytest.raises(SnapshotError):SnapshotService(sessions,code_version='test',max_records=1001)
    with pytest.raises(SnapshotError):SnapshotService(sessions,code_version='test',max_bytes=4000001)
    svc=SnapshotService(sessions,code_version='test',max_records=1)
    first=svc.capture(OWNER,**PARAMS)
    with pytest.raises(SnapshotError,match='capacity'):svc.capture(OWNER,**PARAMS)
    assert svc.get(OWNER,first['snapshot_id'])==first
    tiny=SnapshotService(sessions,code_version='test',max_bytes=100)
    with pytest.raises(SnapshotError,match='bytes'):tiny.capture(FOREIGN,**PARAMS)
    with sessions() as db:assert len(list(db.scalars(select(SnapshotRow))))==1


def test_capture_concurrent_tenant_revisions_no_lost_cap(env):
    from concurrent.futures import ThreadPoolExecutor
    _,sessions,_=env;svc=SnapshotService(sessions,code_version='test',max_records=1)
    def cap():
        try:return svc.capture(OWNER,**PARAMS)['revision']
        except SnapshotError:return 'refused'
    with ThreadPoolExecutor(2) as pool:out=list(pool.map(lambda _:cap(),range(2)))
    assert sorted(map(str,out))==['1','refused']
    with sessions() as db:assert len(list(db.scalars(select(SnapshotRow))))==1


def test_actual_oidc_capture_read_compare_tenant_and_owner_routes(env,monkeypatch,oidc_auth_headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m19_idea_incubator import snapshot_router
    svc,_,_=env;app=FastAPI();app.include_router(snapshot_router.router)
    app.dependency_overrides[snapshot_router.get_snapshot_service]=lambda:svc
    monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
    body={**PARAMS,'as_of':ASOF.isoformat()}
    with TestClient(app) as client:
        url='/portfolio/ranking-snapshots';owner=oidc_auth_headers('a','owner')
        assert client.post(url,json=body).status_code==401
        response=client.post(url,json=body,headers=owner);assert response.status_code==201,response.text
        sid=response.json()['snapshot_id']
        assert client.get(url+'/'+sid,headers=owner).json()==response.json()
        assert client.get(url+'/'+sid+'/compare',headers=owner).json()['diverged'] is False
        for other in (oidc_auth_headers('b','other'),oidc_auth_headers('a','other')):
            assert client.get(url+'/'+sid,headers=other).status_code==404
        assert client.post(url+'/find',headers=owner,json=body).json()['snapshot_available'] is True
        assert client.post(url,headers=owner,json={**body,'as_of':'2026-09-01T00:00:00'}).status_code==422


def test_pg_repeatable_read_concurrent_edit_after_first_read(env,monkeypatch):
    import app.modules.m19_idea_incubator.snapshots as module
    svc,sessions,_=env;original=module.SessionRepository.list_ideas;hit=[]
    def edit_after_read(repo):
        rows=original(repo)
        with sessions.begin() as other:other.scalar(select(EvidenceRow).where(EvidenceRow.id=='e')).claim='concurrent-new-value'
        hit.append(True);return rows
    monkeypatch.setattr(module.SessionRepository,'list_ideas',edit_after_read)
    snapshot=svc.capture(OWNER,**PARAMS)
    assert hit and snapshot['included']['evidence'][0]['claim']=='claim-e'
    monkeypatch.setattr(module.SessionRepository,'list_ideas',original)
    assert svc.compare(OWNER,snapshot['snapshot_id'])['diverged'] is True


def test_no_unvisited_terminal_evidence_or_deleted_history_is_invented(env):
    svc,sessions,_=env
    with sessions.begin() as db:
        db.scalar(select(IdeaRow)).stage='parked'
    snapshot=svc.capture(OWNER,**PARAMS)
    assert snapshot['included']['evidence']==[] and snapshot['excluded']==[]
    assert snapshot['result']['ranking']['ranked']==[]
    assert snapshot['census_scope']=='visited_rows_only'
    assert svc.find(OWNER,**{**PARAMS,'as_of':T0})=={'snapshot_available':False}


def test_migration_pg_empty_down_and_up(env):
    import importlib.util
    from pathlib import Path
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect
    _,_,engine=env
    with engine.begin() as connection:
        SnapshotRow.__table__.drop(connection);SnapshotCounterRow.__table__.drop(connection)
        path=Path(__file__).resolve().parents[2]/'migrations/versions/20261010_m19_rank_snapshots.py'
        spec=importlib.util.spec_from_file_location('snapshot_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();assert connection.execute(select(SnapshotRow)).all()==[]
            module.downgrade();assert 'm19_ranking_snapshots' not in inspect(connection).get_table_names()
            module.upgrade()

@pytest.mark.parametrize('bad',[{'half_life_days':float('nan')},{'half_life_days':0},{'half_life_days':float('inf')},{'include_terminal':1},{'limit':True},{'stale_experiment_policy':'invent'}])
def test_invalid_parameters_never_create_record(env,bad):
    svc,sessions,_=env
    with pytest.raises(SnapshotError):svc.capture(OWNER,**{**PARAMS,**bad})
    with sessions() as db:assert not db.scalar(select(SnapshotRow)) and not db.scalar(select(SnapshotCounterRow))


def test_hash_tampering_and_transaction_rollback_no_reserved_slot(env,monkeypatch):
    svc,sessions,_=env;original=svc._rank
    def fault(*a):raise RuntimeError('capture interrupted')
    monkeypatch.setattr(svc,'_rank',fault)
    with pytest.raises(RuntimeError):svc.capture(OWNER,**PARAMS)
    with sessions() as db:assert not db.scalar(select(SnapshotCounterRow)) and not db.scalar(select(SnapshotRow))
    monkeypatch.setattr(svc,'_rank',original);record=svc.capture(OWNER,**PARAMS)
    with sessions.begin() as db:db.get(SnapshotRow,record['snapshot_id']).content_hash='0'*64
    with pytest.raises(SnapshotError,match='checksum'):svc.get(OWNER,record['snapshot_id'])
