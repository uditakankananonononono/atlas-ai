"""UNIT 6 [P270|L215]: resumable ingestion framework.

The RSS source under test is the repo's existing FeedCollector, exercised with
real RSS/Atom bytes through httpx.MockTransport (real httpx machinery, no
network). ScriptedSource is an interface-level test double implementing the
Collector protocol to drive multi-batch cursors; it is not presented as a
feature.
"""
import asyncio
import hashlib
import json

import httpx
import pytest

from app.collectors.base import CollectionBatch, CollectedItem
from app.collectors.research_news import FeedCollector
from app.ingest.pipeline import ResumableIngestJob
from app.ingest.store import IngestStore, content_hash

RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>example</title>
<item><title>Alpha</title><link>https://example.com/a</link><description>first post</description></item>
<item><title>Beta</title><link>https://example.com/b</link><description>second post</description></item>
</channel></rss>'''

ATOM = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Gamma</title><link href="https://example.com/g"/><summary>third post</summary><id>urn:g</id></entry>
</feed>'''


def client_for(body):
    def handler(request):
        return httpx.Response(200, content=body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def item(ext_id, url=None, payload=None):
    return CollectedItem(url or f"https://example.com/{ext_id}", ext_id, payload or {"title": ext_id})


class ScriptedSource:
    """Collector-protocol test double that pages through scripted batches."""

    def __init__(self, pages, fail_on=None):
        self.pages = pages
        self.fail_on = fail_on
        self.calls = 0
        self.received_cursors = []
        self.closed = False
        self.failed_once = False

    async def collect(self, config):
        self.received_cursors.append(config.get("cursor"))
        if self.fail_on is not None and self.calls == self.fail_on and not self.failed_once:
            self.failed_once = True
            raise RuntimeError("source exploded")
        items, cursor = self.pages[self.calls]
        self.calls += 1
        return CollectionBatch(items, requests=1, cursor=cursor)

    async def close(self):
        self.closed = True


def three_pages():
    return [
        ([item("e1"), item("e2")], "c1"),
        ([item("e3"), item("e4")], "c2"),
        ([item("e5"), item("e6")], None),
    ]


def test_feedcollector_parses_real_rss_bytes():
    collector = FeedCollector(client=client_for(RSS))
    batch = asyncio.run(collector.collect({"feeds": ["https://feed.example/rss"]}))
    asyncio.run(collector.close())
    assert batch.requests == 1 and len(batch.items) == 2
    assert batch.items[0].canonical_url == "https://example.com/a"
    assert batch.items[0].external_id == "https://example.com/a"
    assert batch.items[0].payload["title"] == "Alpha"
    assert batch.items[0].payload["summary"] == "first post"
    assert batch.items[1].payload["title"] == "Beta"


def test_feedcollector_parses_real_atom_bytes():
    collector = FeedCollector(client=client_for(ATOM))
    batch = asyncio.run(collector.collect({"feeds": ["https://feed.example/atom"]}))
    asyncio.run(collector.close())
    assert len(batch.items) == 1
    assert batch.items[0].canonical_url == "https://example.com/g"
    assert batch.items[0].payload["title"] == "Gamma"


def test_store_schema_roundtrip_and_content_hash():
    store = IngestStore(":memory:")
    new, dup = store.commit_batch("job", "rss_atom", [item("e1", payload={"title": "T", "n": 1})], "c1", now="2026-10-11T00:00:00+00:00")
    assert (new, dup) == (1, 0)
    row = store.get_item("rss_atom", "e1")
    assert row["payload"] == {"title": "T", "n": 1}
    assert row["canonical_url"] == "https://example.com/e1"
    assert row["first_seen_at"] == "2026-10-11T00:00:00+00:00"
    assert row["seen_count"] == 1
    assert row["content_hash"] == hashlib.sha256(json.dumps({"title": "T", "n": 1}, sort_keys=True, default=str).encode()).hexdigest()
    assert row["content_hash"] == content_hash({"n": 1, "title": "T"})
    checkpoint = store.load_checkpoint("job")
    assert checkpoint["cursor"] == "c1" and checkpoint["batches_committed"] == 1
    store.close()


def test_dedupe_across_commits_updates_seen_metadata():
    store = IngestStore(":memory:")
    assert store.commit_batch("job", "rss_atom", [item("e1"), item("e2")], None, now="2026-10-11T00:00:00+00:00") == (2, 0)
    assert store.commit_batch("job", "rss_atom", [item("e1"), item("e2")], None, now="2026-10-12T00:00:00+00:00") == (0, 2)
    row = store.get_item("rss_atom", "e1")
    assert row["seen_count"] == 2
    assert row["first_seen_at"] == "2026-10-11T00:00:00+00:00"
    assert row["last_seen_at"] == "2026-10-12T00:00:00+00:00"
    assert store.count_items("rss_atom") == 2
    store.close()


def test_within_batch_duplicate_external_id_counted_once():
    store = IngestStore(":memory:")
    assert store.commit_batch("job", "rss_atom", [item("e1"), item("e1")], None) == (1, 1)
    assert store.count_items("rss_atom") == 1
    store.close()


def test_commit_batch_rejects_missing_external_id():
    store = IngestStore(":memory:")
    with pytest.raises(ValueError, match="external_id"):
        store.commit_batch("job", "rss_atom", [CollectedItem("https://example.com/x", "", {})], None)
    store.close()


def test_job_resumes_after_batch_limit(tmp_path):
    db = str(tmp_path / "ingest.sqlite")
    source = ScriptedSource(three_pages())
    store = IngestStore(db)
    report = asyncio.run(ResumableIngestJob(store).run(job_key="rss", source_name="rss_atom", collector=source, config={}, max_batches=2))
    assert report["status"] == "batch_limit" and report["batches_committed"] == 2
    assert report["items_new"] == 4 and report["resumed_from_cursor"] is None
    assert source.received_cursors == [None, "c1"]
    assert store.load_checkpoint("rss")["cursor"] == "c2"
    store.close()
    assert source.closed is True

    store = IngestStore(db)
    report = asyncio.run(ResumableIngestJob(store).run(job_key="rss", source_name="rss_atom", collector=source, config={}, max_batches=100))
    assert report["status"] == "completed" and report["resumed_from_cursor"] == "c2"
    assert report["items_new"] == 2 and report["items_duplicate"] == 0
    assert source.received_cursors == [None, "c1", "c2"]
    assert store.count_items("rss_atom") == 6
    checkpoint = store.load_checkpoint("rss")
    assert checkpoint["batches_committed"] == 3 and checkpoint["items_new"] == 6
    store.close()


def test_job_resumes_after_source_failure():
    source = ScriptedSource(three_pages(), fail_on=2)
    store = IngestStore(":memory:")
    with pytest.raises(RuntimeError, match="source exploded"):
        asyncio.run(ResumableIngestJob(store).run(job_key="rss", source_name="rss_atom", collector=source, config={}))
    assert store.load_checkpoint("rss")["cursor"] == "c2"
    assert store.count_items("rss_atom") == 4
    report = asyncio.run(ResumableIngestJob(store).run(job_key="rss", source_name="rss_atom", collector=source, config={}))
    assert report["status"] == "completed" and report["items_new"] == 2 and report["items_duplicate"] == 0
    assert store.count_items("rss_atom") == 6
    store.close()


def test_job_rejects_cursor_without_progress():
    looping = [([item("e1")], "x"), ([item("e2")], "x")]
    store = IngestStore(":memory:")
    with pytest.raises(RuntimeError, match="no progress"):
        asyncio.run(ResumableIngestJob(store).run(job_key="rss", source_name="rss_atom", collector=ScriptedSource(looping), config={}))
    store.close()


def test_completed_job_starts_fresh_pass():
    source = ScriptedSource([([item("e1")], None)])
    store = IngestStore(":memory:")
    job = ResumableIngestJob(store)
    first = asyncio.run(job.run(job_key="rss", source_name="rss_atom", collector=source, config={}))
    assert first["status"] == "completed"
    source.pages = [([item("e1")], None)]
    source.calls = 0
    second = asyncio.run(job.run(job_key="rss", source_name="rss_atom", collector=source, config={}))
    assert second["resumed_from_cursor"] is None
    assert second["items_new"] == 0 and second["items_duplicate"] == 1
    store.close()


def test_job_refusals():
    store = IngestStore(":memory:")
    job = ResumableIngestJob(store)
    source = ScriptedSource([([item("e1")], None)])
    with pytest.raises(ValueError, match="max_batches"):
        asyncio.run(job.run(job_key="rss", source_name="rss_atom", collector=source, config={}, max_batches=0))
    with pytest.raises(ValueError, match="collect"):
        asyncio.run(job.run(job_key="rss", source_name="rss_atom", collector=object(), config={}))
    with pytest.raises(ValueError, match="job_key"):
        asyncio.run(job.run(job_key="  ", source_name="rss_atom", collector=source, config={}))
    with pytest.raises(TypeError):
        ResumableIngestJob(object())
    store.close()


# --- audit pins on tip e47c4a31 (runtime frozen; pins only) ---

def test_stored_payload_json_is_canonical_sorted_key_serialization(tmp_path):
    import sqlite3
    db = str(tmp_path / "ingest.sqlite")
    store = IngestStore(db)
    payload = {"zeta": 1, "alpha": [1, 2], "mid": {"b": 2, "a": 1}}
    store.commit_batch("job", "rss_atom", [item("e1", payload=payload)], None)
    store.close()
    raw = sqlite3.connect(db).execute(
        "SELECT payload_json FROM ingest_items WHERE source = 'rss_atom' AND external_id = 'e1'").fetchone()[0]
    assert raw == json.dumps(payload, sort_keys=True, default=str)
    assert raw.index("alpha") < raw.index("mid") < raw.index("zeta")


class CountingCollector:
    """Collector-protocol double that only counts invocations."""

    def __init__(self):
        self.calls = 0

    async def collect(self, config):
        self.calls += 1
        return CollectionBatch([item("e1")], requests=1, cursor=None)


def test_invalid_names_refuse_before_collector_is_invoked():
    store = IngestStore(":memory:")
    job = ResumableIngestJob(store)
    for override in ({"job_key": "  "}, {"job_key": ""}, {"source_name": ""},
                     {"source_name": "   "}, {"max_batches": 0}, {"max_batches": -3},
                     {"max_batches": 1.5}, {"max_batches": "2"}):
        collector = CountingCollector()
        kwargs = {"job_key": "rss", "source_name": "rss_atom", "collector": collector, "config": {}}
        kwargs.update(override)
        with pytest.raises(ValueError):
            asyncio.run(job.run(**kwargs))
        assert collector.calls == 0, f"collector invoked despite invalid {override}"
    store.close()


def test_optional_config_none_accepted():
    collector = CountingCollector()
    store = IngestStore(":memory:")
    report = asyncio.run(ResumableIngestJob(store).run(
        job_key="rss", source_name="rss_atom", collector=collector, config=None))
    assert report["status"] == "completed" and collector.calls == 1
    assert report["items_new"] == 1
    store.close()


def test_duplicate_update_stores_canonical_sorted_serialization(tmp_path):
    import sqlite3
    db = str(tmp_path / "ingest.sqlite")
    store = IngestStore(db)
    store.commit_batch("job", "rss_atom", [item("e1", payload={"title": "T", "n": 1})], None,
                       now="2026-10-11T00:00:00+00:00")
    reordered = {"zeta": 1, "mid": {"b": 2, "a": 1}, "alpha": [1, 2]}
    store.commit_batch("job", "rss_atom", [item("e1", payload=reordered)], None,
                       now="2026-10-12T00:00:00+00:00")
    store.close()
    raw = sqlite3.connect(db).execute(
        "SELECT payload_json FROM ingest_items WHERE source = 'rss_atom' AND external_id = 'e1'").fetchone()[0]
    assert raw == json.dumps(reordered, sort_keys=True, default=str)
    assert raw.index("alpha") < raw.index("mid") < raw.index("zeta")
