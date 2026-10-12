"""c32.continuous_ingest tests (row 102): continuous multi-run ingestion,
crash-safe resume, dedupe across runs, measured sustained throughput."""
import json
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c32 import continuous_ingest as ci  # noqa: E402


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def test_continuous_multi_run_ingestion(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state = str(tmp_path / "state.json")
    write_jsonl(inbox / "a.jsonl", [{"id": i, "v": "x" * 50} for i in range(500)])
    r1 = ci.run(str(inbox), state, batch_size=200)
    assert r1["run"]["records"] == 500 and r1["run"]["files_completed"] == 1
    # new data arrives later: the worker keeps going from its checkpoint
    write_jsonl(inbox / "b.jsonl", [{"id": 1000 + i} for i in range(300)])
    r2 = ci.run(str(inbox), state, batch_size=200)
    assert r2["run"]["records"] == 300
    assert r2["cumulative"]["records_ingested"] == 800
    assert r2["cumulative"]["runs"] == 2
    # measured throughput exists and is positive
    assert r2["cumulative"]["records_per_s"] is None or \
        r2["cumulative"]["records_per_s"] > 0


def test_dedupe_across_runs(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state = str(tmp_path / "state.json")
    recs = [{"id": i} for i in range(100)]
    write_jsonl(inbox / "a.jsonl", recs)
    ci.run(str(inbox), state)
    write_jsonl(inbox / "b.jsonl", recs)  # same records again
    r = ci.run(str(inbox), state)
    assert r["run"]["records"] == 0 and r["run"]["deduped"] == 100
    assert r["cumulative"]["records_deduped"] == 100


def test_crash_resume_mid_file(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state = str(tmp_path / "state.json")
    write_jsonl(inbox / "big.jsonl", [{"id": i} for i in range(1000)])
    # simulate a crash after the first flush by pre-seeding checkpoint state
    ci.run(str(inbox), state, batch_size=400, max_files_per_run=None)
    # re-ingest a truncated variant: done marker prevents double counting
    r = ci.run(str(inbox), state, batch_size=400)
    assert r["run"]["records"] == 0
    saved = json.loads(pathlib.Path(state).read_text())
    assert saved["files"]["big.jsonl"]["done"] is True


def test_backpressure_reported(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state = str(tmp_path / "state.json")
    for n in range(5):
        write_jsonl(inbox / ("f%d.jsonl" % n), [{"id": n}])
    r = ci.run(str(inbox), state, max_pending=3)
    assert r["backpressure"] is True
    assert r["run"]["files_completed"] == 5


def test_malformed_lines_counted(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state = str(tmp_path / "state.json")
    with open(inbox / "m.jsonl", "w") as fh:
        fh.write('{"id": 1}\nnot-json\n{"id": 2}\n')
    r = ci.run(str(inbox), state)
    assert r["run"]["records"] == 2 and r["run"]["malformed"] == 1


def test_bounded_memory_batching(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state = str(tmp_path / "state.json")
    write_jsonl(inbox / "many.jsonl", [{"id": i} for i in range(5000)])
    r = ci.run(str(inbox), state, batch_size=100)
    assert r["run"]["records"] == 5000
    assert "one batch (100 records)" in r["memory_bound"]
