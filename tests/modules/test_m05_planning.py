"""Offline tests for scoped outreach planning (audiences, PR, survey, proposals)."""

import asyncio
from datetime import datetime, timezone

import pytest

from app.modules.m05_outreach_manager.planning import (
    AUDIENCE_PROFILES,
    DEFAULT_SURVEY_QUESTION,
    OutreachScope,
    PRTarget,
    ProjectSummary,
    ScopeViolationError,
    audience_prompt_profile,
    build_micro_survey,
    draft_proposal,
    plan_campaign,
    plan_pr_outreach,
)
from app.modules.m05_outreach_manager.schemas import ContactCreate
from app.modules.m05_outreach_manager.service import InMemoryContactRepository, Service


def make_contact(email=None, verified=False, name="Dr. Rao"):
    repo = InMemoryContactRepository()
    service = Service(repo, None, scholar=None)
    metadata = {}
    if verified:
        metadata = {"enrichment": {"email_verified": True}}
    return service.create_contact(
        ContactCreate(project_id="p", name=name, email=email, metadata=metadata)
    )


def make_contacts(specs):
    repo = InMemoryContactRepository()
    service = Service(repo, None, scholar=None)
    contacts = []
    for email, verified in specs:
        metadata = {"enrichment": {"email_verified": True}} if verified else {}
        contacts.append(
            service.create_contact(
                ContactCreate(project_id="p", name=email or "No Email", email=email, metadata=metadata)
            )
        )
    return contacts


def test_plan_stages_name_every_approval_gate():
    contacts = make_contacts([("a@x.edu", True), ("b@y.edu", True)])
    plan = plan_campaign(goal="Find supervisors", audience="professor", contacts=contacts)
    gated = {step.stage: step.approval_action_type for step in plan.steps if step.requires_approval}
    assert gated["review"] == "send_outreach_email"
    assert gated["send"] == "send_outreach_email"
    assert gated["follow_up"] == "send_follow_up"
    assert [assignment.position for assignment in plan.assignments] == [1, 2]
    assert any("provider-verified" in check for check in plan.scope_checks)


def test_max_contacts_cap_is_enforced():
    contacts = make_contacts([("a@x.edu", True), ("b@y.edu", True), ("c@z.edu", True)])
    with pytest.raises(ScopeViolationError, match="exceeds the scope cap of 2"):
        plan_campaign(
            goal="g",
            audience="professor",
            contacts=contacts,
            scope=OutreachScope(max_contacts=2),
        )


def test_per_domain_cap_is_enforced():
    contacts = make_contacts(
        [("a@big.edu", True), ("b@big.edu", True), ("c@big.edu", True), ("d@other.edu", True)]
    )
    with pytest.raises(ScopeViolationError, match="per-domain cap 2 exceeded.*big.edu"):
        plan_campaign(
            goal="g",
            audience="professor",
            contacts=contacts,
            scope=OutreachScope(per_domain_cap=2),
        )


def test_verified_email_scope_is_enforced():
    contacts = make_contacts([("a@x.edu", True), ("b@y.edu", False)])
    with pytest.raises(ScopeViolationError, match="lack a provider-verified email"):
        plan_campaign(goal="g", audience="professor", contacts=contacts)

    plan = plan_campaign(
        goal="g",
        audience="professor",
        contacts=contacts,
        scope=OutreachScope(require_verified_email=False),
    )
    assert any("verification not required" in check for check in plan.scope_checks)


def test_manual_channels_are_handoffs_not_automation():
    contacts = make_contacts([("a@x.edu", True)])
    plan = plan_campaign(
        goal="g",
        audience="professional",
        contacts=contacts,
        manual_channels=["email", "linkedin", "discord"],
    )
    assert plan.manual_channels == ["discord", "linkedin"]
    assert any("manual handoffs" in check for check in plan.scope_checks)


def test_audience_profiles_cover_all_ledger_audiences():
    for audience in ("professor", "researcher", "professional", "student", "press"):
        profile = audience_prompt_profile(audience)
        assert profile["tone"] and profile["guidance"]
    with pytest.raises(ValueError, match="unknown audience"):
        audience_prompt_profile("celebrity")


def test_pr_plan_with_embargo_gate():
    targets = [
        PRTarget(outlet="TechDaily", contact_name="A. Writer", email="a@techdaily.example", beat="AI"),
        PRTarget(outlet="ScienceWeek", contact_name="B. Editor", email="b@scienceweek.example"),
    ]
    embargo = datetime(2026, 10, 1, tzinfo=timezone.utc)
    plan = plan_pr_outreach(goal="Launch coverage", targets=targets, embargo=embargo)
    assert plan.audience == "press" and plan.kind == "pr_pitch"
    stages = [step.stage for step in plan.steps]
    assert "embargo" in stages
    assert stages.index("embargo") < stages.index("send")
    assert plan.assignments[0].contact_id == "pr:TechDaily"

    with pytest.raises(ValueError, match="at least one supplied target"):
        plan_pr_outreach(goal="g", targets=[])


def test_micro_survey_uses_the_exact_question_and_survey_kind():
    contacts = make_contacts([("a@x.edu", True)])
    plan = build_micro_survey(goal="Tool wishes", contacts=contacts)
    assert plan.kind == "survey"
    assert any(DEFAULT_SURVEY_QUESTION in check for check in plan.scope_checks)
    action_types = {step.approval_action_type for step in plan.steps if step.approval_action_type}
    assert "send_micro_survey" in action_types

    with pytest.raises(ValueError, match="must not be empty"):
        build_micro_survey(goal="g", contacts=contacts, question="   ")


def test_proposal_is_grounded_in_supplied_facts_only():
    captured = {}

    async def fake_generate(prompt, provider, model):
        captured["prompt"] = prompt
        return model or "test-model", "Subject: Partnership on Atlas\nProposal body."

    project = ProjectSummary(
        name="Atlas",
        problem="Students miss deadlines",
        solution="An approval-gated planning agent",
        evidence=["200 beta users supplied by the project record"],
        ask="Intro to university innovation offices",
    )
    draft = asyncio.run(
        draft_proposal(project=project, recipient_context="Innovation office director", llm_generate=fake_generate)
    )

    assert draft.subject == "Partnership on Atlas"
    prompt = captured["prompt"]
    assert "ONLY the supplied project facts" in prompt
    assert "200 beta users supplied by the project record" in prompt
    assert "Innovation office director" in prompt

    with pytest.raises(ValueError, match="recipient context is required"):
        asyncio.run(draft_proposal(project=project, recipient_context="  ", llm_generate=fake_generate))
