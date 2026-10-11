"""Resumable batch ingestion over any Collector-protocol source.

The job follows a source's batch cursors and commits each batch plus the
cursor checkpoint in one store transaction. A run interrupted by a source
failure or a batch limit resumes from the last committed cursor; a run that
reaches the end of a source completes, and the next run starts a fresh pass.
"""
from __future__ import annotations

import inspect
from typing import Any

from .store import IngestStore


class ResumableIngestJob:
    def __init__(self, store: IngestStore) -> None:
        if not isinstance(store, IngestStore):
            raise TypeError("store must be an IngestStore")
        self._store = store

    async def run(self, *, job_key, source_name, collector, config, max_batches=100) -> dict[str, Any]:
        if not isinstance(job_key, str) or not job_key.strip():
            raise ValueError("job_key requires nonempty string")
        if not isinstance(source_name, str) or not source_name.strip():
            raise ValueError("source_name requires nonempty string")
        if type(max_batches) is not int or max_batches < 1:
            raise ValueError("max_batches requires positive integer")
        collect = getattr(collector, "collect", None)
        if not callable(collect):
            raise ValueError("collector requires a collect method")
        base_config = dict(config or {})
        checkpoint = self._store.load_checkpoint(job_key)
        resumed = checkpoint["cursor"] if checkpoint else None
        cursor = resumed if resumed is not None else base_config.get("cursor")
        used_cursors = {cursor}
        batches = new_total = duplicate_total = requests_total = 0
        try:
            while True:
                batch = await collect({**base_config, "cursor": cursor})
                new, duplicate = self._store.commit_batch(job_key, source_name, batch.items, batch.cursor)
                batches += 1
                new_total += new
                duplicate_total += duplicate
                requests_total += batch.requests
                if batch.cursor is None:
                    status = "completed"
                    cursor = None
                    break
                if batch.cursor in used_cursors:
                    raise RuntimeError(f"source cursor made no progress: {batch.cursor!r}")
                used_cursors.add(batch.cursor)
                cursor = batch.cursor
                if batches >= max_batches:
                    status = "batch_limit"
                    break
        finally:
            close = getattr(collector, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result
        return {"job_key": job_key, "source": source_name, "status": status,
                "resumed_from_cursor": resumed, "final_cursor": cursor,
                "batches_committed": batches, "items_new": new_total,
                "items_duplicate": duplicate_total, "requests": requests_total}
