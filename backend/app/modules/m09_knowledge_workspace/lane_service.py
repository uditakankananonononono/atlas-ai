from __future__ import annotations

import json
import math
import re
from difflib import unified_diff
from collections import Counter, deque
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from .lane_models import (
    AuditEvent, ConflictError, DocumentVersion, KnowledgeError, NotFoundError,
    ProvenanceEdge, Relation, SearchHit, SourceRef, Suggestion, SuggestionStatus,
    utcnow,
)
from .lane_store import InMemoryKnowledgeStore

_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)


def _terms(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(value) if len(token) > 1]


def _required(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise KnowledgeError(f"{name} cannot be blank")
    return value


class KnowledgeWorkspace:
    """Versioned knowledge base with traceable provenance and review workflow."""

    def __init__(
        self,
        store: InMemoryKnowledgeStore | None = None,
        *,
        clock: Callable[[], datetime] = utcnow,
        id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self.store = store or InMemoryKnowledgeStore()
        self.clock = clock
        self.id_factory = id_factory

    def create_document(
        self, *, title: str, content: str, actor_id: str,
        document_id: str | None = None, source_refs: Iterable[SourceRef] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> DocumentVersion:
        title, content, actor_id = (_required(title, "title"), _required(content, "content"), _required(actor_id, "actor_id"))
        document_id = document_id or self.id_factory()
        now = self.clock()
        with self.store.lock:
            if self.store.versions(document_id):
                raise ConflictError(f"document already exists: {document_id}")
            version = DocumentVersion(document_id, 1, title, content, actor_id, now, tuple(source_refs), dict(metadata or {}))
            self.store.append_version(version)
            self._audit("document.created", actor_id, "document", document_id, {"version": 1})
            return version

    def get_document(self, document_id: str, version: int | None = None) -> DocumentVersion:
        versions = self.store.versions(document_id)
        if not versions:
            raise NotFoundError(f"unknown document: {document_id}")
        if version is None:
            return versions[-1]
        if version < 1 or version > len(versions):
            raise NotFoundError(f"unknown version {version} for document {document_id}")
        return versions[version - 1]

    def update_document(
        self, document_id: str, *, actor_id: str, expected_version: int,
        title: str | None = None, content: str | None = None,
        source_refs: Iterable[SourceRef] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DocumentVersion:
        actor_id = _required(actor_id, "actor_id")
        with self.store.lock:
            current = self.get_document(document_id)
            if current.version != expected_version:
                raise ConflictError(f"stale version: expected {expected_version}, current {current.version}")
            next_title = _required(title, "title") if title is not None else current.title
            next_content = _required(content, "content") if content is not None else current.content
            version = DocumentVersion(
                document_id, current.version + 1, next_title, next_content, actor_id,
                self.clock(), tuple(source_refs) if source_refs is not None else current.source_refs,
                dict(metadata) if metadata is not None else dict(current.metadata), current.version,
            )
            self.store.append_version(version)
            self._audit("document.updated", actor_id, "document", document_id, {"from_version": current.version, "version": version.version})
            return version

    def history(self, document_id: str) -> tuple[DocumentVersion, ...]:
        self.get_document(document_id)
        return self.store.versions(document_id)

    def diff_versions(self, document_id: str, from_version: int, to_version: int) -> str:
        """Return a stable unified diff of title and body for review or audit."""
        before = self.get_document(document_id, from_version)
        after = self.get_document(document_id, to_version)
        before_lines = [f"# {before.title}\n", *before.content.splitlines(keepends=True)]
        after_lines = [f"# {after.title}\n", *after.content.splitlines(keepends=True)]
        return "".join(unified_diff(
            before_lines, after_lines,
            fromfile=f"{document_id}@{from_version}",
            tofile=f"{document_id}@{to_version}",
        ))

    def restore_version(
        self, document_id: str, *, restore_version: int, actor_id: str,
        expected_version: int, reason: str,
    ) -> DocumentVersion:
        """Restore old content as a new version, preserving the full timeline."""
        reason = _required(reason, "reason")
        historical = self.get_document(document_id, restore_version)
        with self.store.lock:
            current = self.get_document(document_id)
            if current.version != expected_version:
                raise ConflictError(f"stale version: expected {expected_version}, current {current.version}")
            restored = self.update_document(
                document_id, actor_id=actor_id, expected_version=expected_version,
                title=historical.title, content=historical.content,
                source_refs=historical.source_refs,
                metadata={**historical.metadata, "restored_from_version": restore_version, "restore_reason": reason},
            )
            self._audit("document.restored", actor_id, "document", document_id, {
                "restored_from_version": restore_version, "version": restored.version, "reason": reason,
            })
            return restored

    def add_provenance(
        self, *, source_document_id: str, target_document_id: str,
        relation: Relation | str, actor_id: str, source_version: int | None = None,
        target_version: int | None = None, note: str | None = None,
    ) -> ProvenanceEdge:
        relation = Relation(relation)
        actor_id = _required(actor_id, "actor_id")
        if source_document_id == target_document_id:
            raise KnowledgeError("self-referential provenance is not allowed")
        source = self.get_document(source_document_id, source_version)
        target = self.get_document(target_document_id, target_version)
        with self.store.lock:
            duplicate = next((e for e in self.store.edges() if (
                e.source_document_id, e.target_document_id, e.relation, e.source_version, e.target_version
            ) == (source_document_id, target_document_id, relation, source.version, target.version)), None)
            if duplicate:
                return duplicate
            edge = ProvenanceEdge(self.id_factory(), source_document_id, target_document_id, relation, actor_id, self.clock(), source.version, target.version, note)
            self.store.add_edge(edge)
            self._audit("provenance.added", actor_id, "provenance_edge", edge.edge_id, {
                "source_document_id": source_document_id, "target_document_id": target_document_id,
                "relation": relation.value, "source_version": source.version, "target_version": target.version,
            })
            return edge

    def provenance_graph(self, document_id: str, *, direction: str = "both", max_depth: int = 4) -> tuple[ProvenanceEdge, ...]:
        self.get_document(document_id)
        if direction not in {"incoming", "outgoing", "both"}:
            raise KnowledgeError("direction must be incoming, outgoing, or both")
        if max_depth < 0:
            raise KnowledgeError("max_depth cannot be negative")
        edges, found, seen = self.store.edges(), [], set()
        queue = deque([(document_id, 0)])
        visited = {document_id}
        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in edges:
                next_node = None
                if direction in {"outgoing", "both"} and edge.source_document_id == node:
                    next_node = edge.target_document_id
                elif direction in {"incoming", "both"} and edge.target_document_id == node:
                    next_node = edge.source_document_id
                if next_node is not None:
                    if edge.edge_id not in seen:
                        found.append(edge); seen.add(edge.edge_id)
                    if next_node not in visited:
                        visited.add(next_node); queue.append((next_node, depth + 1))
        return tuple(found)

    def provenance_path(self, source_document_id: str, target_document_id: str, *, max_depth: int = 8) -> tuple[ProvenanceEdge, ...]:
        """Find the shortest directed provenance path between two documents."""
        self.get_document(source_document_id)
        self.get_document(target_document_id)
        if max_depth < 1:
            raise KnowledgeError("max_depth must be positive")
        if source_document_id == target_document_id:
            return ()
        outgoing: dict[str, list[ProvenanceEdge]] = {}
        for edge in self.store.edges():
            outgoing.setdefault(edge.source_document_id, []).append(edge)
        queue = deque([(source_document_id, ())])
        visited = {source_document_id}
        while queue:
            node, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for edge in outgoing.get(node, ()):
                candidate = (*path, edge)
                if edge.target_document_id == target_document_id:
                    return candidate
                if edge.target_document_id not in visited:
                    visited.add(edge.target_document_id)
                    queue.append((edge.target_document_id, candidate))
        return ()

    def retrieve(self, query: str, *, limit: int = 10, metadata_filter: Mapping[str, Any] | None = None) -> tuple[SearchHit, ...]:
        query_terms = _terms(_required(query, "query"))
        if limit < 1 or limit > 100:
            raise KnowledgeError("limit must be between 1 and 100")
        documents = [d for d in self.store.all_latest() if all(d.metadata.get(k) == v for k, v in (metadata_filter or {}).items())]
        if not documents:
            return ()
        document_terms = [Counter(_terms(f"{d.title} {d.title} {d.content}")) for d in documents]
        doc_frequency = Counter(term for term in set(query_terms) for counts in document_terms if counts[term])
        hits = []
        for document, counts in zip(documents, document_terms):
            score, matched = 0.0, []
            norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
            for term in dict.fromkeys(query_terms):
                if counts[term]:
                    matched.append(term)
                    score += (1.0 + math.log(counts[term])) * (math.log((len(documents) + 1) / (doc_frequency[term] + 0.5)) + 1.0)
            if score:
                hits.append(SearchHit(document, round(score / norm, 8), tuple(matched)))
        hits.sort(key=lambda hit: (-hit.score, -hit.document.version, hit.document.document_id))
        return tuple(hits[:limit])

    def propose_change(
        self, document_id: str, *, proposer_id: str, base_version: int,
        rationale: str, proposed_title: str | None = None,
        proposed_content: str | None = None,
    ) -> Suggestion:
        proposer_id, rationale = _required(proposer_id, "proposer_id"), _required(rationale, "rationale")
        self.get_document(document_id, base_version)
        if proposed_title is None and proposed_content is None:
            raise KnowledgeError("suggestion must change title or content")
        if proposed_title is not None: _required(proposed_title, "proposed_title")
        if proposed_content is not None: _required(proposed_content, "proposed_content")
        suggestion = Suggestion(self.id_factory(), document_id, base_version, proposed_title, proposed_content, rationale, proposer_id, SuggestionStatus.PENDING, self.clock())
        with self.store.lock:
            self.store.put_suggestion(suggestion)
            self._audit("suggestion.created", proposer_id, "suggestion", suggestion.suggestion_id, {"document_id": document_id, "base_version": base_version})
        return suggestion

    def decide_suggestion(self, suggestion_id: str, *, reviewer_id: str, accept: bool, note: str | None = None) -> Suggestion:
        reviewer_id = _required(reviewer_id, "reviewer_id")
        with self.store.lock:
            suggestion = self.store.suggestion(suggestion_id)
            if suggestion is None:
                raise NotFoundError(f"unknown suggestion: {suggestion_id}")
            if suggestion.status is not SuggestionStatus.PENDING:
                raise ConflictError("suggestion has already been decided")
            resulting_version = None
            if accept:
                current = self.get_document(suggestion.document_id)
                if current.version != suggestion.base_version:
                    raise ConflictError(f"suggestion is stale: based on {suggestion.base_version}, current {current.version}")
                updated = self.update_document(suggestion.document_id, actor_id=reviewer_id, expected_version=current.version, title=suggestion.proposed_title, content=suggestion.proposed_content)
                resulting_version = updated.version
            decided = replace(suggestion, status=SuggestionStatus.ACCEPTED if accept else SuggestionStatus.REJECTED, decided_at=self.clock(), decided_by=reviewer_id, decision_note=note, resulting_version=resulting_version)
            self.store.put_suggestion(decided)
            self._audit("suggestion.accepted" if accept else "suggestion.rejected", reviewer_id, "suggestion", suggestion_id, {"resulting_version": resulting_version, "note": note})
            return decided

    def list_suggestions(self, *, document_id: str | None = None, status: SuggestionStatus | str | None = None) -> tuple[Suggestion, ...]:
        wanted = SuggestionStatus(status) if status is not None else None
        return tuple(s for s in self.store.suggestions() if (document_id is None or s.document_id == document_id) and (wanted is None or s.status is wanted))

    def audit_history(self, *, resource_type: str | None = None, resource_id: str | None = None, actor_id: str | None = None, after_sequence: int = 0, limit: int = 100) -> tuple[AuditEvent, ...]:
        if limit < 1 or limit > 1000:
            raise KnowledgeError("limit must be between 1 and 1000")
        return tuple(event for event in self.store.audit_events() if event.sequence > after_sequence and (resource_type is None or event.resource_type == resource_type) and (resource_id is None or event.resource_id == resource_id) and (actor_id is None or event.actor_id == actor_id))[:limit]

    def document_fingerprint(self, document_id: str, version: int | None = None) -> str:
        doc = self.get_document(document_id, version)
        return sha256(f"{doc.document_id}\0{doc.version}\0{doc.title}\0{doc.content}".encode()).hexdigest()

    def verify_audit_integrity(self) -> bool:
        """Verify sequence continuity and the append-only audit hash chain."""
        previous_hash = ""
        for expected_sequence, event in enumerate(self.store.audit_events(), start=1):
            if event.sequence != expected_sequence or event.previous_hash != previous_hash:
                return False
            if event.event_hash != self._audit_digest(
                event.sequence, event.event_id, event.action, event.actor_id,
                event.occurred_at, event.resource_type, event.resource_id,
                event.details, event.previous_hash,
            ):
                return False
            previous_hash = event.event_hash
        return True

    @staticmethod
    def _audit_digest(sequence: int, event_id: str, action: str, actor_id: str, occurred_at: datetime, resource_type: str, resource_id: str, details: Mapping[str, Any], previous_hash: str) -> str:
        canonical = json.dumps({
            "sequence": sequence, "event_id": event_id, "action": action,
            "actor_id": actor_id, "occurred_at": occurred_at.isoformat(),
            "resource_type": resource_type, "resource_id": resource_id,
            "details": dict(details), "previous_hash": previous_hash,
        }, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(canonical.encode()).hexdigest()

    def _audit(self, action: str, actor_id: str, resource_type: str, resource_id: str, details: Mapping[str, Any]) -> None:
        events = self.store.audit_events()
        sequence = len(events) + 1
        previous_hash = events[-1].event_hash if events else ""
        event_id, occurred_at = self.id_factory(), self.clock()
        frozen_details = dict(details)
        event_hash = self._audit_digest(sequence, event_id, action, actor_id, occurred_at, resource_type, resource_id, frozen_details, previous_hash)
        self.store.append_audit(AuditEvent(sequence, event_id, action, actor_id, occurred_at, resource_type, resource_id, frozen_details, previous_hash, event_hash))
