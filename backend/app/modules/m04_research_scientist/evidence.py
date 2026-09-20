from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from itertools import combinations

from .models import Cluster, EvidenceGap, Paper

TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")
STOP = frozenset("the and for with from this that are was were have has into using use study studies results method methods between among our their".split())


def tokenize(text: str) -> list[str]:
    return [word.lower() for word in TOKEN.findall(text) if word.lower() not in STOP]


def _vectors(papers: list[Paper]) -> tuple[list[dict[str, float]], Counter[str]]:
    docs = [Counter(tokenize(f"{p.title} {p.abstract}")) for p in papers]
    document_frequency = Counter(term for doc in docs for term in doc)
    vectors = []
    for doc in docs:
        normed = {term: (1 + math.log(count)) * math.log((1 + len(docs)) / (1 + document_frequency[term])) + 1
                  for term, count in doc.items()}
        norm = math.sqrt(sum(value * value for value in normed.values())) or 1
        vectors.append({term: value / norm for term, value in normed.items()})
    return vectors, document_frequency


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(term, 0.0) for term, value in a.items())


def cluster_papers(papers: list[Paper], similarity_threshold: float = 0.22) -> list[Cluster]:
    """Deterministic connected-component clustering over TF-IDF similarity."""
    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be between 0 and 1")
    if not papers:
        return []
    papers = sorted(papers, key=lambda p: p.paper_id)
    vectors, _ = _vectors(papers)
    adjacency: dict[int, set[int]] = defaultdict(set)
    for left, right in combinations(range(len(papers)), 2):
        if _cosine(vectors[left], vectors[right]) >= similarity_threshold:
            adjacency[left].add(right)
            adjacency[right].add(left)
    components, seen = [], set()
    for start in range(len(papers)):
        if start in seen:
            continue
        stack, component = [start], []
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node); component.append(node); stack.extend(sorted(adjacency[node] - seen, reverse=True))
        components.append(sorted(component))
    result = []
    for component in components:
        counts = Counter(term for i in component for term in tokenize(f"{papers[i].title} {papers[i].abstract}"))
        keywords = tuple(term for term, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5])
        ids = tuple(papers[i].paper_id for i in component)
        digest = hashlib.sha256("\0".join(ids).encode()).hexdigest()[:12]
        result.append(Cluster(f"cluster-{digest}", " / ".join(keywords[:3]) or "uncategorized", ids, keywords))
    return result


def detect_evidence_gaps(papers: list[Paper], clusters: list[Cluster], *, sparse_cluster_size: int = 1) -> list[EvidenceGap]:
    """Produce traceable candidate gaps; claims are explicitly heuristic, not truth assertions."""
    by_id = {paper.paper_id: paper for paper in papers}
    gaps: list[EvidenceGap] = []
    for cluster in clusters:
        if len(cluster.paper_ids) <= sparse_cluster_size:
            statement = f"Sparse evidence around {cluster.label}: only {len(cluster.paper_ids)} indexed paper(s)."
            gaps.append(EvidenceGap(f"gap-sparse-{cluster.cluster_id[8:]}", "sparse_cluster", statement,
                                    cluster.paper_ids, 1 / (1 + len(cluster.paper_ids)), {"heuristic": True}))
    for cluster in clusters:
        dated = [by_id[i] for i in cluster.paper_ids if by_id[i].published_at]
        undated = [i for i in cluster.paper_ids if not by_id[i].published_at]
        if undated and dated:
            gaps.append(EvidenceGap(f"gap-date-{cluster.cluster_id[8:]}", "missing_metadata",
                                    f"Publication dates are missing for {len(undated)} paper(s) in {cluster.label}.",
                                    tuple(undated), len(undated) / len(cluster.paper_ids), {"field": "published_at"}))
    return sorted(gaps, key=lambda gap: (-gap.score, gap.gap_id))
