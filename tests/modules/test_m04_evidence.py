from app.modules.m04_research_scientist.evidence import cluster_papers, detect_evidence_gaps
from app.modules.m04_research_scientist.models import Paper


def test_cluster_is_deterministic_and_gap_is_traceable():
    papers = [
        Paper("b", "Protein folding model", "protein structure prediction neural", published_at="2026"),
        Paper("a", "Neural protein structure", "protein folding prediction network", published_at="2025"),
        Paper("c", "Forest beetle census", "tree mortality field ecology"),
    ]
    clusters = cluster_papers(papers, 0.15)
    assert cluster_papers(list(reversed(papers)), 0.15) == clusters
    grouped = [set(c.paper_ids) for c in clusters]
    assert {"a", "b"} in grouped and {"c"} in grouped
    gaps = detect_evidence_gaps(papers, clusters)
    assert any(g.kind == "sparse_cluster" and g.supporting_paper_ids == ("c",) for g in gaps)


def test_empty_and_bad_threshold():
    assert cluster_papers([]) == []
    try:
        cluster_papers([], 1.1)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid threshold accepted")
