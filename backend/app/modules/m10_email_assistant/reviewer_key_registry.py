"""Reviewer key governance for M10 promise-reconciliation attestations.

Reviewer decisions are signed with Ed25519. Before this module, anyone in a
tenant could register key bytes for any reviewer name, and verification used
whatever keys the caller put in the request, so a signature proved nothing
about who reviewed. The rules now:

Identity binding
  A key is bound to one (tenant, reviewer_id). Only that reviewer (the
  authenticated actor) or an ``atlas-admin`` may enroll it, and enrollment
  needs a proof-of-possession signature over the canonical registration
  statement, so nobody can enroll a public key they do not hold.
One active key per reviewer
  A second enrollment while a key is active is refused; use rotation.
Rotation
  The new key signs its own registration statement, and the current key
  endorses the new key's fingerprint (key continuity). Both happen in one
  transaction that retires the old key. An admin may rotate without the old
  key (lost-key recovery); that path is recorded as ``recovery``.
Retirement / revocation
  Reviewer or admin, with a reason. Retired keys never verify again:
  attestations carry no trusted timestamp, so "signed before retirement"
  cannot be proven.
Verification
  Keys come only from this registry, looked up by (reviewer_id, key_id) and
  required to be active. Caller-supplied keys are not accepted.
Audit
  Every enroll/rotate/retire/refusal is appended to
  ``m10_reviewer_key_events`` with actor and fingerprints.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, DateTime, LargeBinary, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal

ENROLL_PURPOSE = "atlas-m10-reviewer-key-enrollment"
ENDORSE_PURPOSE = "atlas-m10-reviewer-key-rotation"
ADMIN_ROLE = "atlas-admin"


class ReviewerKeyRow(Base):
    __tablename__ = "m10_reviewer_public_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "reviewer_id", "key_id"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(200))
    key_id: Mapped[str] = mapped_column(String(200))
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrolled_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retired_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retire_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    replaced_by_key_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Signatures by a retired key still verify only if a trusted timestamp
    # proves they existed before this instant (rotation/retirement time, or the
    # declared compromise time).
    signatures_valid_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewerKeyEventRow(Base):
    __tablename__ = "m10_reviewer_key_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(200), index=True)
    key_id: Mapped[str] = mapped_column(String(200))
    event: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KeyGovernanceError(ValueError):
    """Refused by policy (maps to 403)."""


class RegisterReviewerKey(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=200)
    key_id: str = Field(min_length=1, max_length=200)
    public_key_base64: str = Field(min_length=1)
    proof_signature_base64: str = Field(min_length=1, description="Ed25519 signature by the new key over enrollment_statement(...)")


class RotateReviewerKey(BaseModel):
    new_key_id: str = Field(min_length=1, max_length=200)
    new_public_key_base64: str = Field(min_length=1)
    proof_signature_base64: str = Field(min_length=1)
    endorsement_signature_base64: str | None = Field(default=None, description="Signature by the current active key over rotation_statement(...); admins may omit it for lost-key recovery")


class RetireReviewerKey(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    compromised: bool = Field(default=False, description="Key material may be in someone else's hands")
    compromised_since: datetime | None = Field(default=None, description="Earliest possible compromise; unknown means no earlier signature is trusted")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def enrollment_statement(tenant_id: str, reviewer_id: str, key_id: str, fingerprint_sha256: str) -> bytes:
    return _canonical({"purpose": ENROLL_PURPOSE, "tenant_id": tenant_id, "reviewer_id": reviewer_id,
                       "key_id": key_id, "fingerprint_sha256": fingerprint_sha256})


def rotation_statement(tenant_id: str, reviewer_id: str, old_key_id: str, new_key_id: str, new_fingerprint_sha256: str) -> bytes:
    return _canonical({"purpose": ENDORSE_PURPOSE, "tenant_id": tenant_id, "reviewer_id": reviewer_id,
                       "old_key_id": old_key_id, "new_key_id": new_key_id, "new_fingerprint_sha256": new_fingerprint_sha256})


def _decode_key(encoded: str) -> bytes:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("invalid public key encoding") from exc
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return raw


def _verify(raw_key: bytes, signature_b64: str, message: bytes, what: str) -> None:
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        Ed25519PublicKey.from_public_bytes(raw_key).verify(signature, message)
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise KeyGovernanceError(f"{what} signature does not verify") from exc


class ReviewerKeyRegistry:
    def __init__(self, tenant_id: str, sessions: sessionmaker = SessionLocal, *,
                 actor_id: str = "system", roles: frozenset[str] = frozenset(),
                 clock: Callable[[], datetime] | None = None) -> None:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id, self.sessions = tenant_id, sessions
        self.actor_id, self.roles = actor_id, roles
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        bind = getattr(sessions, "kw", {}).get("bind")
        if bind is not None:
            Base.metadata.create_all(bind, tables=[ReviewerKeyRow.__table__, ReviewerKeyEventRow.__table__])

    # -- policy ---------------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return ADMIN_ROLE in self.roles

    def _authorize(self, reviewer_id: str, key_id: str, action: str) -> None:
        if self.actor_id == reviewer_id or self.is_admin:
            return
        # Own transaction so the refusal is kept in the audit log.
        self._refuse(reviewer_id, key_id, f"{action}_refused", "actor is neither the reviewer nor an atlas-admin")
        raise KeyGovernanceError(f"only reviewer {reviewer_id!r} or an {ADMIN_ROLE} may {action} this key")

    def _event(self, db, reviewer_id: str, key_id: str, event: str, details: dict[str, Any]) -> None:
        db.add(ReviewerKeyEventRow(tenant_id=self.tenant_id, reviewer_id=reviewer_id, key_id=key_id, event=event,
                                   actor=self.actor_id, details=details, at=self._clock()))

    def _row(self, db, reviewer_id: str, key_id: str) -> ReviewerKeyRow | None:
        return db.scalar(select(ReviewerKeyRow).where(ReviewerKeyRow.tenant_id == self.tenant_id,
                         ReviewerKeyRow.reviewer_id == reviewer_id, ReviewerKeyRow.key_id == key_id))

    def _active(self, db, reviewer_id: str) -> ReviewerKeyRow | None:
        return db.scalar(select(ReviewerKeyRow).where(ReviewerKeyRow.tenant_id == self.tenant_id,
                         ReviewerKeyRow.reviewer_id == reviewer_id, ReviewerKeyRow.active.is_(True)))

    def _refuse(self, reviewer_id: str, key_id: str, event: str, reason: str) -> None:
        with self.sessions.begin() as db:
            self._event(db, reviewer_id, key_id, event, {"reason": reason})

    # -- operations -----------------------------------------------------------
    def register(self, body: RegisterReviewerKey) -> ReviewerKeyRow:
        raw = _decode_key(body.public_key_base64)
        fingerprint = hashlib.sha256(raw).hexdigest()
        self._authorize(body.reviewer_id, body.key_id, "enroll")
        try:
            _verify(raw, body.proof_signature_base64,
                    enrollment_statement(self.tenant_id, body.reviewer_id, body.key_id, fingerprint), "proof-of-possession")
        except KeyGovernanceError:
            self._refuse(body.reviewer_id, body.key_id, "enroll_refused", "proof-of-possession failed")
            raise
        with self.sessions.begin() as db:
            existing = self._row(db, body.reviewer_id, body.key_id)
            if existing is not None:
                if existing.public_key != raw:
                    raise ValueError("key_id is already bound to different public key bytes")
                if not existing.active:
                    raise ValueError("key_id was retired and cannot be re-enrolled; enroll a new key_id")
                db.expunge(existing)
                return existing
            active = self._active(db, body.reviewer_id)
            if active is not None:
                raise ValueError(f"reviewer already has active key {active.key_id!r}; rotate instead")
            row = ReviewerKeyRow(tenant_id=self.tenant_id, reviewer_id=body.reviewer_id, key_id=body.key_id, public_key=raw,
                                 fingerprint_sha256=fingerprint, active=True, created_at=self._clock(), enrolled_by=self.actor_id)
            db.add(row)
            self._event(db, body.reviewer_id, body.key_id, "enrolled", {"fingerprint_sha256": fingerprint})
            db.flush()
            db.expunge(row)
            return row

    def rotate(self, reviewer_id: str, body: RotateReviewerKey) -> dict[str, Any]:
        raw = _decode_key(body.new_public_key_base64)
        fingerprint = hashlib.sha256(raw).hexdigest()
        self._authorize(reviewer_id, body.new_key_id, "rotate")
        with self.sessions.begin() as db:
            current = self._active(db, reviewer_id)
            if current is None:
                raise ValueError("reviewer has no active key; enroll instead")
            current_key, current_id = current.public_key, current.key_id
        if self._row_exists(reviewer_id, body.new_key_id):
            raise ValueError("new_key_id is already used for this reviewer")
        try:
            _verify(raw, body.proof_signature_base64,
                    enrollment_statement(self.tenant_id, reviewer_id, body.new_key_id, fingerprint), "proof-of-possession")
            if body.endorsement_signature_base64:
                _verify(current_key, body.endorsement_signature_base64,
                        rotation_statement(self.tenant_id, reviewer_id, current_id, body.new_key_id, fingerprint), "old-key endorsement")
                mode = "continuity"
            elif self.is_admin:
                mode = "recovery"
            else:
                raise KeyGovernanceError("rotation needs an endorsement from the current key (admins may recover without it)")
        except KeyGovernanceError as exc:
            self._refuse(reviewer_id, body.new_key_id, "rotate_refused", str(exc))
            raise
        now = self._clock()
        with self.sessions.begin() as db:
            current = self._active(db, reviewer_id)
            if current is None or current.key_id != current_id:
                raise ValueError("active key changed during rotation; retry")
            current.active, current.retired_at, current.retired_by = False, now, self.actor_id
            current.retire_reason, current.replaced_by_key_id = f"rotated ({mode})", body.new_key_id
            current.signatures_valid_before = now
            db.flush()
            db.add(ReviewerKeyRow(tenant_id=self.tenant_id, reviewer_id=reviewer_id, key_id=body.new_key_id, public_key=raw,
                                  fingerprint_sha256=fingerprint, active=True, created_at=now, enrolled_by=self.actor_id))
            self._event(db, reviewer_id, body.new_key_id, "rotated",
                        {"mode": mode, "old_key_id": current_id, "new_fingerprint_sha256": fingerprint})
        return {"reviewer_id": reviewer_id, "old_key_id": current_id, "new_key_id": body.new_key_id,
                "fingerprint_sha256": fingerprint, "mode": mode, "rotated_at": now}

    def _row_exists(self, reviewer_id: str, key_id: str) -> bool:
        with self.sessions() as db:
            return self._row(db, reviewer_id, key_id) is not None

    def retire(self, reviewer_id: str, key_id: str, reason: str = "retired", *, compromised: bool = False,
               compromised_since: datetime | None = None) -> ReviewerKeyRow:
        with self.sessions.begin() as db:
            row = self._row(db, reviewer_id, key_id)
            if not row:
                raise LookupError("reviewer key not found")
        self._authorize(reviewer_id, key_id, "retire")
        with self.sessions.begin() as db:
            row = self._row(db, reviewer_id, key_id)
            now = self._clock()
            if compromised:
                since = compromised_since.astimezone(timezone.utc) if compromised_since and compromised_since.tzinfo else (
                    compromised_since.replace(tzinfo=timezone.utc) if compromised_since else None)
                created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
                cutoff = max(created, min(since, now)) if since else created
            else:
                cutoff = now
            if row.active:
                row.active, row.retired_at, row.retired_by, row.retire_reason = False, now, self.actor_id, reason
                row.signatures_valid_before = cutoff
                self._event(db, reviewer_id, key_id, "retired", {"reason": reason, "compromised": compromised,
                                                                 "signatures_valid_before": cutoff.isoformat()})
            elif compromised:
                # Declaring compromise later can only move the cutoff earlier.
                current = row.signatures_valid_before
                current = current if current is None or current.tzinfo else current.replace(tzinfo=timezone.utc)
                if current is None or cutoff < current:
                    row.signatures_valid_before = cutoff
                self._event(db, reviewer_id, key_id, "compromise_declared", {"reason": reason, "signatures_valid_before": cutoff.isoformat()})
            db.flush()
            db.expunge(row)
            return row

    def list_keys(self, reviewer_id: str | None = None) -> list[dict[str, Any]]:
        with self.sessions() as db:
            stmt = select(ReviewerKeyRow).where(ReviewerKeyRow.tenant_id == self.tenant_id)
            if reviewer_id:
                stmt = stmt.where(ReviewerKeyRow.reviewer_id == reviewer_id)
            return [{"reviewer_id": r.reviewer_id, "key_id": r.key_id, "fingerprint_sha256": r.fingerprint_sha256,
                     "active": r.active, "created_at": r.created_at, "retired_at": r.retired_at, "enrolled_by": r.enrolled_by,
                     "retire_reason": r.retire_reason, "replaced_by_key_id": r.replaced_by_key_id,
                     "signatures_valid_before": r.signatures_valid_before}
                    for r in db.scalars(stmt.order_by(ReviewerKeyRow.id))]

    def events(self, reviewer_id: str) -> list[dict[str, Any]]:
        with self.sessions() as db:
            rows = db.scalars(select(ReviewerKeyEventRow).where(ReviewerKeyEventRow.tenant_id == self.tenant_id,
                              ReviewerKeyEventRow.reviewer_id == reviewer_id).order_by(ReviewerKeyEventRow.id))
            return [{"key_id": r.key_id, "event": r.event, "actor": r.actor, "details": r.details, "at": r.at} for r in rows]

    def retired_key_record(self, reviewer_id: str, key_id: str) -> tuple[bytes, datetime]:
        """Key bytes plus the instant before which its signatures may still be trusted."""
        with self.sessions() as db:
            row = self._row(db, reviewer_id, key_id)
            if row is None:
                raise LookupError(f"no registered key {key_id!r} for reviewer {reviewer_id!r}")
            if row.active:
                raise LookupError("key is active")
            cutoff = row.signatures_valid_before or row.retired_at
            if cutoff is None:
                raise LookupError("retired key has no validity cutoff")
            return bytes(row.public_key), cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)

    # -- verification lookup ----------------------------------------------------
    def active_public_key(self, reviewer_id: str, key_id: str) -> bytes:
        with self.sessions() as db:
            row = self._row(db, reviewer_id, key_id)
            if row is None:
                raise LookupError(f"no registered key {key_id!r} for reviewer {reviewer_id!r}")
            if not row.active:
                raise LookupError(f"key {key_id!r} for reviewer {reviewer_id!r} is retired ({row.retire_reason})")
            return bytes(row.public_key)
