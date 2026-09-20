import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.m13_browser_agent.domain import ActionType, AuditEvent
from app.modules.m13_browser_agent.store import SQLStore


@pytest.fixture
def store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SQLStore(sessionmaker(bind=engine))


@pytest.mark.asyncio
async def test_approval_claim_is_single_use(store):
    await store.consume("approval", "tenant")
    assert await store.was_consumed("approval")
    with pytest.raises(PermissionError):
        await store.consume("approval", "tenant")


@pytest.mark.asyncio
async def test_audit_reads_are_tenant_and_run_scoped(store):
    await store.append_audit(AuditEvent("a", "r", ActionType.CLICK, {"selector": "#x"}))
    await store.append_audit(AuditEvent("b", "r", ActionType.CLICK, {"selector": "#secret"}))
    events = await store.audit_events("a", "r")
    assert len(events) == 1
    assert events[0].payload == {"selector": "#x"}
