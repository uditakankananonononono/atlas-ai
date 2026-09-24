"""Receipt inbox + beat-driven worker loop for queued reproducible-run checkpoints (M12).

Resuming a checkpoint means provider calls, which Atlas does not make or pay for.
The external runner (or the provider) posts the Ed25519-signed receipts for the
resumed nodes into a tenant-scoped inbox. A checkpoint is *due* once its inbox
covers every node that is not completed in the checkpoint payload.

``CheckpointLoop.run_once`` (driven by the Celery beat task
``atlas.m12.run_checkpoint_worker``) claims only due checkpoints through the
existing lease, heartbeats, and calls ``CheckpointWorker.complete`` (signature
and registered-key checks). A verification failure goes through
``CheckpointWorker.fail`` (retry until max_attempts, then failed) and clears the
rejected receipts, so the checkpoint waits for new receipts instead of retrying
the same bad ones. Checkpoints still waiting for receipts are never claimed and
never burn attempts. Nothing here calls a provider or spends money.
"""
from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, delete, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from .asymmetric_resume_verification import SignedProviderReceipt
from .checkpoint_queue import CheckpointQueueRow
from .checkpoint_worker import CheckpointWorker, LeaseError


class InboxError(ValueError):
    pass


class InboxNotFound(InboxError):
    pass


class CheckpointReceiptRow(Base):
    __tablename__ = "m12_checkpoint_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "queue_row_id", "node_id", name="uq_m12_receipt_node"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    queue_row_id: Mapped[int] = mapped_column(index=True)
    node_id: Mapped[str] = mapped_column(String(300))
    receipt: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _ensure_tables(sessions) -> None:
    if sessions is SessionLocal:
        Base.metadata.create_all(engine, tables=[CheckpointReceiptRow.__table__])


def required_nodes(payload: dict) -> list[str]:
    """Nodes a resume must redo: every node in the checkpoint that is not completed."""
    return [n["node_id"] for n in payload.get("nodes") or [] if n.get("status") != "completed"]


def resume_node(payload: dict) -> str | None:
    return payload.get("resume_from_node_id") or next(iter(required_nodes(payload)), None)


class ReceiptInbox:
    def __init__(self, tenant_id: str, sessions: sessionmaker = SessionLocal,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.tenant_id, self.sessions, self.clock = tenant_id, sessions, clock
        _ensure_tables(sessions)

    def _queued(self, db, run_id: str) -> CheckpointQueueRow:
        q = db.scalar(select(CheckpointQueueRow).where(CheckpointQueueRow.tenant_id == self.tenant_id,
                                                       CheckpointQueueRow.run_id == run_id,
                                                       CheckpointQueueRow.state == "queued"))
        if q is None:
            raise InboxNotFound(f"no queued checkpoint for run {run_id}")
        return q

    def post(self, run_id: str, receipts: list[SignedProviderReceipt]) -> dict:
        """Store signed receipts for the queued checkpoint of ``run_id``. Signatures are checked at completion."""
        if not receipts:
            raise InboxError("no receipts")
        ids = [r.node_id for r in receipts]
        if len(ids) != len(set(ids)):
            raise InboxError("duplicate node_id")
        now = self.clock()
        with self.sessions.begin() as db:
            q = self._queued(db, run_id)
            needed = set(required_nodes(q.payload))
            extra = sorted(set(ids) - needed)
            if extra:
                raise InboxError(f"nodes not awaiting a receipt in this checkpoint: {', '.join(extra)}")
            for r in receipts:  # a re-posted node replaces its earlier receipt
                db.execute(delete(CheckpointReceiptRow).where(CheckpointReceiptRow.tenant_id == self.tenant_id,
                                                              CheckpointReceiptRow.queue_row_id == q.id,
                                                              CheckpointReceiptRow.node_id == r.node_id))
                db.add(CheckpointReceiptRow(tenant_id=self.tenant_id, queue_row_id=q.id, node_id=r.node_id,
                                            receipt=r.model_dump(mode="json"), received_at=now))
            db.flush()
            return self._status(db, q)

    def status(self, run_id: str) -> dict:
        with self.sessions() as db:
            return self._status(db, self._queued(db, run_id))

    def _received(self, db, queue_row_id: int) -> list[CheckpointReceiptRow]:
        return list(db.scalars(select(CheckpointReceiptRow).where(CheckpointReceiptRow.tenant_id == self.tenant_id,
                                                                  CheckpointReceiptRow.queue_row_id == queue_row_id)
                               .order_by(CheckpointReceiptRow.node_id)))

    def _status(self, db, q: CheckpointQueueRow) -> dict:
        needed = required_nodes(q.payload)
        got = {r.node_id for r in self._received(db, q.id)}
        missing = [n for n in needed if n not in got]
        return {"run_id": q.run_id, "checkpoint_sha256": q.checkpoint_sha256, "required": needed,
                "received": sorted(got), "missing": missing, "due": bool(needed) and not missing}

    def due(self) -> list[tuple[int, str]]:
        """(queue_row_id, run_id) for queued checkpoints whose inbox covers every incomplete node, oldest first."""
        with self.sessions() as db:
            rows = db.scalars(select(CheckpointQueueRow).where(CheckpointQueueRow.tenant_id == self.tenant_id,
                                                               CheckpointQueueRow.state == "queued")
                              .order_by(CheckpointQueueRow.enqueued_at, CheckpointQueueRow.id)).all()
            return [(q.id, q.run_id) for q in rows if self._status(db, q)["due"]]

    def receipts_for(self, queue_row_id: int) -> list[SignedProviderReceipt]:
        with self.sessions() as db:
            return [SignedProviderReceipt(**r.receipt) for r in self._received(db, queue_row_id)]

    def clear(self, queue_row_id: int) -> None:
        with self.sessions.begin() as db:
            db.execute(delete(CheckpointReceiptRow).where(CheckpointReceiptRow.tenant_id == self.tenant_id,
                                                          CheckpointReceiptRow.queue_row_id == queue_row_id))


class CheckpointLoop:
    def __init__(self, tenant_id: str, sessions: sessionmaker = SessionLocal, *, worker: CheckpointWorker | None = None,
                 worker_id: str | None = None, lease_seconds: int = 300,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.tenant_id = tenant_id
        self.worker = worker or CheckpointWorker(tenant_id, sessions, clock=clock)
        self.inbox = ReceiptInbox(tenant_id, sessions, clock)
        self.worker_id = worker_id or f"beat:{socket.gethostname()}"
        self.lease_seconds = lease_seconds

    def run_once(self, limit: int = 100) -> dict:
        completed, failed, skipped = [], [], []
        for queue_row_id, run_id in self.inbox.due()[:limit]:
            lease = self.worker.claim(self.worker_id, self.lease_seconds, queue_row_ids=[queue_row_id])
            if lease is None:  # leased by another worker, or just exhausted its attempts
                skipped.append({"run_id": run_id, "reason": "leased or no longer claimable"})
                continue
            token = lease["lease_token"]
            try:
                self.worker.heartbeat(token, self.lease_seconds)
                receipts = self.inbox.receipts_for(queue_row_id)
                out = self.worker.complete(token, receipts, resume_node(lease["checkpoint"]) or receipts[0].node_id)
                completed.append({"run_id": run_id, "verification_sha256": out["verification_sha256"],
                                  "receipts_verified": out["receipts_verified"]})
            except LeaseError as exc:
                try:
                    res = self.worker.fail(token, str(exc))
                except LeaseError as lost:  # lease lost mid-run: leave the checkpoint to its new holder
                    skipped.append({"run_id": run_id, "reason": str(lost)})
                    continue
                self.inbox.clear(queue_row_id)
                failed.append({"run_id": run_id, "error": str(exc), "state": res["state"], "attempts": res["attempts"]})
        return {"tenant_id": self.tenant_id, "worker_id": self.worker_id, "completed": completed, "failed": failed,
                "skipped": skipped, "provider_calls": 0}


def tenants_with_queued_checkpoints(sessions: sessionmaker = SessionLocal) -> list[str]:
    _ensure_tables(sessions)
    with sessions() as db:
        return sorted(set(db.scalars(select(CheckpointQueueRow.tenant_id).where(CheckpointQueueRow.state == "queued"))))
