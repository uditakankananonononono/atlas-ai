import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.m14_project_builder.asymmetric_live_receipts import SignedLiveReceipt
from app.modules.m14_project_builder.issuer_key_registry import IssuerKeyRegistry, RegisterIssuerKey
from app.modules.m14_project_builder.live_receipt_store import LiveReceiptRow, LiveReceiptStore
from app.modules.m14_project_builder.registered_live_receipts import (RegisteredReceiptsIn, reverify,
                                                                      verify_and_persist_registered)

IN = "a" * 64


@pytest.fixture
def env():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    sf = sessionmaker(bind=e, expire_on_commit=False)
    priv = Ed25519PrivateKey.generate()
    reg = IssuerKeyRegistry("t", sf)
    reg.register(RegisterIssuerKey(issuer="ci", key_id="k1", public_key_base64=base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()))
    return reg, LiveReceiptStore("t", sf), priv, sf


def signed(priv, rid="r1", key_id="k1", issued=None, **kw):
    meta = {"receipt_id": rid, "requirement_id": "REQ-1", "deployed_version": "v1.2.0", "environment": "prod",
            "acceptance_inputs_sha256": IN, "result_sha256": "b" * 64, "status": "passed",
            "issued_at": (issued or datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), "key_id": key_id} | kw
    r = SignedLiveReceipt(**meta, signature_base64="x")
    canonical = json.dumps(r.model_dump(mode="json", exclude={"signature_base64"}), sort_keys=True, separators=(",", ":")).encode()
    return SignedLiveReceipt(**meta, signature_base64=base64.b64encode(priv.sign(canonical)).decode())


def body(*receipts, issuer="ci"):
    return RegisteredReceiptsIn(issuer=issuer, expected_version="v1.2.0", expected_environment="prod",
                                expected_inputs_sha256=IN, receipts=list(receipts))


def test_verifies_with_registry_and_persists_idempotently(env):
    reg, store, priv, _ = env
    r1, r2 = signed(priv, "r1"), signed(priv, "r2")
    out = verify_and_persist_registered(body(r1, r2), reg, store)
    assert [x["repeat"] for x in out["persisted_receipts"]] == [False, False]
    again = verify_and_persist_registered(body(r1), reg, store)
    assert again["persisted_receipts"][0]["repeat"] is True
    assert reverify("r1", reg, store)["valid"] is True


def test_fails_closed_and_all_or_nothing(env):
    reg, store, priv, _ = env
    with pytest.raises(ValueError, match="not registered"):
        verify_and_persist_registered(body(signed(priv), issuer="other"), reg, store)
    with pytest.raises(ValueError, match="predates"):
        verify_and_persist_registered(body(signed(priv, issued=datetime(2020, 1, 1, tzinfo=timezone.utc))), reg, store)
    with pytest.raises(ValueError, match="invalid receipt signature"):
        verify_and_persist_registered(body(signed(priv, "ok"), signed(Ed25519PrivateKey.generate(), "bad")), reg, store)
    assert store.get("ok") is None  # nothing from the failed batch stored
    verify_and_persist_registered(body(signed(priv, "r1")), reg, store)
    with pytest.raises(ValueError, match="different content"):
        verify_and_persist_registered(body(signed(priv, "r1", status="failed")), reg, store)
    reg.retire("ci", "k1")
    with pytest.raises(ValueError, match="retired"):
        verify_and_persist_registered(body(signed(priv, "r9")), reg, store)
    assert reverify("r1", reg, store)["key_retired"] is True


def test_reverify_detects_tampering(env):
    reg, store, priv, sf = env
    verify_and_persist_registered(body(signed(priv, "r1")), reg, store)
    with sf.begin() as db:
        row = db.query(LiveReceiptRow).filter_by(receipt_id="r1").one()
        row.payload = {**row.payload, "status": "failed"}
    out = reverify("r1", reg, store)
    assert out["valid"] is False and "no longer verifies" in out["problems"][0]


def test_routes(env):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.m14_project_builder import routes
    reg, store, priv, _ = env
    app.dependency_overrides[routes.get_issuer_key_registry] = lambda: reg
    app.dependency_overrides[routes.get_live_receipt_store] = lambda: store
    try:
        c = TestClient(app); H = {"X-Atlas-Tenant": "t", "X-Atlas-Actor": "u"}; base = "/api/v1/project-builder/proof-status/live-receipts"
        r = c.post(f"{base}/registered/verify-and-persist", json=json.loads(body(signed(priv)).model_dump_json()), headers=H)
        assert r.status_code == 200, r.text
        assert c.get(f"{base}/r1/reverify", headers=H).json()["valid"] is True
        assert c.get(f"{base}/nope/reverify", headers=H).status_code == 404
        bad = json.loads(body(signed(priv, "r2")).model_dump_json()); bad["issuer"] = "x"
        assert c.post(f"{base}/registered/verify-and-persist", json=bad, headers=H).status_code == 409
    finally:
        app.dependency_overrides.clear()
