"""SQLite-backed ingest store: item dedupe and resumable job checkpoints.

One row per (source, external_id); re-seen items update seen metadata in
place. Every batch commit also upserts the job checkpoint in the same
transaction, so an interrupted job always resumes from its last committed
batch cursor.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_items (
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (source, external_id)
);
CREATE TABLE IF NOT EXISTS ingest_checkpoints (
    job_key TEXT PRIMARY KEY,
    cursor TEXT,
    batches_committed INTEGER NOT NULL DEFAULT 0,
    items_new INTEGER NOT NULL DEFAULT 0,
    items_duplicate INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


def content_hash(payload: dict) -> str:
    """Stable digest of a payload, matching the repo's canonical-JSON convention."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class IngestStore:
    def __init__(self, path: str) -> None:
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def commit_batch(self, job_key, source, items, cursor, *, now=None):
        """Insert new items, touch duplicates, and advance the job checkpoint atomically."""
        if not isinstance(job_key, str) or not job_key.strip():
            raise ValueError("job_key requires nonempty string")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source requires nonempty string")
        stamp = now or datetime.now(timezone.utc).isoformat()
        new = duplicate = 0
        seen_in_batch = set()
        with self._db:
            for entry in items:
                external_id = getattr(entry, "external_id", None)
                if not external_id:
                    raise ValueError("ingest item requires external_id")
                if external_id in seen_in_batch:
                    duplicate += 1
                    continue
                seen_in_batch.add(external_id)
                digest = content_hash(entry.payload)
                row = self._db.execute(
                    "SELECT 1 FROM ingest_items WHERE source = ? AND external_id = ?",
                    (source, external_id),
                ).fetchone()
                if row is None:
                    self._db.execute(
                        "INSERT INTO ingest_items (source, external_id, canonical_url, content_hash, payload_json, first_seen_at, last_seen_at, seen_count)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                        (source, external_id, entry.canonical_url, digest, json.dumps(entry.payload, sort_keys=True, default=str), stamp, stamp),
                    )
                    new += 1
                else:
                    self._db.execute(
                        "UPDATE ingest_items SET last_seen_at = ?, seen_count = seen_count + 1, content_hash = ?, payload_json = ?"
                        " WHERE source = ? AND external_id = ?",
                        (stamp, digest, json.dumps(entry.payload, sort_keys=True, default=str), source, external_id),
                    )
                    duplicate += 1
            self._db.execute(
                "INSERT INTO ingest_checkpoints (job_key, cursor, batches_committed, items_new, items_duplicate, updated_at)"
                " VALUES (?, ?, 1, ?, ?, ?)"
                " ON CONFLICT(job_key) DO UPDATE SET"
                " cursor = excluded.cursor,"
                " batches_committed = batches_committed + 1,"
                " items_new = items_new + excluded.items_new,"
                " items_duplicate = items_duplicate + excluded.items_duplicate,"
                " updated_at = excluded.updated_at",
                (job_key, cursor, new, duplicate, stamp),
            )
        return new, duplicate

    def load_checkpoint(self, job_key):
        row = self._db.execute(
            "SELECT cursor, batches_committed, items_new, items_duplicate, updated_at FROM ingest_checkpoints WHERE job_key = ?",
            (job_key,),
        ).fetchone()
        if row is None:
            return None
        return {"cursor": row[0], "batches_committed": row[1], "items_new": row[2], "items_duplicate": row[3], "updated_at": row[4]}

    def get_item(self, source, external_id):
        row = self._db.execute(
            "SELECT canonical_url, content_hash, payload_json, first_seen_at, last_seen_at, seen_count"
            " FROM ingest_items WHERE source = ? AND external_id = ?",
            (source, external_id),
        ).fetchone()
        if row is None:
            return None
        return {"canonical_url": row[0], "content_hash": row[1], "payload": json.loads(row[2]),
                "first_seen_at": row[3], "last_seen_at": row[4], "seen_count": row[5]}

    def count_items(self, source=None):
        if source is None:
            return self._db.execute("SELECT COUNT(*) FROM ingest_items").fetchone()[0]
        return self._db.execute("SELECT COUNT(*) FROM ingest_items WHERE source = ?", (source,)).fetchone()[0]

    def close(self):
        self._db.close()
