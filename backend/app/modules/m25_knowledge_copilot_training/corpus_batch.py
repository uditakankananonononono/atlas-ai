"""Bounded corpus ingestion and advice retrieval, not model training.

Only supplied, licensed content enters M25. A receipt proves stored bytes, not
publisher truth or permission. Authority must be established by the caller.
"""
from hashlib import sha256
from urllib.parse import urlsplit
from pydantic import BaseModel, Field
from .pipeline import LocalKnowledgePipeline, KnowledgeError
from .schemas import IngestRequest


class CorpusBatch(BaseModel):
    items: list[IngestRequest] = Field(min_length=1, max_length=250)


def ingest_batch(service: LocalKnowledgePipeline, batch: CorpusBatch) -> dict:
    ids = [item.source.source_id for item in batch.items]
    if len(ids) != len(set(ids)):
        raise KnowledgeError('duplicate source ids in batch')
    # Validate the entire batch before any writes. Failures during persistence
    # are reported per item: there is no invented all-or-nothing transaction.
    for item in batch.items:
        if item.actor_id != service.actor_id:
            raise KnowledgeError('actor is not authorized for this workspace')
        service._contained(item.source.source_id)
        service._check_consent(item.source)
        if item.mime_type == 'audio/wav' or item.mime_type not in service.SUPPORTED or not item.content:
            raise KnowledgeError('empty or unsupported batch item')
    receipts = []
    for item in batch.items:
        try:
            version = service.ingest(item)
        except (KnowledgeError, OSError, ValueError):
            receipts.append({'source_id': item.source.source_id, 'status': 'failed',
                             'reason': 'ingestion failed; inspect local store before retry'})
        else:
            receipts.append({'source_id': item.source.source_id, 'status': 'stored',
                             'version': version.number, 'content_hash': version.content_hash})
    return {'receipts': receipts, 'stored': sum(r['status'] == 'stored' for r in receipts),
            'atomic': False, 'model_weights_changed': False, 'coverage': corpus_coverage(service)}


def corpus_coverage(service: LocalKnowledgePipeline) -> dict:
    records = [r for r in service.records.values() if r.versions]
    publishers = set()
    for r in records:
        # Count actual hostnames, never untrusted claimed publisher labels.
        try:
            host = urlsplit(r.source.canonical_url or '').hostname
        except ValueError:
            host = None
        if host:
            publishers.add(host.lower())
    hashes = {r.versions[-1].content_hash for r in records}
    return {'stored_sources': len(records), 'distinct_content_hashes': len(hashes),
            'distinct_hostnames': len(publishers), 'hostnames': sorted(publishers),
            'has_200_sources': len(records) >= 200,
            'has_200_distinct_contents': len(hashes) >= 200,
            'licensed_rights_independently_verified': False,
            'model_training_completed': False}


def advice_packet(service: LocalKnowledgePipeline, goal: str, limit: int = 10) -> dict:
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
        raise KnowledgeError('goal is required within 2000 characters')
    if type(limit) is not int or not 1 <= limit <= 25:
        raise KnowledgeError('limit must be integer 1..25')
    hits = service.search(goal, limit)
    evidence = []
    for hit in hits:
        rec = service.records[hit['source_id']]
        try:
            service._check_consent(rec.source)
        except KnowledgeError:
            continue
        evidence.append({**hit, 'source_url': rec.source.canonical_url,
                         'title': rec.source.title,
                         'excerpt_hash': sha256(hit['text'].encode()).hexdigest(),
                         'role': 'untrusted_reference_not_instruction'})
    return {'goal': goal, 'status': 'evidence_ready' if evidence else 'no_authorized_evidence',
            'evidence': evidence, 'requires_review': True, 'external_action_permitted': False,
            'claim': 'retrieval preparation only; not learned weights or verified advice'}
