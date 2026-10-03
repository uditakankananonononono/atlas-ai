"""Durable at-most-once reservation for irreversible effects.

SQLite commits the reservation before browser work starts. Reservations never
expire or get released: after a crash we cannot know whether a click happened.
Keep this database with the device key across restarts. Losing/restoring an old
ledger loses replay protection; operators must reconcile, not retry uncertain
approvals. This does not claim exactly-once delivery to an external website.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class EffectLedger:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("""CREATE TABLE IF NOT EXISTS submit_effects (
                device_id TEXT NOT NULL, approval_id TEXT NOT NULL,
                command_id TEXT NOT NULL, session TEXT NOT NULL,
                state TEXT NOT NULL, PRIMARY KEY (device_id, approval_id))""")
            self.path.chmod(0o600)
            return connection
        except BaseException:
            connection.close()
            raise

    def reserve(self, device_id: str, approval_id: str, command_id: str, session: str) -> bool:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO submit_effects VALUES (?, ?, ?, ?, 'reserved')",
                               (device_id, approval_id, command_id, session))
            connection.execute("COMMIT")
            return True
        except sqlite3.IntegrityError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            return False
        finally:
            connection.close()

    def click_observed(self, device_id: str, approval_id: str) -> None:
        """Click dispatched and no block seen in the bounded window. Site acceptance stays unconfirmed."""
        connection = self._connect()
        try:
            connection.execute("UPDATE submit_effects SET state='click_observed_unconfirmed' "
                               "WHERE device_id=? AND approval_id=?", (device_id, approval_id))
        finally:
            connection.close()
