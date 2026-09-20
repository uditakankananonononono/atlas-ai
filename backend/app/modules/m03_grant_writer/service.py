"""Domain logic for proposal drafting, budgeting, analysis, and safe export staging."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Awaitable, Callable
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol
from uuid import uuid4

from app.core.models import ApprovalRequest
from app.core.providers import generate as byok_generate

from .schemas import (
    BudgetLine,
    BudgetRequest,
    BudgetResponse,
    ExportRequest,
    ProposalRequest,
    ProposalResponse,
    ProposedExportResponse,
    StageResult,
    SuccessAnalysisRequest,
    SuccessAnalysisResponse,
)

GenerateFn = Callable[[str, str, str | None], Awaitable[tuple[str, str]]]


class ApprovalSink(Protocol):
    """Minimal approval boundary required by this module."""

    def put(self, item: ApprovalRequest) -> ApprovalRequest: ...


class Service:
    """Build grounded grant drafts while keeping external effects human-controlled."""

    def __init__(self, approval_sink: ApprovalSink, generate_fn: GenerateFn = byok_generate) -> None:
        self._approvals = approval_sink
        self._generate = generate_fn

    async def generate_proposal(self, request: ProposalRequest) -> ProposalResponse:
        """Run research, draft, critique, and revision stages using the shared BYOK provider."""
        evidence = "\n".join(
            f"- {item.title}: {item.summary}" + (f" ({item.source_url})" if item.source_url else "")
            for item in request.evidence
        ) or "No external evidence was supplied. Do not invent sources or past awards."
        stages: list[StageResult] = []

        research_prompt = (
            "Extract the funder's explicit requirements, scoring criteria, key themes, constraints, and "
            "unknowns. Do not invent requirements.\n\nGUIDELINES:\n"
            f"{request.guidelines}\n\nPERMISSIONED EVIDENCE:\n{evidence}"
        )
        research = await self._run_stage("guideline_research", research_prompt, request.provider)
        stages.append(research)

        draft_prompt = (
            "Draft a complete grant or fellowship proposal. Use only the facts provided. Mark missing facts "
            "as [NEEDS INPUT]. Make feasibility, impact, methods, timeline, and evaluation explicit.\n\n"
            f"OPPORTUNITY: {request.opportunity_name}\nAPPLICANT:\n{request.applicant_profile}\n"
            f"PROJECT:\n{request.project_summary}\nGUIDELINE ANALYSIS:\n{research.text}\nEVIDENCE:\n{evidence}"
        )
        draft = await self._run_stage("draft", draft_prompt, request.draft_provider)
        stages.append(draft)

        critique_prompt = (
            "Critique this proposal against the guideline analysis. Score clarity, impact, and feasibility "
            "from 1-10, identify unsupported claims, and list concrete fixes.\n\n"
            f"GUIDELINE ANALYSIS:\n{research.text}\n\nDRAFT:\n{draft.text}"
        )
        critique = await self._run_stage("self_critique", critique_prompt, request.provider)
        stages.append(critique)

        revision_prompt = (
            "Revise the draft using the critique. Preserve factual uncertainty as [NEEDS INPUT], retain no "
            "unsupported claims, and return only the revised proposal.\n\n"
            f"DRAFT:\n{draft.text}\n\nCRITIQUE:\n{critique.text}"
        )
        revision = await self._run_stage("revision", revision_prompt, request.draft_provider)
        stages.append(revision)
        return ProposalResponse(
            opportunity_name=request.opportunity_name,
            proposal=revision.text,
            stages=stages,
        )

    async def _run_stage(self, stage: str, prompt: str, provider: str) -> StageResult:
        """Invoke one BYOK stage and retain model provenance without exposing credentials."""
        model, text = await self._generate(prompt, provider, None)
        if not text.strip():
            raise RuntimeError(f"{stage} returned an empty response")
        return StageResult(stage=stage, provider=provider, model=model, text=text.strip())

    def build_budget(self, request: BudgetRequest) -> BudgetResponse:
        """Calculate a transparent budget without claiming unverified market-rate accuracy."""
        money = Decimal("0.01")
        lines: list[BudgetLine] = []
        direct = Decimal("0")
        for item in request.items:
            total = (Decimal(str(item.quantity)) * Decimal(str(item.unit_cost))).quantize(money, ROUND_HALF_UP)
            direct += total
            lines.append(BudgetLine(**item.model_dump(), total=float(total)))
        direct = direct.quantize(money, ROUND_HALF_UP)
        indirect = (direct * Decimal(str(request.indirect_rate_percent)) / Decimal("100")).quantize(
            money, ROUND_HALF_UP
        )
        return BudgetResponse(
            currency=request.currency.upper(),
            lines=lines,
            direct_total=float(direct),
            indirect_total=float(indirect),
            grand_total=float(direct + indirect),
        )

    def analyze_success(self, request: SuccessAnalysisRequest) -> SuccessAnalysisResponse:
        """Compare language only against examples the user is allowed to use."""
        if not request.funded_examples:
            return SuccessAnalysisResponse(
                comparable_examples=0,
                shared_language=[],
                missing_common_terms=[],
                caveat="No permissioned funded examples were supplied; no success comparison was performed.",
            )
        proposal_terms = set(self._terms(request.proposal))
        corpus_counts = Counter(term for example in request.funded_examples for term in set(self._terms(example)))
        common = [term for term, count in corpus_counts.most_common(30) if count >= max(1, len(request.funded_examples) // 2)]
        return SuccessAnalysisResponse(
            comparable_examples=len(request.funded_examples),
            shared_language=sorted(proposal_terms.intersection(common)),
            missing_common_terms=sorted(set(common).difference(proposal_terms)),
            caveat="Language overlap is diagnostic only and does not predict funding success.",
        )

    def propose_export(self, request: ExportRequest) -> ProposedExportResponse:
        """Stage DOCX/PDF generation; no file is created until the approval center allows it."""
        item = ApprovalRequest(
            id=str(uuid4()),
            module_id=3,
            action_type="generate_grant_documents",
            payload=request.model_dump(),
        )
        stored = self._approvals.put(item)
        return ProposedExportResponse(
            approval_id=stored.id,
            status=stored.status.value,
            action_type=stored.action_type,
            formats=request.formats,
        )

    @staticmethod
    def _terms(text: str) -> list[str]:
        stop = {"about", "after", "again", "also", "been", "being", "from", "have", "into", "that", "their", "there", "these", "this", "with", "would"}
        return [word for word in re.findall(r"[a-z][a-z-]{3,}", text.lower()) if word not in stop]
