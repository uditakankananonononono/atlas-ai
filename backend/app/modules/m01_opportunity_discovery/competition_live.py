"""m01.competition_live (U37-live): LIVE public discovery of high-school
competitions.

Closes the gap named in the audit of high_school_competitions_u37 ("curated
bounded registry, not exhaustive verified all-competition coverage"): this
unit fetches SUPPLIED public listing pages through c30.public_http
(robots-honoring, throttled), extracts candidate competition links, VERIFIES
each candidate by fetching its official page (status 200, content present),
dedupes against the supplied existing registry, and emits registry additions
with full provenance (listing page, anchor text, verification status, fetch
date).

Honest scope, reported on every run:
- "All top high-school competitions" is unbounded; this unit discovers from
  exactly the supplied listing pages and reports coverage counts. It never
  claims exhaustive coverage.
- Verification = the candidate official URL fetched successfully at run
  time. It is not an eligibility, quality or legitimacy judgement.
- Public pages only; no logins, no account creation, no applications.
Stdlib only. Guard: c30.policy + c30.public_http.
"""
from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.modules.c30 import policy, public_http

PREFIX = "OPPS"
MAX_LISTINGS = 32
MAX_CANDIDATES = 50
MAX_LINK_TEXT = 200
MAX_TITLE = 256

KEYWORDS = (
    "olympiad", "competition", "contest", "challenge", "hackathon", "scholarship",
    "quiz", "tournament", "championship", "award", "prize", "science fair",
    "math league", "debate", "model un", "olympics",
)
HIGH_SCHOOL_HINTS = (
    "high school", "secondary", "student", "grades", "class 9", "class 10",
    "class 11", "class 12", "9-12", "k-12", "under 18", "youth", "junior",
)

LIMITS = (
    "Discovery is bounded to the supplied listing pages; not exhaustive coverage.",
    "Verification means the official URL fetched OK at run time; nothing more.",
    "Public pages only: no logins, accounts, applications or submissions.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


class _Links(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())[:MAX_LINK_TEXT]
            if text:
                self.links.append((urljoin(self.base, self._href), text))
            self._href = None
            self._text = []


def _canonical_id(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = re.sub(r"/+$", "", parts.path or "/")
    return hashlib.sha256(("%s%s" % (host, path)).encode("utf-8")).hexdigest()[:16]


def _is_candidate(text):
    low = text.lower()
    return any(k in low for k in KEYWORDS)


def _hs_hint(text):
    low = text.lower()
    return any(h in low for h in HIGH_SCHOOL_HINTS)


def run(body, fetcher=None):
    """body = {"as_of": "YYYY-MM-DD", "listing_urls": [...],
    "allowed_hosts": [...], "existing_ids": [...]}. Returns discovered,
    verified registry additions with provenance and coverage."""
    if isinstance(body, bool) or not isinstance(body, dict) or \
            set(body) != {"as_of", "listing_urls", "allowed_hosts", "existing_ids"}:
        raise ValueError("%s_REFUSED_BAD_TYPE:body" % PREFIX)
    as_of = policy.clean_text(body["as_of"], PREFIX, "as_of", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        raise ValueError("%s_REFUSED_BAD_TYPE:as_of" % PREFIX)
    listings = body["listing_urls"]
    if isinstance(listings, bool) or not isinstance(listings, (list, tuple)) or not listings:
        _err("NOSOURCE")
    if len(listings) > MAX_LISTINGS:
        _err("OVERSIZE")
    existing = set()
    if isinstance(body["existing_ids"], bool) or not isinstance(body["existing_ids"], (list, tuple)):
        raise ValueError("%s_REFUSED_BAD_TYPE:existing_ids" % PREFIX)
    for e in body["existing_ids"]:
        existing.add(policy.clean_text(e, PREFIX, "existing_id", 64))
    fetcher = fetcher or public_http.Fetcher(body["allowed_hosts"])
    candidates, seen_urls, fetch_log = [], set(), []
    for url in listings:
        public_http.validate_url(url, fetcher.allowed_hosts, fetcher.allow_http)
        result = fetcher.fetch(url)
        fetch_log.append({"listing": url, "status": result["status"]})
        if result["not_modified"]:
            continue
        parser = _Links(result["url"])
        try:
            parser.feed(result["body"].decode("utf-8", "replace"))
        except Exception:
            _err("PARSE", "listing")
        for href, text in parser.links:
            if len(candidates) >= MAX_CANDIDATES:
                break
            if not _is_candidate(text):
                continue
            try:
                public_http.validate_url(href, fetcher.allowed_hosts, fetcher.allow_http)
            except ValueError:
                continue  # off-allow-list links are skipped, never fetched
            cid = _canonical_id(href)
            if cid in seen_urls:
                continue
            seen_urls.add(cid)
            candidates.append({"url": href, "anchor_text": text, "id": cid,
                               "high_school_hint": _hs_hint(text), "listing": result["url"]})
    verified, failed, duplicates = [], [], []
    for cand in candidates:
        if cand["id"] in existing:
            duplicates.append(cand["id"])
            continue
        try:
            check = fetcher.fetch(cand["url"])
            ok = check["status"] == 200 and len(check["body"]) > 0
        except ValueError:
            ok = False
        entry = {"id": cand["id"], "name": cand["anchor_text"][:MAX_TITLE],
                 "official_url": cand["url"], "high_school_hint": cand["high_school_hint"],
                 "verified_reachable_at_run": ok,
                 "provenance": {"listing_page": cand["listing"], "anchor_text": cand["anchor_text"],
                                "fetch_date": as_of}}
        (verified if ok else failed).append(entry)
    return {
        "as_of": as_of,
        "additions": verified,
        "unverified_candidates": [{"id": f["id"], "official_url": f["official_url"]} for f in failed],
        "duplicates_skipped": sorted(duplicates),
        "coverage": {"listings_fetched": len(fetch_log),
                     "candidates_found": len(candidates),
                     "verified_reachable": len(verified),
                     "already_registered": len(duplicates),
                     "candidate_cap": MAX_CANDIDATES},
        "fetch_log": fetch_log,
        "limits": list(LIMITS),
        "scope": policy.scope(["live-listing-fetch", "candidate-extraction",
                               "official-url-verification", "registry-dedupe"],
                              ["exhaustive-coverage", "legitimacy-judgement",
                               "accounts-or-applications"],
                              "live-public-pages", as_of),
    }
