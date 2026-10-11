# Export file adapter: contract

Source lines (owner's requirements document, paragraphs 277 and 278):
- "-see my likes and comments on social media and try to understand my likes and get inspired from the posts I liked ..."
- "-see the people I follow and try to create similar work/products they have built but better"

This module is a bounded mechanism for reading export files the caller already holds. It does
not fulfil either line. It does not look at likes, comments or follows by itself, does not
understand them, and builds nothing from them. Paragraph 279 ("Across all fields new products ...")
is analysis, has no export file, and is not covered.

Module: `backend/app/collectors/export_file_adapters.py`. Tests: `tests/modules/test_collectors_export_file_adapters.py`.
It imports only the standard library plus `CollectedItem` and `CollectionBatch` from `app.collectors.base`.

## Offline only

No login, no export request, no scraping, no network call, no subprocess. The caller supplies a local
file path. A test blocks `socket` and checks the module source imports no network library.
The file is only read; nothing is written.

## Interface

`ExportFileCollector().collect(config)` is an async method that follows the `Collector` protocol and returns a `CollectionBatch`.

Config keys: `path`, `format` (`csv`, `json`, `jsonl`), `mapping`, `record_path` (JSON only, dotted path to the list),
`limit`, `cursor`, `max_bytes` (default 256 MiB), `max_records` (default 500000), `kind`, `platform` (free-text labels copied into each payload).
Any other key is an error.

Mapping: `{"url": <column or dotted key>, "external_id": <optional>, "fields": {<output name>: <column or dotted key>}}`.
- CSV: columns are header names, read with a UTF-8 BOM tolerated. A missing mapped column is an error that names it.
- JSON and JSONL: dotted keys may index lists (`a.b.0.c`). A missing field value becomes `None`.
- A record is emitted only if its url is a string starting with `http://` or `https://`. Otherwise it is rejected. A record with no usable external_id (when one is mapped) is rejected, as is a duplicate external_id, and any JSON record that is not an object.
- With no `external_id` mapping, the id is the first 16 hex characters of a SHA-256 over the url and the mapped fields. Two identical rows therefore count as duplicates.
- Output field names `provider`, `source_file`, `record_index`, `kind`, `platform` are reserved.

Result: `CollectedItem(canonical_url, external_id, payload)` with `payload` holding `provider: "export_file"`, `source_file` (file name only, no directory), `record_index`, the optional labels, and the mapped fields.
`CollectionBatch.requests` is 0. `detail` has `format`, `file_bytes`, `file_sha256`, `records_read`, `records_accepted_in_file`, `records_emitted`, `records_rejected`, `rejected` (first 50: index and reason) and `layout_verified` (always `false`).

Paging: `limit` plus `cursor` page over the accepted records; the returned `cursor` is the next position as a string, or `None` at the end. Each call re-reads and re-parses the whole file.

Refused: files over `max_bytes`, ZIP or other archives (by magic bytes or suffix; extract first), non-UTF-8 text, invalid JSON, JSON that is not a list.

## Gaps (stated plainly)

- No platform layout is verified. `PROFILES` is empty. Official help pages (checked 2026-10-11, self-fetched, not independently verified) list LinkedIn data categories and fields but give no file names or column headers; the Instagram page names no layout; the X help page could not be fetched. No real export file has been used. Formats stay UNVERIFIED until real fixtures exist, and the tests use synthetic files written by the tests.
- The mapping is only as right as the caller makes it. The module cannot tell whether a file really is a LinkedIn, Instagram or X export.
- The adapter does not read ZIP archives, HTML exports, or Excel files.
- Whole-file in memory up to `max_bytes`. Records are counted as lines or rows, not checked for meaning.
- The module is not registered in `registry.py` and has no HTTP route; no wiring patch was produced. It has not been run inside a unit 6 job.
- Not run: the full repo test suite, mounted auth/tenant tests, Postgres, hosted CI.

## Memory and re-read limits (added 2026-10-11, doc and tests only, core unchanged)

- The `max_bytes` cap (default 256 MiB) limits the RAW INPUT FILE only. The parsed objects (CSV rows as dicts, decoded JSON values, the emitted items and their payloads) can use more memory than the file size, often several times more. There is NO total memory cap. Callers that handle large exports should lower `max_bytes` and `max_records`.
- Every call re-reads and re-parses the whole file, including each paged call made with `cursor`. Paging bounds the size of what is returned, not the work or memory done per call.

## Mapping rules pinned by tests (added 2026-10-11)

- CSV: a mapped name is looked up as a literal header, so a header such as `a.url` is one column. It is not treated as a nested path.
- JSON and JSONL: a mapped name with dots is a nested path (`a.url` means key `a`, then key `url`), even if a literal key `a.url` also exists in the record.
- Derived external ids (used when no `external_id` is mapped) are computed with sorted keys, so reordering the `fields` mapping does not change them.
- Validation errors have fixed messages for: config not an object, `mapping.url`, `mapping.external_id`, `record_path`, `mapping.fields`.
