from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from .models import Paper


@dataclass(frozen=True, slots=True)
class ReviewProtocol:
    protocol_id: str
    research_question: str
    inclusion_criteria: tuple[str, ...]
    exclusion_criteria: tuple[str, ...]
    required_fields: tuple[str, ...] = ("title", "abstract")

    def __post_init__(self) -> None:
        if not self.protocol_id.strip() or not self.research_question.strip():
            raise ValueError("protocol_id and research_question are required")
        if not self.inclusion_criteria:
            raise ValueError("at least one inclusion criterion is required")


@dataclass(frozen=True, slots=True)
class ScreeningDecision:
    paper_id: str
    decision: Literal["include", "exclude", "uncertain"]
    reasons: tuple[str, ...]
    reviewer: str


@dataclass(frozen=True, slots=True)
class ScreeningConflict:
    paper_id: str
    decisions: tuple[ScreeningDecision, ...]


class ScreeningLedger:
    def __init__(self, protocol: ReviewProtocol) -> None:
        self.protocol = protocol
        self._decisions: dict[str, dict[str, ScreeningDecision]] = {}

    def record(self, decision: ScreeningDecision) -> None:
        if not decision.reviewer.strip() or not decision.reasons:
            raise ValueError("reviewer and reasons are required")
        by_reviewer = self._decisions.setdefault(decision.paper_id, {})
        if decision.reviewer in by_reviewer:
            raise ValueError(f"reviewer {decision.reviewer!r} already screened {decision.paper_id!r}")
        by_reviewer[decision.reviewer] = decision

    def conflicts(self) -> tuple[ScreeningConflict, ...]:
        found = []
        for paper_id, mapping in sorted(self._decisions.items()):
            decisions = tuple(mapping[key] for key in sorted(mapping))
            if len({item.decision for item in decisions}) > 1:
                found.append(ScreeningConflict(paper_id, decisions))
        return tuple(found)

    def consensus(self) -> dict[str, str]:
        result = {}
        for paper_id, mapping in sorted(self._decisions.items()):
            decisions = {item.decision for item in mapping.values()}
            result[paper_id] = next(iter(decisions)) if len(decisions) == 1 else "conflict"
        return result


Screener = Callable[[ReviewProtocol, Paper], ScreeningDecision]


def screen(protocol: ReviewProtocol, papers: Iterable[Paper], reviewer: str, decide: Callable[[ReviewProtocol, Paper], tuple[str, Iterable[str]]]) -> ScreeningLedger:
    """Apply an injected human/model rule while forcing per-paper reasons into an audit ledger."""
    ledger = ScreeningLedger(protocol)
    for paper in sorted(papers, key=lambda item: item.paper_id):
        missing = tuple(field for field in protocol.required_fields if not getattr(paper, field, None))
        if missing:
            ledger.record(ScreeningDecision(paper.paper_id, "uncertain", (f"missing required fields: {', '.join(missing)}",), reviewer))
            continue
        decision, reasons = decide(protocol, paper)
        if decision not in {"include", "exclude", "uncertain"}:
            raise ValueError(f"invalid screening decision: {decision}")
        ledger.record(ScreeningDecision(paper.paper_id, decision, tuple(reasons), reviewer))
    return ledger
