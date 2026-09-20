"""Offline tests for Module 3, Grant & Fellowship Writer."""

import asyncio
import sys
from dataclasses import dataclass
from types import ModuleType

# The current foundation snapshot has not yet landed the shared ModuleSpec file.
# Supply its documented shape only for isolated lane testing; INTEGRATION.md requests the shared file.
if "app.modules.types" not in sys.modules:
    types_module = ModuleType("app.modules.types")

    @dataclass(frozen=True)
    class ModuleSpec:
        id: int
        slug: str
        name: str
        router: object
        service_type: type

    types_module.ModuleSpec = ModuleSpec
    sys.modules["app.modules.types"] = types_module

from app.modules.m03_grant_writer import spec
from app.modules.m03_grant_writer.schemas import (
    BudgetItem,
    BudgetRequest,
    ExportRequest,
    ProposalRequest,
    SuccessAnalysisRequest,
)
from app.modules.m03_grant_writer.service import Service


class FakeApprovals:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)
        return item


async def fake_generate(prompt: str, provider: str, model: str | None):
    fake_generate.calls.append((prompt, provider, model))
    return f"{provider}-test-model", f"output-{len(fake_generate.calls)}"


fake_generate.calls = []


def test_spec_and_successful_pipeline_use_injected_byok_boundary():
    fake_generate.calls.clear()
    service = Service(FakeApprovals(), generate_fn=fake_generate)
    response = asyncio.run(
        service.generate_proposal(
            ProposalRequest(
                opportunity_name="Research Fellowship",
                guidelines="Explain impact, feasibility, methods, evaluation, and applicant fit.",
                applicant_profile="A researcher with permissioned experience in public-interest data science.",
                project_summary="Build and evaluate a reproducible method for measuring local air quality.",
            )
        )
    )
    assert (spec.id, spec.slug, spec.name) == (3, "grant-writer", "Grant & Fellowship Writer")
    assert [stage.stage for stage in response.stages] == [
        "guideline_research",
        "draft",
        "self_critique",
        "revision",
    ]
    assert response.proposal == "output-4"
    assert response.requires_human_review is True
    assert len(fake_generate.calls) == 4


def test_budget_is_deterministic_and_marks_rates_for_verification():
    result = Service(FakeApprovals(), fake_generate).build_budget(
        BudgetRequest(
            currency="usd",
            items=[BudgetItem(category="Compute", description="GPU hours", quantity=2.5, unit_cost=10.01)],
            indirect_rate_percent=10,
        )
    )
    assert result.direct_total == 25.03
    assert result.indirect_total == 2.50
    assert result.grand_total == 27.53
    assert result.requires_rate_verification is True


def test_export_is_queued_for_approval_and_never_rendered_directly():
    approvals = FakeApprovals()
    result = Service(approvals, fake_generate).propose_export(
        ExportRequest(title="Proposal", proposal="A sufficiently long proposal body for export review.")
    )
    assert result.status == "pending"
    assert result.action_type == "generate_grant_documents"
    assert len(approvals.items) == 1
    assert approvals.items[0].module_id == 3


def test_success_analysis_refuses_to_infer_without_permissioned_examples():
    result = Service(FakeApprovals(), fake_generate).analyze_success(
        SuccessAnalysisRequest(proposal="A sufficiently detailed proposal body with measurable impact.")
    )
    assert result.comparable_examples == 0
    assert result.shared_language == []
    assert "no success comparison" in result.caveat.lower()


def test_empty_model_output_fails_closed():
    async def empty_generate(prompt: str, provider: str, model: str | None):
        return "test-model", "   "

    service = Service(FakeApprovals(), empty_generate)
    request = ProposalRequest(
        opportunity_name="Research Fellowship",
        guidelines="Explain impact, feasibility, methods, evaluation, and applicant fit.",
        applicant_profile="A researcher with permissioned experience in public-interest data science.",
        project_summary="Build and evaluate a reproducible method for measuring local air quality.",
    )
    try:
        asyncio.run(service.generate_proposal(request))
    except RuntimeError as exc:
        assert "empty response" in str(exc)
    else:
        raise AssertionError("empty model output must fail closed")
