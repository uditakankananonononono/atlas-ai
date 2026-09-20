from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .lane_models import (Approval, Draft, DraftStatus, EmailMessage, FollowUp,
                     FollowUpStatus, TriageDecision, TriageLabel, iso)


class EmailStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self._db.execute("BEGIN IMMEDIATE")
            yield self._db
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def _migrate(self) -> None:
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS sync_state(tenant_id TEXT, mailbox_id TEXT, cursor TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(tenant_id,mailbox_id));
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, mailbox_id TEXT NOT NULL, provider_id TEXT NOT NULL, thread_id TEXT NOT NULL, sender TEXT NOT NULL, recipients TEXT NOT NULL, subject TEXT NOT NULL, body_text TEXT NOT NULL, received_at TEXT NOT NULL, headers TEXT NOT NULL, in_reply_to TEXT, UNIQUE(tenant_id,mailbox_id,provider_id));
        CREATE INDEX IF NOT EXISTS messages_tenant_thread ON messages(tenant_id,mailbox_id,thread_id,received_at);
        CREATE TABLE IF NOT EXISTS triage(message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE, tenant_id TEXT NOT NULL, label TEXT NOT NULL, score REAL NOT NULL, reasons TEXT NOT NULL, needs_reply INTEGER NOT NULL, due_at TEXT);
        CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, mailbox_id TEXT NOT NULL, thread_id TEXT NOT NULL, recipients TEXT NOT NULL, cc TEXT NOT NULL, subject TEXT NOT NULL, body_text TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, source_message_id TEXT, provider_message_id TEXT);
        CREATE INDEX IF NOT EXISTS drafts_tenant ON drafts(tenant_id,status,updated_at);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, draft_id TEXT NOT NULL REFERENCES drafts(id), requested_by TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT, reason TEXT, draft_revision INTEGER NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS approvals_one_pending ON approvals(draft_id) WHERE status='pending';
        CREATE TABLE IF NOT EXISTS followups(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, mailbox_id TEXT NOT NULL, thread_id TEXT NOT NULL, due_at TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, source_message_id TEXT, completed_at TEXT);
        CREATE INDEX IF NOT EXISTS followups_due ON followups(tenant_id,status,due_at);
        CREATE TABLE IF NOT EXISTS send_receipts(draft_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, provider_message_id TEXT NOT NULL, sent_at TEXT NOT NULL);
        """)
        self._db.commit()

    def cursor(self, tenant_id: str, mailbox_id: str) -> str | None:
        row = self._db.execute("SELECT cursor FROM sync_state WHERE tenant_id=? AND mailbox_id=?", (tenant_id, mailbox_id)).fetchone()
        return row[0] if row else None

    def save_sync_page(self, tenant_id: str, mailbox_id: str, messages: list[EmailMessage], cursor: str | None) -> tuple[int, int]:
        inserted = updated = 0
        with self.transaction() as db:
            for m in messages:
                existing = db.execute("SELECT id FROM messages WHERE tenant_id=? AND mailbox_id=? AND provider_id=?", (tenant_id, mailbox_id, m.provider_id)).fetchone()
                db.execute("""INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,mailbox_id,provider_id) DO UPDATE SET thread_id=excluded.thread_id,sender=excluded.sender,recipients=excluded.recipients,subject=excluded.subject,body_text=excluded.body_text,received_at=excluded.received_at,headers=excluded.headers,in_reply_to=excluded.in_reply_to""", (m.id,m.tenant_id,m.mailbox_id,m.provider_id,m.thread_id,m.sender,json.dumps(m.recipients),m.subject,m.body_text,iso(m.received_at),json.dumps(dict(m.headers)),m.in_reply_to))
                updated += bool(existing); inserted += not bool(existing)
            db.execute("INSERT INTO sync_state VALUES(?,?,?,?) ON CONFLICT(tenant_id,mailbox_id) DO UPDATE SET cursor=excluded.cursor,updated_at=excluded.updated_at", (tenant_id,mailbox_id,cursor,iso(datetime.now().astimezone())))
        return inserted, updated

    def get_message(self, tenant_id: str, message_id: str) -> EmailMessage | None:
        r = self._db.execute("SELECT * FROM messages WHERE tenant_id=? AND id=?", (tenant_id,message_id)).fetchone()
        return self._message(r) if r else None

    def thread(self, tenant_id: str, mailbox_id: str, thread_id: str) -> list[EmailMessage]:
        rows=self._db.execute("SELECT * FROM messages WHERE tenant_id=? AND mailbox_id=? AND thread_id=? ORDER BY received_at",(tenant_id,mailbox_id,thread_id)).fetchall()
        return [self._message(r) for r in rows]

    @staticmethod
    def _message(r: sqlite3.Row) -> EmailMessage:
        return EmailMessage(r['id'],r['tenant_id'],r['mailbox_id'],r['provider_id'],r['thread_id'],r['sender'],tuple(json.loads(r['recipients'])),r['subject'],r['body_text'],datetime.fromisoformat(r['received_at']),json.loads(r['headers']),r['in_reply_to'])

    def save_triage(self, tenant_id: str, d: TriageDecision) -> None:
        self._db.execute("INSERT INTO triage VALUES(?,?,?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET label=excluded.label,score=excluded.score,reasons=excluded.reasons,needs_reply=excluded.needs_reply,due_at=excluded.due_at",(d.message_id,tenant_id,d.label.value,d.score,json.dumps(d.reasons),d.needs_reply,iso(d.due_at) if d.due_at else None)); self._db.commit()

    def save_draft(self, d: Draft) -> None:
        self._db.execute("INSERT INTO drafts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(d.id,d.tenant_id,d.mailbox_id,d.thread_id,json.dumps(d.to),json.dumps(d.cc),d.subject,d.body_text,d.status.value,d.revision,iso(d.created_at),iso(d.updated_at),d.source_message_id,d.provider_message_id)); self._db.commit()

    def get_draft(self, tenant_id: str, draft_id: str) -> Draft | None:
        r=self._db.execute("SELECT * FROM drafts WHERE tenant_id=? AND id=?",(tenant_id,draft_id)).fetchone(); return self._draft(r) if r else None

    @staticmethod
    def _draft(r: sqlite3.Row) -> Draft:
        return Draft(r['id'],r['tenant_id'],r['mailbox_id'],r['thread_id'],tuple(json.loads(r['recipients'])),tuple(json.loads(r['cc'])),r['subject'],r['body_text'],DraftStatus(r['status']),r['revision'],datetime.fromisoformat(r['created_at']),datetime.fromisoformat(r['updated_at']),r['source_message_id'],r['provider_message_id'])

    def update_draft(self, tenant_id: str, draft_id: str, *, body_text: str | None=None, status: DraftStatus | None=None, provider_message_id: str | None=None, expected_revision: int | None=None) -> Draft:
        d=self.get_draft(tenant_id,draft_id)
        if not d: raise KeyError("draft not found")
        if expected_revision is not None and d.revision != expected_revision: raise RuntimeError("draft revision conflict")
        revision=d.revision + (body_text is not None and body_text != d.body_text)
        self._db.execute("UPDATE drafts SET body_text=?,status=?,revision=?,updated_at=?,provider_message_id=COALESCE(?,provider_message_id) WHERE tenant_id=? AND id=?",(body_text if body_text is not None else d.body_text,(status or d.status).value,revision,iso(datetime.now().astimezone()),provider_message_id,tenant_id,draft_id)); self._db.commit()
        return self.get_draft(tenant_id,draft_id)  # type: ignore[return-value]

    def save_approval(self, a: Approval) -> None:
        self._db.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?)",(a.id,a.tenant_id,a.draft_id,a.requested_by,a.status,iso(a.created_at),iso(a.decided_at) if a.decided_at else None,a.decided_by,a.reason,a.draft_revision)); self._db.commit()

    def pending_approval(self, tenant_id: str, draft_id: str) -> Approval | None:
        r=self._db.execute("SELECT * FROM approvals WHERE tenant_id=? AND draft_id=? AND status='pending'",(tenant_id,draft_id)).fetchone(); return self._approval(r) if r else None

    @staticmethod
    def _approval(r: sqlite3.Row) -> Approval:
        return Approval(r['id'],r['tenant_id'],r['draft_id'],r['requested_by'],r['status'],datetime.fromisoformat(r['created_at']),datetime.fromisoformat(r['decided_at']) if r['decided_at'] else None,r['decided_by'],r['reason'],r['draft_revision'])

    def decide_approval(self, tenant_id: str, approval_id: str, status: str, actor: str, reason: str | None) -> Approval:
        now=iso(datetime.now().astimezone()); cur=self._db.execute("UPDATE approvals SET status=?,decided_at=?,decided_by=?,reason=? WHERE tenant_id=? AND id=? AND status='pending'",(status,now,actor,reason,tenant_id,approval_id))
        if cur.rowcount != 1: raise RuntimeError("approval is missing or already decided")
        self._db.commit(); r=self._db.execute("SELECT * FROM approvals WHERE tenant_id=? AND id=?",(tenant_id,approval_id)).fetchone(); return self._approval(r)

    def save_followup(self, f: FollowUp) -> None:
        self._db.execute("INSERT INTO followups VALUES(?,?,?,?,?,?,?,?,?,?)",(f.id,f.tenant_id,f.mailbox_id,f.thread_id,iso(f.due_at),f.status.value,f.reason,iso(f.created_at),f.source_message_id,iso(f.completed_at) if f.completed_at else None)); self._db.commit()

    def due_followups(self, tenant_id: str, at: datetime) -> list[FollowUp]:
        rows=self._db.execute("SELECT * FROM followups WHERE tenant_id=? AND status IN ('open','due') AND due_at<=? ORDER BY due_at",(tenant_id,iso(at))).fetchall(); return [self._followup(r) for r in rows]

    @staticmethod
    def _followup(r: sqlite3.Row) -> FollowUp:
        return FollowUp(r['id'],r['tenant_id'],r['mailbox_id'],r['thread_id'],datetime.fromisoformat(r['due_at']),FollowUpStatus(r['status']),r['reason'],datetime.fromisoformat(r['created_at']),r['source_message_id'],datetime.fromisoformat(r['completed_at']) if r['completed_at'] else None)

    def complete_followups_for_thread(self, tenant_id: str, mailbox_id: str, thread_id: str, at: datetime) -> int:
        cur=self._db.execute("UPDATE followups SET status='completed',completed_at=? WHERE tenant_id=? AND mailbox_id=? AND thread_id=? AND status IN ('open','due')",(iso(at),tenant_id,mailbox_id,thread_id)); self._db.commit(); return cur.rowcount

    def record_send(self, tenant_id: str, draft_id: str, key: str, provider_id: str, sent_at: datetime) -> None:
        self._db.execute("INSERT INTO send_receipts VALUES(?,?,?,?,?)",(draft_id,tenant_id,key,provider_id,iso(sent_at))); self._db.commit()

    def send_receipt(self, tenant_id: str, draft_id: str) -> sqlite3.Row | None:
        return self._db.execute("SELECT * FROM send_receipts WHERE tenant_id=? AND draft_id=?",(tenant_id,draft_id)).fetchone()
