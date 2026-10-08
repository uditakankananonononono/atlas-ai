"""Durable review snapshots and one-time local preflight claims.

Standalone opt-in component, not wired to DeliveryService or HTTP routes.
The integrator authenticates the reviewer/tenant and supplies a trusted live
inspector. This module cannot establish mailbox ownership, SMTP auth identity,
permission, recipient provenance or external delivery. A claim is consumed
before any send; errors after it require reconciliation, never automatic retry.
SQLite serializes claims, not writes to the inspector's external sources.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Callable
from uuid import uuid4


class PreflightRefused(ValueError):
    """The exact reviewed state cannot be claimed."""


@dataclass(frozen=True)
class SendState:
    message_id: str
    message_revision: str
    contact_id: str
    contact_revision: str
    recipient: str
    subject: str
    body: str
    account_id: str
    account_revision: str
    from_address: str
    auth_principal: str
    transport_route: str

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not str or (name != 'body' and not value.strip()):
                raise ValueError(f'{name} must be text and nonempty except body')
        for name in ('recipient', 'from_address', 'subject'):
            if '\r' in getattr(self, name) or '\n' in getattr(self, name):
                raise ValueError(f'{name} contains a header newline')


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('clock must be timezone aware')
    return value.astimezone(timezone.utc).isoformat()


def _required(value: str, field: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f'{field} must be nonempty text')


class SnapshotStore:
    """Tenant-separated SQLite snapshots. Cooperative trusted DB required.

    External review/authentication is mandatory before record_review. One token
    per tenant+message lifetime: a consumed message cannot be re-opened by a new
    review. Prepare a new message ID after manual reconciliation when needed.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], datetime] | None = None):
        self.path = str(path)
        if self.path == ':memory:':
            raise ValueError('use a durable SQLite file, not :memory:')
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS send_reviews (
              tenant TEXT NOT NULL, message_id TEXT NOT NULL, token TEXT NOT NULL,
              reviewer TEXT NOT NULL, snapshot TEXT NOT NULL,
              reviewed_at TEXT NOT NULL, expires_at TEXT NOT NULL,
              claimed_at TEXT,
              PRIMARY KEY(tenant,message_id), UNIQUE(tenant,token))''')
            db.execute('''CREATE TRIGGER IF NOT EXISTS send_review_immutable
              BEFORE UPDATE OF tenant,message_id,token,reviewer,snapshot,reviewed_at,expires_at
              ON send_reviews BEGIN SELECT RAISE(ABORT,'immutable review'); END''')
            db.execute('''CREATE TRIGGER IF NOT EXISTS send_claim_immutable
              BEFORE UPDATE OF claimed_at ON send_reviews WHEN OLD.claimed_at IS NOT NULL
              BEGIN SELECT RAISE(ABORT,'consumed claim'); END''')
            db.execute('''CREATE TRIGGER IF NOT EXISTS send_review_no_delete
              BEFORE DELETE ON send_reviews BEGIN SELECT RAISE(ABORT,'immutable review'); END''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_review(self, tenant: str, reviewer: str, state: SendState,
                      *, valid_for: timedelta = timedelta(minutes=15)) -> str:
        _required(tenant, 'tenant'); _required(reviewer, 'reviewer')
        if not isinstance(state, SendState):
            raise ValueError('state must be SendState')
        if not isinstance(valid_for, timedelta) or not timedelta(0) < valid_for <= timedelta(hours=1):
            raise ValueError('review lifetime must be positive and at most one hour')
        now = self.clock(); reviewed_at = _utc(now)
        expires_at = _utc(now + valid_for)
        token = uuid4().hex
        snapshot = json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)
        try:
            with self._db() as db:
                db.execute('INSERT INTO send_reviews VALUES (?,?,?,?,?,?,?,NULL)',
                           (tenant,state.message_id,token,reviewer,snapshot,reviewed_at,expires_at))
        except sqlite3.IntegrityError as exc:
            raise PreflightRefused('message already has an immutable review') from exc
        return token

    def claim(self, tenant: str, token: str,
              inspect: Callable[[str, str], SendState]) -> SendState:
        """Compare trusted current state and consume atomically; no send occurs.

        inspect receives tenant and message ID and must read current account,
        contact and content. It must never return a cache of this snapshot. An
        external source can still change after inspection; this claim is not a
        source lock or distributed CAS. Send only returned immutable values,
        with independently pinned transport authorization at dispatch.
        """
        _required(tenant, 'tenant'); _required(token, 'token')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM send_reviews WHERE tenant=? AND token=?',
                             (tenant,token)).fetchone()
            if row is None:
                raise PreflightRefused('review not found for tenant')
            if row['claimed_at'] is not None:
                raise PreflightRefused('claim already consumed; reconcile, do not retry')
            if _utc(self.clock()) < row['reviewed_at']:
                raise PreflightRefused('clock precedes review')
            current = inspect(tenant, row['message_id'])
            if not isinstance(current, SendState):
                raise PreflightRefused('inspector did not return SendState')
            expected = SendState(**json.loads(row['snapshot']))
            changed = [k for k,v in asdict(expected).items() if getattr(current,k) != v]
            if changed:
                raise PreflightRefused('review drift: ' + ','.join(changed))
            claimed_at = _utc(self.clock())
            if claimed_at >= row['expires_at']:
                raise PreflightRefused('review expired')
            if claimed_at < row['reviewed_at']:
                raise PreflightRefused('clock precedes review')
            updated = db.execute('''UPDATE send_reviews SET claimed_at=?
                WHERE tenant=? AND token=? AND claimed_at IS NULL''',
                (claimed_at,tenant,token)).rowcount
            if updated != 1:
                raise PreflightRefused('claim conflict')
            return expected

    def read_review(self, tenant: str, token: str) -> dict:
        _required(tenant, 'tenant'); _required(token, 'token')
        with self._db() as db:
            row = db.execute('SELECT * FROM send_reviews WHERE tenant=? AND token=?',
                             (tenant,token)).fetchone()
        if row is None:
            raise PreflightRefused('review not found for tenant')
        result = dict(row)
        result['snapshot'] = asdict(SendState(**json.loads(result['snapshot'])))
        return result
