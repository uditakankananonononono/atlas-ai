from app.modules.m04_research_scientist.evidence import cluster_papers, detect_evidence_gaps
from app.modules.m04_research_scientist.models import Paper, SearchQuery
from app.modules.m04_research_scientist.snapshots import create_snapshot


def test_snapshot_identity_is_stable_but_timestamp_is_not_identity_input():
    papers = [Paper("p", "Title", "abstract")]
    clusters = cluster_papers(papers)
    gaps = detect_evidence_gaps(papers, clusters)
    a = create_snapshot(SearchQuery("q", "topic", created_at="2026-01-01T00:00:00Z"), papers, clusters, gaps)
    b = create_snapshot(SearchQuery("q", "topic", created_at="2026-01-01T00:00:00Z"), papers, clusters, gaps)
    assert a.snapshot_id == b.snapshot_id
    assert a.papers[0]["paper_id"] == "p"
