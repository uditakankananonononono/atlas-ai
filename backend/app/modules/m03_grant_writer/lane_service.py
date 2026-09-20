from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping

from .lane_models import (
    Budget, BudgetLine, BudgetRate, BudgetRequestLine, CritiqueItem, GrantReport,
    GroundingHit, ProposalSection, ReportPart, ReviewApproval, ReviewHandoff,
    Severity, ValidationError,
)
from .lane_repository import GrantCorpus

_MONEY = Decimal("0.01")
_WORD = re.compile(r"\b[\w'-]+\b")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def canonical_json(value: object) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class GrantWriterService:
    def __init__(self, corpus: GrantCorpus, rates: Iterable[BudgetRate]) -> None:
        self.corpus = corpus
        grouped: dict[str, list[BudgetRate]] = {}
        for rate in rates:
            grouped.setdefault(rate.code, []).append(rate)
        self._rates = {code: tuple(sorted(items, key=lambda x: (x.effective_from, x.observed_at))) for code, items in grouped.items()}

    def retrieve_grounding(
        self, opportunity_id: str, project_summary: str, *, as_of: datetime, limit: int = 8
    ) -> tuple[GroundingHit, ...]:
        opportunity = self.corpus.get_opportunity(opportunity_id, as_of=as_of)
        query = " ".join((opportunity.title, opportunity.sponsor, *opportunity.priorities, project_summary))
        return self.corpus.search(query, as_of=as_of, limit=limit)

    def critique(
        self,
        opportunity_id: str,
        sections: Iterable[ProposalSection],
        grounding: Iterable[GroundingHit],
        *,
        as_of: datetime,
    ) -> tuple[CritiqueItem, ...]:
        opportunity = self.corpus.get_opportunity(opportunity_id, as_of=as_of)
        parts = tuple(sections)
        evidence = {h.document_id for h in grounding}
        items: list[CritiqueItem] = []
        present = {p.name.lower(): p for p in parts}
        for required in ("need", "approach", "outcomes", "evaluation"):
            if required not in present:
                items.append(CritiqueItem(
                    code="missing_section", severity=Severity.ERROR, section=required,
                    message=f"Required section '{required}' is missing.",
                    suggestion=f"Add a {required} section tied to the funder's stated priorities.",
                ))
        for part in parts:
            words = _WORD.findall(part.text)
            if len(words) < 35:
                items.append(CritiqueItem(
                    code="underdeveloped", severity=Severity.WARNING, section=part.name,
                    message=f"Section has only {len(words)} words.",
                    suggestion="Add concrete activities, ownership, timing, and measurable details.",
                ))
            unknown = tuple(sorted(set(part.citation_ids) - evidence))
            if unknown:
                items.append(CritiqueItem(
                    code="ungrounded_citation", severity=Severity.ERROR, section=part.name,
                    message=f"Unknown evidence ids: {', '.join(unknown)}.",
                    suggestion="Remove these citations or retrieve the cited sources into the grounding set.",
                    evidence_ids=unknown,
                ))
            numeric_claim = bool(re.search(r"\b\d+(?:\.\d+)?%?\b", part.text))
            if numeric_claim and not part.citation_ids:
                items.append(CritiqueItem(
                    code="unsupported_numeric_claim", severity=Severity.ERROR, section=part.name,
                    message="The section contains a numeric claim without evidence.",
                    suggestion="Attach a corpus evidence id or remove/qualify the numeric claim.",
                ))
        joined = " ".join(p.text.lower() for p in parts)
        for priority in opportunity.priorities:
            keywords = [w for w in _WORD.findall(priority.lower()) if len(w) > 3]
            if keywords and not any(w in joined for w in keywords):
                items.append(CritiqueItem(
                    code="priority_gap", severity=Severity.WARNING, section="overall",
                    message=f"Funder priority is not addressed: {priority}",
                    suggestion="Explain the direct connection to this priority using project-specific facts.",
                ))
        return tuple(items)

    def revise(
        self,
        sections: Iterable[ProposalSection],
        replacements: Mapping[str, str],
        grounding: Iterable[GroundingHit],
    ) -> tuple[ProposalSection, ...]:
        """Apply explicit replacements without inventing evidence or rewriting untouched text."""
        evidence = {h.document_id for h in grounding}
        revised: list[ProposalSection] = []
        found: set[str] = set()
        for section in sections:
            text = replacements.get(section.name, section.text).strip()
            found.add(section.name)
            unknown = set(section.citation_ids) - evidence
            if unknown:
                raise ValidationError(f"section {section.name} cites unavailable evidence: {sorted(unknown)}")
            if not text:
                raise ValidationError(f"revision would empty section: {section.name}")
            revised.append(ProposalSection(section.name, text, section.citation_ids))
        extras = set(replacements) - found
        if extras:
            raise ValidationError(f"replacements name unknown sections: {sorted(extras)}")
        return tuple(revised)

    def build_budget(
        self,
        requests: Iterable[BudgetRequestLine],
        *,
        as_of: date,
        observed_by: datetime,
        indirect_rate: Decimal = Decimal("0"),
    ) -> Budget:
        if not Decimal("0") <= indirect_rate <= Decimal("1"):
            raise ValidationError("indirect_rate must be between 0 and 1")
        lines: list[BudgetLine] = []
        currency: str | None = None
        for request in requests:
            candidates = [
                rate for rate in self._rates.get(request.rate_code, ())
                if rate.effective_from <= as_of
                and (rate.effective_to is None or as_of <= rate.effective_to)
                and rate.observed_at <= observed_by
            ]
            if not candidates:
                raise ValidationError(f"no current, observed rate for {request.rate_code} on {as_of}")
            rate = max(candidates, key=lambda x: (x.effective_from, x.observed_at))
            if currency is not None and rate.currency != currency:
                raise ValidationError("mixed-currency budgets are not supported")
            currency = rate.currency
            total = _money(rate.amount * request.quantity)
            lines.append(BudgetLine(
                rate_code=rate.code, description=request.description, quantity=request.quantity,
                unit=rate.unit, unit_amount=rate.amount, total=total, currency=rate.currency,
                rate_effective_from=rate.effective_from, source_url=rate.source_url,
            ))
        if not lines:
            raise ValidationError("budget requires at least one line")
        direct = _money(sum((line.total for line in lines), Decimal("0")))
        indirect = _money(direct * indirect_rate)
        return Budget(tuple(lines), currency or "", direct, indirect, direct + indirect, indirect_rate, as_of)

    def build_report(
        self,
        opportunity_id: str,
        sections: Iterable[ProposalSection],
        budget: Budget,
        grounding: Iterable[GroundingHit],
        *,
        as_of: datetime,
    ) -> GrantReport:
        sections = tuple(sections)
        grounding = tuple(grounding)
        critique = self.critique(opportunity_id, sections, grounding, as_of=as_of)
        parts = [ReportPart(i + 1, "proposal", section.name, section.text, section.citation_ids) for i, section in enumerate(sections)]
        budget_text = "\n".join(
            f"{line.description}: {line.quantity} {line.unit} × {line.unit_amount} {line.currency} = {line.total} {line.currency}"
            for line in budget.lines
        )
        parts.append(ReportPart(len(parts) + 1, "budget", "Budget", budget_text))
        critique_text = "\n".join(f"[{x.severity.value}] {x.section}: {x.message}" for x in critique) or "No deterministic checks failed."
        parts.append(ReportPart(len(parts) + 1, "critique", "Review findings", critique_text))
        return GrantReport(opportunity_id, as_of, tuple(parts), budget, critique, grounding)

    def prepare_review_handoff(
        self, report: GrantReport, *, recipient: str, action: str, created_at: datetime
    ) -> ReviewHandoff:
        if not recipient.strip() or not action.strip():
            raise ValidationError("review handoff requires an exact recipient and action")
        artifact_json = canonical_json(asdict(report))
        digest = hashlib.sha256(artifact_json.encode("utf-8")).hexdigest()
        return ReviewHandoff(str(uuid.uuid4()), digest, artifact_json, recipient.strip(), action.strip(), created_at)

    def approve_handoff(
        self,
        handoff: ReviewHandoff,
        *,
        reviewed_artifact_json: str,
        reviewer: str,
        approved_at: datetime,
    ) -> ReviewApproval:
        """Approve only the exact immutable payload shown to the reviewer."""
        digest = hashlib.sha256(reviewed_artifact_json.encode("utf-8")).hexdigest()
        if digest != handoff.artifact_sha256 or reviewed_artifact_json != handoff.artifact_json:
            raise ValidationError("reviewed artifact differs from handoff; prepare a new review")
        if not reviewer.strip():
            raise ValidationError("reviewer is required")
        return ReviewApproval(handoff.handoff_id, digest, reviewer.strip(), approved_at)

    @staticmethod
    def assert_dispatchable(handoff: ReviewHandoff, approval: ReviewApproval, artifact_json: str) -> None:
        digest = hashlib.sha256(artifact_json.encode("utf-8")).hexdigest()
        if approval.handoff_id != handoff.handoff_id or approval.artifact_sha256 != digest or digest != handoff.artifact_sha256:
            raise ValidationError("artifact lacks exact-review approval")
