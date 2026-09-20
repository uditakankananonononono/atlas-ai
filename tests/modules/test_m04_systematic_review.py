from app.modules.m04_research_scientist.evidence_tables import ExtractedFinding, build_evidence_table
from app.modules.m04_research_scientist.models import Paper
from app.modules.m04_research_scientist.systematic_review import ReviewProtocol, ScreeningDecision, ScreeningLedger, screen


def protocol():
    return ReviewProtocol("pr", "Does X improve Y?", ("randomized",), ("animals",))


def test_missing_abstract_is_uncertain_and_conflicts_are_explicit():
    paper = Paper("p", "Trial")
    ledger = screen(protocol(), [paper], "r1", lambda pr, p: ("include", ("randomized",)))
    assert ledger.consensus() == {"p": "uncertain"}
    ledger.record(ScreeningDecision("p", "include", ("full text found",), "r2"))
    assert ledger.consensus() == {"p": "conflict"}
    assert ledger.conflicts()[0].paper_id == "p"


def test_evidence_table_requires_known_paper_and_verbatim_quote():
    paper = Paper("p", "Trial", "abstract", doi="10.1/x")
    finding = ExtractedFinding("f", "p", "X improved Y", "Y", "1.2", "adults", "Y increased by 1.2", "Results", "r1")
    row = build_evidence_table([finding], [paper])[0]
    assert row["doi"] == "10.1/x" and row["evidence_quote"] == "Y increased by 1.2"
