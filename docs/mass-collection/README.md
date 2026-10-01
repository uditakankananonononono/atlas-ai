# Local corpus collection

This is a working bounded collector, not an account scraper or a trained model.
It uses local disk, CPU and network only. It does not start on import, spend money,
use paid APIs, solve CAPTCHAs, use proxies, or bypass blocks. No real user account
or public bulk crawl was accessed in testing.

## Install and run

From the repository root, with Python 3.12:

```sh
python3.12 -m venv .venv-collection
.venv-collection/bin/pip install -r backend/app/mass_collection/requirements-test.txt
PYTHONPATH=backend .venv-collection/bin/python -m app.mass_collection --help
.venv-collection/bin/python -m pytest tests/mass_collection -q
```

The requirements are a pinned small feature/test environment. They do not install
or prove the full existing Atlas backend. A full Atlas install additionally needs
`pip install '.[collection]'` and its existing base dependencies.

Copy `example.json`, replace the URL/format/license/terms fields, review each site's
current terms and data rights, and set `terms_accepted` yourself. The example is
intentionally non-executable without operator edits. Use `unknown` rather than
inventing a license. `training_reviewed` defaults false. It is an operator attestation,
not a legal verifier. Unknown licenses should never be marked reviewed.

```sh
PYTHONPATH=backend .venv-collection/bin/python -m app.mass_collection --root ./data/corpus --tenant local collect /path/to/reviewed-config.json
PYTHONPATH=backend .venv-collection/bin/python -m app.mass_collection --root ./data/corpus --tenant local export
PYTHONPATH=backend .venv-collection/bin/python -m app.mass_collection --root ./data/corpus --tenant local status
PYTHONPATH=backend .venv-collection/bin/python -m app.mass_collection --root ./data/corpus --tenant local stop
```

A configuration has `sources` (up to 10000) and optional `limits`. Processing is
sequential. Each source is one bounded file/page; multiple sources provide mass
collection. No automatic link following or unbounded dataset discovery exists.
For a previously downloaded dataset/export, `ingest CONFIG FILE` takes exactly one
source and never contacts the URL. That URL records the true upstream provenance.

Roots are namespaced by SHA-256 of the tenant string. The root contains an authoritative
SQLite corpus and job journal, downloads, timestamped exports and `manifest.json`.
Only one writer can run per root. Stop creates `STOP` without waiting for the writer;
the writer checks it between requests/chunks/records and during pacing. A request
already blocked on network I/O can take up to the configured timeout to stop.
After review, remove that tenant's STOP file locally to resume. Export also refuses
while stopped. There is deliberately no remote resume or remote secret API.

## Source formats

- `html`: real BeautifulSoup text extraction; script/style/noscript/nav removed.
- `text`: UTF-8 text (optionally gzip/bzip2).
- `jsonl`: one object per line, configured string `text_field`, optional `id`.
  Use for open Hugging Face JSONL files or local dataset exports.
- `parquet`: real PyArrow batches of the selected `text_field`; use for open Hugging
  Face Parquet files. Exact shard URLs and dataset-specific licenses are required.
- `wikipedia`: streaming MediaWiki pages-articles XML, gzip/bzip2 supported.
  Preserves title/page ID and raw wikitext. It does not turn templates into prose.
- `arxiv`: real Atom entries (title/summary/id), such as a reviewed API feed URL.
  This collects metadata/abstracts, not PDFs or unrestricted full-text rights.
- `commoncrawl`: real gzip WARC response records, HTML and HTTP 200 only. Preserves
  original target URL and WARC timestamp. All such records remain training-ineligible
  because an archive's availability is not a grant of each page's copyright.

For Common Crawl, download a selected crawl's `warc.paths.gz` yourself. The Python
helper `app.mass_collection.catalog.commoncrawl_sources(path, terms_accepted=True,
max_files=100)` converts its validated relative WARC paths into bounded Source
objects. Serialize them with `dataclasses.asdict` into `sources`. It never contacts
a discovery service. Large WARC files need deliberately increased download/disk
quotas. The helper does not certify terms or licenses.

The operator must choose current URLs from the publishers' official listings.
No guessed current dump, crawl, arXiv paper license or Hugging Face dataset license
is embedded. Site policies can change. Missing robots (404) allows a fetch only
when the operator has accepted terms. Other robots errors and redirects stop.
Every page/dump request checks robots first, including same-origin redirects.
`Crawl-delay` and `Request-rate` are honored; the greater of the server value and
configured per-origin interval is used. The default is three seconds, one request
at a time. A 401/403/429 stops without automatic retry. Cross-origin redirects stop
and require a separately reviewed source, which can affect CDN-backed downloads.

## Own-account collection

Only origin-scoped bearer-authenticated HTTP endpoints are supported, not automated
password login, OAuth refresh, arbitrary cookies, browser sessions, or other
people's accounts. Use a documented export/read endpoint that you own and that
allows this use. Store the token interactively, never in config/URL/argv:

```sh
# Set ATLAS_TOKEN_KEY through the existing secure local environment mechanism.
PYTHONPATH=backend .venv-collection/bin/python -m app.mass_collection --root ./data/corpus --tenant local credential mine https://your-owned-service.example --confirm-own-account
```

Then set `credential: "mine"` and `owner_account: true` on that source. The
credential store uses the existing `app.core.token_crypto.TokenCipher`, keyed
per tenant, and private local file permissions. It fails when ATLAS_TOKEN_KEY is
absent. Authentication is sent only on the exact recorded origin and only after
robots checks. Tokens never enter dataset manifests. Own-account data is always
training-ineligible, but can still contain private information in the corpus.
Do not publish the corpus. Token ownership is operator-confirmed, not checked
against an identity provider. Local operators must keep the root private and
must not give untrusted users access to the CLI or Python API.

## Resume, dedupe and training

Rerun the same config after a transport/parse/quota stop. Strong ETag + validated
Content-Range resumes a partial file. If validators are unavailable/weak, restart
from byte zero. Completed jobs are skipped. Changed config produces a new job.
Content SHA-256 dedupe prevents duplicate training text, including when a failed
parse is re-read from the start. There is no record-index seek inside compressed
files. Each unique text retains every distinct source URL in `provenance_all`.
A later unreviewed/private duplicate conservatively removes training eligibility.
The first license remains in `license`; every observed license is in provenance.

Export produces versioned JSONL shards and a manifest with record counts, byte
sizes and SHA-256 checksums, then atomically updates the root manifest. Use only
records where `training_eligible == true`, after independently checking rights,
privacy, data quality, attribution and model-training terms. This module does not
perform PII removal, copyright analysis, malware scanning, toxicity filtering,
train/validation split, tokenization, or model training. Unknown licenses and
Common Crawl remain ineligible. No claim is made that collected text is safe.

Quotas cover download, expanded parse, single record, corpus records/serialized
bytes, and a filesystem byte ceiling. SQLite indexes/journal and retained exports
add overhead; checks are application-level, not a filesystem hard quota. Export
needs room for a second copy. Old snapshots and abandoned downloads are not
automatically deleted; remove them locally when safe. A large XML page or Parquet
batch can still consume substantial RAM before per-record checks. Use OS resource
limits for hostile input. XML DTDs/entities are rejected with defusedxml.

## Minimal Atlas mount

The existing backend mounts only:

- `GET /api/v1/mass-collection/status`
- `POST /api/v1/mass-collection/stop`

Both use existing tenant authentication and hashed tenant roots under
ATLAS_COLLECTION_ROOT. There is no remotely triggered collection, arbitrary file
read or token registration endpoint. Development mode retains Atlas's existing
local header identity behavior; it is not safe for an internet-exposed server.

## Test boundaries

Tests use a real threaded loopback HTTP server, httpx TCP requests, real robots,
HTML/XML/Atom/JSONL/Parquet/WARC parsing, ETag range resume, persisted SQLite,
real encryption, CLI, sharded export/checksums, throttling stops, quotas and tenant
isolation. Loopback allowance is a Python fixture switch only and is not exposed
in CLI/routes. Production network requests reject all non-global addresses and pin
DNS to the validated address, with original Host/SNI. No upstream live download,
large-scale throughput, internet HTTPS/IPv6 or authenticated vendor integration
was exercised. Full Atlas regression suite and deployment were not validated.

### Scaling limits

This version favors correctness and simple recovery over throughput. Per-record
SQLite commits, byte accounting and filesystem scans are intentionally conservative
and can be slow for millions of records. Single-worker operation is enforced per
root; parallel independent roots are possible but do not coordinate origin rates.
Do not use parallel roots to exceed a publisher's rate policy. The default quotas
are a small starting corpus, not a promise of billion-record scale. Terms acceptance
is manually supplied; this module cannot read or interpret legal terms for you.
