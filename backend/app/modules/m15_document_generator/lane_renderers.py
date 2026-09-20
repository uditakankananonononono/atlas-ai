"""Render grounded documents to portable, deterministic formats."""
from __future__ import annotations

from html import escape
import json
import re
from typing import Any

from .lane_models import GroundedDocument


def _marker(numbers: tuple[int, ...]) -> str:
    return "".join(f"[{number}]" for number in numbers)


def render_markdown(grounded: GroundedDocument) -> str:
    doc = grounded.document
    lines = [f"# {doc.title}"]
    if doc.subtitle:
        lines.extend(("", f"_{doc.subtitle}_"))
    for si, section in enumerate(doc.sections):
        lines.extend(("", f"{'#' * section.level} {section.heading}"))
        if section.prose:
            lines.extend(("", section.prose.strip()))
        for ci, claim in enumerate(section.claims):
            marker = _marker(grounded.citation_numbers(si, ci))
            lines.extend(("", f"{claim.text.strip()}{marker}"))
    if grounded.citations:
        lines.extend(("", "## References"))
        for citation in grounded.citations:
            source = citation.source
            title = f"[{source.title}]({source.url})" if source.url else source.title
            details = [title]
            if source.author:
                details.append(source.author)
            if source.published_at:
                details.append(source.published_at.date().isoformat())
            lines.extend(("", f"{citation.number}. {' - '.join(details)}. “{citation.quote}”"))
    return "\n".join(lines).strip() + "\n"


def _inline_markdown(text: str) -> str:
    """Render only a deliberately small safe markdown subset."""
    result = escape(text)
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    result = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"<em>\1</em>", result)
    result = re.sub(r"`([^`]+)`", r"<code>\1</code>", result)
    return result.replace("\n", "<br>\n")


def render_html(grounded: GroundedDocument) -> str:
    doc = grounded.document
    output = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
              f"<title>{escape(doc.title)}</title></head><body>",
              f"<h1>{escape(doc.title)}</h1>"]
    if doc.subtitle:
        output.append(f'<p class="subtitle">{escape(doc.subtitle)}</p>')
    for si, section in enumerate(doc.sections):
        level = section.level
        output.append(f"<h{level}>{escape(section.heading)}</h{level}>")
        if section.prose:
            output.append(f"<p>{_inline_markdown(section.prose.strip())}</p>")
        for ci, claim in enumerate(section.claims):
            markers = []
            for number in grounded.citation_numbers(si, ci):
                markers.append(f'<sup><a href="#ref-{number}">[{number}]</a></sup>')
            output.append(f"<p>{_inline_markdown(claim.text.strip())}{''.join(markers)}</p>")
    if grounded.citations:
        output.append("<h2>References</h2><ol>")
        for citation in grounded.citations:
            source = citation.source
            title = escape(source.title)
            if source.url:
                title = f'<a href="{escape(source.url, quote=True)}">{title}</a>'
            metadata = []
            if source.author:
                metadata.append(escape(source.author))
            if source.published_at:
                metadata.append(source.published_at.date().isoformat())
            suffix = f" - {' - '.join(metadata)}" if metadata else ""
            output.append(
                f'<li id="ref-{citation.number}">{title}{suffix}. '
                f'<q>{escape(citation.quote)}</q></li>'
            )
        output.append("</ol>")
    output.append("</body></html>")
    return "\n".join(output) + "\n"


def render_text(grounded: GroundedDocument) -> str:
    doc = grounded.document
    lines = [doc.title, "=" * len(doc.title)]
    if doc.subtitle:
        lines.extend((doc.subtitle, ""))
    for si, section in enumerate(doc.sections):
        lines.extend((section.heading, "-" * len(section.heading)))
        if section.prose:
            lines.append(section.prose.strip())
        for ci, claim in enumerate(section.claims):
            lines.append(f"{claim.text.strip()}{_marker(grounded.citation_numbers(si, ci))}")
        lines.append("")
    if grounded.citations:
        lines.append("REFERENCES")
        for citation in grounded.citations:
            source = citation.source
            link = f" ({source.url})" if source.url else ""
            lines.append(f"[{citation.number}] {source.title}{link}: \"{citation.quote}\"")
    return "\n".join(lines).strip() + "\n"


def render_json(grounded: GroundedDocument, *, indent: int | None = 2) -> str:
    doc = grounded.document
    payload: dict[str, Any] = {
        "title": doc.title,
        "subtitle": doc.subtitle,
        "created_at": doc.created_at.isoformat(),
        "metadata": dict(doc.metadata),
        "sections": [],
        "citations": [],
    }
    for si, section in enumerate(doc.sections):
        payload["sections"].append({
            "heading": section.heading,
            "level": section.level,
            "prose": section.prose,
            "claims": [
                {"text": claim.text, "citations": list(grounded.citation_numbers(si, ci))}
                for ci, claim in enumerate(section.claims)
            ],
        })
    for citation in grounded.citations:
        payload["citations"].append({
            "number": citation.number,
            "source_id": citation.source.id,
            "title": citation.source.title,
            "url": citation.source.url,
            "author": citation.source.author,
            "published_at": citation.source.published_at.isoformat() if citation.source.published_at else None,
            "quote": citation.quote,
        })
    return json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True) + "\n"
