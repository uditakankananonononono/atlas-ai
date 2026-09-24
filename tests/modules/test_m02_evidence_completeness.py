"""M02 evidence completeness: every claim links to an owner source or says [NEEDS INPUT]."""
from app.modules.m02_competition_manager.evidence import score_answer, score_package, split_claims

SOURCES = [
    {"id": 11, "source_type": "google_doc", "source_id": "doc-activities", "locator": "p2",
     "text": "In 2025 I founded the Bioplex reading club at my school and grew it to 40 members."},
    {"id": 12, "source_type": "google_sheet", "source_id": "sheet-awards", "locator": "A4",
     "text": "Regional science fair 2024: second place for a protein folding poster."},
]


def test_supported_claims_link_to_exact_sources():
    out = score_answer("impact", "I founded the Bioplex reading club in 2025 and grew it to 40 members. [1] "
                                 "I placed second at the regional science fair in 2024. [2]", SOURCES)
    assert out["score"] == 1.0 and out["complete"] is True
    assert out["claims"][1]["sources"][0] == {"marker": 2, "id": 12, "source_type": "google_sheet",
                                              "source_id": "sheet-awards", "locator": "A4"}


def test_fabricated_number_is_caught_even_with_a_citation():
    out = score_answer("impact", "I grew the Bioplex reading club to 400 members. [1]", SOURCES)
    claim = out["claims"][0]
    assert claim["status"] == "unsupported" and "400" in claim["issues"][0]
    assert out["score"] == 0.0


def test_invented_award_name_is_caught():
    out = score_answer("impact", "I won the Regeneron Science Talent Search in 2024. [2]", SOURCES)
    assert out["claims"][0]["status"] == "unsupported"
    assert "regeneron science talent search" in out["claims"][0]["issues"][0]


def test_uncited_and_dangling_markers_are_flagged():
    out = score_answer("why", "I care deeply about science. I also ran a marathon. [5]", SOURCES)
    statuses = [c["status"] for c in out["claims"]]
    assert statuses == ["uncited", "unsupported"]
    assert "[5] points to no retrieved source" in out["claims"][1]["issues"][0]


def test_needs_input_is_an_honest_gap_not_support():
    out = score_answer("goals", "I founded the Bioplex reading club in 2025. [1] [NEEDS INPUT] what you plan to study.", SOURCES)
    assert out["counts"] == {"claims": 2, "supported": 1, "needs_input": 1, "unsupported": 0}
    assert out["score"] == 1.0 and out["complete"] is False


def test_trailing_marker_after_period_stays_with_its_claim():
    assert split_claims("Built Atlas in 2025. [1] Then more. [2]") == ["Built Atlas in 2025. [1]", "Then more. [2]"]


def test_package_rolls_up_fields():
    pkg = score_package({
        "a": {"draft": "I founded the Bioplex reading club in 2025. [1]", "sources": SOURCES},
        "b": {"draft": "I led a team of 12 engineers at NASA. [1]", "sources": SOURCES},
    })
    assert pkg["overall_score"] == 0.5 and pkg["complete"] is False
    assert pkg["fields"]["b"]["claims"][0]["status"] == "unsupported"


def test_http_endpoint_scores_package(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m02_competition_manager import routes
    monkeypatch.setenv("ATLAS_ENV", "development")
    app = FastAPI(); app.include_router(routes.router)
    res = TestClient(app).post("/competition-manager/evidence-completeness", json={"fields": {
        "a": {"draft": "I founded the Bioplex reading club in 2025. [1]", "sources": SOURCES}}})
    assert res.status_code == 200 and res.json()["complete"] is True
