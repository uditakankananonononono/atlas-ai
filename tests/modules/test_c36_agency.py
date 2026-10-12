"""c36.agency tests (row 108): brand kit, catalog, full CRM pipeline with
exact-draft approval, invoice + recorded-payment ledger, money refusals."""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c36 import agency  # noqa: E402

SERVICES = [{"id": "svc1", "name": "Landing page", "price_cents": 15000, "unit": "page"}]


def test_brand_kit_deterministic():
    k = agency.brand_kit({"name": "Udita Builds", "skills": ["web apps", "design"],
                          "audience": "student founders"})
    assert k["brand_name"] == "Udita Builds"
    assert k["positioning"].startswith("web apps for student founders")
    assert len(k["palette"]) == 3 and all(p.startswith("#") for p in k["palette"])
    assert k["generated_posting"] is False


def test_catalog_validation():
    out = agency.catalog(SERVICES)
    assert out["count"] == 1
    with pytest.raises(ValueError, match="AGENCY_REFUSED_BAD_TYPE:price_cents"):
        agency.catalog([{"id": "x", "name": "y", "price_cents": -5}])


def full_pipeline(store):
    lead = agency.add_lead(store, {"name": "Cafe K", "need": "new landing page",
                                   "service_id": "svc1"})
    agency.qualify(store, lead["id"])
    agency.draft_proposal(store, lead["id"], "One landing page, two revisions",
                          SERVICES)
    return lead


def test_pipeline_states_and_exact_draft_approval():
    store = {}
    lead = full_pipeline(store)
    client = store["clients"][lead["id"]]
    assert client["state"] == "proposal_drafted"
    assert client["proposal"]["sent"] is False
    with pytest.raises(ValueError, match="AGENCY_REFUSED_EXACT_DRAFT"):
        agency.owner_approve(store, lead["id"], "Udita", "wrong-hash")
    agency.owner_approve(store, lead["id"], "Udita", client["proposal"]["hash"])
    assert store["clients"][lead["id"]]["state"] == "owner_approved"


def test_invoice_payment_ledger():
    store = {}
    lead = full_pipeline(store)
    client = store["clients"][lead["id"]]
    agency.owner_approve(store, lead["id"], "Udita", client["proposal"]["hash"])
    agency.mark_delivered(store, lead["id"], "page live at staging link")
    with pytest.raises(ValueError, match="AGENCY_REFUSED_STATE"):
        agency.record_payment(store, lead["id"],
                              {"amount_cents": 15000, "received_date": "2026-10-12"})
    agency.draft_invoice(store, lead["id"], 15000, "2026-10-12")
    # receivable visible before payment
    before = agency.ledger(store)
    assert before["receivables_cents"] == {lead["id"]: 15000}
    entry = agency.record_payment(store, lead["id"],
                                  {"amount_cents": 15000,
                                   "received_date": "2026-10-12",
                                   "note": "UPI"})
    assert entry["executed_by_atlas"] is False
    after = agency.ledger(store)
    assert after["total_received_cents"] == 15000
    assert after["receivables_cents"] == {}
    assert after["per_client_cents"] == {lead["id"]: 15000}
    assert after["clients_by_state"]["paid"] == 1


def test_state_machine_blocks_skips():
    store = {}
    lead = agency.add_lead(store, {"name": "X", "need": "y"})
    with pytest.raises(ValueError, match="AGENCY_REFUSED_STATE"):
        agency.mark_delivered(store, lead["id"], "nope")


@pytest.mark.parametrize("key,code", [
    ("send", "OUTREACH"), ("post", "AUTOPOST"), ("charge_card", "CHARGE"),
    ("buy_ads", "SPEND")])
def test_money_and_outreach_refusals(key, code):
    store = {}
    with pytest.raises(ValueError, match="AGENCY_REFUSED_%s" % code):
        agency.add_lead(store, {"name": "X", "need": "y", key: True})
