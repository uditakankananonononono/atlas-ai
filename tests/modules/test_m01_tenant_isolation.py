from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m01_opportunity_discovery.schemas import ProfileIn, SourceKind
from app.modules.m01_opportunity_discovery.service import Service, Source


RSS = b"""<rss><channel><item><title>Open science grant</title><link>https://example.org/call</link><description>Grant funding</description></item></channel></rss>"""


def services():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    source = Source("official", "Official", SourceKind.RSS, "https://example.org/feed")
    common = dict(session_factory=sessions, fetcher=lambda _: RSS, sources=[source])
    return Service(**common, tenant_id="tenant-a"), Service(**common, tenant_id="tenant-b")


def test_same_url_is_isolated_with_distinct_storage_identity():
    a, b = services()
    assert a.run_scan(profile=ProfileIn()).new == 1
    assert b.run_scan(profile=ProfileIn()).new == 1
    a_item = a.list_opportunities()[0]
    b_item = b.list_opportunities()[0]
    assert a_item.url == b_item.url
    assert a_item.id != b_item.id
    assert a.get_opportunity(b_item.id) is None
    assert b.get_opportunity(a_item.id) is None


def test_tenant_rescan_updates_only_its_own_record():
    a, b = services()
    first = a.run_scan(profile=ProfileIn())
    second = a.run_scan(profile=ProfileIn())
    assert (first.new, first.updated) == (1, 0)
    assert (second.new, second.updated) == (0, 1)
    assert b.list_opportunities() == []


def test_digest_approval_carries_tenant_boundary():
    captured = []
    a, _ = services()
    a._approval_putter = lambda request: captured.append(request) or request
    a.run_scan(profile=ProfileIn())
    item = a.list_opportunities()[0]
    a.propose_digest([item], "body", "owner@example.org")
    assert captured[0].payload["tenant_id"] == "tenant-a"


def test_default_digest_approval_is_stored_under_service_tenant(monkeypatch):
    captured = {}
    class ApprovalService:
        def submit(self, **values):
            captured.update(values)
            return {"id": "approval-1", "module_id": values["module_id"],
                    "action_type": values["action_type"], "payload": values["payload"],
                    "status": __import__("app.core.models", fromlist=["ApprovalStatus"]).ApprovalStatus.PENDING}
    monkeypatch.setattr("app.modules.m00_approval_center.service.default_service",
                        lambda: ApprovalService())
    a, _ = services()
    a.run_scan(profile=ProfileIn())
    result = a.propose_digest(a.list_opportunities(), "body")
    assert result.id == "approval-1"
    assert captured["user_id"] == "tenant-a"
    assert captured["payload"]["tenant_id"] == "tenant-a"
