"""Domain logic for literature clustering, hypothesis drafting, and safe analysis proposals."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Awaitable, Callable
from itertools import combinations
from typing import TypeAlias

from app.core.providers import generate
from .schemas import (
    AnalysisProposalRequest,
    Cluster,
    HypothesisRequest,
    HypothesisResponse,
    PaperInput,
    ProposedAnalysis,
    SurveillanceResponse,
)

GenerateFunction: TypeAlias = Callable[[str, str, str | None], Awaitable[tuple[str, str]]]

_STOPWORDS = {
    "about", "after", "also", "among", "based", "before", "between", "both",
    "could", "data", "from", "have", "into", "more", "paper", "results", "show",
    "study", "than", "that", "their", "these", "this", "using", "were", "which",
    "with", "within",
}


class Service:
    """Research workflows with explicit dependencies and no import-time network work."""

    def __init__(self, generate_func: GenerateFunction = generate) -> None:
        self._generate = generate_func

    @staticmethod
    def _terms(paper: PaperInput) -> set[str]:
        text = f"{paper.title} {paper.abstract} {' '.join(paper.keywords)}".lower()
        return {
            word for word in re.findall(r"[a-z][a-z0-9-]{3,}", text)
            if word not in _STOPWORDS
        }

    def cluster_papers(
        self, papers: list[PaperInput], similarity_threshold: float = 0.22
    ) -> SurveillanceResponse:
        """Cluster papers using connected components over transparent Jaccard similarity."""
        by_id = {paper.paper_id: paper for paper in papers}
        if len(by_id) != len(papers):
            raise ValueError("paper_id values must be unique")
        terms = {paper.paper_id: self._terms(paper) for paper in papers}
        neighbors = {paper.paper_id: set() for paper in papers}
        for left, right in combinations(papers, 2):
            union = terms[left.paper_id] | terms[right.paper_id]
            score = len(terms[left.paper_id] & terms[right.paper_id]) / len(union) if union else 0.0
            if score >= similarity_threshold:
                neighbors[left.paper_id].add(right.paper_id)
                neighbors[right.paper_id].add(left.paper_id)

        clusters: list[Cluster] = []
        visited: set[str] = set()
        unclustered: list[str] = []
        for paper in papers:
            if paper.paper_id in visited:
                continue
            stack = [paper.paper_id]
            component: list[str] = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                stack.extend(sorted(neighbors[current] - visited, reverse=True))
            component.sort()
            if len(component) == 1:
                unclustered.extend(component)
                continue
            counts = Counter(term for item in component for term in terms[item])
            shared = [term for term, count in counts.most_common() if count > 1][:8]
            label = " / ".join(shared[:3]) if shared else "related literature"
            clusters.append(Cluster(
                cluster_id=f"cluster-{len(clusters) + 1}",
                label=label,
                paper_ids=component,
                shared_terms=shared,
            ))
        return SurveillanceResponse(clusters=clusters, unclustered_paper_ids=unclustered)

    async def generate_hypothesis(self, request: HypothesisRequest) -> HypothesisResponse:
        """Draft a testable hypothesis through the shared BYOK model provider."""
        sources = "\n\n".join(
            f"[{paper.paper_id}] {paper.title}\n{paper.abstract}" for paper in request.papers
        )
        prompt = (
            "Act as a careful research assistant. Based only on the supplied abstracts, "
            "propose one novel but testable hypothesis. State the independent variable, "
            "dependent variable, expected direction, a falsification criterion, and a small "
            "computational experiment. Cite evidence only with the supplied [paper_id] labels. "
            "Do not claim that novelty, causality, or factual correctness has been verified. "
            f"Potential public dataset catalogs: {', '.join(request.dataset_catalogs)}.\n\n"
            f"Research question: {request.research_question}\n\nAbstracts:\n{sources}"
        )
        model, text = await self._generate(prompt, request.provider, request.model)
        return HypothesisResponse(
            hypothesis=text,
            provider=request.provider.lower(),
            model=model,
            evidence_paper_ids=[paper.paper_id for paper in request.papers],
            dataset_catalogs=list(request.dataset_catalogs),
            caveats=[
                "Generated hypothesis requires expert review and independent literature validation.",
                "Dataset licenses, consent terms, and intended-use restrictions must be checked before use.",
            ],
        )

    @staticmethod
    def propose_analysis(request: AnalysisProposalRequest) -> ProposedAnalysis:
        """Return an inert approval-gated proposal rather than executing generated code."""
        if request.network_access:
            raise ValueError("analysis execution proposals must disable network access")
        return ProposedAnalysis(
            objective=request.objective,
            language=request.language,
            code=request.code,
            dataset_urls=[str(url) for url in request.dataset_urls],
        )
