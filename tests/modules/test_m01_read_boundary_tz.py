"""Pin for M01 read-boundary tz attachment on first_seen/last_seen.

sqlite drops tzinfo on DateTime(timezone=True) reads. Both fields have a
single writer (_ingest) that stores datetime.now(timezone.utc), so the read
side attaches the known-UTC zone, matching the deadline convention already in
_to_out. Establishes the storage-convention read coercion only; legacy
pre-policy rows are not rewritten.
"""
from datetime import timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m01_opportunity_discovery.schemas import OpportunityType
from app.modules.m01_opportunity_discovery.service import Service, Source, SourceKind

_FEED = (b'<?xml version="1.0"?><rss version="2.0"><channel><item>'
         b'<title>Hack</title><link>https://x/1</link>'
         b'<description>d deadline: 2026-12-31</description></item></channel></rss>')

def _service():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    src = Source(id="s1", name="t", kind=SourceKind.RSS, url="https://x/feed",
                 default_type=OpportunityType.HACKATHON)
    return Service(tenant_id="t1", sources=[src], fetcher=lambda s: _FEED,
                   session_factory=sessions)

def test_first_seen_last_seen_read_back_aware_utc():
    svc = _service()
    svc.run_scan()
    (out,) = svc.list_opportunities()
    assert out.first_seen.tzinfo is not None
    assert out.last_seen.tzinfo is not None
    assert out.first_seen.utcoffset() == out.last_seen.utcoffset() == timezone.utc.utcoffset(None)
    assert out.first_seen <= out.last_seen
