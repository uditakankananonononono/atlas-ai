from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m21_claire.persistent_journal import PersistentJournal,JournalBase
from app.modules.m21_claire.cursor_journal_retrieval import cursor_retrieve

@pytest.fixture
def journal(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "journal.db"}')
    j=PersistentJournal('tenant','actor',sessionmaker(bind=engine))
    yield j
    engine.dispose()


def test_single_limit_no_count_and_probe_not_consumed(journal):
    ids=[journal.capture('topic','why','','ref')['id'] for _ in range(7)]
    queries=[]
    event.listen(journal.sessions.kw['bind'],'before_cursor_execute',lambda c,u,s,p,x,m:queries.append(s))
    out=journal.retrieve_cursor('topic',limit=3,scan_cap=3)
    assert out['matched_total'] is None and out['has_more'] and out['rows_materialized']==4 and out['rows_scored']==3
    assert out['next_before_id']==ids[-3]
    assert len(queries)==1 and 'count(' not in queries[0].lower() and 'LIMIT' in queries[0]
    next_=journal.retrieve_cursor('topic',limit=3,scan_cap=3,before_id=out['next_before_id'])
    assert ids[-4] in [x['id'] for x in next_['hits']]


def test_zero_hit_pages_union_exact(journal):
    ids=[journal.capture('topic','why','','ref')['id'] for _ in range(7)]
    before=None;seen=[]
    while True:
        out=journal.retrieve_cursor('unrelated',limit=3,scan_cap=3,before_id=before)
        assert not out['hits']
        seen.extend(range(out['oldest_scanned_id'],out['newest_scanned_id']+1))
        if not out['has_more']:break
        before=out['next_before_id']
    assert sorted(seen)==ids


def test_empty_window_total_unknown(journal):
    out=journal.retrieve_cursor('topic',limit=1,scan_cap=1)
    assert out['matched_total'] is None and out['rows_materialized']==0
    assert out['next_before_id'] is None and out['has_more'] is False


def test_scope_filters_time_and_cursor(journal):
    own=journal.capture('topic','why','','ref')['id']
    foreign=PersistentJournal('foreign','actor',journal.sessions);foreign.capture('topic','why','','ref')
    other=PersistentJournal('tenant','other',journal.sessions);other.capture('topic','why','','ref')
    assert [x['id'] for x in journal.retrieve_cursor('topic')['hits']]==[own]
    assert not journal.retrieve_cursor('topic',after_id=own)['hits']
    assert not journal.retrieve_cursor('topic',until=datetime(2000,1,1,tzinfo=timezone.utc))['hits']

@pytest.mark.parametrize('kw',[{'limit':0},{'scan_cap':0},{'scan_cap':True},{'limit':2,'scan_cap':1},{'before_id':True},{'since':datetime(2026,1,1)},{'kind':'bad'},{'after_id':2,'before_id':1}])
def test_invalid_before_any_query(kw):
    class Explode:
        def scalars(self,*a):raise AssertionError('queried')
    with pytest.raises(ValueError):cursor_retrieve(Explode(),tenant_id='t',actor_id='a',query='topic',**kw)


def test_real_auth_route_and_errors(journal,oidc_auth_headers,monkeypatch):
    from app.modules.m21_claire import persistent_journal_routes as r
    from app.auth import context
    monkeypatch.setattr(r,'SessionLocal',journal.sessions)
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    journal.capture('topic','why','','ref')
    app=FastAPI();app.include_router(r.router)
    with TestClient(app) as c:
        headers=oidc_auth_headers('tenant','actor')
        out=c.get('/claire/journal/decisions/cursor',params={'query':'topic'},headers=headers)
        assert out.status_code==200 and out.json()['matched_total'] is None and len(out.json()['hits'])==1
        assert c.get('/claire/journal/decisions/cursor',params={'query':'topic'}).status_code==401
        other=c.get('/claire/journal/decisions/cursor',params={'query':'topic'},headers=oidc_auth_headers('foreign','actor'))
        assert other.status_code==200 and other.json()['hits']==[]
        bad=c.get('/claire/journal/decisions/cursor',params={'query':'topic','since':'2026-01-01T00:00:00'},headers=headers)
        assert bad.status_code==422


def test_postgres_cursor_actual_limit_query(tmp_path):
    pgserver=pytest.importorskip('pgserver');pytest.importorskip('psycopg')
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    engine=create_engine(server.get_uri().replace('postgresql://','postgresql+psycopg://'))
    try:
        j=PersistentJournal('tenant','actor',sessionmaker(bind=engine))
        ids=[j.capture('topic','why','','ref')['id'] for _ in range(5)]
        statements=[]
        event.listen(engine,'before_cursor_execute',lambda c,u,s,p,x,m:statements.append(s))
        out=j.retrieve_cursor('topic',limit=2,scan_cap=2)
        assert out['has_more'] and out['rows_materialized']==3 and out['next_before_id']==ids[-2]
        assert len(statements)==1 and 'count(' not in statements[0].lower()
        with engine.connect() as db:
            version=db.exec_driver_sql('SELECT version()').scalar()
        print('PG cursor probe:',version)
    finally:engine.dispose()
