from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m07_brand_collaboration.obligations import ObligationError, ObligationNotFound, ObligationTracker

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
CLAUSE = "3.2 Creator will publish two (2) Instagram Reels featuring the product by 20 October 2026."


class Approvals:
    def __init__(self):
        self.items = {}

    def get(self, item_id, *, user_id=None):
        a = self.items.get(item_id)
        return a if a and a.tenant == user_id else None


def setup(tmp_path, tenant="t1"):
    e = create_engine(f"sqlite:///{tmp_path/'o.db'}"); Base.metadata.create_all(e)
    now = [T0]
    brands = {"b1": object()}
    arts = {"inv1": SimpleNamespace(kind="invoice", brand_id="b1", sha256="a" * 64),
            "kit": SimpleNamespace(kind="media_kit", brand_id="b1", sha256="b" * 64)}
    appr = Approvals()
    tr = ObligationTracker(tenant, brands=brands.get, artifacts=arts.get, approvals=appr,
                           session_factory=sessionmaker(bind=e), clock=lambda: now[0])
    return tr, now, appr, e


def reels(tr):
    return tr.create(brand_id="b1", kind="deliverable", title="2 Reels", clause_text=CLAUSE,
                     clause_locator="Section 3.2", quantity=2, due_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
                     amount_minor=150000, currency="USD")


def test_status_moves_open_due_soon_overdue_and_delivered_needs_evidence_and_approval(tmp_path):
    tr, now, appr, _ = setup(tmp_path)
    ob = reels(tr)
    assert ob["status"] == "open" and ob["clause"]["locator"] == "Section 3.2" and ob["billing"] == "not_invoiced"
    now[0] = datetime(2026, 10, 18, tzinfo=timezone.utc)
    assert tr.get(ob["id"])["status"] == "due_soon"
    tr.add_evidence(ob["id"], url="https://instagram.com/reel/1")
    now[0] = datetime(2026, 10, 21, tzinfo=timezone.utc)
    got = tr.get(ob["id"])
    assert got["status"] == "overdue" and "deliverable_overdue" in got["flags"]  # 1 of 2 reels
    appr.items["ap1"] = SimpleNamespace(tenant="t1", status=ApprovalStatus.PENDING)
    tr.link_approval(ob["id"], "ap1")
    got = tr.add_evidence(ob["id"], url="https://instagram.com/reel/2")
    assert got["status"] == "overdue" and "evidence_awaiting_approval" in got["flags"]
    appr.items["ap1"].status = ApprovalStatus.APPROVED
    got = tr.get(ob["id"])
    assert got["status"] == "delivered" and got["flags"] == ["delivered_not_invoiced"]


def test_billing_invoiced_overdue_paid_and_leak_flags(tmp_path):
    tr, now, _, _ = setup(tmp_path)
    ob = reels(tr)
    got = tr.link_invoice(ob["id"], "inv1", payment_due_at=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert got["billing"] == "invoiced" and "invoiced_before_delivery" in got["flags"]
    tr.add_evidence(ob["id"], url="u1"); tr.add_evidence(ob["id"], url="u2")
    now[0] = datetime(2026, 11, 5, tzinfo=timezone.utc)
    got = tr.get(ob["id"])
    assert got["status"] == "delivered" and got["billing"] == "payment_overdue" and got["flags"] == ["payment_overdue"]
    summary = tr.brand_tracker("b1")["summary"]
    assert summary["outstanding_minor"] == 150000 and summary["flags"] == ["payment_overdue"]
    tr.record_payment(ob["id"], amount_minor=100000)
    assert tr.get(ob["id"])["billing"] == "payment_overdue"
    got = tr.record_payment(ob["id"], amount_minor=50000, note="bank transfer ref 991")
    assert got["billing"] == "paid" and got["flags"] == [] and got["paid_minor"] == 150000


def test_exclusivity_and_waiver_and_brand_summary(tmp_path):
    tr, now, _, _ = setup(tmp_path)
    ex = tr.create(brand_id="b1", kind="exclusivity", title="No competing skincare", clause_text="5.1 No competitor posts for 60 days.",
                   clause_locator="Section 5.1", ends_at=T0 + timedelta(days=60))
    assert "exclusivity_active" in ex["flags"] and ex["status"] == "open"
    ob = reels(tr)
    tr.waive(ob["id"], reason="Brand email 12 Oct releases the second Reel")
    s = tr.brand_tracker("b1")["summary"]
    assert s["total"] == 2 and s["open"] == 1 and s["next_deadline"] is None
    now[0] = T0 + timedelta(days=61)
    assert tr.get(ex["id"])["status"] == "delivered" and tr.get(ex["id"])["flags"] == []


def test_guards_and_tenant_isolation(tmp_path):
    tr, _, appr, e = setup(tmp_path)
    with pytest.raises(ObligationNotFound):
        tr.create(brand_id="nope", kind="deliverable", title="x", clause_text=CLAUSE, clause_locator="s")
    with pytest.raises(ObligationError):
        tr.create(brand_id="b1", kind="deliverable", title="x", clause_text="  ", clause_locator="s")
    ob = reels(tr)
    with pytest.raises(ObligationError):
        tr.add_evidence(ob["id"])
    with pytest.raises(ObligationNotFound):
        tr.link_invoice(ob["id"], "kit", payment_due_at=T0)
    appr.items["other"] = SimpleNamespace(tenant="t2", status=ApprovalStatus.APPROVED)
    with pytest.raises(ObligationNotFound):
        tr.link_approval(ob["id"], "other")
    other = ObligationTracker("t2", brands={"b1": 1}.get, artifacts={}.get, approvals=appr,
                              session_factory=sessionmaker(bind=e))
    with pytest.raises(ObligationNotFound):
        other.get(ob["id"])
    assert other.brand_tracker("b1")["obligations"] == []


def test_http_routes_create_and_track(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m07_brand_collaboration import routes
    monkeypatch.setenv("ATLAS_ENV", "development")
    app = FastAPI(); app.include_router(routes.router)
    c = TestClient(app)
    brand = c.post("/brand-collaboration/brands", params={"creator_mission": "science education for kids"},
                   json={"name": "Lab Co", "mission": "science kits for kids", "public_url": "https://lab.example.com"})
    assert brand.status_code == 201, brand.text
    bid = brand.json()["id"]
    r = c.post("/brand-collaboration/obligations", json={"brand_id": bid, "kind": "deliverable", "title": "1 video",
                                                          "clause_text": "2.1 One YouTube video.", "clause_locator": "2.1",
                                                          "amount_minor": 5000})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert c.post(f"/brand-collaboration/obligations/{oid}/evidence", json={"url": "https://youtu.be/x"}).json()["status"] == "delivered"
    t = c.get(f"/brand-collaboration/brands/{bid}/obligations").json()
    assert t["summary"]["unbilled_delivered_minor"] == 5000
    assert c.post(f"/brand-collaboration/obligations/{oid}/approvals", json={"approval_id": "nope"}).status_code == 404
