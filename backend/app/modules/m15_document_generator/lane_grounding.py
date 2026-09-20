"""Deterministic source validation and citation assignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .lane_models import Citation, Document, Evidence, GroundedDocument, GroundingError, Source


@dataclass(frozen=True, slots=True)
class GroundingPolicy:
    require_citations: bool = True
    require_exact_quotes: bool = True
    minimum_quote_characters: int = 8
    allow_duplicate_evidence: bool = False

    def __post_init__(self) -> None:
        if self.minimum_quote_characters < 1:
            raise ValueError("minimum quote length must be positive")


class GroundingEngine:
    def __init__(self, policy: GroundingPolicy | None = None) -> None:
        self.policy = policy or GroundingPolicy()

    def ground(self, document: Document) -> GroundedDocument:
        source_map = {source.id: source for source in document.sources}
        citations: list[Citation] = []
        numbers_by_key: dict[tuple[str, str], int] = {}
        claim_citations: dict[tuple[int, int], tuple[int, ...]] = {}

        for section_index, section in enumerate(document.sections):
            for claim_index, claim in enumerate(section.claims):
                if self.policy.require_citations and not claim.evidence:
                    raise GroundingError(
                        f"claim {claim_index + 1} in section {section.heading!r} has no evidence"
                    )
                assigned: list[int] = []
                for evidence in claim.evidence:
                    source = source_map.get(evidence.source_id)
                    if source is None:
                        raise GroundingError(f"unknown source id {evidence.source_id!r}")
                    self._validate_evidence(evidence, source)
                    key = (source.id, evidence.quote)
                    number = numbers_by_key.get(key)
                    if number is None or self.policy.allow_duplicate_evidence:
                        number = len(citations) + 1
                        citations.append(Citation(number, source, evidence.quote))
                        if not self.policy.allow_duplicate_evidence:
                            numbers_by_key[key] = number
                    if number not in assigned:
                        assigned.append(number)
                claim_citations[(section_index, claim_index)] = tuple(assigned)

        return GroundedDocument(document, tuple(citations), claim_citations)

    def _validate_evidence(self, evidence: Evidence, source: Source) -> None:
        quote = evidence.quote.strip()
        if len(quote) < self.policy.minimum_quote_characters:
            raise GroundingError(
                f"evidence from source {source.id!r} is shorter than "
                f"{self.policy.minimum_quote_characters} characters"
            )
        if evidence.start is not None:
            actual = source.content[evidence.start : evidence.end]
            if actual != evidence.quote:
                raise GroundingError(f"offsets do not match quote in source {source.id!r}")
        if self.policy.require_exact_quotes and quote not in source.content:
            raise GroundingError(f"quote was not found in source {source.id!r}")
