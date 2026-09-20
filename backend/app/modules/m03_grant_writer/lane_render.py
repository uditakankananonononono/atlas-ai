from __future__ import annotations

from html import escape

from .lane_models import GrantReport


def render_markdown(report: GrantReport) -> str:
    """Render a complete, ordered review artifact with a source appendix."""
    chunks = [f"# Grant report: {report.opportunity_id}", ""]
    for part in sorted(report.parts, key=lambda item: item.order):
        chunks.extend((f"## {part.title}", part.content, ""))
        if part.evidence_ids:
            chunks.extend(("Evidence: " + ", ".join(f"[{item}]" for item in part.evidence_ids), ""))
    chunks.extend(("## Sources", ""))
    if report.grounding:
        for hit in report.grounding:
            chunks.append(f"- [{hit.document_id}] {hit.title}: {hit.source_url} (observed {hit.observed_at.isoformat()})")
    else:
        chunks.append("- No sources retrieved.")
    chunks.extend(("", "## Budget rate sources", ""))
    for line in report.budget.lines:
        chunks.append(f"- {line.rate_code}: {line.source_url} (effective {line.rate_effective_from.isoformat()})")
    chunks.append("")
    return "\n".join(chunks)
