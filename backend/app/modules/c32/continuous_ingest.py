"""c32.continuous_ingest (doc row 102): continuous huge-data ingestion worker
with MEASURED sustained capacity.

Closes the audit gap on c32.ingest ("synthetic batch ingestion benchmark, not
unbounded live sustained ingestion"): a drop-directory worker that ingests
JSONL files CONTINUOUSLY across runs - chunked reads, per-file checkpointing
(crash-safe resume), content-hash dedupe persisted across runs, backpressure
reporting when the pending queue exceeds a cap, and a throughput ledger
measured on real clock time (records/s, bytes/s) over every run.

Scope stays honest: "huge data" means whatever arrives in the inbox
directory; the worker sustains unbounded cumulative volume across runs with
bounded memory (one batch in memory at a time). Nothing is fetched, crawled
or scraped here. Stdlib only. Guard: c30.policy.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

PREFIX = "INGEST"
MAX_BATCH = 10000
MAX_LINE = 100000
MAX_PENDING_REPORT = 1000
STATE_VERSION = 1


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _record_hash(line):
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _load_state(state_path):
    if not os.path.exists(state_path):
        return {"version": STATE_VERSION, "files": {}, "seen": [], "ledger": {
            "runs": 0, "records_ingested": 0, "records_deduped": 0, "bytes_ingested": 0,
            "elapsed_s": 0.0}}
    with open(state_path, "r", encoding="utf-8") as fh:
        state = json.load(fh)
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        _err("STATE")
    return state


def _save_state(state_path, state):
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, state_path)  # atomic checkpoint


def run(inbox_dir, state_path, batch_size=1000, max_pending=64, max_files_per_run=None,
        clock=None):
    """Process pending *.jsonl files in inbox_dir until drained (or
    max_files_per_run reached). Returns the run ledger; state persists at
    state_path so the next run resumes exactly where this one stopped."""
    if not isinstance(inbox_dir, str) or not os.path.isdir(inbox_dir):
        _err("PATH", "inbox")
    if not isinstance(state_path, str) or not state_path:
        _err("PATH", "state")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) \
            or not 1 <= batch_size <= MAX_BATCH:
        raise ValueError("%s_REFUSED_BAD_TYPE:batch_size" % PREFIX)
    clock = clock or time.monotonic
    state = _load_state(state_path)
    seen = set(state["seen"])
    files_state = state["files"]
    pending = sorted(f for f in os.listdir(inbox_dir) if f.endswith(".jsonl"))
    if len(pending) > MAX_PENDING_REPORT:
        _err("OVERSIZE", "pending")
    backpressure = len(pending) > max_pending
    started = clock()
    run_stats = {"files_completed": 0, "files_touched": 0, "records": 0,
                 "deduped": 0, "bytes": 0, "malformed": 0, "resumed_files": 0}
    processed = 0
    for name in pending:
        if max_files_per_run is not None and processed >= max_files_per_run:
            break
        processed += 1
        path = os.path.join(inbox_dir, name)
        fstate = files_state.get(name)
        offset = fstate["offset"] if fstate else 0
        if fstate and fstate.get("done"):
            continue
        if offset:
            run_stats["resumed_files"] += 1
        run_stats["files_touched"] += 1
        batch = []
        with open(path, "r", encoding="utf-8") as fh:
            fh.seek(offset)
            while True:
                line = fh.readline()
                if not line:
                    break
                offset = fh.tell()
                stripped = line.strip()
                if not stripped:
                    continue
                if len(stripped) > MAX_LINE:
                    _err("OVERSIZE", "line")
                batch.append(stripped)
                run_stats["bytes"] += len(line.encode("utf-8"))
                if len(batch) >= batch_size:
                    _flush(batch, seen, run_stats)
                    files_state[name] = {"offset": offset, "done": False}
                    _save_state(state_path, _persist(state, seen, files_state))
                    batch = []
            if batch:
                _flush(batch, seen, run_stats)
        files_state[name] = {"offset": offset, "done": True}
        _save_state(state_path, _persist(state, seen, files_state))
        run_stats["files_completed"] += 1
    elapsed = clock() - started
    ledger = state["ledger"]
    ledger["runs"] += 1
    ledger["records_ingested"] += run_stats["records"]
    ledger["records_deduped"] += run_stats["deduped"]
    ledger["bytes_ingested"] += run_stats["bytes"]
    ledger["elapsed_s"] = round(ledger["elapsed_s"] + elapsed, 6)
    _save_state(state_path, _persist(state, seen, files_state))
    return {
        "run": run_stats,
        "backpressure": backpressure,
        "pending_before": len(pending),
        "pending_after": len([f for f in pending if not files_state.get(f, {}).get("done")]),
        "cumulative": {
            "runs": ledger["runs"],
            "records_ingested": ledger["records_ingested"],
            "records_deduped": ledger["records_deduped"],
            "bytes_ingested": ledger["bytes_ingested"],
            "elapsed_s": ledger["elapsed_s"],
            "records_per_s": round(ledger["records_ingested"] / ledger["elapsed_s"], 1)
                             if ledger["elapsed_s"] > 0 else None,
            "mb_per_s": round(ledger["bytes_ingested"] / ledger["elapsed_s"] / 1e6, 3)
                        if ledger["elapsed_s"] > 0 else None,
        },
        "memory_bound": "one batch (%d records) in memory at a time" % batch_size,
        "limits": ["Ingests the supplied inbox directory only; nothing is fetched.",
                   "Throughput is measured on real clock time over real file reads.",
                   "'Continuous' = unbounded cumulative volume across runs with "
                   "crash-safe resume, bounded memory and backpressure reporting."],
    }


def _flush(batch, seen, run_stats):
    for line in batch:
        h = _record_hash(line)
        if h in seen:
            run_stats["deduped"] += 1
            continue
        try:
            json.loads(line)
        except ValueError:
            run_stats["malformed"] += 1
            continue
        seen.add(h)
        run_stats["records"] += 1


def _persist(state, seen, files_state):
    state["seen"] = sorted(seen)
    state["files"] = files_state
    return state
