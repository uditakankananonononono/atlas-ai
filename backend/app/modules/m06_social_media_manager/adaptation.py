"""Cross-platform content adaptation preview (M06 enhancement).

One source text is adapted into several platform drafts. Shortening for X or
reshaping for LinkedIn is where facts drift: a figure changes, a cited claim
loses its source, or a new unsupported number appears. This preview compares
every draft with the source and reports, per platform:

- ``limits``: the existing compliance engine (caption length, hashtags,
  thread split, disclosure) plus the actual X thread chunks;
- ``claims``: which source claims (sentences carrying a figure or a
  citation) the draft keeps, and whether a kept cited claim still carries
  its citation (URL, domain, ``[n]`` marker or reference title);
- ``unsupported_figures``: numbers in the draft that appear nowhere in the
  source - an error, because that is how a stat gets distorted;
- ``parity``: a claim x platform matrix so the reviewer can see at a glance
  where a claim appears with or without its source.

Pure and deterministic: no network, no model, nothing is posted.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from .compliance import PLATFORM_LIMITS, split_x_thread, validate_draft

_URL = re.compile(r"https?://[^\s)>\]]+")
_MARKER = re.compile(r"\[(\d{1,3})\]")
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?\s?(?:%|x\b|k\b|m\b|million\b|billion\b)?", re.IGNORECASE)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\"'(#@0-9])")
_WORD = re.compile(r"[a-z][a-z'-]{3,}")
_STOP = frozenset("""this that with from have were been their there which about would could should
into also because while where when what your they them then than these those very more most such each
other only over under after before during being does make made many much some through within without
across between will just like post thread read more link here today""".split())
_THREAD_SUFFIX = re.compile(r"\s\d{1,2}/\d{1,2}$")


def _norm_num(raw: str) -> str:
    s = raw.lower().replace(",", "").replace(" ", "")
    for word, sym in (("million", "m"), ("billion", "b")):
        s = s.replace(word, sym)
    return s


def figures(text: str) -> set[str]:
    body = _URL.sub(" ", _MARKER.sub(" ", text))
    body = _THREAD_SUFFIX.sub("", body)
    out = set()
    for m in _NUM.finditer(body):
        n = _norm_num(m.group(0))
        if re.fullmatch(r"\d", n):  # lone single digits ("3 ways", "1/5") are too noisy to police
            continue
        out.add(n)
    return out


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(_URL.sub(" ", text.lower())) if w not in _STOP}


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def source_claims(source: str, references: dict[int, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Sentences in the source that carry a figure, a URL or a citation marker."""
    references = references or {}
    claims = []
    for para in re.split(r"\n\s*\n|\n", source.strip()):
        for sent in (s.strip() for s in _SENT.split(" ".join(para.split())) if s.strip()):
            urls = _URL.findall(sent)
            markers = [int(m) for m in _MARKER.findall(sent)]
            figs = figures(sent)
            if not (urls or markers or figs):
                continue
            cites = []
            for u in urls:
                cites.append({"url": u, "domain": _domain(u)})
            for m in markers:
                ref = references.get(m, {})
                cites.append({"marker": m, "url": ref.get("url"), "domain": _domain(ref["url"]) if ref.get("url") else None,
                              "title": ref.get("title")})
            claims.append({"id": f"c{len(claims) + 1}", "text": sent, "figures": sorted(figs),
                           "words": _words(sent), "citations": cites})
    return claims


def _cited_in(draft: str, cite: dict[str, Any]) -> bool:
    low = draft.lower()
    if cite.get("url") and cite["url"].lower() in low:
        return True
    if cite.get("domain") and cite["domain"] in low:
        return True
    if cite.get("marker") and f"[{cite['marker']}]" in draft:
        return True
    title = (cite.get("title") or "").strip().lower()
    return bool(title) and title in low


def _claim_kept(claim: dict[str, Any], draft: str, draft_figs: set[str], draft_words: set[str]) -> bool:
    if claim["figures"]:
        return any(f in draft_figs for f in claim["figures"])
    if not claim["words"]:
        return False
    return len(claim["words"] & draft_words) / len(claim["words"]) >= 0.5


def preview(source: str, drafts: list[dict[str, Any]], *, references: dict[int, dict[str, str]] | None = None,
            sponsored: bool = False) -> dict[str, Any]:
    """``drafts``: [{platform, format, post_copy, media_count?, alt_texts?}]."""
    claims = source_claims(source, references)
    src_figs = figures(source)
    platforms: list[dict[str, Any]] = []
    parity: dict[str, dict[str, str]] = {c["id"]: {} for c in claims}
    for d in drafts:
        platform, fmt, copy = d["platform"], d.get("format", "post"), d["post_copy"]
        issues = [asdict(i) for i in validate_draft(platform, fmt, copy, sponsored=sponsored,
                                                    media_count=int(d.get("media_count", 0)),
                                                    alt_texts=int(d.get("alt_texts", 0)))]
        chunks = split_x_thread(copy) if platform == "twitter" else [copy]
        limit = PLATFORM_LIMITS.get(platform, {}).get("caption_chars")
        draft_figs, draft_words = figures(copy), _words(copy)
        kept = []
        for c in claims:
            if not _claim_kept(c, copy, draft_figs, draft_words):
                parity[c["id"]][platform] = "dropped"
                continue
            if not c["citations"]:
                parity[c["id"]][platform] = "kept"
                kept.append({"claim": c["id"], "cited": None})
                continue
            ok = any(_cited_in(copy, ct) for ct in c["citations"])
            parity[c["id"]][platform] = "kept_cited" if ok else "kept_uncited"
            kept.append({"claim": c["id"], "cited": ok})
            if not ok:
                hint = next((ct.get("url") or ct.get("title") or f"[{ct.get('marker')}]" for ct in c["citations"]), "")
                issues.append({"code": "citation_dropped", "severity": "error",
                               "message": f"keeps claim {c['id']} but drops its source ({hint})"})
        unsupported = sorted(draft_figs - src_figs)
        for f in unsupported:
            issues.append({"code": "unsupported_figure", "severity": "error",
                           "message": f"figure '{f}' is not in the source text"})
        if platform == "instagram" and any(p == "kept_cited" and _URL.search(copy) for p in [parity[k["claim"]][platform] for k in kept]):
            issues.append({"code": "citation_not_clickable", "severity": "warning",
                           "message": "Instagram caption links are not clickable; name the source and put the link in bio"})
        platforms.append({
            "platform": platform, "format": fmt,
            "chars": len(copy), "limit": limit,
            "chunks": [{"text": ch, "chars": len(ch)} for ch in chunks],
            "claims_kept": kept,
            "claims_dropped": [c["id"] for c in claims if parity[c["id"]].get(platform) == "dropped"],
            "unsupported_figures": unsupported,
            "issues": issues,
            "blocking": any(i["severity"] == "error" for i in issues),
        })
    return {
        "source_claims": [{k: v for k, v in c.items() if k != "words"} for c in claims],
        "platforms": platforms,
        "parity": parity,
        "ready": bool(platforms) and not any(p["blocking"] for p in platforms),
    }
