"""Pairing registry tests against real sqlite: challenge, confirm, auth, receipts."""
import time
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.m13_browser_agent.session_bridge.registry import BridgeRegistry, PairingError
from app.modules.m13_browser_agent.pc_daemon.receipts import ReceiptChain


@pytest.fixture
def registry(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'bridge.db'}")
    Base.metadata.create_all(engine)
    return BridgeRegistry(sessionmaker(bind=engine, expire_on_commit=False))


def _keypair():
    key = Ed25519PrivateKey.generate()
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return key, pem


def test_pairing_happy_path(registry):
    challenge = registry.create_challenge("tenant-1")
    key, pem = _keypair()
    device = registry.confirm_pairing(challenge["server_nonce"], challenge["code"],
                                      name="laptop", public_key=pem,
                                      capabilities=["navigate", "extract", "bogus-capability"])
    assert device["tenant_id"] == "tenant-1"
    assert set(device["capabilities"]) == {"navigate", "extract"}  # unknown capabilities dropped
    assert device["command_secret"]
    listed = registry.list_devices("tenant-1")
    assert len(listed) == 1 and listed[0]["name"] == "laptop" and not listed[0]["revoked"]


def test_pairing_rejects_wrong_code_replay_and_expiry(registry):
    challenge = registry.create_challenge("tenant-1")
    _, pem = _keypair()
    with pytest.raises(PairingError, match="code mismatch"):
        registry.confirm_pairing(challenge["server_nonce"], "000000",
                                 name="laptop", public_key=pem, capabilities=["navigate"])
    device = registry.confirm_pairing(challenge["server_nonce"], challenge["code"],
                                      name="laptop", public_key=pem, capabilities=["navigate"])
    assert device["device_id"]
    with pytest.raises(PairingError, match="already-used|unknown"):
        registry.confirm_pairing(challenge["server_nonce"], challenge["code"],
                                 name="laptop2", public_key=pem, capabilities=["navigate"])
    second = registry.create_challenge("tenant-1")
    with registry.sessions.begin() as db:
        from app.modules.m13_browser_agent.session_bridge.registry import PairingChallengeRow
        row = db.get(PairingChallengeRow, second["server_nonce"])
        row.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(PairingError, match="expired"):
        registry.confirm_pairing(second["server_nonce"], second["code"],
                                 name="laptop", public_key=pem, capabilities=["navigate"])


def test_connect_signature_verification_and_revocation(registry):
    challenge = registry.create_challenge("tenant-1")
    key, pem = _keypair()
    device = registry.confirm_pairing(challenge["server_nonce"], challenge["code"],
                                      name="laptop", public_key=pem, capabilities=["navigate"])
    ts = str(int(time.time()))
    sig = key.sign(f"{device['device_id']}.{ts}".encode()).hex()
    verified = registry.verify_connect_signature(device["device_id"], ts, sig)
    assert verified.device_id == device["device_id"]

    other_key, _ = _keypair()
    bad_sig = other_key.sign(f"{device['device_id']}.{ts}".encode()).hex()
    with pytest.raises(PairingError, match="did not verify"):
        registry.verify_connect_signature(device["device_id"], ts, bad_sig)
    stale = str(int(time.time()) - 1000)
    stale_sig = key.sign(f"{device['device_id']}.{stale}".encode()).hex()
    with pytest.raises(PairingError, match="timestamp"):
        registry.verify_connect_signature(device["device_id"], stale, stale_sig)

    assert registry.revoke("tenant-1", device["device_id"])
    with pytest.raises(PairingError, match="revoked"):
        registry.verify_connect_signature(device["device_id"], ts, sig)
    # Revocation is tenant-scoped.
    assert not registry.revoke("someone-else", device["device_id"])


def test_receipt_verification_against_device_identity(registry):
    challenge = registry.create_challenge("tenant-1")
    _, pem = _keypair()
    device = registry.confirm_pairing(challenge["server_nonce"], challenge["code"],
                                      name="laptop", public_key=pem, capabilities=["navigate"])
    chain = ReceiptChain(device["device_id"])
    chain.append("cmd-1", "completed", {"kind": "navigate"})
    chain.append("cmd-2", "blocked", {"block": "rate_limit"})
    events = chain.events
    result = registry.verify_receipt(device["device_id"], events)
    assert result["events_verified"] == 2 and result["receipt_complete"]
    assert result["terminal_phase"] == "blocked"

    tampered = [dict(event) for event in events]
    tampered[1]["payload"] = {"block": "nothing-to-see"}
    with pytest.raises(PairingError, match="hash mismatch"):
        registry.verify_receipt(device["device_id"], tampered)
