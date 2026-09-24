"""Worker dequeue/lease semantics for queued reproducible-run checkpoints (M12).

- ``claim`` leases the oldest queued checkpoint for the tenant whose lease is
  absent or expired. Leases live in their own table (one row per queue row,
  unique), and takeover of an expired lease is a conditional UPDATE on the old
  token, so two workers cannot both win.
- ``heartbeat`` extends a live lease; ``fail`` releases it (the checkpoint goes
  back to queued until ``max_attempts``, then is marked failed).
- ``complete`` requires provider receipts for the finished nodes and verifies
  each one against the tenant's registered, unretired Ed25519 keys for that
  receipt's own provider (a key registered for provider A cannot sign for B).
  Only then is the checkpoint marked completed.

The worker never spends: receipts record provider spend that already happened,
and nothing here calls a provider.
"""
from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from .asymmetric_resume_verification import (AsymmetricResumeVerificationRequest, SignedProviderReceipt,
                                             verify_asymmetric_resume)
from .checkpoint_queue import CheckpointQueueRow
from .provider_key_registry import ProviderKeyRow


class LeaseError(ValueError):
    pass


class CheckpointLeaseRow(Base):
    __tablename__ = "m12_checkpoint_leases"
    __table_args__ = (UniqueConstraint("queue_row_id", name="uq_m12_lease_queue_row"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    queue_row_id: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(200))
    lease_token: Mapped[str] = mapped_column(String(64))
    leased_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


class CheckpointWorker:
    def __init__(self, tenant_id: str, sessions: sessionmaker = SessionLocal, *, max_attempts: int = 3,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.tenant_id, self.sessions, self.max_attempts, self.clock = tenant_id, sessions, max_attempts, clock
        if sessions is SessionLocal:
            Base.metadata.create_all(engine, tables=[CheckpointLeaseRow.__table__])

    def claim(self, worker_id: str, lease_seconds: int = 300) -> dict | None:
        if not 10 <= lease_seconds <= 3600:
            raise LeaseError("lease_seconds must be 10..3600")
        now = self.clock()
        with self.sessions.begin() as db:
            queued = db.scalars(select(CheckpointQueueRow).where(CheckpointQueueRow.tenant_id == self.tenant_id,
                                                                 CheckpointQueueRow.state == "queued")
                                .order_by(CheckpointQueueRow.enqueued_at, CheckpointQueueRow.id).limit(50)).all()
            for q in queued:
                lease = db.scalar(select(CheckpointLeaseRow).where(CheckpointLeaseRow.queue_row_id == q.id))
                token = secrets.token_hex(16)
                until = now + timedelta(seconds=lease_seconds)
                if lease is None:
                    try:
                        with db.begin_nested():
                            db.add(CheckpointLeaseRow(tenant_id=self.tenant_id, queue_row_id=q.id, worker_id=worker_id,
                                                      lease_token=token, leased_until=until, attempts=1))
                    except IntegrityError:
                        continue
                    attempts = 1
                else:
                    if _aware(lease.leased_until) > now:
                        continue
                    prev_token, prev_attempts = lease.lease_token, lease.attempts
                    won = db.execute(update(CheckpointLeaseRow).where(CheckpointLeaseRow.id == lease.id,
                                                                      CheckpointLeaseRow.lease_token == prev_token)
                                     .values(worker_id=worker_id, lease_token=token, leased_until=until,
                                             attempts=prev_attempts + 1)).rowcount
                    if not won:
                        continue
                    attempts = prev_attempts + 1
                    if attempts > self.max_attempts:
                        q.state = "failed"
                        continue
                return {"run_id": q.run_id, "checkpoint_sha256": q.checkpoint_sha256, "lease_token": token,
                        "leased_until": until.isoformat(), "attempt": attempts, "checkpoint": q.payload}
        return None

    def _live(self, db, token: str) -> tuple[CheckpointLeaseRow, CheckpointQueueRow]:
        lease = db.scalar(select(CheckpointLeaseRow).where(CheckpointLeaseRow.tenant_id == self.tenant_id,
                                                           CheckpointLeaseRow.lease_token == token))
        if lease is None:
            raise LeaseError("unknown or superseded lease")
        q = db.get(CheckpointQueueRow, lease.queue_row_id)
        if q is None or q.state != "queued":
            raise LeaseError("checkpoint is no longer queued")
        if _aware(lease.leased_until) <= self.clock():
            raise LeaseError("lease expired; claim again")
        return lease, q

    def heartbeat(self, token: str, lease_seconds: int = 300) -> dict:
        with self.sessions.begin() as db:
            lease, _ = self._live(db, token)
            lease.leased_until = self.clock() + timedelta(seconds=min(max(lease_seconds, 10), 3600))
            return {"leased_until": lease.leased_until.isoformat()}

    def fail(self, token: str, error: str) -> dict:
        with self.sessions.begin() as db:
            lease, q = self._live(db, token)
            lease.leased_until = self.clock()
            lease.last_error = error[:2000]
            if lease.attempts >= self.max_attempts:
                q.state = "failed"
            return {"run_id": q.run_id, "state": q.state, "attempts": lease.attempts}

    def _trusted_keys(self, db, receipts: list[SignedProviderReceipt]) -> dict[str, str]:
        keys = {}
        for r in receipts:
            row = db.scalar(select(ProviderKeyRow).where(ProviderKeyRow.tenant_id == self.tenant_id,
                                                         ProviderKeyRow.provider == r.provider,
                                                         ProviderKeyRow.key_id == r.key_id))
            if row is None:
                raise LeaseError(f"no registered key {r.provider}/{r.key_id} for receipt {r.node_id}")
            if not row.active or row.retired_at is not None:
                raise LeaseError(f"key {r.provider}/{r.key_id} is retired")
            if row.retired_at is None and _aware(row.created_at) > _aware(r.issued_at):
                raise LeaseError(f"receipt {r.node_id} predates registration of key {r.key_id}")
            keys[r.key_id] = base64.b64encode(row.public_key).decode()
        return keys

    def complete(self, token: str, receipts: list[SignedProviderReceipt], resume_from_node_id: str) -> dict:
        if not receipts:
            raise LeaseError("completion needs provider receipts")
        with self.sessions.begin() as db:
            lease, q = self._live(db, token)
            ids = [r.key_id for r in receipts]
            trusted = self._trusted_keys(db, receipts)
            if len(set(ids)) != len(trusted):
                raise LeaseError("key_id is reused across providers")
            try:
                verdict = verify_asymmetric_resume(AsymmetricResumeVerificationRequest(
                    checkpoint_sha256=q.checkpoint_sha256, resume_from_node_id=resume_from_node_id,
                    provider_receipts=receipts, trusted_ed25519_public_keys=trusted))
            except ValueError as exc:
                raise LeaseError(str(exc)) from exc
            q.state = "completed"
            lease.leased_until = self.clock()
            return {"run_id": q.run_id, "state": "completed", "verification_sha256": verdict["verification_sha256"],
                    "receipts_verified": len(verdict["provider_receipts"]),
                    "spent_cents_reported": sum(r.spent_cents for r in receipts),
                    "boundary": "Receipts verified against registered, unretired provider keys. Spend figures are what providers signed; the worker executes no provider calls and spends nothing."}
