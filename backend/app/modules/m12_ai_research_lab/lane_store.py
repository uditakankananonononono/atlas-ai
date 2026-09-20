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
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .lane_models import canonical_json

_SCHEMA = """
CREATE TABLE IF NOT EXISTS spend (
    entry_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    amount_micro INTEGER NOT NULL CHECK (amount_micro >= 0),
    ts_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spend_ts ON spend(ts_utc);

CREATE TABLE IF NOT EXISTS step_state (
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    output_json TEXT NOT NULL,
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
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

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

    def clear_run(self, run_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM step_state WHERE run_id = ?", (run_id,))
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
