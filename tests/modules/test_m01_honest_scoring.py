from datetime import datetime, timezone

from app.modules.m01_opportunity_discovery.schemas import OpportunityOut, OpportunityType


def test_opportunity_output_names_heuristic_and_denies_probability_semantics():
    item = OpportunityOut(
        id="1", source_id="official", title="Grant", url="https://example.org/grant",
        description="", deadline=None, opportunity_type=OpportunityType.GRANT,
        match_score=0.5, impact_heuristic=0.8, tags=[],
        first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc),
    )
    payload = item.model_dump()
    assert payload["impact_heuristic"] == 0.8
    assert payload["score_kind"] == "heuristic"
    assert payload["advisory_only"] is True
    assert "expected_impact" not in payload and "win_probability" not in payload
