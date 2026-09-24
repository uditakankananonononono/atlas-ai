import asyncio
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m07_brand_collaboration.contract_extraction import ContractExtractor, ExtractionError, vet
from app.modules.m07_brand_collaboration.obligations import ObligationTracker

CONTRACT = """BRAND COLLABORATION AGREEMENT
3.2 Creator will publish two (2) Instagram Reels featuring the product by 20 October 2026.
3.3 Each post must include the disclosure #ad in the first line of the caption.
5.1 Creator will not promote competing skincare brands until December 31, 2026.
7.1 Brand will pay Creator USD 1,500 within 30 days of receiving an invoice.
"""
MODEL_OUT = json.dumps([
    {"quote": "3.2 Creator will publish two (2) Instagram Reels featuring the product by 20 October 2026.",
     "locator": "3.2", "kind": "deliverable", "title": "2 Reels", "quantity": 2, "due_date": "2026-10-20",
     "amount": 1500, "currency": "USD"},
    {"quote": "Creator will not promote competing skincare brands until December 31, 2026.", "locator": "5.1",
     "kind": "exclusivity", "title": "Skincare exclusivity", "ends_date": "2026-12-31"},
    {"quote": "Creator will post three TikToks weekly.", "locator": "9.9", "kind": "deliverable", "title": "invented"},
    {"quote": "Each post must include the disclosure #ad in the first line of the caption.", "locator": "3.3",
     "kind": "disclosure", "title": "#ad disclosure", "quantity": 4},
])


class Approvals:
    def get(self, *a, **k):
        return None


def build(tmp_path, out=MODEL_OUT, tenant="t1"):
    e = create_engine(f"sqlite:///{tmp_path/'c.db'}"); Base.metadata.create_all(e)
    s = sessionmaker(bind=e)
    brands = {"b1": object()}.get
    tracker = ObligationTracker(tenant, brands=brands, artifacts={}.get, approvals=Approvals(), session_factory=s,
                                clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    calls = []

    async def gen(prompt):
        calls.append(prompt)
        return "ollama", "llama3.1:8b", "Here you go:\n" + out
    return ContractExtractor(tenant, tracker=tracker, brands=brands, generate=gen, session_factory=s), tracker, calls


def test_extract_keeps_only_verbatim_quotes_and_flags_unsupported_values(tmp_path):
    x, tracker, calls = build(tmp_path)
    res = asyncio.run(x.extract(brand_id="b1", contract_text=CONTRACT))
    assert "3.2 Creator will publish" in calls[0]
    assert [d["quote"][:12] for d in res["drafts"]] == ["3.2 Creator ", "Creator will", "Each post mu"]
    assert res["dropped"] == [{"quote": "Creator will post three TikToks weekly.", "reason": "quote_not_in_contract"}]
    reels, excl, disc = res["drafts"]
    assert reels["fields"]["quantity"] == 2 and reels["fields"]["due_date"] == "2026-10-20"
    assert reels["flags"] == ["amount_not_in_quote"]  # 1500 is in clause 7.1, not in this quote
    assert excl["flags"] == [] and disc["flags"] == ["quantity_not_in_quote"]
    assert all(d["status"] == "pending" for d in res["drafts"])
    assert tracker.brand_tracker("b1")["obligations"] == []  # nothing auto-created


def test_confirm_creates_obligation_with_quote_and_owner_edits(tmp_path):
    x, tracker, _ = build(tmp_path)
    reels, excl, disc = asyncio.run(x.extract(brand_id="b1", contract_text=CONTRACT))["drafts"]
    with pytest.raises(ExtractionError):
        x.confirm(reels["id"], edits={"quote": "something nicer"})
    out = x.confirm(reels["id"], edits={"amount_minor": 0}, note="fee is billed under 7.1")
    ob = out["obligation"]
    assert ob["clause"]["text"] == reels["quote"] and ob["clause"]["locator"] == "3.2"
    assert ob["quantity"] == 2 and ob["due_at"].startswith("2026-10-20") and ob["amount_minor"] == 0
    assert out["draft"]["status"] == "confirmed" and out["draft"]["obligation_id"] == ob["id"]
    with pytest.raises(ExtractionError):
        x.confirm(reels["id"])
    x.reject(disc["id"], reason="covered by 3.2 posts; track manually")
    assert [d["id"] for d in x.pending("b1")] == [excl["id"]]


def test_bad_model_output_and_private_routes_only(tmp_path, monkeypatch):
    x, _, _ = build(tmp_path, out="sorry, no")
    with pytest.raises(ExtractionError):
        asyncio.run(x.extract(brand_id="b1", contract_text=CONTRACT))

    from app.core import model_catalog, providers
    from app.core.providers import ProviderError
    from app.modules.m07_brand_collaboration import contract_extraction as ce
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    used = []

    async def fake(prompt, provider, model=None):
        used.append(provider)
        raise ProviderError("down")
    monkeypatch.setattr(providers, "generate", fake)
    with pytest.raises(ExtractionError, match="not sent to hosted"):
        asyncio.run(ce.private_generate("contract"))
    assert "huggingface" not in used and used == ["ollama", "openai_compat"]


def test_vet_date_forms():
    kept, _ = vet([{"quote": "Report due 5/11 each month to the brand.", "due_date": "2026-05-11"}], "Report due 5/11 each month to the brand.")
    assert kept[0]["flags"] == []


def test_attention_digest_lists_due_soon_and_overdue(tmp_path):
    x, tracker, _ = build(tmp_path)
    reels = asyncio.run(x.extract(brand_id="b1", contract_text=CONTRACT))["drafts"][0]
    x.confirm(reels["id"])
    assert tracker.attention()["count"] == 0  # 19 days out
    tracker.clock = lambda: datetime(2026, 10, 18, tzinfo=timezone.utc)
    a = tracker.attention()
    assert a["count"] == 1 and a["items"][0]["reasons"] == ["due_soon"]
    tracker.clock = lambda: datetime(2026, 10, 22, tzinfo=timezone.utc)
    assert tracker.attention()["items"][0]["reasons"] == ["deliverable_overdue"]
