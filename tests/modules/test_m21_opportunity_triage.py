from fastapi.testclient import TestClient
from app.main import app
from app.modules.m21_claire import opportunity_triage


def test_source_linked_cards_keep_unknowns_and_no_external_effects(monkeypatch):
    monkeypatch.setattr(opportunity_triage, "search_and_analyze", lambda *a, **kw: {
        "items": [{"id": "x", "title": "Robotics challenge", "url": "https://official.example/contest",
                   "source_url": "https://official.example/", "platform": "challengerocket",
                   "deadline": {"value": None, "evidence": None}, "award": {"amount": None, "currency": None},
                   "student_level": {"levels": ["high school"]}, "region": {"mentions": []}},
                  {"id": "bad", "title": "credential lure", "url": "https://user:pass@evil.example/x",
                   "source_url": "https://official.example/", "platform": "challengerocket"}],
        "failures": [{"platform": "blocked", "error": "HTTP 429"}], "launch_only": [], "scanned_at": "now"})
    result = opportunity_triage.triage(["challengerocket"], "robotics")
    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["deadline_mentioned"]["value"] is None
    assert card["status"] == "needs_official_rules_and_owner_eligibility_review"
    assert not card["application_submitted"] and not card["outreach_sent"]
    assert result["failures"] and result["external_effects"] == []
    client = TestClient(app)
    response = client.post("/api/v1/claire/opportunities/triage", json={"platform_ids": ["challengerocket"], "query": "robotics"})
    assert response.status_code == 200 and len(response.json()["cards"]) == 1


def test_query_validation():
    import pytest
    with pytest.raises(ValueError):
        opportunity_triage.triage(["challengerocket"], " ")
