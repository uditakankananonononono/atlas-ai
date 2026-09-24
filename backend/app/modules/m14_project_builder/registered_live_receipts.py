"""Verify live receipts with registered issuer keys and persist them immutably (M14).

- Keys come only from the tenant's issuer-key registry: (issuer, key_id) must be
  registered, active and unretired, and registered no later than the receipt's
  ``issued_at``. Callers can no longer supply their own trusted-key map here.
- Signature and deployment/environment/input bindings are checked with the
  existing Ed25519 verifier.
- All receipts in a request persist in one transaction (all or nothing), with
  the signature, key id and key fingerprint stored alongside. An exact repeat of
  a stored receipt is idempotent; a different receipt under a stored receipt_id
  fails closed.
- ``reverify`` re-checks a stored receipt's signature against the registered key
  so later database edits show up.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, Field
from sqlalchemy import select

from .asymmetric_live_receipts import SignedLiveReceipt, VerifyAsymmetricLiveReceipts, verify_asymmetric_live_receipts
from .issuer_key_registry import IssuerKeyRegistry, IssuerKeyRow
from .live_receipt_store import LiveReceiptRow, LiveReceiptStore


class RegisteredReceiptsIn(BaseModel):
    issuer: str = Field(min_length=1, max_length=200)
    expected_version: str = Field(min_length=1)
    expected_environment: str = Field(min_length=1)
    expected_inputs_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipts: list[SignedLiveReceipt] = Field(min_length=1, max_length=1000)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _key(db, tenant_id: str, issuer: str, key_id: str) -> IssuerKeyRow:
    row = db.scalar(select(IssuerKeyRow).where(IssuerKeyRow.tenant_id == tenant_id, IssuerKeyRow.issuer == issuer,
                                               IssuerKeyRow.key_id == key_id))
    if row is None:
        raise ValueError(f"issuer key {issuer}/{key_id} is not registered for this tenant")
    return row


def verify_and_persist_registered(body: RegisteredReceiptsIn, registry: IssuerKeyRegistry, store: LiveReceiptStore) -> dict:
    ids = [r.receipt_id for r in body.receipts]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate receipt_id in request")
    with registry.sessions() as db:
        trusted, fps = {}, {}
        for r in body.receipts:
            k = _key(db, registry.tenant_id, body.issuer, r.key_id)
            if not k.active or k.retired_at is not None:
                raise ValueError(f"issuer key {body.issuer}/{r.key_id} is retired")
            if _aware(k.created_at) > _aware(r.issued_at):
                raise ValueError(f"receipt {r.receipt_id} predates registration of key {r.key_id}")
            trusted[r.key_id] = base64.b64encode(k.public_key).decode()
            fps[r.key_id] = k.fingerprint_sha256
    verified = verify_asymmetric_live_receipts(VerifyAsymmetricLiveReceipts(
        expected_version=body.expected_version, expected_environment=body.expected_environment,
        expected_inputs_sha256=body.expected_inputs_sha256, receipts=body.receipts, trusted_ed25519_public_keys=trusted))
    sigs = {r.receipt_id: r.signature_base64 for r in body.receipts}
    stored = []
    with store.sessions.begin() as db:
        for rec in verified["receipts"]:
            payload = {**rec, "issuer": body.issuer, "signature_base64": sigs[rec["receipt_id"]],
                       "key_fingerprint_sha256": fps[rec["key_id"]]}
            existing = db.scalar(select(LiveReceiptRow).where(LiveReceiptRow.tenant_id == store.tenant_id,
                                                              LiveReceiptRow.receipt_id == rec["receipt_id"]))
            if existing is not None:
                if existing.payload != payload:
                    raise ValueError(f"receipt {rec['receipt_id']} is already stored with different content")
                stored.append({"receipt_id": existing.receipt_id, "persisted_at": existing.persisted_at.isoformat(), "repeat": True})
                continue
            row = LiveReceiptRow(tenant_id=store.tenant_id, receipt_id=rec["receipt_id"], requirement_id=rec["requirement_id"],
                                 deployed_version=rec["deployed_version"], environment=rec["environment"],
                                 acceptance_inputs_sha256=rec["acceptance_inputs_sha256"], proof_sha256=rec["result_sha256"],
                                 payload=payload, persisted_at=datetime.now(timezone.utc))
            db.add(row)
            db.flush()
            stored.append({"receipt_id": row.receipt_id, "persisted_at": row.persisted_at.isoformat(), "repeat": False})
    return {**verified, "issuer": body.issuer, "persisted_receipts": stored,
            "boundary": "Receipts verified only against registered, unretired issuer keys and stored append-only in one transaction. It does not deploy, run acceptance tests, or prove who controls the issuer key."}


def reverify(receipt_id: str, registry: IssuerKeyRegistry, store: LiveReceiptStore) -> dict:
    row = store.get(receipt_id)
    if row is None:
        raise LookupError("receipt not found")
    p = dict(row.payload)
    if "signature_base64" not in p or "issuer" not in p:
        return {"receipt_id": receipt_id, "valid": None, "reason": "stored before registered-key persistence; no signature kept"}
    with registry.sessions() as db:
        k = _key(db, registry.tenant_id, p["issuer"], p["key_id"])
    signed = {f: p[f] for f in SignedLiveReceipt.model_fields if f != "signature_base64"}
    canonical = json.dumps(SignedLiveReceipt(**signed, signature_base64="x").model_dump(mode="json", exclude={"signature_base64"}),
                           sort_keys=True, separators=(",", ":")).encode()
    problems = []
    try:
        Ed25519PublicKey.from_public_bytes(k.public_key).verify(base64.b64decode(p["signature_base64"]), canonical)
    except InvalidSignature:
        problems.append("signature no longer verifies against stored content")
    if k.fingerprint_sha256 != p.get("key_fingerprint_sha256"):
        problems.append("registered key fingerprint differs from the one recorded at persistence")
    if (row.deployed_version, row.environment, row.acceptance_inputs_sha256, row.proof_sha256) != (
            p["deployed_version"], p["environment"], p["acceptance_inputs_sha256"], p["result_sha256"]):
        problems.append("indexed columns differ from the signed payload")
    return {"receipt_id": receipt_id, "valid": not problems, "problems": problems,
            "key_retired": bool(k.retired_at), "status": p["status"]}
