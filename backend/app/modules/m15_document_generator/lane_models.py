"""Domain models for Atlas' grounded document generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class DocumentError(ValueError):
    """Base error for invalid document generation requests."""


class GroundingError(DocumentError):
    """Raised when claims cannot be grounded in supplied sources."""


class TemplateError(DocumentError):
    """Raised when a template cannot be rendered safely."""


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    title: str
    content: str
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DocumentError("source id must not be empty")
        if not self.title.strip():
            raise DocumentError("source title must not be empty")
        if not self.content.strip():
            raise DocumentError(f"source {self.id!r} has no content")
        if self.url and not self.url.startswith(("http://", "https://")):
            raise DocumentError("source URL must use http or https")


@dataclass(frozen=True, slots=True)
class Evidence:
    source_id: str
    quote: str
    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.quote.strip():
            raise DocumentError("evidence needs a source id and quote")
        if (self.start is None) != (self.end is None):
            raise DocumentError("evidence offsets must be supplied together")
        if self.start is not None and (self.start < 0 or self.end <= self.start):
            raise DocumentError("invalid evidence offsets")


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise DocumentError("claim text must not be empty")


@dataclass(frozen=True, slots=True)
class Section:
    heading: str
    claims: tuple[Claim, ...]
    level: int = 2
    prose: str | None = None

    def __post_init__(self) -> None:
        if not self.heading.strip():
            raise DocumentError("section heading must not be empty")
        if not 1 <= self.level <= 6:
            raise DocumentError("section heading level must be between 1 and 6")
        if not self.claims and not (self.prose and self.prose.strip()):
            raise DocumentError("section must contain prose or claims")


@dataclass(frozen=True, slots=True)
class Document:
    title: str
    sections: tuple[Section, ...]
    sources: tuple[Source, ...] = ()
    subtitle: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise DocumentError("document title must not be empty")
        if not self.sections:
            raise DocumentError("document needs at least one section")
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise DocumentError("source ids must be unique")


@dataclass(frozen=True, slots=True)
class Citation:
    number: int
    source: Source
    quote: str


@dataclass(frozen=True, slots=True)
class GroundedDocument:
    document: Document
    citations: tuple[Citation, ...]
    claim_citations: Mapping[tuple[int, int], tuple[int, ...]]

    def citation_numbers(self, section_index: int, claim_index: int) -> tuple[int, ...]:
        return self.claim_citations.get((section_index, claim_index), ())
