from datetime import date, datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m07_brand_collaboration.schemas import MediaKitIn, ReportIn
from app.modules.m07_brand_collaboration.service import Service
from app.modules.m07_brand_collaboration.sql_repository import Repository, EventRow

class Repo:
    tenant_id='local-fixture'
    def __init__(self):self.artifacts=[];self.queries=[]
    def brand(self,i):return object() if i=='b1' else None
    def add_artifact(self,**data):self.artifacts.append(data)
    def events(self,i,*,start_at,end_before):
        self.queries.append((i,start_at,end_before))
        times=['2025-12-31T23:59:59+00:00','2026-01-01T00:00:00+00:00','2026-01-31T23:59:59.999999+00:00','2026-02-01T00:00:00+00:00']
        return [SimpleNamespace(occurred_at=datetime.fromisoformat(t)) for t in times if start_at<=datetime.fromisoformat(t)<end_before]

def service():
    r=Repo();return Service(r,None),r

@pytest.mark.parametrize('kind',['kit','report'])
def test_caller_metrics_not_promoted_to_verified(kind,monkeypatch):
    svc,r=service();monkeypatch.setattr(svc,'_pdf',lambda h:(h.encode(),'text/html'))
    if kind=='kit':a=svc.media_kit(MediaKitIn(brand_id='b1',creator_name='Ada <script>',creator_mission='science',metrics={'<reach>':100}))
    else:a=svc.report(ReportIn(brand_id='b1',period_start=date(2026,1,1),period_end=date(2026,1,31),metrics={'<views>':50}))
    html=r.artifacts[-1]['content'].decode()
    assert 'Verified metrics' not in html
    assert 'Supplied metrics (not independently verified)' in html
    assert '&lt;' in html and '<reach>' not in html and '<views>' not in html
    assert a.metadata['metrics_verified'] is False and a.metadata['metrics_source']=='caller_supplied'
    assert a.sha256==sha256(r.artifacts[-1]['content']).hexdigest()

def test_report_passes_exact_inclusive_utc_period(monkeypatch):
    svc,r=service();monkeypatch.setattr(svc,'_pdf',lambda h:(h.encode(),'text/html'))
    a=svc.report(ReportIn(brand_id='b1',period_start=date(2026,1,1),period_end=date(2026,1,31),metrics={}))
    assert r.queries==[('b1',datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,2,1,tzinfo=timezone.utc))]
    assert a.metadata['event_count']==2 and a.metadata['period_timezone']=='UTC'
    assert '2 partnership ledger events within the reporting period' in r.artifacts[-1]['content'].decode()

def test_sql_period_filters_both_boundaries_brand_and_tenant(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "period.db"}');Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine);repo=Repository('t1',sessions)
    with sessions.begin() as db:
        for i,(tenant,brand,at) in enumerate([('t1','b1','2025-12-31T23:59:59'),('t1','b1','2026-01-01T00:00:00'),('t1','b1','2026-01-31T23:59:59.999999'),('t1','b1','2026-02-01T00:00:00'),('t2','b1','2026-01-15T00:00:00'),('t1','b2','2026-01-15T00:00:00')]):
            db.add(EventRow(tenant_id=tenant,brand_id=brand,id=str(i),kind='metric',occurred_at=datetime.fromisoformat(at),created_at=datetime.now(timezone.utc),data={}))
    rows=repo.events('b1',start_at=datetime(2026,1,1,tzinfo=timezone.utc),end_before=datetime(2026,2,1,tzinfo=timezone.utc))
    assert [r.id for r in rows]==['1','2']

def test_invalid_period_creates_no_artifact():
    svc,r=service()
    with pytest.raises(ValueError,match='invalid reporting period'):svc.report(ReportIn(brand_id='b1',period_start=date(2026,2,1),period_end=date(2026,1,31),metrics={}))
    assert not r.artifacts and not r.queries

def test_sql_service_logs_native_dates_and_report_reads_only_period(tmp_path,monkeypatch):
    from app.modules.m07_brand_collaboration.schemas import BrandDiscoveryIn,PartnershipEventIn
    engine=create_engine(f'sqlite:///{tmp_path / "service.db"}');Base.metadata.create_all(engine)
    repo=Repository('t1',sessionmaker(bind=engine));svc=Service(repo,None)
    brand=svc.discover(BrandDiscoveryIn(name='Fixture',mission='science access',public_url='https://fixture.test'),'science')
    for at in ['2025-12-31T23:59:59+00:00','2026-01-01T00:00:00+00:00','2026-01-31T23:59:59+00:00','2026-02-01T00:00:00+00:00']:
        svc.log_event(PartnershipEventIn(brand_id=brand.id,kind='metric',occurred_at=datetime.fromisoformat(at),data={}))
    monkeypatch.setattr(svc,'_pdf',lambda h:(h.encode(),'text/html'))
    report=svc.report(ReportIn(brand_id=brand.id,period_start=date(2026,1,1),period_end=date(2026,1,31),metrics={}))
    stored=repo.artifact(report.id)
    assert report.metadata['event_count']==stored.metadata_json['event_count']==2
    assert b'2 partnership ledger events within the reporting period' in stored.content

@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_actual_service_nonzero_offsets_use_utc_period(tmp_path,kind,monkeypatch):
    from app.modules.m07_brand_collaboration.schemas import BrandDiscoveryIn,PartnershipEventIn
    if kind=='postgres':
        pgserver=pytest.importorskip('pgserver');pytest.importorskip('psycopg')
        server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop');url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    else:url=f'sqlite:///{tmp_path / "offset.db"}'
    engine=create_engine(url);Base.metadata.create_all(engine);repo=Repository('t1',sessionmaker(bind=engine));svc=Service(repo,None)
    brand=svc.discover(BrandDiscoveryIn(name='Fixture',mission='science access',public_url='https://fixture.test'),'science')
    included=svc.log_event(PartnershipEventIn(brand_id=brand.id,kind='metric',occurred_at=datetime.fromisoformat('2026-02-01T00:30:00+05:30'),data={}))
    excluded=svc.log_event(PartnershipEventIn(brand_id=brand.id,kind='metric',occurred_at=datetime.fromisoformat('2026-01-31T23:30:00-05:00'),data={}))
    assert included.occurred_at==datetime(2026,1,31,19,tzinfo=timezone.utc)
    assert included.occurred_at.utcoffset().total_seconds()==0
    with repo.sessions() as db:
        from sqlalchemy import select
        stored=db.scalar(select(EventRow).where(EventRow.id==included.id))
        assert (stored.occurred_at.replace(tzinfo=timezone.utc) if stored.occurred_at.tzinfo is None else stored.occurred_at.astimezone(timezone.utc))==included.occurred_at
    rows=repo.events(brand.id,start_at=datetime(2026,1,1,tzinfo=timezone.utc),end_before=datetime(2026,2,1,tzinfo=timezone.utc))
    assert [r.id for r in rows]==[included.id] and excluded.id not in [r.id for r in rows]
    monkeypatch.setattr(svc,'_pdf',lambda h:(h.encode(),'text/html'))
    report=svc.report(ReportIn(brand_id=brand.id,period_start=date(2026,1,1),period_end=date(2026,1,31),metrics={}))
    assert repo.artifact(report.id).metadata_json['event_count']==1
    with pytest.raises(ValueError,match='must include a timezone'):
        svc.log_event(PartnershipEventIn(brand_id=brand.id,kind='metric',occurred_at=datetime(2026,1,15),data={}))
    assert len(repo.events(brand.id,start_at=datetime(2026,1,1,tzinfo=timezone.utc),end_before=datetime(2026,3,1,tzinfo=timezone.utc)))==2
    engine.dispose()
