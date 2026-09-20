from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .alerts import ScholarlyAlert, classify_alerts
from .evidence import cluster_papers, detect_evidence_gaps
from .experiments import ExperimentPlan, ExperimentResult, Runner, execute_experiment
from .manuscripts import Manuscript, render_manuscript
from .models import Cluster, EvidenceGap, Paper, SearchQuery
from .lane_surveillance import SurveillanceStore


@dataclass(frozen=True, slots=True)
class SurveillanceReport:
    query: SearchQuery
    new_papers: tuple[Paper, ...]
    all_papers: tuple[Paper, ...]
    clusters: tuple[Cluster, ...]
    candidate_gaps: tuple[EvidenceGap, ...]
    alerts: tuple[ScholarlyAlert, ...]


class ResearchScientistService:
    """Application seam. Transport layers may inject retrieval and execution functions."""

    def __init__(self, store: SurveillanceStore | None = None) -> None:
        self.store = store or SurveillanceStore()

    def survey(self, query: SearchQuery, retrieve: Callable[[SearchQuery], Iterable[Paper]], *, similarity_threshold: float = 0.22) -> SurveillanceReport:
        self.store.save_query(query)
        retrieved = list(retrieve(query))
        new = self.store.ingest(query.query_id, retrieved)
        all_papers = self.store.list_results(query.query_id)
        clusters = cluster_papers(all_papers, similarity_threshold)
        gaps = detect_evidence_gaps(all_papers, clusters)
        return SurveillanceReport(query, tuple(new), tuple(all_papers), tuple(clusters), tuple(gaps), classify_alerts(new))

    def run_experiment(self, plan: ExperimentPlan, runner: Runner, inputs: dict | None = None) -> ExperimentResult:
        return execute_experiment(plan, runner, inputs)

    def manuscript(self, title: str, report: SurveillanceReport, results: Iterable[ExperimentResult] = ()) -> Manuscript:
        return render_manuscript(title, report.all_papers, results, report.candidate_gaps)


MODULE_REGISTRY_ENTRY = {
    "module_id": "04",
    "slug": "research_scientist",
    "factory": ResearchScientistService,
    "capabilities": (
        "scholarly_surveillance", "evidence_clustering", "gap_candidates",
        "experiment_execution", "legal_dataset_ingestion", "reproducible_manuscripts",
    ),
}
