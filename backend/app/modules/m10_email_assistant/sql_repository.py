"""Tenant-scoped SQL storage for module 10, with append-only change rows.

Every row carries tenant_id and every query filters on it, matching the
module 2/5 durable-SQL pattern. Gmail messages are idempotent on
(tenant_id, gmail_id) so Pub/Sub redelivery never duplicates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GmailAccountRow(Base):
    __tablename__ = "m10_gmail_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "email_address"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    email_address: Mapped[str] = mapped_column(String(320))
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    history_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmailMessageRow(Base):
    __tablename__ = "m10_email_messages"
    __table_args__ = (UniqueConstraint("tenant_id", "gmail_id"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    gmail_id: Mapped[str] = mapped_column(String(64))
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    history_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(String(320), index=True)
    recipients: Mapped[list] = mapped_column(JSON, default=list)
    snippet: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    unsubscribe_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActionItemRow(Base):
    __tablename__ = "m10_action_items"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    message_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(Text)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    related_entity: Mapped[str | None] = mapped_column(String(300), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="open")


class EmailDraftRow(Base):
    __tablename__ = "m10_email_drafts"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    message_id: Mapped[str] = mapped_column(String(36), index=True)
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    to: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="pending_approval")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmailEventRow(Base):
    """Append-only audit log for module 10 mutations."""

    __tablename__ = "m10_email_events"
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    event: Mapped[str] = mapped_column(String(60))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PromiseSnapshotRow(Base):
    __tablename__ = "m10_promise_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "thread_id"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    thread_id: Mapped[str] = mapped_column(String(300), index=True)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    previous_snapshot_sha256: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlEmailRepository:
    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal) -> None:
        self.tenant_id = tenant_id
        self.sessions = session_factory
        Base.metadata.create_all(engine)

    # -- accounts ---------------------------------------------------------
    def save_account(self, *, account_id: str, email_address: str, encrypted_refresh_token: str,
                     history_id: str | None, watch_expiration: datetime | None) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == self.tenant_id,
                GmailAccountRow.email_address == email_address))
            now = _utcnow()
            if row is None:
                db.add(GmailAccountRow(
                    tenant_id=self.tenant_id, id=account_id, email_address=email_address,
                    encrypted_refresh_token=encrypted_refresh_token, history_id=history_id,
                    watch_expiration=watch_expiration, created_at=now, updated_at=now))
            else:
                row.encrypted_refresh_token = encrypted_refresh_token
                row.history_id = history_id or row.history_id
                row.updated_at = now
            self._log(db, "gmail_account", account_id, "account_saved", {"email_address": email_address})

    def get_account_by_email(self, email_address: str) -> GmailAccountRow | None:
        with self.sessions() as db:
            return db.scalar(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == self.tenant_id,
                GmailAccountRow.email_address == email_address))

    def get_account(self, account_id: str) -> GmailAccountRow | None:
        with self.sessions() as db:
            return db.scalar(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == self.tenant_id, GmailAccountRow.id == account_id))

    def list_accounts(self) -> list[GmailAccountRow]:
        with self.sessions() as db:
            return list(db.scalars(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == self.tenant_id)))

    def update_history_id(self, account_id: str, history_id: str) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == self.tenant_id, GmailAccountRow.id == account_id))
            if row is not None:
                row.history_id = history_id
                row.updated_at = _utcnow()

    def update_watch_expiration(self, account_id: str, expires_at: datetime, history_id: str) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(GmailAccountRow).where(
                GmailAccountRow.tenant_id == self.tenant_id, GmailAccountRow.id == account_id))
            if row is not None:
                row.watch_expiration = expires_at
                row.history_id = history_id
                row.updated_at = _utcnow()
                self._log(db, "gmail_account", account_id, "watch_renewed",
                          {"watch_expiration": expires_at.isoformat()})

    # -- messages ---------------------------------------------------------
    def has_message(self, gmail_id: str) -> bool:
        with self.sessions() as db:
            return db.scalar(select(EmailMessageRow.pk).where(
                EmailMessageRow.tenant_id == self.tenant_id,
                EmailMessageRow.gmail_id == gmail_id)) is not None

    def save_message(self, *, message_id: str, account_id: str, gmail_id: str,
                     thread_id: str | None, history_id: str | None, subject: str,
                     sender: str, recipients: list[str], snippet: str, body_text: str,
                     received_at: datetime | None, labels: list[str], headers: dict,
                     category: str | None, category_confidence: float,
                     embedding: list[float] | None, unsubscribe_url: str | None) -> None:
        with self.sessions.begin() as db:
            if db.scalar(select(EmailMessageRow.pk).where(
                    EmailMessageRow.tenant_id == self.tenant_id,
                    EmailMessageRow.gmail_id == gmail_id)) is not None:
                return  # idempotent on (tenant, gmail_id)
            db.add(EmailMessageRow(
                tenant_id=self.tenant_id, id=message_id, account_id=account_id,
                gmail_id=gmail_id, thread_id=thread_id, history_id=history_id,
                subject=subject, sender=sender, recipients=recipients, snippet=snippet,
                body_text=body_text, received_at=received_at, labels=labels, headers=headers,
                category=category, category_confidence=category_confidence,
                embedding=embedding, unsubscribe_url=unsubscribe_url, created_at=_utcnow()))
            self._log(db, "email_message", message_id, "ingested",
                      {"gmail_id": gmail_id, "category": category})

    def list_messages(self, category: str | None = None, limit: int = 100) -> list[EmailMessageRow]:
        with self.sessions() as db:
            statement = select(EmailMessageRow).where(
                EmailMessageRow.tenant_id == self.tenant_id
            ).order_by(EmailMessageRow.received_at.desc()).limit(limit)
            if category:
                statement = statement.where(EmailMessageRow.category == category)
            return list(db.scalars(statement))

    def get_message(self, message_id: str) -> EmailMessageRow | None:
        with self.sessions() as db:
            return db.scalar(select(EmailMessageRow).where(
                EmailMessageRow.tenant_id == self.tenant_id, EmailMessageRow.id == message_id))

    def thread_messages(self, thread_id: str, limit: int = 10) -> list[EmailMessageRow]:
        with self.sessions() as db:
            return list(db.scalars(select(EmailMessageRow).where(
                EmailMessageRow.tenant_id == self.tenant_id,
                EmailMessageRow.thread_id == thread_id,
            ).order_by(EmailMessageRow.received_at.desc()).limit(limit)))

    def sender_counts(self) -> dict[str, int]:
        with self.sessions() as db:
            rows = db.execute(
                select(EmailMessageRow.sender).where(
                    EmailMessageRow.tenant_id == self.tenant_id)
            ).all()
            counts: dict[str, int] = {}
            for (sender,) in rows:
                counts[sender] = counts.get(sender, 0) + 1
            return counts

    # -- action items -----------------------------------------------------
    def save_action_items(self, message_id: str, items: list[dict]) -> None:
        with self.sessions.begin() as db:
            for item in items:
                db.add(ActionItemRow(
                    tenant_id=self.tenant_id, id=item["id"], message_id=message_id,
                    action=item["action"], deadline=item.get("deadline"),
                    related_entity=item.get("related_entity"),
                    confidence=item.get("confidence", 0.0), status="open"))
            if items:
                self._log(db, "email_message", message_id, "actions_extracted",
                          {"count": len(items)})

    def list_action_items(self, status: str = "open", limit: int = 100) -> list[ActionItemRow]:
        with self.sessions() as db:
            return list(db.scalars(select(ActionItemRow).where(
                ActionItemRow.tenant_id == self.tenant_id,
                ActionItemRow.status == status).limit(limit)))

    # -- drafts -----------------------------------------------------------
    def save_draft(self, *, draft_id: str, message_id: str, approval_id: str, to: str,
                   subject: str, body: str, model: str) -> None:
        with self.sessions.begin() as db:
            db.add(EmailDraftRow(
                tenant_id=self.tenant_id, id=draft_id, message_id=message_id,
                approval_id=approval_id, to=to, subject=subject, body=body, model=model,
                status="pending_approval", created_at=_utcnow()))
            self._log(db, "email_draft", draft_id, "draft_proposed",
                      {"approval_id": approval_id, "message_id": message_id})

    def list_drafts(self, limit: int = 100) -> list[EmailDraftRow]:
        with self.sessions() as db:
            return list(db.scalars(select(EmailDraftRow).where(
                EmailDraftRow.tenant_id == self.tenant_id
            ).order_by(EmailDraftRow.created_at.desc()).limit(limit)))

    # -- promise reconciliation snapshots ----------------------------------
    def persist_promise_snapshot(self, *, thread_id: str, previous_snapshot_sha256: str,
                                 snapshot_sha256: str, snapshot: dict) -> PromiseSnapshotRow:
        """Atomic tenant/thread compare-and-swap; stale writers fail closed."""
        with self.sessions.begin() as db:
            row = db.scalar(select(PromiseSnapshotRow).where(
                PromiseSnapshotRow.tenant_id == self.tenant_id,
                PromiseSnapshotRow.thread_id == thread_id))
            if row is None:
                row = PromiseSnapshotRow(
                    tenant_id=self.tenant_id, thread_id=thread_id,
                    snapshot_sha256=snapshot_sha256,
                    previous_snapshot_sha256=previous_snapshot_sha256,
                    snapshot=snapshot, updated_at=_utcnow())
                db.add(row)
            else:
                if row.snapshot_sha256 != previous_snapshot_sha256:
                    raise ValueError("stale promise snapshot: compare-and-swap failed")
                row.previous_snapshot_sha256 = previous_snapshot_sha256
                row.snapshot_sha256 = snapshot_sha256
                row.snapshot = snapshot
                row.updated_at = _utcnow()
            self._log(db, "promise_snapshot", thread_id, "snapshot_persisted", {
                "previous_snapshot_sha256": previous_snapshot_sha256,
                "snapshot_sha256": snapshot_sha256,
            })
            db.flush()
            return row

    def get_promise_snapshot(self, thread_id: str) -> PromiseSnapshotRow | None:
        with self.sessions() as db:
            return db.scalar(select(PromiseSnapshotRow).where(
                PromiseSnapshotRow.tenant_id == self.tenant_id,
                PromiseSnapshotRow.thread_id == thread_id))

    # -- audit ------------------------------------------------------------
    def _log(self, db, entity: str, entity_id: str, event: str, details: dict) -> None:
        db.add(EmailEventRow(tenant_id=self.tenant_id, entity=entity,
                             entity_id=entity_id, event=event, at=_utcnow(), details=details))

    def events(self, entity_id: str) -> list[EmailEventRow]:
        with self.sessions() as db:
            return list(db.scalars(select(EmailEventRow).where(
                EmailEventRow.tenant_id == self.tenant_id,
                EmailEventRow.entity_id == entity_id).order_by(EmailEventRow.pk)))
