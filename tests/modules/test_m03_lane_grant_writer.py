from datetime import date, datetime, timezone
from decimal import Decimal
import json
import pytest

from app.modules.m03_grant_writer.lane_models import (
    BudgetRate, BudgetRequestLine, CorpusDocument, Opportunity, ProposalSection,
    ValidationError,
)
from app.modules.m03_grant_writer.lane_repository import GrantCorpus
from app.modules.m03_grant_writer.lane_service import GrantWriterService

UTC = timezone.utc
NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


def service():
    opportunity = Opportunity(
        "opp", "Community Health Fund", "Example Foundation",
        datetime(2026, 12, 1, tzinfo=UTC), ("nonprofit",),
        ("measurable health access", "community leadership"), "https://fund.test/opp",
        "Supports measurable health access led by community partners.",
        datetime(2026, 9, 1, tzinfo=UTC),
    )
    docs = [
        CorpusDocument("baseline", "Clinic baseline", "A community survey found 40 percent lack local screening access. Community leaders requested mobile clinics.", "https://data.test/base", datetime(2026, 8, 2, tzinfo=UTC), ("health",)),
        CorpusDocument("evaluation", "Evaluation guide", "Measure completed screenings, referrals, and follow-up outcomes monthly.", "https://data.test/eval", datetime(2026, 8, 5, tzinfo=UTC), ("health",)),
        CorpusDocument("future", "Future study", "Screening access improves dramatically.", "https://data.test/future", datetime(2027, 1, 1, tzinfo=UTC), ("health",)),
    ]
    rates = [
        BudgetRate("nurse_hour", "Nurse", "hour", Decimal("40"), "USD", date(2025, 1, 1), "https://rates.test/old", datetime(2025, 1, 1, tzinfo=UTC), date(2026, 6, 30)),
        BudgetRate("nurse_hour", "Nurse", "hour", Decimal("52.255"), "USD", date(2026, 7, 1), "https://rates.test/current", datetime(2026, 7, 2, tzinfo=UTC)),
        BudgetRate("nurse_hour", "Nurse", "hour", Decimal("99"), "USD", date(2027, 1, 1), "https://rates.test/future", datetime(2026, 9, 1, tzinfo=UTC)),
    ]
    return GrantWriterService(GrantCorpus([opportunity], docs), rates)


def complete_sections():
    text = "Community partners will lead mobile clinics and document activities, timing, ownership, measurable outcomes, and monthly follow-up for residents. " * 3
    return (
        ProposalSection("need", text + "Survey evidence shows 40 percent lack access.", ("baseline",)),
        ProposalSection("approach", text, ("baseline",)),
        ProposalSection("outcomes", text, ("evaluation",)),
        ProposalSection("evaluation", text, ("evaluation",)),
    )


def test_retrieval_is_grounded_and_excludes_future_observations():
    hits = service().retrieve_grounding("opp", "mobile clinic health screening outcomes", as_of=NOW)
    assert [hit.document_id for hit in hits] == ["baseline", "evaluation"]
    assert all(hit.source_url.startswith("https://") for hit in hits)
    assert all(hit.observed_at <= NOW for hit in hits)


def test_critique_detects_structure_priority_and_unsupported_claims():
    svc = service()
    hits = svc.retrieve_grounding("opp", "health", as_of=NOW)
    critique = svc.critique("opp", [ProposalSection("need", "Reach 90% of people")], hits, as_of=NOW)
    codes = {item.code for item in critique}
    assert {"missing_section", "underdeveloped", "unsupported_numeric_claim", "priority_gap"}.issubset(codes)


def test_revision_is_controlled_and_rejects_unknown_evidence_or_sections():
    svc = service()
    hits = svc.retrieve_grounding("opp", "health", as_of=NOW)
    sections = [ProposalSection("need", "old text", ("baseline",))]
    assert svc.revise(sections, {"need": "new grounded text"}, hits)[0].text == "new grounded text"
    with pytest.raises(ValidationError, match="unknown sections"):
        svc.revise(sections, {"other": "x"}, hits)
    with pytest.raises(ValidationError, match="unavailable evidence"):
        svc.revise([ProposalSection("need", "x", ("made-up",))], {}, hits)


def test_budget_uses_latest_current_observed_rate_and_decimal_rounding():
    budget = service().build_budget(
        [BudgetRequestLine("nurse_hour", Decimal("3.5"), "Clinic nursing")],
        as_of=date(2026, 9, 20), observed_by=NOW, indirect_rate=Decimal("0.10"),
    )
    assert budget.lines[0].unit_amount == Decimal("52.255")
    assert budget.lines[0].total == Decimal("182.89")
    assert budget.indirect_total == Decimal("18.29")
    assert budget.grand_total == Decimal("201.18")
    assert budget.lines[0].source_url == "https://rates.test/current"


def test_budget_rejects_absent_current_rate_and_bad_indirect_rate():
    svc = service()
    with pytest.raises(ValidationError, match="no current"):
        svc.build_budget([BudgetRequestLine("missing", Decimal("1"), "x")], as_of=date(2026, 9, 20), observed_by=NOW)
    with pytest.raises(ValidationError, match="between 0 and 1"):
        svc.build_budget([BudgetRequestLine("nurse_hour", Decimal("1"), "x")], as_of=date(2026, 9, 20), observed_by=NOW, indirect_rate=Decimal("1.2"))


def test_multipart_report_and_exact_review_handoff_blocks_changed_payload():
    svc = service()
    hits = svc.retrieve_grounding("opp", "mobile clinic health outcomes", as_of=NOW)
    budget = svc.build_budget([BudgetRequestLine("nurse_hour", Decimal("10"), "Nursing")], as_of=NOW.date(), observed_by=NOW)
    report = svc.build_report("opp", complete_sections(), budget, hits, as_of=NOW)
    assert [p.kind for p in report.parts][-2:] == ["budget", "critique"]
    assert [p.order for p in report.parts] == list(range(1, len(report.parts) + 1))
    handoff = svc.prepare_review_handoff(report, recipient="grants@foundation.test", action="submit proposal", created_at=NOW)
    approval = svc.approve_handoff(handoff, reviewed_artifact_json=handoff.artifact_json, reviewer="Udita", approved_at=NOW)
    svc.assert_dispatchable(handoff, approval, handoff.artifact_json)
    changed = handoff.artifact_json.replace("Nursing", "Changed line")
    with pytest.raises(ValidationError, match="differs"):
        svc.approve_handoff(handoff, reviewed_artifact_json=changed, reviewer="Udita", approved_at=NOW)
    with pytest.raises(ValidationError, match="exact-review"):
        svc.assert_dispatchable(handoff, approval, changed)
