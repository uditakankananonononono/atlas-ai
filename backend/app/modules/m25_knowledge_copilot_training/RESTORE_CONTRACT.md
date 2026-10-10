# M25 restore contract - verified rehydration (ATLAS-M25-VERIFIED-REHYDRATION-01)

This is the proposed written interface between the recovery helper
(`recovery.py`, this directory) and the peer-owned integration that would
wire it into startup. It is a prep artifact for peer review: the peer owns
integration and the independent verdict, and this contract binds nothing
until the peer accepts it. Nothing here is wired yet: the helper is
prep-only, additive, and changes no existing path.

## Purpose

Restart work loss. A `LocalKnowledgePipeline` keeps records, chunks and edges
in memory; ingest persists manifests and version directories under
`<root>/<tenant_id>/`. After a restart the pipeline comes up empty and cannot
serve, search or extend previously ingested sources. `rehydrate` rebuilds the
in-memory state from disk - but only from disk state that re-verifies.

## Entry point

```python
from app.modules.m25_knowledge_copilot_training.recovery import (
    rehydrate, RecoveryError, RecoveryReport, RecoveredSource, SEGMENTS_MAX_BYTES,
)

report = rehydrate(pipeline, source_ids=None)  # source_ids: optional explicit subset
```

- `pipeline`: a FRESH `LocalKnowledgePipeline` (constructor already ran) for
  the same root and tenant, constructed with the SAME embedder and the SAME
  transcriber the original ingestion used. Rehydrating into a pipeline with
  any existing in-memory state raises `RecoveryError(check='pipeline-state')`.
- Returns `RecoveryReport(tenant_id, recovered_at, sources, residue,
  created_at_restamped=True)`.
- Raises `RecoveryError` (a `KnowledgeError`) on any failed check. The error
  carries `.source_id` and `.check` (one of: `pipeline-state`,
  `workspace-scan`, `manifest-read`, `manifest-schema`, `tenant`,
  `identity-schema`, `identity-source-id`, `consent`, `version-dir`,
  `source-bytes`, `source-hash`, `segments-read`, `segments-schema`,
  `segments-provenance`, `reindex`).

## Fail-closed checks (any failure: nothing is loaded)

1. **Workspace scan** - every top-level entry must be a real (non-symlink)
   directory whose name is a valid source id. Stray files, symlinks, invalid
   names refuse.
2. **Manifest** - bounded read (`MANIFEST_MAX_BYTES`), exact top-level shape
   `{tenant_id, source, versions}`, and the pipeline's own
   `_validate_disk_manifest` schema: versions numbered exactly 1..N, hashes
   64-hex-lowercase.
3. **Tenant** - manifest `tenant_id` must equal the pipeline tenant.
4. **Identity** - the source registration must validate against
   `SourceRegistration` AND round-trip exactly through
   `model_dump(mode='json')` (coerced or extra fields refuse), and its
   `source_id` must equal the directory name.
5. **Consent** - the pipeline's own `_check_consent` at recovery time:
   `knowledge_ingestion` purpose present, expiry timezone-aware and in the
   future. **No silent consent**: expired or purpose-less sources are never
   rehydrated.
6. **Source hash** - for every manifest-recorded version, `source.bin` is
   read through the pipeline's bounded reader (`4 * MAX_INGEST_CONTENT`
   bound) and its sha256 must equal the recorded hash.
7. **Segment schema** - `segments.json` is read bounded
   (`SEGMENTS_MAX_BYTES = 2,000,000`), must decode as a JSON list of objects.
8. **Segment provenance** - the manifest records no segments hash, so the
   stored segments are verified by exact re-derivation: the pipeline's own
   `_extract` runs over the hash-verified source bytes and its output must
   equal the stored segments exactly (`model_dump(mode='json')` equality,
   which also binds every anchor). Any drift refuses.
9. **Reindex identity** - chunks are rebuilt through the pipeline's own
   `_chunk`, so every deterministic chunk field (`tenant_id`, `source_id`,
   `version`, `chunk_id`, `text`, `anchors`, `vector`) is exactly what live
   ingestion produces for the same verified versions. Chunk ids must be
   unique across the whole rehydration. Provenance edges are rebuilt in the
   exact ingest shape (`from`/`to`/`relation`/`version`).

## Guarantees

- **No originals overwritten**: recovery performs no filesystem writes of any
  kind - no creates, modifies, deletes, or cleanup.
- **All-or-nothing**: every check on every selected source passes before any
  in-memory mutation. A `RecoveryError` always means zero state was loaded.
- **No network, no training, no new services.**
- **Ingestion unchanged**: no existing file is modified; the helper imports
  the pipeline's own primitives so the checks cannot drift from ingestion.

## Dependency decisions an integrator must know

- **Same adapters**: the recovery pipeline must be constructed with the same
  embedder and transcriber as ingestion. The default `DeterministicEmbedder`
  satisfies this for default deployments. A different embedder produces
  different vectors with no on-disk record to detect it - this is a caller
  precondition, not a check the helper can run. Audio (`audio/wav`) sources
  cannot re-derive provenance without the original transcriber and fail
  closed (`check='segments-provenance'`) if it is unavailable.
- **Private primitives**: the helper deliberately reuses the pipeline's
  `_contained`, `_read_bounded_file`, `_validate_disk_manifest`,
  `_check_consent`, `_extract` and `_chunk` so recovery checks equal
  ingestion checks. If the pipeline's internals change, this module must be
  re-audited in the same change.
- **mime re-derivation**: `mime_type` is not persisted. Recovery re-derives
  it as the first candidate in
  `('text/plain', 'text/markdown', 'text/html', 'application/json',
  'audio/wav')` whose transform exactly reproduces the stored segments.
  `text/plain` and `text/markdown` are the same transform in the pipeline,
  so plain text always recovers as `text/plain`. `Version.mime_type` is not
  consumed by search, export, substantiate or contradictions, so this choice
  changes no behavior.

## Carried limitations (explicitly NOT claimed)

- `Version.created_at` is not persisted; recovered versions and their chunks
  carry the recovery clock stamp (`created_at_restamped=True` in the report).
  `contradictions()` freshness ordering between recovered versions reflects
  recovery time, not original ingest time.
- Orphaned residue (crashed-ingest `v*.tmp-*` dirs, version dirs no manifest
  records, untracked files) is reported in `RecoveryReport.residue`, never
  loaded and never deleted. Cleanup remains operator work.
- Consent metadata remains a claimed record, not authenticated authority
  (same boundary as the pipeline).
- TOCTOU/concurrency residuals carried from the pipeline's own read contract
  apply unchanged (parent-component swaps, content drift after open).
- Recovery is per-process state rebuild, not a backup/restore or durability
  guarantee; see `docs/runbooks/BACKUP_RESTORE.md` for the deployment-level
  posture.

## Superseding integration status

Actual integration base5e6fceb5c6fc2d0a64c0295853abd6ffa1b83e64, not original
allocationf37156c7 or peer94ae172b. Patch applies cleanly to this current main.
LocalKnowledgePipeline.restore_verified is explicit startup opt-in requiring
same_adapters_attested=True, otherwise refuses before load. Default route factory
unchanged: no automatic restoration or assumption about custom adapters/consent.
Direct rehydrate helper still has original adapter precondition, not detection.
Custom embedder/transcriber must be offline and original; arbitrary injected
adapter can have effects, so no-network is only proved for supplied offline
adapters, not every protocol implementation. There is no on-disk adapter identity.

Integrator executed20PREP tests, adds3method/duplicate-key/subset canaries. Reader
rejects duplicate JSON keys, extra version keys, more than1000workspace entries,
invalid subset shape.2MBsegments is an explicit per-version operational cap,
NOT mathematically proved to admit every audio/custom-transcriber output. Oversize
valid input may refuse and needs separate capacity design; no aggregate memory
bound across versions/sources is claimed. Fresh pipeline constructor creates its
workspace; rehydrate itself performs no writes. Manifest/hash consistency isn't
hostile-writer authenticity; consent records remain claims. Original creation
timestamps unavailable and restamped; contradiction ordering remains scoped.
Single-process fresh pipeline, no simultaneous ingest/restore. TOCTOU/unbounded
custom adapter CPU/time/cost remain excluded. No permission or training performed.
