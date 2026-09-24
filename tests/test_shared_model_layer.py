import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core import shared_model_layer as sml
from app.modules.m07_brand_collaboration.contract_extraction import ObligationDraftRow
from app.modules.m07_brand_collaboration.needle_dataset import AtlasObligationDataset, draft_to_row
from instinct_models import InklingHFRouter, Router
from instinct_models.providers import HOSTED, LOCAL, ChatResult, Provider
from instinct_models.training.dataset import build_needle_jsonl, check_row

Q1 = "3.2 Creator will publish two (2) Instagram Reels featuring the product by 20 October 2026."
Q2 = "Creator will not promote competing skincare brands until December 31, 2026."
Q3 = "7.1 Brand will pay Creator USD 1,500 within 30 days of receiving an invoice."


def _draft(pk, quote, fields, status, tenant="t1"):
    return ObligationDraftRow(pk=pk, tenant_id=tenant, id=f"d{pk}", brand_id="b1", contract_sha256="0" * 64,
                              quote=quote, fields=fields, flags=[], extractor={}, status=status,
                              created_at=datetime.now(timezone.utc))


@pytest.fixture
def session(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'n.db'}"); Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([
        _draft(1, Q1, {"kind": "deliverable", "quantity": 2, "due_date": "2026-10-20", "amount_minor": None,
                       "currency": None}, "confirmed"),
        _draft(2, Q2, {"kind": "exclusivity", "ends_date": "2026-12-31"}, "confirmed"),
        _draft(3, Q3, {"kind": "other", "amount_minor": 150000, "currency": "USD"}, "confirmed"),
        _draft(4, "Creator will post three TikToks weekly on the brand page.", {"kind": "deliverable"}, "rejected"),
        _draft(5, "Brand may repost content for 90 days after publication.", {"kind": "usage_rights"}, "pending"),
        _draft(6, Q1, {"kind": "deliverable", "quantity": 2}, "confirmed", tenant="other"),
    ])
    s.commit()
    return s


def test_only_confirmed_rows_for_this_tenant(session):
    refs = [r.source_ref for r in AtlasObligationDataset(session, "t1").rows()]
    assert refs == ["m07_obligation_drafts:t1:d1", "m07_obligation_drafts:t1:d2", "m07_obligation_drafts:t1:d3"]


def test_arguments_are_literal_substrings_of_the_quote(session):
    rows = {r.source_ref[-2:]: r for r in AtlasObligationDataset(session, "t1").rows()}
    assert rows["d1"].answers[0]["arguments"] == {"quantity": "2", "due_date": "20 October 2026"}
    assert rows["d2"].answers[0]["arguments"] == {"ends_date": "December 31, 2026"}
    assert rows["d3"].answers[0]["arguments"] == {"amount": "1,500", "currency": "USD"}
    for r in rows.values():
        assert check_row(r) is None and r.private and r.product == "atlas"


def test_unprovable_values_are_omitted_not_guessed():
    d = _draft(9, "Creator will deliver the videos next month.", {"kind": "deliverable", "quantity": 3,
                                                                    "due_date": "2026-11-01"}, "confirmed")
    assert draft_to_row(d).answers[0]["arguments"] == {}


def test_build_jsonl_is_private_and_excludes_unconfirmed(session, tmp_path):
    m = build_needle_jsonl(AtlasObligationDataset(session, "t1"), tmp_path / "atlas.jsonl")
    assert m["product"] == "atlas" and m["rows"] == 3 and m["train_locally_only"] is True
    text = (tmp_path / "atlas.jsonl").read_text()
    assert "TikToks" not in text and "repost" not in text
    assert all(json.loads(l)["tools"][0]["name"] == "log_obligation" for l in text.splitlines())


def test_config_forces_atlas_and_maps_atlas_env():
    cfg = sml.atlas_config({"ATLAS_HF_MODEL": "x/y", "ATLAS_ALLOW_HOSTED": "0", "INSTINCT_ORNITH_URL": "http://o/v1"})
    assert cfg.product == "atlas" and cfg.hf_model == "x/y" and cfg.allow_hosted is False
    assert cfg.ornith_url == "http://o/v1"
    with pytest.raises(ValueError):
        sml.atlas_env({"INSTINCT_PRODUCT": "meemee"})


def test_hosted_off_removes_hf_route():
    r = Router.from_config(sml.atlas_config({"ATLAS_ALLOW_HOSTED": "0"}))
    assert not any(isinstance(p, InklingHFRouter) for p in r.providers)


class _Fake(Provider):
    def __init__(self, name, locality):
        self.name, self.locality, self.calls = name, locality, 0

    def available(self):
        return True

    def chat(self, messages, *, tools=None, max_tokens=1024):
        self.calls += 1
        return ChatResult(self.name, "m", "hi", [], {})


def test_run_defaults_private_and_never_uses_hosted():
    hosted = _Fake("hosted", HOSTED)
    res = sml.run([{"role": "user", "content": "contract text"}], router=Router([hosted]))
    assert not res.ok and hosted.calls == 0
    local = _Fake("local", LOCAL)
    assert sml.run([{"role": "user", "content": "x"}], router=Router([hosted, local])).result.provider == "local"


def test_core_generate_shared_provider_is_private(monkeypatch):
    import asyncio
    from app.core import providers
    hosted, local = _Fake("hosted", HOSTED), _Fake("local", LOCAL)
    monkeypatch.setattr(sml, "atlas_router", lambda: Router([hosted, local]))
    assert asyncio.run(providers.generate("hello", "shared")) == ("local:m", "hi")
    assert hosted.calls == 0
    monkeypatch.setattr(sml, "atlas_router", lambda: Router([hosted]))
    with pytest.raises(providers.ProviderError):
        asyncio.run(providers.generate("hello", "shared"))
    assert asyncio.run(providers.generate("hello", "shared-public")) == ("hosted:m", "hi")


def test_m12_catalog_and_m14_default_use_shared_layer():
    import inspect
    from app.modules.m12_ai_research_lab.wiring import CATALOG
    from app.modules.m14_project_builder.service import Service
    assert any(m.model_id == "shared:instinct" and m.cents_per_1k_tokens == 0 for m in CATALOG)
    assert inspect.signature(Service.plan).parameters["provider"].default == "shared"
