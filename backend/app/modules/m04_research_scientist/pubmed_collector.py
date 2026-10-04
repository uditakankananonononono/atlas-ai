"""Real PubMed collector via NCBI E-utilities (esearch + efetch). Free, official, no key.

Limits: <=3 requests/second without an API key (enforced by source_throttle). NCBI also
asks for registered `tool` and `email` values; this code sends tool=atlas-m04 and an email
only if ATLAS_NCBI_EMAIL is set. Registration with NCBI has NOT been done, so unattended
heavy use may be blocked. Large jobs should run on weekends or 9pm-5am US Eastern.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable
from urllib.parse import urlencode

from defusedxml import ElementTree as DET
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError

from pydantic import ValidationError

from .schemas import PaperInput
from .source_throttle import THROTTLE

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
MAX_BYTES = 10_000_000
_QUERY_RE = re.compile(r"^[\w\s\-.:\"()*+'\[\]]{3,300}$")


class PubmedCollectorError(RuntimeError):
    pass


def _clean(t: str | None) -> str:
    return " ".join((t or "").split())


def _params(extra: dict) -> str:
    p = {"tool": "atlas-m04", **extra}
    if os.getenv("ATLAS_NCBI_EMAIL"):
        p["email"] = os.environ["ATLAS_NCBI_EMAIL"]
    return urlencode(p)


def _default_fetch(url: str) -> bytes:
    from .arxiv_collector import capped_get
    return capped_get(url, MAX_BYTES, PubmedCollectorError)


def parse_pubmed_xml(payload: bytes) -> list[PaperInput]:
    try:  # PubMed XML carries a DOCTYPE, so allow the DTD but forbid entities and external refs
        root = DET.fromstring(payload, forbid_dtd=False, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise PubmedCollectorError("entities not allowed") from exc
    except ParseError as exc:
        raise PubmedCollectorError("malformed PubMed XML") from exc
    out: list[PaperInput] = []
    for art in root.findall("./PubmedArticle"):
        pmid = _clean(art.findtext("./MedlineCitation/PMID"))
        title = _clean("".join(art.find("./MedlineCitation/Article/ArticleTitle").itertext())) \
            if art.find("./MedlineCitation/Article/ArticleTitle") is not None else ""
        parts = ["".join(a.itertext()) for a in art.findall("./MedlineCitation/Article/Abstract/AbstractText")]
        abstract = _clean(" ".join(parts))
        if not pmid.isdigit() or len(title) < 3 or len(abstract) < 20:
            continue  # records without an abstract are skipped, never filled in
        year = _clean(art.findtext("./MedlineCitation/Article/Journal/JournalIssue/PubDate/Year")) or None
        kws = [_clean(m.findtext("./DescriptorName")) for m in art.findall("./MedlineCitation/MeshHeadingList/MeshHeading")]
        try:
            out.append(PaperInput(paper_id="pubmed:" + pmid, title=title[:1000], abstract=abstract[:50_000],
                              source="pubmed", url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                              published_at=year, keywords=[k for k in kws if k][:50]))
        except ValidationError as exc:
            raise PubmedCollectorError("upstream record failed validation") from exc
    return out


def collect_pubmed(query: str, max_results: int = 20, *,
                   fetch: Callable[[str], bytes] | None = None) -> list[PaperInput]:
    if not _QUERY_RE.match(query or ""):
        raise ValueError("query must be 3-300 plain characters")
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be 1-50")
    raw = fetch or _default_fetch
    call = lambda u: THROTTLE.run("pubmed", lambda: raw(u))  # noqa: E731
    s = call(BASE + "esearch.fcgi?" + _params({"db": "pubmed", "term": query, "retmax": max_results,
                                                "retmode": "json", "sort": "pub_date"}))
    import json
    try:
        ids = json.loads(s)["esearchresult"]["idlist"]
    except (ValueError, KeyError, TypeError) as exc:
        raise PubmedCollectorError("unexpected esearch response") from exc
    ids = [i for i in ids if isinstance(i, str) and i.isdigit()][:max_results]
    if not ids:
        return []
    x = call(BASE + "efetch.fcgi?" + _params({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}))
    return parse_pubmed_xml(x)
