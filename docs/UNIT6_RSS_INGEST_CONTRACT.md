# UNIT6 [P270|L215]: resumable bounded ingestion framework

Candidate SCOPED unit. The doc line asks for continuous ingestion of
"everything on the internet"; that is a permanent gap (unbounded scope,
platform terms barring scraping, paid services in the examples). This unit
builds only the cleared bounded mechanism: a continuous-ingestion framework
with a pluggable source, dedupe, a storage schema, and a resumable batch
job, with one RSS source wired in. No scraping, no account or bot
deployment, no paid services, no universal-internet ingestion.

Pluggable source: any object implementing the repo's existing Collector
protocol (async collect(config) returning CollectionBatch). The RSS source
is the existing FeedCollector (rss_atom) in
backend/app/collectors/research_news.py, reused, not re-implemented; it is
tested against real RSS 2.0 and Atom bytes over httpx.MockTransport with no
network access.

Storage schema (backend/app/ingest/store.py, SQLite, stdlib sqlite3):
ingest_items keyed on (source, external_id) carrying canonical URL,
content hash (canonical-JSON sha256, matching the repo convention), payload
JSON, first/last seen timestamps and a seen count; ingest_checkpoints
keyed on job_key carrying the last committed cursor and cumulative batch
and item counters. Each batch commit writes its items and the checkpoint
in one transaction, so the checkpoint never points past committed items.

Dedupe: re-seen (source, external_id) pairs never duplicate a row; they
update last_seen_at, seen_count, content hash and payload, and are counted
as duplicates. Duplicates inside one batch are counted once.

Resumable batch job (backend/app/ingest/pipeline.py): the run loop resumes
from the stored checkpoint cursor, follows source cursors batch by batch,
stops with status batch_limit after max_batches (checkpoint kept), marks
completed when the source exhausts its cursor (next run starts a fresh
pass), and refuses a source whose cursor makes no progress. A source
failure mid-run leaves the checkpoint at the last committed batch; the
next run resumes there and no committed item is re-counted as new.

Honest labels: this moves and dedupes caller-fetched feed items only. It
does not verify item truth, rank, analyze, train models, generate content,
or monitor platforms. Overlap with existing repo code is explicit:
core/collection.py runs single-shot collection with content-hash dedupe
and no resume; collectors/monitoring.py paginates within one run without
mid-run checkpoints. This unit adds the missing resumable checkpointed
job and its own standalone store; it does not replace either.

Synthetic tests: real RSS/Atom parsing via MockTransport, schema roundtrip
and hash stability, cross-commit and within-batch dedupe with seen
metadata, missing-external-id refusal, resume after batch limit (across a
closed and reopened on-disk store), resume after a transient source
failure, cursor-without-progress refusal, fresh pass after completion, and
typed job refusals. ScriptedSource in the test file is an interface-level
test double for cursor paging, not a feature.
