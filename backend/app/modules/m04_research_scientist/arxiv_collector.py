"""Real arXiv collector: queries the public arXiv Atom API and returns PaperInput rows.

REAL network fetch from a fixed host (export.arxiv.org). It is a collector only; the
embedding and gap logic live in surveillance.py. Not covered: PubMed, bioRxiv,
Nature/Science, custom journals. Transport is injectable for tests only.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from urllib.parse import urlencode

import httpx

from .schemas import PaperInput

ARXIV_API = "https://export.arxiv.org/api/query"
MAX_BYTES = 5_000_000
_NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
_QUERY_RE = re.compile(r"^[\w\s\-.:\"()*+']{3,300}$")
_ID_RE = re.compile(r"arxiv\.org/abs/(.+)$")


class ArxivCollectorError(RuntimeError):
    pass


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def parse_arxiv_atom(payload: bytes) -> list[PaperInput]:
    if len(payload) > MAX_BYTES:
        raise ArxivCollectorError("response too large")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ArxivCollectorError("DTD not allowed")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ArxivCollectorError("malformed Atom response") from exc
    papers: list[PaperInput] = []
    for entry in root.findall("a:entry", _NS):
        url = _clean(entry.findtext("a:id", namespaces=_NS))
        m = _ID_RE.search(url)
        title = _clean(entry.findtext("a:title", namespaces=_NS))
        abstract = _clean(entry.findtext("a:summary", namespaces=_NS))
        if not m or len(title) < 3 or len(abstract) < 20:
            continue  # arXiv error entries and stubs are skipped, not invented
        cats = [c.get("term") for c in entry.findall("a:category", _NS) if c.get("term")]
        papers.append(PaperInput(
            paper_id="arxiv:" + m.group(1), title=title[:1000], abstract=abstract[:50_000],
            source="arxiv", url=url, published_at=_clean(entry.findtext("a:published", namespaces=_NS)) or None,
            keywords=cats[:50]))
    return papers


def collect_arxiv(query: str, max_results: int = 20, *,
                  fetch: Callable[[str], bytes] | None = None) -> list[PaperInput]:
    if not _QUERY_RE.match(query or ""):
        raise ValueError("query must be 3-300 plain characters")
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be 1-50")
    if not re.findall(r"\w[\w\-.]*", query):
        raise ValueError("query needs at least one word")
    url = ARXIV_API + "?" + urlencode({"search_query": " AND ".join(f"all:{t}" for t in re.findall(r"\w[\w\-.]*", query)), "start": 0,
                                       "max_results": max_results, "sortBy": "submittedDate",
                                       "sortOrder": "descending"})
    if fetch is None:
        def fetch(u: str) -> bytes:
            with httpx.Client(timeout=30, follow_redirects=False) as c:
                r = c.get(u, headers={"User-Agent": "atlas-m04-surveillance/1"})
            if r.status_code != 200:
                raise ArxivCollectorError(f"arXiv returned HTTP {r.status_code}")
            return r.content
    return parse_arxiv_atom(fetch(url))
