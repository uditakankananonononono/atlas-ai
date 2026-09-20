from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from threading import RLock
from typing import Iterable

from .lane_models import AuditEvent, DocumentVersion, ProvenanceEdge, Suggestion


class InMemoryKnowledgeStore:
    """Thread-safe repository. The service owns validation and audit semantics.

    It is intentionally replaceable by a database adapter: returned objects are
    immutable and collections are copied, so callers cannot mutate stored state.
    """

    def __init__(self) -> None:
        self._documents: dict[str, list[DocumentVersion]] = defaultdict(list)
        self._edges: dict[str, ProvenanceEdge] = {}
        self._suggestions: dict[str, Suggestion] = {}
        self._audit: list[AuditEvent] = []
        self.lock = RLock()

    def versions(self, document_id: str) -> tuple[DocumentVersion, ...]:
        with self.lock:
            return tuple(self._documents.get(document_id, ()))

    def all_latest(self) -> tuple[DocumentVersion, ...]:
        with self.lock:
            return tuple(versions[-1] for versions in self._documents.values() if versions)

    def append_version(self, value: DocumentVersion) -> None:
        with self.lock:
            self._documents[value.document_id].append(value)

    def add_edge(self, value: ProvenanceEdge) -> None:
        with self.lock:
            self._edges[value.edge_id] = value

    def edges(self) -> tuple[ProvenanceEdge, ...]:
        with self.lock:
            return tuple(self._edges.values())

    def put_suggestion(self, value: Suggestion) -> None:
        with self.lock:
            self._suggestions[value.suggestion_id] = value

    def suggestion(self, suggestion_id: str) -> Suggestion | None:
        with self.lock:
            return self._suggestions.get(suggestion_id)

    def suggestions(self) -> tuple[Suggestion, ...]:
        with self.lock:
            return tuple(self._suggestions.values())

    def append_audit(self, value: AuditEvent) -> None:
        with self.lock:
            self._audit.append(value)

    def audit_events(self) -> tuple[AuditEvent, ...]:
        with self.lock:
            return tuple(self._audit)
