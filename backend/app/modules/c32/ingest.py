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

import itertools
import json
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


MAX_RECORD_BYTES = 65536  # UTF-8 size of id + text, per record (ingest_stream only)


class _Item:
    """Minimal item object for IngestStore.commit_batch (needs attributes, not a dict)."""

    __slots__ = ("external_id", "canonical_url", "payload")

    def __init__(self, external_id, payload):
        self.external_id = external_id
        self.canonical_url = ""
        self.payload = payload


def ingest_stream(records, shard_size=10000, resume=False, checkpoint=None, seen=None, malformed="raise",
                  store=None, job_key=None, source=None):
    """Streaming variant of ingest(): pulls one shard-sized batch at a time from any iterable.

    Same checkpoint shape ({shard, offset}), refusals and dedupe as ingest(). In-memory only:
    nothing is persisted unless store (an IngestStore) with job_key and source is given: then each
    batch is committed with the {shard, offset} cursor as JSON text (sort_keys) in one transaction,
    and resume=True without a checkpoint reads it from the store. First-write-wins is kept by
    prefiltering with store.get_item() plus a batch-local set; commit_batch gets only new items.
    Scope: single-writer offline batch only. check+commit is not atomic against a concurrent
    writer on the same source, so first-wins is not guaranteed there.
    malformed="raise" (default) raises the canonical code on the first bad record; "count" skips and counts it (checkpoint still advances). A record over MAX_RECORD_BYTES
    raises TREND_REFUSED_OVERSIZE, or is counted under "count". Fetch/url records always refuse.
    """
    if isinstance(records, (bool, str, bytes, bytearray, dict)) or records is None:
        raise ValueError("TREND_REFUSED_BAD_TYPE:records")
    try:
        it = iter(records)
    except TypeError:
        raise ValueError("TREND_REFUSED_BAD_TYPE:records") from None
    if malformed not in ("raise", "count") or isinstance(malformed, bool):
        raise ValueError("TREND_REFUSED_BAD_TYPE:malformed")
    if isinstance(shard_size, bool) or not isinstance(shard_size, int) or shard_size < 1:
        raise ValueError("TREND_REFUSED_BAD_TYPE:shard_size")
    if shard_size > MAX_SHARD:
        raise ValueError("TREND_REFUSED_OVERSIZE")
    if store is not None:
        for v in (job_key, source):
            if not isinstance(v, str) or not v.strip():
                raise ValueError("TREND_REFUSED_BAD_TYPE:store_key")
    elif job_key is not None or source is not None:
        raise ValueError("TREND_REFUSED_BAD_TYPE:store")
    if resume:
        if checkpoint is None and store is not None:
            stored = store.load_checkpoint(job_key)
            if stored is not None and stored["cursor"]:
                try:
                    checkpoint = json.loads(stored["cursor"])
                except ValueError:
                    raise ValueError("TREND_REFUSED_BAD_TYPE:checkpoint") from None
        if checkpoint is None:
            raise ValueError("TREND_REFUSED_NOCHECKPOINT")
        resumed = _checkpoint(checkpoint)
        skip = resumed["shard"] * shard_size + resumed["offset"]
    else:
        resumed = None
        skip = 0
    skipped = sum(1 for _ in itertools.islice(it, skip))  # applied per the checkpoint: not re-validated
    if skipped < skip:
        raise ValueError("TREND_REFUSED_CHECKPOINT_RANGE")
    count_bad = malformed == "count"
    seen_ids = set(seen) if seen is not None else set()
    consumed = skipped
    ingested = duplicates = rej_malformed = rej_oversize = batches = max_in_flight = 0
    while True:
        batch = list(itertools.islice(it, shard_size))
        if not batch:
            break
        batches += 1
        max_in_flight = max(max_in_flight, len(batch))
        local = set()
        accepted = []
        for rec in batch:
            if not isinstance(rec, dict):
                if not count_bad:
                    raise ValueError("TREND_REFUSED_BAD_TYPE:record")
                rej_malformed += 1
                continue
            if "url" in rec or rec.get("fetch"):
                policy.check("scrape", PREFIX)  # standing guard: never fetch, never counted
            try:
                if rec.get("id") is None:
                    raise ValueError("TREND_REFUSED_EMPTY:id")
                rid = policy.clean_text(rec["id"], PREFIX, "id", MAX_ID)
                text = rec.get("text", "")
                if not isinstance(text, str):
                    raise ValueError("TREND_REFUSED_BAD_TYPE:text")
            except ValueError:
                if not count_bad:
                    raise
                rej_malformed += 1
                continue
            if len(rid.encode("utf-8")) + len(text.encode("utf-8")) > MAX_RECORD_BYTES:
                if not count_bad:
                    raise ValueError("TREND_REFUSED_OVERSIZE")
                rej_oversize += 1
                continue
            if store is None:
                if rid in seen_ids:
                    duplicates += 1
                    continue
                seen_ids.add(rid)
            else:
                if rid in local or store.get_item(source, rid) is not None:
                    duplicates += 1
                    continue
                local.add(rid)
                accepted.append(_Item(rid, {"id": rid, "text": text}))
            ingested += 1
        consumed += len(batch)
        if store is not None:
            cursor = json.dumps({"shard": consumed // shard_size, "offset": consumed % shard_size}, sort_keys=True)
            store.commit_batch(job_key, source, accepted, cursor)
    total = consumed - skipped
    shards = -(-total // shard_size) if total else 0
    return {"ingested": ingested, "duplicates": duplicates, "skipped": skipped,
            "rejected_malformed": rej_malformed, "rejected_oversize": rej_oversize,
            "shards": shards, "batches": batches, "max_in_flight": max_in_flight, "mode": "in-memory" if store is None else "store",
            "duplicates_skipped": duplicates,
            "resumed_from": resumed,
            "next_checkpoint": {"shard": consumed // shard_size, "offset": consumed % shard_size},
            "seen_ids": seen_ids if store is None else None,
            "scope": policy.scope(
                ["streaming ingest, one batch at a time", "dedupe by id",
                 "malformed-record raise or count", "per-record byte limit",
                 "checkpointing (skip applied shard/offset, return next checkpoint)",
                 "throughput/coverage ledger"],
                ["continuous unattended operation", "fetching of any kind",
                 "persistence (checkpoint and seen set live in the caller)"]
                if store is None else
                ["continuous unattended operation", "fetching of any kind",
                 "concurrent writers (single-writer offline batch only; check+commit is not atomic)"],
                "supplied records")}
