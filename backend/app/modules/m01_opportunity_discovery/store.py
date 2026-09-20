"""SQLite persistence for normalized opportunities and monitor snapshots.

Uses only the standard library and transactionally replaces a named snapshot.
Callers can persist per-user/per-monitor snapshots without sharing in-memory state.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Iterable, Iterator

from .models import Opportunity, OpportunityKind, Provenance
from .lane_service import OpportunityChange, _fingerprint


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def _dump(item: Opportunity) -> str:
    return json.dumps(asdict(item), default=_json_default, sort_keys=True, separators=(",", ":"))


def _load(raw: str) -> Opportunity:
    value = json.loads(raw)
    provenance = tuple(Provenance(
        p["source"], p["source_id"], p["source_url"], datetime.fromisoformat(p["fetched_at"]), p["raw_sha256"], p.get("adapter_version", "1")
    ) for p in value.pop("provenance"))
    for key in ("open_date", "close_date"):
        value[key] = date.fromisoformat(value[key]) if value.get(key) else None
    value["updated_at"] = datetime.fromisoformat(value["updated_at"]) if value.get("updated_at") else None
    value["kind"] = OpportunityKind(value["kind"])
    for key in ("countries", "eligibility", "tags"):
        value[key] = tuple(value[key])
    return Opportunity(provenance=provenance, **value)


class SqliteOpportunityStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS opportunity_snapshots (
                monitor_key TEXT NOT NULL,
                opportunity_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                PRIMARY KEY (monitor_key, opportunity_id)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_opportunity_snapshots_observed ON opportunity_snapshots(observed_at)")

    def load(self, monitor_key: str) -> tuple[Opportunity, ...]:
        if not monitor_key:
            raise ValueError("monitor_key is required")
        with self._lock, self._connection() as db:
            rows = db.execute("SELECT payload FROM opportunity_snapshots WHERE monitor_key=? ORDER BY opportunity_id", (monitor_key,)).fetchall()
        return tuple(_load(row[0]) for row in rows)

    def replace_and_diff(self, monitor_key: str, items: Iterable[Opportunity], *, observed_at: datetime | None = None) -> tuple[OpportunityChange, ...]:
        if not monitor_key:
            raise ValueError("monitor_key is required")
        observed_at = observed_at or datetime.now().astimezone()
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        incoming = {item.id: item for item in items}
        with self._lock, self._connection() as db:
            rows = db.execute("SELECT opportunity_id, payload, fingerprint FROM opportunity_snapshots WHERE monitor_key=?", (monitor_key,)).fetchall()
            previous = {row[0]: (_load(row[1]), row[2]) for row in rows}
            changes: list[OpportunityChange] = []
            for key, item in incoming.items():
                fingerprint = json.dumps(_fingerprint(item), default=_json_default, separators=(",", ":"))
                old = previous.get(key)
                if old is None:
                    changes.append(OpportunityChange("new", key, None, item))
                elif old[1] != fingerprint:
                    changes.append(OpportunityChange("updated", key, old[0], item))
                db.execute("""INSERT INTO opportunity_snapshots(monitor_key, opportunity_id, payload, fingerprint, observed_at)
                    VALUES(?,?,?,?,?) ON CONFLICT(monitor_key, opportunity_id) DO UPDATE SET
                    payload=excluded.payload, fingerprint=excluded.fingerprint, observed_at=excluded.observed_at""",
                    (monitor_key, key, _dump(item), fingerprint, observed_at.isoformat()))
            removed = set(previous) - set(incoming)
            for key in removed:
                changes.append(OpportunityChange("removed", key, previous[key][0], None))
            if removed:
                db.executemany("DELETE FROM opportunity_snapshots WHERE monitor_key=? AND opportunity_id=?", [(monitor_key, key) for key in removed])
        return tuple(sorted(changes, key=lambda x: (x.kind, x.opportunity_id)))

    def delete_monitor(self, monitor_key: str) -> int:
        with self._lock, self._connection() as db:
            cursor = db.execute("DELETE FROM opportunity_snapshots WHERE monitor_key=?", (monitor_key,))
            return cursor.rowcount
