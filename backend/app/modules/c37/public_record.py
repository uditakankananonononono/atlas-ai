"""S6.3 / c37.public_record - public-record watcher.

Her words (15:01:13, verbatim): "keep an eye out for top secret projects,
governement stuff too, super elite stuff".

Watches a fixed REGISTRY of public government / R&D sources over SUPPLIED
fixtures (nothing is fetched here; a live fetcher would be a separate unit).
Detects new or changed items by diff, classifies topic, ranks by novelty and
reports each item with its source URL and fetch date.

It covers PUBLIC RECORDS ONLY. It cannot see, obtain or confirm "top secret"
content, and never claims to watch "all government": only the registry-listed
sources are watched and the count is reported.

Refusals (ValueError, codes INTEL_REFUSED_*):
  CLASSIFIED  classification markers on an item; credentials, auth bypass or
              system probing in a request
  NOSOURCE    item without a public https URL on its registry source's hosts,
              or from a source that is not in the registry
  PRIVATE     private-individual data (SSN/email/phone patterns, private fields)
Stdlib only, offline, deterministic. Guard: c30.policy.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from urllib.parse import urlsplit

from app.modules.c30 import policy

PREFIX = "INTEL"
HER_WORDS = "keep an eye out for top secret projects, governement stuff too, super elite stuff"
MAX_ITEMS = 5000
MAX_SOURCES = 64

# (id, name, kind, allowed public hosts). Registry membership is the only
# thing "watched" means. Fixture-only here: no host is contacted.
REGISTRY = (
    ("cia-crest", "CIA CREST FOIA reading room", "foia", ("www.cia.gov",)),
    ("fbi-vault", "FBI Vault FOIA library", "foia", ("vault.fbi.gov",)),
    ("grants-gov", "Grants.gov opportunities", "grants", ("www.grants.gov",)),
    ("usaspending", "USAspending awards", "procurement", ("www.usaspending.gov", "api.usaspending.gov")),
    ("uspto-pub", "USPTO patent publications", "patents", ("ppubs.uspto.gov", "patents.uspto.gov")),
    ("epo-pub", "EPO patent publications", "patents", ("data.epo.org", "worldwide.espacenet.com")),
    ("sec-edgar", "SEC EDGAR filings", "filings", ("www.sec.gov",)),
    ("darpa", "DARPA public program pages", "rnd", ("www.darpa.mil",)),
    ("arpa-e", "ARPA-E public program pages", "rnd", ("arpa-e.energy.gov",)),
    ("nih-reporter", "NIH RePORTER projects", "rnd", ("reporter.nih.gov",)),
)
REGISTRY_IDS = tuple(r[0] for r in REGISTRY)
_BY_ID = {r[0]: r for r in REGISTRY}

_CLASSIFIED_RE = re.compile(
    r"top[\s_-]*secret|top%20secret|\bts\s*//|\bsecret\s*//|\bnoforn\b|\bsecret\s+clearance\b|\bclassified\b",
    re.IGNORECASE)
_REQUEST_FORBIDDEN_KEYS = frozenset({
    "password", "passwd", "token", "cookie", "credentials", "api_key", "apikey",
    "authorization", "auth", "login", "session", "probe", "port_scan", "exploit"})
_PRIVATE_FIELDS = frozenset({"ssn", "home_address", "dob", "date_of_birth", "personal_email",
                             "personal_phone", "private_individual"})
_PRIVATE_RE = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\b\(?\d{3}\)?[ -]\d{3}-\d{4}\b")
_ITEM_KEYS = frozenset({"id", "title", "url", "summary", "published", "classification"} | _PRIVATE_FIELDS)

TOPICS = (
    ("quantum", ("quantum", "qubit")),
    ("ai-autonomy", ("artificial intelligence", "machine learning", "autonomous", "neural")),
    ("space", ("space", "orbital", "satellite", "hypersonic")),
    ("defense-tech", ("weapon", "munition", "radar", "defense", "stealth")),
    ("biotech", ("biolog", "genom", "vaccine", "pathogen", "protein")),
    ("energy", ("fusion", "battery", "reactor", "grid", "energy")),
    ("materials", ("alloy", "semiconductor", "photonic", "material")),
    ("cyber", ("cyber", "encryption", "cryptograph")),
)
LIMITS = (
    "Public records only: cannot see, obtain or confirm top secret or classified content.",
    "Only registry-listed sources are watched; this is not all of government.",
    "Items come from supplied fixtures; nothing is fetched or crawled by this unit.",
    "Topic and novelty are keyword/diff heuristics, not analysis of significance.",
)


def _err(code):
    raise ValueError("%s_REFUSED_%s" % (PREFIX, code))


def _scan_request(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.strip().lower() in _REQUEST_FORBIDDEN_KEYS:
                _err("CLASSIFIED")  # credential / auth-bypass / probing request
            _scan_request(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _scan_request(v)


def _refuse_code(source_id, item):
    """Return the refusal code for one item, or None. CLASSIFIED > NOSOURCE > PRIVATE.
    Every string field, including id and url, is scanned before anything is echoed."""
    if item.get("classification") not in (None, "", "UNCLASSIFIED", "public"):
        return "CLASSIFIED"
    texts = [item.get(k) for k in ("id", "title", "summary", "published", "url", "classification")]
    if any(isinstance(t, str) and _CLASSIFIED_RE.search(t) for t in texts):
        return "CLASSIFIED"
    url = item.get("url")
    if not isinstance(url, str):
        return "NOSOURCE"
    try:
        parts = urlsplit(url)
        host = parts.hostname
        userinfo = parts.username or parts.password
        port = parts.port  # raises ValueError when out of range
    except ValueError:  # malformed URL such as "https://["
        return "NOSOURCE"
    if parts.scheme != "https" or host not in _BY_ID[source_id][3] or userinfo \
            or port not in (None, 443):
        return "NOSOURCE"
    if any(item.get(f) for f in _PRIVATE_FIELDS):
        return "PRIVATE"
    if any(isinstance(t, str) and _PRIVATE_RE.search(t) for t in texts):
        return "PRIVATE"
    return None


def classify_topic(item):
    hay = ((item.get("title") or "") + " " + (item.get("summary") or "")).lower()
    return [name for name, words in TOPICS if any(w in hay for w in words)] or ["other"]


def _digest(item):
    blob = json.dumps({k: item.get(k) for k in ("title", "url", "summary", "published")}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Watcher:
    """Holds the diff state (seen digests) and the last report."""

    def __init__(self):
        self.seen = {}          # (source_id, item_id) -> digest
        self.topic_counts = {}  # topic -> number of items seen before
        self.last_report = None

    def run(self, body):
        if isinstance(body, bool) or not isinstance(body, dict) or set(body) != {"fetch_date", "sources"}:
            raise ValueError("%s_REFUSED_BAD_TYPE:body" % PREFIX)
        _scan_request(body)
        fetch_date = policy.clean_text(body["fetch_date"], PREFIX, "fetch_date", 10)
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fetch_date):
                raise ValueError
            datetime.date.fromisoformat(fetch_date)
        except ValueError:
            raise ValueError("%s_REFUSED_BAD_TYPE:fetch_date" % PREFIX) from None
        sources = body["sources"]
        if isinstance(sources, bool) or not isinstance(sources, dict) or not sources:
            _err("NOSOURCE")
        if len(sources) > MAX_SOURCES:
            raise ValueError("%s_REFUSED_OVERSIZE" % PREFIX)
        total = 0
        found, refused, per_source = [], [], {}
        for sn, (sid, items) in enumerate(sources.items()):
            if sid not in _BY_ID:  # the unknown key is caller content: report a handle only
                refused.append({"source": "unknown-source#%d" % sn, "item_ref": None,
                                "code": "INTEL_REFUSED_NOSOURCE"})
                continue
            if isinstance(items, bool) or not isinstance(items, (list, tuple)):
                raise ValueError("%s_REFUSED_BAD_TYPE:items" % PREFIX)
            total += len(items)
            if total > MAX_ITEMS:
                raise ValueError("%s_REFUSED_OVERSIZE" % PREFIX)
            per_source[sid] = len(items)
            for pos, item in enumerate(items):
                if isinstance(item, bool) or not isinstance(item, dict) or not set(item) <= _ITEM_KEYS:
                    raise ValueError("%s_REFUSED_BAD_TYPE:item" % PREFIX)
                iid = policy.clean_text(item.get("id"), PREFIX, "id", 256)
                for k in ("title", "summary", "published"):
                    if item.get(k) is not None:
                        policy.clean_text(item[k], PREFIX, k, 4000, allow_blank=True)
                code = _refuse_code(sid, item)
                if code:  # report a positional handle and the code only, never any content
                    refused.append({"source": sid, "item_ref": "%s#%d" % (sid, pos),
                                    "code": "%s_REFUSED_%s" % (PREFIX, code)})
                    continue
                digest = _digest(item)
                prev = self.seen.get((sid, iid))
                if prev == digest:
                    continue
                status = "new" if prev is None else "changed"
                topics = classify_topic(item)
                prior = min(self.topic_counts.get(t, 0) for t in topics)
                novelty = round((1.0 if status == "new" else 0.5) / (1 + prior), 4)
                found.append({"source": sid, "id": iid, "title": item.get("title"), "status": status,
                              "topics": topics, "novelty": novelty,
                              "source_url": item["url"], "fetch_date": fetch_date, "_digest": digest})
        for f in found:  # state is updated only after the whole run validated
            self.seen[(f["source"], f["id"])] = f.pop("_digest")
            if f["status"] == "new":
                for t in f["topics"]:
                    self.topic_counts[t] = self.topic_counts.get(t, 0) + 1
        found.sort(key=lambda f: (-f["novelty"], f["source"], f["id"]))
        self.last_report = {
            "statement": ("Public records only. This report cannot see top secret or classified content "
                          "and does not cover all of government."),
            "her_words": HER_WORDS,
            "fetch_date": fetch_date,
            "items": found,
            "refused": refused,
            "coverage": {"registry_sources": len(REGISTRY), "sources_in_run": len(per_source),
                         "sources_with_items": sum(1 for n in per_source.values() if n),
                         "items_supplied": total, "items_reported": len(found),
                         "items_refused": len(refused), "registry_ids": list(REGISTRY_IDS)},
            "limits": list(LIMITS),
            "scope": policy.scope(["diff", "topic-classify", "novelty-rank", "registry-source-check"],
                                  ["fetching", "classified-content", "all-government coverage"],
                                  "supplied-fixtures", fetch_date),
        }
        return self.last_report

    def report(self):
        if self.last_report is None:
            raise ValueError("%s_REFUSED_NOSOURCE" % PREFIX)
        return self.last_report


_DEFAULT = Watcher()

ROUTES = (("POST", "/api/v1/c37/public-record/run"), ("GET", "/api/v1/c37/public-record/report"))


def post_run(body):
    """POST /api/v1/c37/public-record/run"""
    return _DEFAULT.run(body)


def get_report():
    """GET /api/v1/c37/public-record/report"""
    return _DEFAULT.report()
