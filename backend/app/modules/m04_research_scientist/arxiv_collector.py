"""Real arXiv collector: queries the public arXiv Atom API and returns PaperInput rows.

REAL network fetch from a fixed host (export.arxiv.org). It is a collector only; the
embedding and gap logic live in surveillance.py. Not covered: PubMed, bioRxiv,
Nature/Science, custom journals. Transport is injectable for tests only.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urlencode

import httpx
from defusedxml import ElementTree as DET
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError

from .schemas import PaperInput
from .source_throttle import THROTTLE

ARXIV_API = "https://export.arxiv.org/api/query"
MAX_BYTES = 5_000_000


def capped_get(url: str, cap: int, err: type) -> bytes:
    """Stream the body and stop at `cap` bytes; never follow redirects."""
    with httpx.Client(timeout=30, follow_redirects=False) as c:
        with c.stream("GET", url, headers={"User-Agent": "atlas-m04-surveillance/1"}) as r:
            if r.status_code != 200:
                raise err(f"HTTP {r.status_code}")
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf += chunk
                if len(buf) > cap:
                    raise err("response too large")
            return bytes(buf)
_NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
_QUERY_RE = re.compile(r"^[\w\s\-.:\"()*+']{3,300}$")
_ID_RE = re.compile(r"^https?://arxiv\.org/abs/((?:[a-z\-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?)$")


class ArxivCollectorError(RuntimeError):
    pass


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def parse_arxiv_atom(payload: bytes) -> list[PaperInput]:
    if len(payload) > MAX_BYTES:
        raise ArxivCollectorError("response too large")
    try:
        root = DET.fromstring(payload, forbid_dtd=True)  # decodes first, so UTF-16 cannot hide a DTD
    except DefusedXmlException as exc:
        raise ArxivCollectorError("DTD or entities not allowed") from exc
    except ParseError as exc:
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
            return capped_get(u, MAX_BYTES, ArxivCollectorError)
    return parse_arxiv_atom(THROTTLE.run("arxiv", lambda: fetch(url)))
