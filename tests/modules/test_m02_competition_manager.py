"""Offline tests for Module 2 domain behavior."""

import asyncio
import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import APIRouter

# The supplied snapshot predates the shared ModuleSpec file required by conventions.
# This compatibility shim is test-only; INTEGRATION.md asks the integrator to add it.
if "app.modules.types" not in sys.modules:
    shared_types = types.ModuleType("app.modules.types")

    @dataclass(frozen=True)
    class ModuleSpec:
        id: int
        slug: str
        name: str
        router: APIRouter
        service_type: type[Any]

    shared_types.ModuleSpec = ModuleSpec
    sys.modules["app.modules.types"] = shared_types

from app.modules.m02_competition_manager.schemas import (  # noqa: E402
    CompetitionCreate,
    FormFillProposalRequest,
    StatusEvidence,
    SubmissionStatus,
)
from app.modules.m02_competition_manager.service import (  # noqa: E402
    RuleExtractionError,
    Service,
    UnsafeStatusTransitionError,
)


def test_extracts_rules_and_builds_checklist_with_mocked_provider() -> None:
    async def fake_generate(
        prompt: str, provider: str, model: str | None
    ) -> tuple[str, str]:
        assert "OFFICIAL RULES" in prompt
        return (
            "mock-model",
            """```json
{"summary":"Build a climate prototype.","eligibility_criteria":["Students"],"required_materials":["abstract","video pitch"],"deadlines":["2026-10-15T23:59:00Z"],"evaluation_criteria":["impact","feasibility"]}
```""",
        )

    service = Service(generator=fake_generate)
    result = asyncio.run(service.create_competition(
        CompetitionCreate(
            name="Climate Challenge",
            official_rules_url="https://example.org/official-rules",
            official_rules_text="Students must submit an abstract and video pitch by October 15. "
            "Entries are judged for impact and feasibility.",
        )
    ))

    assert result.rules.eligibility_criteria == ["Students"]
    assert [item.title for item in result.checklist] == [
        "Prepare abstract",
        "Prepare video pitch",
    ]
    assert all(item.due_hint == "2026-10-15T23:59:00Z" for item in result.checklist)


def test_rejects_invalid_model_output() -> None:
    async def fake_generate(
        prompt: str, provider: str, model: str | None
    ) -> tuple[str, str]:
        return "mock-model", "not json"

    service = Service(generator=fake_generate)
    with pytest.raises(RuleExtractionError):
        asyncio.run(service.create_competition(
            CompetitionCreate(
                name="Bad output",
                official_rules_url="https://example.org/rules",
                official_rules_text="These are long enough official competition rules for testing.",
            )
        ))


def test_form_fill_is_only_a_proposal_and_status_requires_valid_evidence() -> None:
    async def fake_generate(
        prompt: str, provider: str, model: str | None
    ) -> tuple[str, str]:
        return (
            "mock-model",
            '{"summary":"Summary","eligibility_criteria":[],"required_materials":[],"deadlines":[],"evaluation_criteria":[]}',
        )

    service = Service(generator=fake_generate)
    competition = asyncio.run(service.create_competition(
        CompetitionCreate(
            name="Safe challenge",
            official_rules_url="https://example.org/rules",
            official_rules_text="Official rules with sufficient detail for the extraction request.",
        )
    ))
    proposal = service.propose_form_fill(
        competition.id,
        FormFillProposalRequest(
            form_url="https://example.org/apply",
            fields={"abstract": "Reviewed draft"},
        ),
    )

    assert proposal.requires_approval is True
    assert proposal.execution_performed is False
    assert "separate explicit approval" in proposal.payload["instructions"]

    with pytest.raises(UnsafeStatusTransitionError):
        service.update_status(
            competition.id,
            StatusEvidence(
                source="manual",
                reference="No submission receipt exists",
                observed_at=datetime.now(timezone.utc),
                status=SubmissionStatus.ACCEPTED,
            ),
        )

def test_form_fill_contract_targets_browser_agent_without_executing():
    from app.modules.m02_competition_manager.routes import router
    paths={route.path for route in router.routes}
    assert "/competition-manager/competitions/{competition_id}/form-fill-proposals" in paths
    # M13 owns execution; M2 remains proposal-only and therefore cannot click submit itself.
    assert not hasattr(Service,"submit_form")
