from app.modules.m04_research_scientist.lane_api import Paper, ResearchScientistService, SearchQuery, audit_evidence, validate_gap_support


def test_surveillance_delta_and_manuscript_workflow():
    service = ResearchScientistService()
    query = SearchQuery("q", "protein folding")
    papers = [Paper("p1", "Protein folding", "protein structure", doi="10.1/a")]
    first = service.survey(query, lambda q: papers)
    second = service.survey(query, lambda q: papers)
    assert first.new_papers == tuple(papers)
    assert second.new_papers == ()
    assert second.all_papers == tuple(papers)
    validate_gap_support(second.candidate_gaps, second.all_papers)
    manuscript = service.manuscript("Review", second)
    assert "[p1]" in manuscript.markdown


def test_provenance_audit_names_missing_fields():
    audit = audit_evidence([Paper("p", "Title")])[0]
    assert audit.issues == ("no public locator", "abstract unavailable", "publication date unavailable")


def test_retraction_label_becomes_critical_alert_only_when_new():
    service = ResearchScientistService()
    paper = Paper("r", "Retraction: invalid trial", metadata={"status": "retracted"})
    first = service.survey(SearchQuery("retract", "trial"), lambda _: [paper])
    assert first.alerts[0].kind == "retraction"
    assert first.alerts[0].severity == "critical"
    second = service.survey(SearchQuery("retract", "trial"), lambda _: [paper])
    assert second.alerts == ()
