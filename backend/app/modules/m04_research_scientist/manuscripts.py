from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .experiments import ExperimentResult
from .models import EvidenceGap, Paper


@dataclass(frozen=True, slots=True)
class Manuscript:
    title: str
    markdown: str
    cited_paper_ids: tuple[str, ...]
    run_ids: tuple[str, ...]


def render_manuscript(title: str, papers: Iterable[Paper], results: Iterable[ExperimentResult], gaps: Iterable[EvidenceGap] = ()) -> Manuscript:
    """Render an auditable Markdown report whose evidence and runs are addressable."""
    if not title.strip():
        raise ValueError("title is required")
    papers = sorted(papers, key=lambda paper: paper.paper_id)
    results = sorted(results, key=lambda result: result.experiment_id)
    gaps = sorted(gaps, key=lambda gap: gap.gap_id)
    lines = [f"# {title}", "", "## Methods"]
    if results:
        for result in results:
            lines.append(f"- `{result.experiment_id}` used run `{result.manifest.run_id}` (seed {result.manifest.seed}, code `{result.manifest.code_version}`).")
    else:
        lines.append("No computational experiments were supplied.")
    lines.extend(["", "## Results"])
    if results:
        for result in results:
            lines.append(f"- {result.primary_metric}: {result.metric_value:g} (n={result.sample_size}) [`{result.manifest.run_id}`]")
    else:
        lines.append("No experiment results were supplied.")
    lines.extend(["", "## Evidence gaps"])
    if gaps:
        for gap in gaps:
            references = ", ".join(f"[{paper_id}]" for paper_id in gap.supporting_paper_ids) or "none"
            lines.append(f"- {gap.statement} Supporting records: {references}. Score: {gap.score:.3f}.")
    else:
        lines.append("No candidate evidence gaps were supplied.")
    lines.extend(["", "## References"])
    if papers:
        for paper in papers:
            locator = paper.doi and f"https://doi.org/{paper.doi}" or paper.url or "no public locator"
            authors = ", ".join(paper.authors) or "Unknown author"
            lines.append(f"- [{paper.paper_id}] {authors}. {paper.title}. {locator}")
    else:
        lines.append("No references were supplied.")
    lines.extend(["", "> Evidence-gap statements are retrieval-dependent heuristic candidates, not proof of absence.", ""])
    return Manuscript(title, "\n".join(lines), tuple(p.paper_id for p in papers), tuple(r.manifest.run_id for r in results))
