"""Scoped billing boundary pins. No external Stripe mutation is performed."""
from datetime import datetime, timezone
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.core.database import Base
from app.modules.m24_billing import repository as r
from app.modules.m24_billing.service import Service
from app.modules.m24_billing.schemas import BillingEventIn
from app.modules.m24_billing.stripe_client import StripeClient

@pytest.mark.asyncio
async def test_unknown_checkout_is_tenant_bound_refusal():
    class Repo:
        def approval(self, aid): return None
    with pytest.raises(PermissionError, match='tenant-bound'):
        await Service(None, Repo(), None).execute_checkout('missing', 'tenant-a')

@pytest.mark.asyncio
async def test_invoice_request_keys_are_separate_stable_and_approval_bound():
    requests=[]
    def respond(request):
        requests.append((request.url.path, request.headers['Idempotency-Key']))
        return httpx.Response(200, json={'id':'in_test'})
    client=StripeClient('sk_test_fixture', httpx.MockTransport(respond))
    await client.create_invoice('cus_test','example',100,'usd','approval-a')
    await client.create_invoice('cus_test','example',100,'usd','approval-a')
    await client.create_invoice('cus_test','example',100,'usd','approval-b')
    assert requests[0][1] != requests[1][1]
    assert requests[:2] == requests[2:4]
    assert requests[0][1] != requests[4][1]
    assert requests[1][1] != requests[5][1]

@pytest.fixture
def db(tmp_path, monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'billing.db'}")
    factory=sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(r,'engine',engine);monkeypatch.setattr(r,'SessionLocal',factory)
    Base.metadata.create_all(engine)
    yield r.Repository(), factory
    engine.dispose()

def test_usage_race_returns_actual_winner_as_dedup(db, monkeypatch):
    repo,factory=db;now=datetime.now(timezone.utc)
    scalar=Session.scalar; injected=[]
    def competing_read(session, statement, *args, **kwargs):
        result=scalar(session,statement,*args,**kwargs)
        if not injected and 'm24_usage' in str(statement) and result is None:
            injected.append(True)
            with factory.begin() as other:
                other.add(r.UsageRow(id='winner',tenant_id='tenant-a',metric='runs',quantity=7,
                                    idempotency_key='same',occurred_at=now,event_metadata={'owner':'winner'}))
        return result
    monkeypatch.setattr(Session,'scalar',competing_read)
    row,created=repo.record_usage('tenant-a','loser','runs',99,'same',now,{})
    assert not created and row.id=='winner' and row.quantity==7
    with factory() as session: assert len(list(session.scalars(select(r.UsageRow)))) == 1

def test_checkout_without_plan_metadata_does_not_grant_pro(db):
    repo,factory=db
    service=Service(None,repo,None)
    event=BillingEventIn(id='evt_test',type='checkout.session.completed',created=1,data={'object':{'metadata':{'tenant_id':'tenant-a'},'customer':'cus_test'}})
    service.ingest_event(event,trusted_provider=True)
    assert service.entitlements('tenant-a').plan_id=='free'
    assert not service.entitlements('tenant-a').can_use_paid_features

@pytest.mark.asyncio
async def test_unknown_checkout_route_maps_to_409():
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.modules.m24_billing.routes import execute
    class Repo:
        def approval(self, aid): return None
    with pytest.raises(HTTPException) as error:
        await execute('unknown', SimpleNamespace(tenant_id='tenant-a'), Service(None,Repo(),None))
    assert error.value.status_code == 409
    assert 'tenant-bound' in error.value.detail

def test_usage_integrity_without_exact_winner_stays_failure(db, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    repo,factory=db
    original=Session.flush
    def fail(session,*a,**kw):
        if any(isinstance(x,r.UsageRow) for x in session.new):
            raise IntegrityError('insert usage',{},RuntimeError('unrelated integrity failure'))
        return original(session,*a,**kw)
    monkeypatch.setattr(Session,'flush',fail)
    with pytest.raises(IntegrityError):
        repo.record_usage('tenant-a','attempt','runs',1,'key',datetime.now(timezone.utc),{})
