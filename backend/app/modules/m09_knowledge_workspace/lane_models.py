from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeError(ValueError):
    """Base error for invalid knowledge workspace operations."""


class NotFoundError(KnowledgeError):
    pass


class ConflictError(KnowledgeError):
    pass


class Relation(str, Enum):
    DERIVED_FROM = "derived_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFERENCES = "references"
    SUPERSEDES = "supersedes"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SourceRef:
    uri: str
    label: str | None = None
    captured_at: datetime = field(default_factory=utcnow)
    checksum: str | None = None

    def __post_init__(self) -> None:
        if not self.uri.strip():
            raise KnowledgeError("source uri cannot be blank")


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    document_id: str
    version: int
    title: str
    content: str
    author_id: str
    created_at: datetime
    source_refs: tuple[SourceRef, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    previous_version: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    edge_id: str
    source_document_id: str
    target_document_id: str
    relation: Relation
    actor_id: str
    created_at: datetime
    source_version: int | None = None
    target_version: int | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    document: DocumentVersion
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Suggestion:
    suggestion_id: str
    document_id: str
    base_version: int
    proposed_title: str | None
    proposed_content: str | None
    rationale: str
    proposer_id: str
    status: SuggestionStatus
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None
    resulting_version: int | None = None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    event_id: str
    action: str
    actor_id: str
    occurred_at: datetime
    resource_type: str
    resource_id: str
    details: Mapping[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    event_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))
