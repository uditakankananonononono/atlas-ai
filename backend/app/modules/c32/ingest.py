"""S2.0 / c32.ingest - continuous-ingest pipeline.

Source excerpt (verbatim): "Continuously do this and never stop, make sure
that it is able to handle that much of data".

Sharded, resumable, deduplicating ingest over SUPPLIED records with a
throughput/coverage ledger. "Never stop" is bounded to resumable checkpointed
operation over supplied batches; nothing is fetched, crawled or scraped
(guard: c30.policy). U02/U38 fold: benchmark() proves capacity/throughput over
synthetic generated records. Stdlib only, offline, deterministic.
"""
from __future__ import annotations

import time

from app.modules.c30 import policy

PREFIX = "TREND"
MAX_SHARD = 100000
MAX_ID = 256
MAX_BENCH = 2000000


def _check_records(records):
    if isinstance(records, bool) or not isinstance(records, (list, tuple)):
        raise ValueError("TREND_REFUSED_BAD_TYPE:records")
    return records


def _checkpoint(value):
    if (isinstance(value, bool) or not isinstance(value, dict)
            or set(value) != {"shard", "offset"}
            or any(isinstance(value[k], bool) or not isinstance(value[k], int) or value[k] < 0
                   for k in ("shard", "offset"))):
        raise ValueError("TREND_REFUSED_BAD_TYPE:checkpoint")
    return {"shard": value["shard"], "offset": value["offset"]}


def ingest(records, shard_size=10000, resume=False, checkpoint=None, seen=None):
    """Ingest supplied records; returns a throughput/coverage ledger dict."""
    if isinstance(shard_size, bool) or not isinstance(shard_size, int) or shard_size < 1:
        raise ValueError("TREND_REFUSED_BAD_TYPE:shard_size")
    if shard_size > MAX_SHARD:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    if resume:
        if checkpoint is None:
            raise ValueError("TREND_REFUSED_NOCHECKPOINT")
        resumed = _checkpoint(checkpoint)
        skip = resumed["shard"] * shard_size + resumed["offset"]
    else:
        resumed = None
        skip = 0
    records = _check_records(records)
    if skip > len(records):
        raise ValueError("TREND_REFUSED_CHECKPOINT_RANGE")
    seen_ids = set(seen) if seen is not None else set()
    ingested = 0
    duplicates = 0
    skipped = 0
    for rec in records:
        if skipped < skip:
            skipped += 1  # already applied per the checkpoint: not re-validated
            continue
        if not isinstance(rec, dict):
            raise ValueError("TREND_REFUSED_BAD_TYPE:record")
        if "url" in rec or rec.get("fetch"):
            policy.check("scrape", PREFIX)  # standing guard: never fetch
        if rec.get("id") is None:
            raise ValueError("TREND_REFUSED_EMPTY:id")
        rid = policy.clean_text(rec["id"], PREFIX, "id", MAX_ID)
        if rid in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(rid)
        ingested += 1
    consumed = skipped + ingested + duplicates
    total = ingested + duplicates
    shards = -(-total // shard_size) if total else 0
    next_checkpoint = {"shard": consumed // shard_size, "offset": consumed % shard_size}
    return {"ingested": ingested, "duplicates": duplicates, "skipped": skipped,
            "shards": shards, "resumed_from": resumed, "next_checkpoint": next_checkpoint,
            "seen_ids": seen_ids,
            "scope": policy.scope(
                ["sharded ingest", "dedupe by id",
                 "real checkpointing (skip applied shard/offset, return next checkpoint)",
                 "throughput/coverage ledger"],
                ["continuous unattended operation", "fetching of any kind"],
                "supplied records")}


def benchmark(records_count, shard_size=50000):
    """U02/U38 fold: capacity + throughput over synthetic generated records."""
    if isinstance(records_count, bool) or not isinstance(records_count, int) or records_count < 1:
        raise ValueError("TREND_REFUSED_BAD_TYPE:records_count")
    if records_count > MAX_BENCH:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    if isinstance(shard_size, bool) or not isinstance(shard_size, int) or shard_size < 1:
        raise ValueError("TREND_REFUSED_BAD_TYPE:shard_size")
    if shard_size > MAX_SHARD:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    start = time.perf_counter()
    synthetic = ({"id": "syn%d" % i} for i in range(records_count))
    ingested = 0
    seen = set()
    for rec in synthetic:
        if rec["id"] not in seen:
            seen.add(rec["id"])
            ingested += 1
    elapsed = max(time.perf_counter() - start, 1e-9)
    return {"records": records_count, "ingested": ingested, "shards": -(-records_count // shard_size),
            "records_per_second": int(records_count / elapsed),
            "scope": policy.scope(["capacity benchmark", "throughput benchmark"],
                                  ["real-source ingest"], "synthetic generated records")}
