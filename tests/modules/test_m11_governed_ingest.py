import base64
import hashlib
import json

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m11_calendar_intelligence.asymmetric_risk_evidence import SignedRiskSnapshot
from app.modules.m11_calendar_intelligence.governed_risk_ingest import (HttpsProviderRetriever, IngestRejected,
                                                                        ingest_signed_snapshot)
from app.modules.m11_calendar_intelligence.provider_key_registry import RegisterRiskProviderKey, RiskProviderKeyRegistry
from app.modules.m11_calendar_intelligence.risk_snapshot_store import RiskSnapshotStore

RAW = b"Free cancellation until 48h before check-in."
URI = "https://terms.vendor.test/policy"


@pytest.fixture
def env(tmp_path):
    e = create_engine(f"sqlite:///{tmp_path/'m11.db'}"); Base.metadata.create_all(e)
    sf = sessionmaker(bind=e, expire_on_commit=False)
    priv = Ed25519PrivateKey.generate()
    reg = RiskProviderKeyRegistry("t1", sf)
    reg.register(RegisterRiskProviderKey(provider="vendor", key_id="k1", public_key_base64=base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()))
    return reg, RiskSnapshotStore("t1", sf), priv


def signed(priv, **kw):
    meta = {"evidence_id": "ev1", "kind": "cancellation_policy", "source_uri": URI, "retrieved_at": "2026-09-24T06:00:00Z",
            "content_sha256": hashlib.sha256(RAW).hexdigest(), "provider": "vendor", "key_id": "k1"} | kw
    sig = priv.sign(json.dumps(meta, sort_keys=True, separators=(",", ":")).encode())
    return SignedRiskSnapshot(**meta, signature_base64=base64.b64encode(sig).decode())


class Fixed:
    def __init__(self, data=RAW): self.data, self.calls = data, []
    def fetch(self, provider, uri): self.calls.append((provider, uri)); return self.data


def test_full_chain_persists_once(env):
    reg, store, priv = env
    out = ingest_signed_snapshot(signed(priv), registry=reg, retriever=Fixed(), store=store)
    assert out["ingested"] and out["byte_count"] == len(RAW) and len(out["key_fingerprint_sha256"]) == 64
    again = ingest_signed_snapshot(signed(priv), registry=reg, retriever=Fixed(), store=store)
    assert again["content_sha256"] == out["content_sha256"]


def test_fails_closed(env):
    reg, store, priv = env
    with pytest.raises(IngestRejected, match="not registered"):
        ingest_signed_snapshot(signed(priv, key_id="k9"), registry=reg, retriever=Fixed(), store=store)
    forged = signed(Ed25519PrivateKey.generate())
    r = Fixed()
    with pytest.raises(IngestRejected, match="does not verify"):
        ingest_signed_snapshot(forged, registry=reg, retriever=r, store=store)
    assert r.calls == []  # never fetches for a bad signature
    with pytest.raises(IngestRejected, match="do not match"):
        ingest_signed_snapshot(signed(priv), registry=reg, retriever=Fixed(b"edited terms"), store=store)
    reg.retire("vendor", "k1")
    with pytest.raises(IngestRejected, match="retired"):
        ingest_signed_snapshot(signed(priv), registry=reg, retriever=Fixed(), store=store)


def test_https_retriever_config_and_auth(monkeypatch):
    seen = {}
    def handler(req):
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, content=RAW)
    t = httpx.MockTransport(handler)
    cfg = {"vendor": {"hosts": ["terms.vendor.test"], "token_env": "VENDOR_TOKEN"}}
    r = HttpsProviderRetriever(cfg, transport=t)
    with pytest.raises(IngestRejected, match="not set"):
        r.fetch("vendor", URI)
    monkeypatch.setenv("VENDOR_TOKEN", "sekret")
    assert r.fetch("vendor", URI) == RAW and seen["auth"] == "Bearer sekret"
    with pytest.raises(IngestRejected, match="not listed"):
        r.fetch("vendor", "https://evil.test/policy")
    with pytest.raises(IngestRejected, match="https"):
        r.fetch("vendor", "http://terms.vendor.test/policy")
    with pytest.raises(IngestRejected, match="no retrieval adapter"):
        r.fetch("other", URI)
    redirect = HttpsProviderRetriever(cfg, transport=httpx.MockTransport(lambda q: httpx.Response(302, headers={"location": "https://x.test"})))
    with pytest.raises(IngestRejected, match="HTTP 302"):
        redirect.fetch("vendor", URI)


def test_route(env):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.m11_calendar_intelligence import routes
    reg, store, priv = env
    app.dependency_overrides[routes.get_risk_provider_key_registry] = lambda: reg
    app.dependency_overrides[routes.get_risk_snapshot_store] = lambda: store
    app.dependency_overrides[routes.get_provider_retriever] = lambda: Fixed()
    try:
        c = TestClient(app)
        H = {"X-Atlas-Tenant": "t1", "X-Atlas-Actor": "u"}
        r = c.post("/api/v1/calendar-intelligence/schedule-risk/live-evidence/ingest", json=signed(priv).model_dump(), headers=H)
        assert r.status_code == 200 and r.json()["ingested"], r.text
        bad = signed(priv).model_dump() | {"retrieved_at": "2026-09-25T06:00:00Z"}
        assert c.post("/api/v1/calendar-intelligence/schedule-risk/live-evidence/ingest", json=bad, headers=H).status_code == 422
    finally:
        app.dependency_overrides.clear()
