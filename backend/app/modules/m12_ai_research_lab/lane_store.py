"""SQLite persistence for the M12 AI Research Lab.

One store implements both seams used elsewhere in the module:
- SpendStore (budget ledger entries)
- StepStateStore (workflow checkpoints)
plus manifest and eval-report persistence.

WAL mode for file-backed databases, a single writer lock, and plain SQL -
no ORM. Dataclasses serialize through canonical JSON so stored payloads are
stable and diffable. Thread-safe for the module's concurrency model
(many lanes, one process).
"""

from __future__ import annotations

import json
import sqlite3
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .lane_models import canonical_json

_SCHEMA = """
CREATE TABLE IF NOT EXISTS spend (
    entry_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    amount_micro INTEGER NOT NULL CHECK (amount_micro >= 0),
    ts_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spend_ts ON spend(ts_utc);

CREATE TABLE IF NOT EXISTS budget_hold (
    run_id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    amount_micro INTEGER NOT NULL CHECK (amount_micro >= 0)
);

CREATE TABLE IF NOT EXISTS step_state (
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    output_json TEXT NOT NULL,
    saved_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, step_id)
);

CREATE TABLE IF NOT EXISTS step_claim (
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'unknown')),
    token TEXT NOT NULL,
    gen TEXT NOT NULL,
    detail TEXT NOT NULL,
    saved_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, step_id)
);

CREATE TABLE IF NOT EXISTS manifests (
    run_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_reports (
    eval_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    created_utc TEXT NOT NULL
);
"""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteLabStore:
    """Implements SpendStore + StepStateStore + manifest/eval persistence."""

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if path != ":memory:":
                # Concurrent first-open of one file can hit "database is locked" on the
                # journal-mode switch (busy timeout is not applied to it): bounded retry,
                # then fail closed.
                for attempt in range(40):
                    try:
                        self._conn.execute("PRAGMA journal_mode=WAL")
                        break
                    except sqlite3.OperationalError as exc:
                        if "locked" not in str(exc) or attempt == 39:
                            raise
                        time.sleep(0.05)
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
            self._migrate_step_claim()

    def _migrate_step_claim(self) -> None:
        """Bounded, idempotent, transactional upgrade of an older step_claim table (no
        token and/or no gen column). Existing pending/unknown markers are preserved as
        they are (never wiped, never auto-retried); each gets a fresh owner token that no
        runner holds, plus a fresh generation. Safe to run repeatedly and concurrently:
        the column check is repeated inside BEGIN IMMEDIATE and rolled back on error."""
        def cols():
            return {r["name"] for r in self._conn.execute("PRAGMA table_info(step_claim)").fetchall()}
        if {"token", "gen"} <= cols():
            return
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            have = cols()
            for name in ("token", "gen"):
                if name not in have:
                    self._conn.execute(
                        "ALTER TABLE step_claim ADD COLUMN %s TEXT NOT NULL DEFAULT ''" % name)
            rows = self._conn.execute(
                "SELECT run_id, step_id FROM step_claim WHERE token = '' OR gen = ''").fetchall()
            for r in rows:
                self._conn.execute(
                    "UPDATE step_claim SET token = CASE WHEN token = '' THEN ? ELSE token END, "
                    "gen = CASE WHEN gen = '' THEN ? ELSE gen END WHERE run_id = ? AND step_id = ?",
                    (uuid.uuid4().hex, uuid.uuid4().hex, r["run_id"], r["step_id"]),
                )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- SpendStore seam -------------------------------------------------

    def add_spend(self, entry_id: str, run_id: str, amount_micro: int, ts_utc: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO spend(entry_id, run_id, amount_micro, ts_utc) VALUES (?,?,?,?)",
                (entry_id, run_id, amount_micro, ts_utc),
            )
            self._conn.commit()

    @staticmethod
    def _valid_hold(run_id, amount_micro) -> None:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a non-empty string")
        if type(amount_micro) is not int or amount_micro < 0:
            raise ValueError("amount_micro must be a nonnegative integer")

    def reserve_hold(self, run_id: str, amount_micro: int, check, owner: str) -> None:
        """Run `check` (limit test reading spend and holds) and insert the hold in
        one BEGIN IMMEDIATE transaction: the write lock is taken before the check,
        so concurrent processes serialize. `check` raising aborts with no hold."""
        self._valid_hold(run_id, amount_micro)
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                check()
                self._conn.execute(
                    "INSERT INTO budget_hold(run_id, owner, amount_micro) VALUES (?,?,?)",
                    (run_id, owner, amount_micro))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def put_hold(self, run_id: str, amount_micro: int, owner: str = "") -> None:
        self._valid_hold(run_id, amount_micro)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO budget_hold(run_id, owner, amount_micro) VALUES (?,?,?)",
                (run_id, owner, amount_micro))
            self._conn.commit()

    def drop_hold(self, run_id: str, owner: Optional[str] = None) -> None:
        """owner=None is a forced drop (authorized reconciliation only)."""
        with self._lock:
            if owner is None:
                self._conn.execute("DELETE FROM budget_hold WHERE run_id = ?", (run_id,))
            else:
                self._conn.execute(
                    "DELETE FROM budget_hold WHERE run_id = ? AND owner = ?", (run_id, owner))
            self._conn.commit()

    def list_holds(self) -> Dict[str, int]:
        with self._lock:
            return {r["run_id"]: int(r["amount_micro"]) for r in
                    self._conn.execute("SELECT run_id, amount_micro FROM budget_hold")}

    def book_and_drop_hold(self, entry_id: str, run_id: str, amount_micro: int,
                           ts_utc: str, owner: str) -> None:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO spend(entry_id, run_id, amount_micro, ts_utc) VALUES (?,?,?,?)",
                    (entry_id, run_id, amount_micro, ts_utc))
                self._conn.execute(
                    "DELETE FROM budget_hold WHERE run_id = ? AND owner = ?", (run_id, owner))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def spend_between(self, start_utc: str, end_utc: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(amount_micro), 0) AS total FROM spend "
                "WHERE ts_utc >= ? AND ts_utc < ?",
                (start_utc, end_utc),
            ).fetchone()
            return int(row["total"])

    def spend_by_run(self, run_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(amount_micro), 0) AS total FROM spend WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            return int(row["total"])

    # ---- StepStateStore seam ---------------------------------------------

    def load_completed(self, run_id: str) -> Dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT step_id, output_json FROM step_state WHERE run_id = ? ORDER BY step_id",
                (run_id,),
            ).fetchall()
            return {r["step_id"]: json.loads(r["output_json"]) for r in rows}

    def save_completed(self, run_id: str, step_id: str, output: Any) -> None:
        payload = canonical_json(output)
        with self._lock:
            self._conn.execute(
                "INSERT INTO step_state(run_id, step_id, output_json, saved_utc) "
                "VALUES (?,?,?,?) "
                "ON CONFLICT(run_id, step_id) DO UPDATE SET output_json=excluded.output_json, "
                "saved_utc=excluded.saved_utc",
                (run_id, step_id, payload, _utcnow_iso()),
            )
            self._conn.commit()

    def claim_step(self, run_id: str, step_id: str) -> Optional[str]:
        """Atomic across engines sharing the database file: the primary key decides.
        Returns the owner token, or None when a claim already exists."""
        token = uuid.uuid4().hex
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO step_claim(run_id, step_id, state, token, gen, detail, saved_utc) "
                "VALUES (?,?,'pending',?,?,'',?)",
                (run_id, step_id, token, uuid.uuid4().hex, _utcnow_iso()),
            )
            self._conn.commit()
            return token if cur.rowcount == 1 else None

    def _tx(self):
        """BEGIN IMMEDIATE so check-and-change is atomic across connections."""
        self._conn.execute("BEGIN IMMEDIATE")

    def complete_step(self, run_id: str, step_id: str, token: str, output: Any) -> bool:
        payload = canonical_json(output)
        with self._lock:
            self._tx()
            try:
                cur = self._conn.execute(
                    "DELETE FROM step_claim WHERE run_id = ? AND step_id = ? AND token = ?",
                    (run_id, step_id, token),
                )
                if cur.rowcount != 1:
                    self._conn.rollback()
                    return False
                self._conn.execute(
                    "INSERT INTO step_state(run_id, step_id, output_json, saved_utc) VALUES (?,?,?,?) "
                    "ON CONFLICT(run_id, step_id) DO UPDATE SET output_json=excluded.output_json, "
                    "saved_utc=excluded.saved_utc",
                    (run_id, step_id, payload, _utcnow_iso()),
                )
                self._conn.commit()
                return True
            except BaseException:
                self._conn.rollback()
                raise

    def mark_unknown(self, run_id: str, step_id: str, token: str, detail: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE step_claim SET state='unknown', gen=?, detail=?, saved_utc=? "
                "WHERE run_id = ? AND step_id = ? AND token = ?",
                (uuid.uuid4().hex, str(detail), _utcnow_iso(), run_id, step_id, token),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def release_claim(self, run_id: str, step_id: str, token: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM step_claim WHERE run_id = ? AND step_id = ? AND token = ?",
                (run_id, step_id, token),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def load_claims(self, run_id: str) -> Dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT step_id, state, detail FROM step_claim WHERE run_id = ? ORDER BY step_id",
                (run_id,),
            ).fetchall()
            return {r["step_id"]: (r["state"], r["detail"]) for r in rows}

    def inspect_claim(self, run_id: str, step_id: str) -> Optional[Tuple[str, str, str]]:
        """(state, detail, generation) or None. The generation is opaque and changes on
        every claim state change; the owner token is never exposed."""
        with self._lock:
            r = self._conn.execute(
                "SELECT state, detail, gen FROM step_claim WHERE run_id = ? AND step_id = ?",
                (run_id, step_id)).fetchone()
            return None if r is None else (r["state"], r["detail"], r["gen"])

    def resolve_claim_completed(self, run_id: str, step_id: str, expected_state: str,
                                expected_gen: str, output: Any) -> bool:
        payload = canonical_json(output)
        with self._lock:
            self._tx()
            try:
                cur = self._conn.execute(
                    "DELETE FROM step_claim WHERE run_id = ? AND step_id = ? AND state = ? AND gen = ?",
                    (run_id, step_id, expected_state, expected_gen),
                )
                if cur.rowcount != 1:
                    self._conn.rollback()
                    return False
                self._conn.execute(
                    "INSERT INTO step_state(run_id, step_id, output_json, saved_utc) VALUES (?,?,?,?) "
                    "ON CONFLICT(run_id, step_id) DO UPDATE SET output_json=excluded.output_json, "
                    "saved_utc=excluded.saved_utc",
                    (run_id, step_id, payload, _utcnow_iso()),
                )
                self._conn.commit()
                return True
            except BaseException:
                self._conn.rollback()
                raise

    def clear_claim_for_retry(self, run_id: str, step_id: str, expected_state: str,
                              expected_gen: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM step_claim WHERE run_id = ? AND step_id = ? AND state = ? AND gen = ?",
                (run_id, step_id, expected_state, expected_gen),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def takeover_pending(self, run_id: str, step_id: str, expected_gen: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE step_claim SET state='unknown', token=?, gen=?, "
                "detail='pending claim taken over; earlier owner revoked', saved_utc=? "
                "WHERE run_id = ? AND step_id = ? AND state = 'pending' AND gen = ?",
                (uuid.uuid4().hex, uuid.uuid4().hex, _utcnow_iso(), run_id, step_id, expected_gen),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def clear_run(self, run_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM step_state WHERE run_id = ?", (run_id,))
            self._conn.execute("DELETE FROM step_claim WHERE run_id = ?", (run_id,))
            self._conn.commit()

    # ---- Manifest persistence ---------------------------------------------

    def save_manifest(self, run_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO manifests(run_id, payload_json, updated_utc) VALUES (?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET payload_json=excluded.payload_json, "
                "updated_utc=excluded.updated_utc",
                (run_id, canonical_json(payload), _utcnow_iso()),
            )
            self._conn.commit()

    def load_manifest(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM manifests WHERE run_id = ?", (run_id,)
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def list_manifests(self, limit: int = 100) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT run_id FROM manifests ORDER BY updated_utc DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [r["run_id"] for r in rows]

    # ---- Eval report persistence ------------------------------------------

    def save_eval_report(self, eval_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO eval_reports(eval_id, payload_json, created_utc) VALUES (?,?,?) "
                "ON CONFLICT(eval_id) DO UPDATE SET payload_json=excluded.payload_json, "
                "created_utc=excluded.created_utc",
                (eval_id, canonical_json(payload), _utcnow_iso()),
            )
            self._conn.commit()

    def load_eval_report(self, eval_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM eval_reports WHERE eval_id = ?", (eval_id,)
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None
