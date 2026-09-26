"""Tenant-scoped pairing and device registry for the session bridge.

Pairing follows the M21 shape (one-time code + expiry + capability set), but
persisted in SQL so devices survive restarts and revocation is durable. The
daemon proves possession of the one-time code; the server answers with a
device id and a command secret, returned once, which later authenticates
submit tokens. Receipts use the M21 hash-chain format and are verified
against the stored device identity.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, JSON, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine


class PairingError(ValueError):
    pass


class PairingChallengeRow(Base):
    __tablename__ = "m13_bridge_pairing_challenges"
    nonce: Mapped[str] = mapped_column(String(80), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class PairedDeviceRow(Base):
    __tablename__ = "m13_bridge_paired_devices"
    device_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    public_key: Mapped[str] = mapped_column(String(4000))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    capabilities: Mapped[list] = mapped_column(JSON)
    command_secret: Mapped[str] = mapped_column(String(80))
    pacing_seconds: Mapped[float] = mapped_column(default=5.0)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def fingerprint_public_key(public_key_pem: str) -> str:
    return hashlib.sha256(public_key_pem.encode("utf-8")).hexdigest()


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class BridgeRegistry:
    def __init__(self, sessions: sessionmaker | None = None):
        if sessions is None:
            Base.metadata.create_all(engine)
            sessions = SessionLocal
        self.sessions = sessions

    def create_challenge(self, tenant_id: str, ttl_seconds: int = 300) -> dict:
        ttl = max(60, min(int(ttl_seconds), 600))
        code = f"{secrets.randbelow(1_000_000):06d}"
        nonce = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        with self.sessions.begin() as db:
            db.add(PairingChallengeRow(nonce=nonce, tenant_id=tenant_id,
                                       code_hash=_hash_code(code), expires_at=expires))
        return {"server_nonce": nonce, "code": code, "expires_at": expires.isoformat()}

    def confirm_pairing(self, nonce: str, code: str, *, name: str, public_key: str,
                        capabilities: list[str], pacing_seconds: float | None = None) -> dict:
        """The daemon proves the one-time code; the device is bound to the challenge's tenant."""
        if not name.strip():
            raise PairingError("device name is required")
        if not capabilities:
            raise PairingError("at least one owner-granted capability is required")
        known = {"navigate", "extract", "screenshot", "read_values", "fill",
                 "click_nav", "click_submit", "social_read", "close"}
        granted = sorted({str(item) for item in capabilities} & known)
        if not granted:
            raise PairingError("no recognized capability requested")
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as db:
            challenge = db.get(PairingChallengeRow, nonce)
            if challenge is None or challenge.consumed:
                raise PairingError("unknown or already-used pairing challenge")
            expires = challenge.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                raise PairingError("pairing challenge expired")
            if not hmac.compare_digest(challenge.code_hash, _hash_code(code)):
                raise PairingError("pairing code mismatch")
            challenge.consumed = True
            device = PairedDeviceRow(
                device_id=secrets.token_hex(16),
                tenant_id=challenge.tenant_id,
                name=name.strip()[:200],
                public_key=public_key,
                fingerprint=fingerprint_public_key(public_key),
                capabilities=granted,
                command_secret=secrets.token_hex(32),
                pacing_seconds=float(pacing_seconds) if pacing_seconds else 5.0,
                paired_at=now,
            )
            db.add(device)
            db.flush()
            return {"device_id": device.device_id, "tenant_id": device.tenant_id,
                    "command_secret": device.command_secret, "capabilities": granted,
                    "fingerprint": device.fingerprint}

    def get_device(self, device_id: str) -> PairedDeviceRow | None:
        with self.sessions() as db:
            device = db.get(PairedDeviceRow, device_id)
            if device is not None:
                db.expunge(device)
            return device

    def list_devices(self, tenant_id: str) -> list[dict]:
        with self.sessions() as db:
            rows = db.scalars(select(PairedDeviceRow).where(PairedDeviceRow.tenant_id == tenant_id)).all()
            return [{"device_id": r.device_id, "name": r.name, "fingerprint": r.fingerprint,
                     "capabilities": list(r.capabilities), "revoked": r.revoked,
                     "paired_at": r.paired_at.isoformat() if r.paired_at else None,
                     "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None}
                    for r in rows]

    def revoke(self, tenant_id: str, device_id: str) -> bool:
        with self.sessions.begin() as db:
            device = db.get(PairedDeviceRow, device_id)
            if device is None or device.tenant_id != tenant_id:
                return False
            device.revoked = True
            return True

    def touch_seen(self, device_id: str) -> None:
        with self.sessions.begin() as db:
            device = db.get(PairedDeviceRow, device_id)
            if device is not None:
                device.last_seen_at = datetime.now(timezone.utc)

    def verify_connect_signature(self, device_id: str, timestamp: str, signature_hex: str) -> PairedDeviceRow:
        """Verify the daemon's ed25519 proof of possession for a websocket connect."""
        device = self.get_device(device_id)
        if device is None:
            raise PairingError("unknown device")
        if device.revoked:
            raise PairingError("device is revoked")
        try:
            signed_at = int(timestamp)
        except (TypeError, ValueError) as error:
            raise PairingError("invalid connect timestamp") from error
        if abs(int(datetime.now(timezone.utc).timestamp()) - signed_at) > 300:
            raise PairingError("connect timestamp outside the allowed window")
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        try:
            key = load_pem_public_key(device.public_key.encode("utf-8"))
            key.verify(bytes.fromhex(signature_hex), f"{device_id}.{timestamp}".encode("utf-8"))
        except Exception as error:  # noqa: BLE001 - any verify failure is an auth failure
            raise PairingError("device signature did not verify") from error
        return device

    def verify_receipt(self, device_id: str, events: list[dict]) -> dict:
        """Hash-chain verification against the stored device identity (M21 format)."""
        device = self.get_device(device_id)
        if device is None:
            raise PairingError("unknown device")
        if device.revoked:
            raise PairingError("device is revoked")
        previous = "0" * 64
        for position, raw in enumerate(events, 1):
            if raw.get("sequence") != position or raw.get("device_id") != device_id \
                    or raw.get("previous_hash") != previous:
                raise PairingError(f"audit chain mismatch at event {position}")
            body = json.dumps({"sequence": position, "device_id": device_id,
                               "action_id": raw.get("action_id"), "phase": raw.get("phase"),
                               "payload": raw.get("payload", {}), "previous_hash": previous},
                              sort_keys=True, default=str)
            computed = hashlib.sha256(body.encode()).hexdigest()
            if not hmac.compare_digest(computed, str(raw.get("event_hash", ""))):
                raise PairingError(f"event hash mismatch at event {position}")
            previous = computed
        phases = [str(item.get("phase")) for item in events]
        return {"device_id": device_id, "fingerprint": device.fingerprint,
                "events_verified": len(events), "chain_head": previous,
                "terminal_phase": phases[-1] if phases else None,
                "receipt_complete": bool(events and phases[-1] in {"completed", "failed", "blocked"})}
