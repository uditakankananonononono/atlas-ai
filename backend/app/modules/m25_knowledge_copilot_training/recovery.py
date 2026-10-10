"""Verified rehydration of M25 knowledge-copilot state after a restart.

Unit ATLAS-M25-VERIFIED-REHYDRATION-01, explicit opt-in integration. The proposed written interface for this module
is RESTORE_CONTRACT.md in this directory; it binds nothing until the peer's
review and integration verdict accept it.

After a process restart a LocalKnowledgePipeline comes up with empty memory
while the tenant workspace on disk still holds every manifest and version
directory ingest wrote. This module rebuilds the in-memory state from that
disk state, but only after every recorded claim is re-verified against the
bytes actually on disk. Any divergence fails closed: RecoveryError is raised
and the pipeline is left completely untouched, because all verification
completes before any in-memory mutation.

Boundary, exactly:
- READ ONLY. No file is created, modified or deleted; no originals are
  overwritten; orphaned residue is reported, never cleaned up.
- No network, no training, no new services. Ingestion code paths are not
  modified; this module imports the pipeline's own primitives (_contained,
  _read_bounded_file, _validate_disk_manifest, _check_consent, _extract,
  _chunk) so recovery runs the SAME checks ingestion relies on rather than a
  re-implementation that could drift.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .pipeline import (
    AdapterUnavailable,
    Chunk,
    KnowledgeError,
    LocalKnowledgePipeline,
    Record,
    Version,
)
from .schemas import MAX_INGEST_CONTENT, SourceRegistration

__all__ = [
    'RecoveryError',
    'RecoveredSource',
    'RecoveryReport',
    'SEGMENTS_MAX_BYTES',
    'rehydrate',
]

_SOURCE_ID_RE = re.compile(r'^[A-Za-z0-9_.-]+$')

# Explicit per-version operational cap, not a proved upper bound for every
# custom transcriber output. Valid oversized input can refuse. No aggregate
# memory/CPU bound across versions/sources is claimed.
SEGMENTS_MAX_BYTES = 2_000_000

# mime_type is not persisted in the on-disk manifest, so recovery re-derives
# it: each candidate transform runs over the hash-verified source bytes and
# the FIRST whose output reproduces the stored segments.json exactly wins.
# text/plain and text/markdown are the same transform in the pipeline, so
# text/plain always wins that pair; the equivalence rules and why this is
# safe are written down in RESTORE_CONTRACT.md.
_MIME_CANDIDATES = ('text/plain', 'text/markdown', 'text/html', 'application/json', 'audio/wav')


class RecoveryError(KnowledgeError):
    """Fail-closed refusal during rehydration.

    Carries the source and the check that refused so the caller can report
    exactly what diverged. A RecoveryError always means zero in-memory
    mutation happened: recovery is all-or-nothing.
    """

    def __init__(self, message: str, *, source_id: str | None = None, check: str | None = None):
        super().__init__(message)
        self.source_id = source_id
        self.check = check


@dataclass
class RecoveredSource:
    source_id: str
    versions: int
    chunks: int


@dataclass
class RecoveryReport:
    tenant_id: str
    recovered_at: str
    sources: list[RecoveredSource] = field(default_factory=list)
    # On-disk entries no live manifest records: orphaned version/tmp dirs
    # from crashed ingests, untracked files, and (with source_ids=) sources
    # not selected. Reported, never loaded, never deleted.
    residue: list[str] = field(default_factory=list)
    # Version.created_at is not persisted on disk, so every recovered version
    # (and its chunks) carries the recovery clock stamp. Chunk identity
    # fields (tenant/source/version/chunk_id/text/anchors/vector) are exact;
    # only the timestamp is restamped.
    created_at_restamped: bool = True


def rehydrate(pipeline: LocalKnowledgePipeline, *, source_ids: list[str] | None = None) -> RecoveryReport:
    """Rebuild a fresh pipeline's in-memory state from its tenant workspace.

    Fail-closed on source hash, segment provenance/schema, registration
    identity, tenant, and consent expiry; reindex identity is exact on every
    deterministic chunk field. All-or-nothing: any refusal leaves the
    pipeline untouched. Performs no writes of any kind.
    """
    if pipeline.records or pipeline.chunks or pipeline.edges:
        raise RecoveryError(
            'rehydration requires a fresh pipeline with no in-memory state; '
            'refusing to merge into or overwrite live state',
            check='pipeline-state')
    stamp = pipeline.clock()
    residue: list[str] = []
    pending: list[tuple[Record, list[Chunk], list[dict]]] = []

    if source_ids is not None and (type(source_ids) is not list or len(source_ids)>1000 or any(type(x) is not str for x in source_ids)):
        raise RecoveryError('source_ids must be a list of at most1000 strings',check='workspace-scan')
    try:entries = sorted(pipeline.workspace.iterdir(), key=lambda p: p.name) if pipeline.workspace.exists() else []
    except OSError as exc:raise RecoveryError('workspace listing unavailable',check='workspace-scan') from exc
    if len(entries)>1000:raise RecoveryError('workspace source capacity exceeded',check='workspace-scan')
    by_name = {e.name: e for e in entries}
    if source_ids is not None:
        selected = list(dict.fromkeys(source_ids))
        for name in selected:
            if name not in by_name:
                raise RecoveryError(f'selected source {name!r} is not present on disk',
                                    source_id=name, check='workspace-scan')
        scan = [(name, by_name[name]) for name in selected]
        keep = set(selected)
        residue.extend(f'{e.name} (not selected)' for e in entries if e.name not in keep)
    else:
        scan = [(e.name, e) for e in entries]

    for name, entry in scan:
        _check_workspace_entry(name, entry)
        pending.append(_verify_source(pipeline, name, stamp, residue))

    # Commit phase: every source verified. Chunk ids must be unique across
    # the whole rehydration; a collision means the disk state disagreed with
    # itself and nothing is loaded.
    seen_chunk_ids: set[str] = set()
    for rec, chunks, _edges in pending:
        for chunk in chunks:
            if chunk.chunk_id in seen_chunk_ids:
                raise RecoveryError(f'duplicate chunk id {chunk.chunk_id} during reindex',
                                    source_id=rec.source.source_id, check='reindex')
            seen_chunk_ids.add(chunk.chunk_id)
    for rec, _chunks, _edges in pending:
        pipeline.records[rec.source.source_id] = rec
    for _rec, chunks, _edges in pending:
        pipeline.chunks.extend(chunks)
    for _rec, _chunks, edges in pending:
        pipeline.edges.extend(edges)

    return RecoveryReport(
        tenant_id=pipeline.tenant_id,
        recovered_at=stamp.isoformat(),
        sources=[RecoveredSource(rec.source.source_id, len(rec.versions), len(chunks))
                 for rec, chunks, _edges in pending],
        residue=sorted(residue),
    )


def _check_workspace_entry(name: str, entry: Path) -> None:
    # Top-level workspace entries must be real source directories: anything
    # else (stray file, symlink, invalid id) is divergence and fails closed.
    if name in ('.', '..') or not _SOURCE_ID_RE.match(name):
        raise RecoveryError(f'workspace entry {name!r} is not a valid source id',
                            source_id=name, check='workspace-scan')
    try:
        st = os.lstat(entry)
    except OSError as exc:
        raise RecoveryError(f'workspace entry {name!r} unreadable',
                            source_id=name, check='workspace-scan') from exc
    if stat.S_ISLNK(st.st_mode):
        raise RecoveryError(f'workspace entry {name!r} is a symlink; refusing to follow',
                            source_id=name, check='workspace-scan')
    if not stat.S_ISDIR(st.st_mode):
        raise RecoveryError(f'workspace entry {name!r} is not a source directory',
                            source_id=name, check='workspace-scan')


def _verify_source(pipeline: LocalKnowledgePipeline, source_id: str, stamp, residue: list[str]):
    reader = LocalKnowledgePipeline._read_bounded_file

    # 1. Manifest: bounded read through the pipeline's own bounded reader,
    # exact top-level shape, then the pipeline's own on-disk manifest schema
    # (versions numbered exactly 1..N, 64-hex-lowercase hashes).
    try:
        manifest_path = pipeline._contained(source_id, 'manifest.json')
        raw_manifest = reader(manifest_path, LocalKnowledgePipeline.MANIFEST_MAX_BYTES,
                              'rehydration refused', 'on-disk manifest', 'exceeds the manifest bound')
    except KnowledgeError as exc:
        raise RecoveryError(str(exc), source_id=source_id, check='manifest-read') from exc
    try:
        disk = json.loads(raw_manifest.decode('utf-8'),object_pairs_hook=_unique_keys)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise RecoveryError('on-disk manifest is not valid JSON',
                            source_id=source_id, check='manifest-schema') from exc
    if not isinstance(disk, dict) or set(disk) != {'tenant_id', 'source', 'versions'}:
        raise RecoveryError('on-disk manifest top-level shape diverges from the written schema',
                            source_id=source_id, check='manifest-schema')
    try:
        disk_versions = LocalKnowledgePipeline._validate_disk_manifest(disk)
        if any(set(x)!={'number','hash'} for x in disk_versions):raise KnowledgeError('version schema extra keys')
    except KnowledgeError as exc:
        raise RecoveryError(str(exc), source_id=source_id, check='manifest-schema') from exc

    # 2. Tenant identity.
    if disk['tenant_id'] != pipeline.tenant_id:
        raise RecoveryError('on-disk manifest tenant differs from this pipeline tenant',
                            source_id=source_id, check='tenant')

    # 3. Registration identity: schema validation plus a full serialization
    # round-trip, so coerced values or extra fields fail closed, and the
    # recorded source id must equal the directory name.
    try:
        source = SourceRegistration.model_validate(disk['source'])
    except ValidationError as exc:
        raise RecoveryError('on-disk source registration fails schema validation',
                            source_id=source_id, check='identity-schema') from exc
    if source.model_dump(mode='json') != disk['source']:
        raise RecoveryError('on-disk source registration does not round-trip exactly',
                            source_id=source_id, check='identity-schema')
    if source.source_id != source_id:
        raise RecoveryError('on-disk manifest source_id differs from its directory name',
                            source_id=source_id, check='identity-source-id')

    # 4. Consent, re-checked at recovery time with the same check ingestion
    # uses: knowledge_ingestion purpose present, expiry timezone-aware and in
    # the future. No silent consent: an expired or purpose-less source is
    # never rehydrated. Carried from the pipeline: consent metadata remains a
    # claimed record, not authenticated authority.
    try:
        pipeline._check_consent(source)
    except KnowledgeError as exc:
        raise RecoveryError(str(exc), source_id=source_id, check='consent') from exc

    # 5. Every recorded version: source bytes must hash to the recorded hash,
    # and the stored segments must be EXACTLY what the pipeline's own
    # deterministic extraction re-derives from those verified bytes.
    versions: list[Version] = []
    expected_dirs: set[str] = set()
    for entry in disk_versions:
        number, recorded_hash = entry['number'], entry['hash']
        vdir_name = f'v{number}'
        expected_dirs.add(vdir_name)
        try:
            vdir = pipeline._contained(source_id, vdir_name)
        except KnowledgeError as exc:
            raise RecoveryError(str(exc), source_id=source_id, check='version-dir') from exc
        try:
            vst = os.lstat(vdir)
        except OSError as exc:
            raise RecoveryError(f'version directory {vdir_name} missing or unreadable',
                                source_id=source_id, check='version-dir') from exc
        if stat.S_ISLNK(vst.st_mode) or not stat.S_ISDIR(vst.st_mode):
            raise RecoveryError(f'version path {vdir_name} is not a real directory',
                                source_id=source_id, check='version-dir')
        try:
            blob_path = pipeline._contained(source_id, vdir_name, 'source.bin')
            raw = reader(blob_path, 4 * MAX_INGEST_CONTENT, 'rehydration refused',
                         f'on-disk source bytes for version {number}', 'exceed the ingest bound')
        except KnowledgeError as exc:
            raise RecoveryError(str(exc), source_id=source_id, check='source-bytes') from exc
        if hashlib.sha256(raw).hexdigest() != recorded_hash:
            raise RecoveryError(
                f'on-disk source bytes for version {number} diverge from the recorded hash',
                source_id=source_id, check='source-hash')
        try:
            seg_path = pipeline._contained(source_id, vdir_name, 'segments.json')
            seg_blob = reader(seg_path, SEGMENTS_MAX_BYTES, 'rehydration refused',
                              f'on-disk segments for version {number}', 'exceeds the segments bound')
        except KnowledgeError as exc:
            raise RecoveryError(str(exc), source_id=source_id, check='segments-read') from exc
        try:
            stored_segments = json.loads(seg_blob.decode('utf-8'),object_pairs_hook=_unique_keys)
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            raise RecoveryError(f'on-disk segments for version {number} are not valid JSON',
                                source_id=source_id, check='segments-schema') from exc
        if not isinstance(stored_segments, list) or not all(isinstance(s, dict) for s in stored_segments):
            raise RecoveryError(f'on-disk segments for version {number} fail schema shape',
                                source_id=source_id, check='segments-schema')
        segments, mime = _rederive_segments(pipeline, raw, source.kind, number, stored_segments, source_id)
        # created_at is not persisted; restamped with the recovery clock.
        versions.append(Version(number, recorded_hash, segments, stamp, mime))

    # Residue: entries inside the source directory that no live manifest
    # records (orphaned version or tmp dirs from crashed ingests, untracked
    # files). Reported, never loaded, never deleted. Best-effort listing:
    # a listing failure never fails an already-verified source.
    try:
        for child in sorted(pipeline._contained(source_id).iterdir(), key=lambda p: p.name):
            if child.name != 'manifest.json' and child.name not in expected_dirs:
                residue.append(f'{source_id}/{child.name}')
            elif child.name in expected_dirs and child.is_dir():
                for grand in sorted(child.iterdir(), key=lambda p: p.name):
                    if grand.name not in ('source.bin', 'segments.json'):
                        residue.append(f'{source_id}/{child.name}/{grand.name}')
    except (OSError, KnowledgeError):
        pass

    # Reindex through the pipeline's own chunking so chunk identity is
    # exactly what live ingestion produces for the same verified versions.
    rec = Record(source, pipeline.tenant_id, versions=versions)
    chunks: list[Chunk] = []
    try:
        for version in rec.versions:
            chunks.extend(pipeline._chunk(rec, version))
    except KnowledgeError as exc:
        raise RecoveryError(str(exc), source_id=source_id, check='reindex') from exc
    edges = [{'from': source_id, 'to': v.content_hash, 'relation': 'has_version', 'version': v.number}
             for v in rec.versions]
    return rec, chunks, edges


def _rederive_segments(pipeline: LocalKnowledgePipeline, raw: bytes, kind: str, number: int,
                       stored_segments: list[dict], source_id: str):
    # Provenance: the manifest records no segments hash, so the only binding
    # between the hash-verified source bytes and the stored segments is exact
    # re-derivation through the pipeline's own extraction. Each candidate
    # transform runs; the first exact reproduction wins. A candidate that
    # cannot run on these bytes (decode/shape failure) simply does not match;
    # an unavailable audio transcriber is recorded so the refusal can say so.
    adapter_blocked = False
    for mime in _MIME_CANDIDATES:
        try:
            derived = pipeline._extract(raw, mime, kind)
        except AdapterUnavailable:
            adapter_blocked = True
            continue
        except KnowledgeError:
            continue
        if [s.model_dump(mode='json') for s in derived] == stored_segments:
            return derived, mime
    detail = ''
    if adapter_blocked:
        detail = '; the audio candidate needs the original transcriber, which is unavailable'
    raise RecoveryError(
        f'on-disk segments for version {number} diverge from a re-derivation of the '
        f'hash-verified source bytes{detail}',
        source_id=source_id, check='segments-provenance')


def _unique_keys(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise ValueError('duplicate JSON key')
        out[key]=value
    return out
