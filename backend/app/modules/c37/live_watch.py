"""c37.live_watch (S6.3-live): LIVE public-source watcher feeding public_record.

Closes the gap named in the audit of c37.public_record ("fixture registry
diff only; no live fetching"): this unit performs the live fetch of PUBLIC
registry sources through c30.public_http (robots-honoring, throttled,
conditional GET), parses RSS 2.0 / Atom feeds with stdlib XML, and hands the
parsed items to the existing c37.public_record.Watcher diff unchanged, so
every public_record guarantee (CLASSIFIED / NOSOURCE / PRIVATE refusals,
host allow-list on item URLs) still applies AFTER parsing.

Scope and limits (reported, never hidden):
- PUBLIC sources only: exactly the registry source ids of c37.public_record.
- Feed URLs are SUPPLIED per run and must sit on that source's own registry
  hosts; this unit does not discover feeds and does not crawl.
- Only RSS 2.0 and Atom are parsed. Other content refuses FETCH_PARSE.
- It cannot see, obtain or confirm classified or "top secret" content.
Stdlib only. Guard: c30.policy + c30.public_http.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

from app.modules.c30 import policy, public_http
from app.modules.c37 import public_record

PREFIX = "INTEL"
MAX_FEEDS = 64
MAX_ITEMS_PER_FEED = 500
MAX_SUMMARY = 4000
_ATOM = "{http://www.w3.org/2005/Atom}"
_DC = "{http://purl.org/dc/elements/1.1/}"

LIMITS = (
    "Public registry sources only; cannot see or confirm classified content.",
    "Fetches exactly the supplied feed URLs on each source's registry hosts; no crawling.",
    "RSS 2.0 / Atom only; unparsable feeds refuse FETCH_PARSE.",
)


def _err(code, detail=None):
    raise ValueError("%s_REFUSED_%s%s" % (PREFIX, code, (":" + detail) if detail else ""))


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def _parse_rss(root, max_items):
    items = []
    for it in root.iter("item"):
        if len(items) >= max_items:
            break
        link = _text(it.find("link"))
        guid = _text(it.find("guid")) or link
        if not guid:
            continue
        items.append({
            "id": guid[:256],
            "title": _text(it.find("title"))[:MAX_SUMMARY] or None,
            "url": link,
            "summary": _text(it.find("description"))[:MAX_SUMMARY] or None,
            "published": (_text(it.find("pubDate")) or _text(it.find(_DC + "date")))[:64] or None,
        })
    return items


def _parse_atom(root, max_items):
    items = []
    for entry in root.iter(_ATOM + "entry"):
        if len(items) >= max_items:
            break
        link = ""
        for l in entry.findall(_ATOM + "link"):
            if l.get("rel") in (None, "alternate") and l.get("href"):
                link = l.get("href")
                break
        iid = _text(entry.find(_ATOM + "id")) or link
        if not iid:
            continue
        items.append({
            "id": iid[:256],
            "title": _text(entry.find(_ATOM + "title"))[:MAX_SUMMARY] or None,
            "url": link,
            "summary": (_text(entry.find(_ATOM + "summary"))
                        or _text(entry.find(_ATOM + "content")))[:MAX_SUMMARY] or None,
            "published": (_text(entry.find(_ATOM + "updated"))
                          or _text(entry.find(_ATOM + "published")))[:64] or None,
        })
    return items


def parse_feed(body: bytes):
    """Parse RSS 2.0 or Atom bytes into public_record-shaped item dicts."""
    if not isinstance(body, (bytes, bytearray)) or not body:
        _err("FETCH_PARSE")
    if len(body) > public_http.MAX_BYTES:
        _err("TOO_LARGE")
    try:
        root = ET.fromstring(bytes(body))
    except ET.ParseError:
        _err("FETCH_PARSE")
    tag = root.tag
    if tag == "rss" or tag.endswith("}rss") or root.find("channel") is not None:
        items = _parse_rss(root, MAX_ITEMS_PER_FEED)
    elif tag == _ATOM + "feed":
        items = _parse_atom(root, MAX_ITEMS_PER_FEED)
    else:
        _err("FETCH_PARSE")
    if not items:
        _err("FETCH_PARSE")  # an empty feed proves nothing; fail loudly
    return items


def run(body, fetcher=None, watcher=None, feed_hosts=None):
    """Fetch supplied feeds, diff them, and return the watcher report plus
    fetch metadata. body = {"fetch_date": "YYYY-MM-DD",
    "feeds": {source_id: feed_url}}. source_id must be a public_record
    registry id; the feed URL must sit on that source's registry hosts."""
    if isinstance(body, bool) or not isinstance(body, dict) or set(body) != {"fetch_date", "feeds"}:
        raise ValueError("%s_REFUSED_BAD_TYPE:body" % PREFIX)
    fetch_date = policy.clean_text(body["fetch_date"], PREFIX, "fetch_date", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fetch_date):
        raise ValueError("%s_REFUSED_BAD_TYPE:fetch_date" % PREFIX)
    feeds = body["feeds"]
    if isinstance(feeds, bool) or not isinstance(feeds, dict) or not feeds:
        _err("NOSOURCE")
    if len(feeds) > MAX_FEEDS:
        _err("OVERSIZE")
    for sid in feeds:
        if sid not in public_record.REGISTRY_IDS:
            _err("NOSOURCE", "unknown-source")
    if fetcher is None:
        hosts = sorted({h for sid in feeds for h in public_record._BY_ID[sid][3]})
        fetcher = public_http.Fetcher(hosts)
    watcher = watcher or public_record.Watcher()
    sources, fetch_meta = {}, []
    for sid, url in feeds.items():
        allowed = (feed_hosts or {}).get(sid, public_record._BY_ID[sid][3])
        if urlsplit_host(url) not in allowed:
            _err("NOSOURCE", "feed-host")  # feed must live on the source's own hosts
        result = fetcher.fetch(url)
        fetch_meta.append({"source": sid, "url": url, "status": result["status"],
                           "not_modified": result["not_modified"]})
        if result["not_modified"]:
            sources[sid] = []
            continue
        sources[sid] = parse_feed(result["body"])
    sources = {sid: items for sid, items in sources.items() if items}
    if sources:
        report = watcher.run({"fetch_date": fetch_date, "sources": sources})
    else:
        report = {"statement": "All feeds not modified since cache; no new public items.",
                  "fetch_date": fetch_date, "items": [], "refused": [],
                  "coverage": {"registry_sources": len(public_record.REGISTRY),
                               "feeds_checked": len(feeds), "items_reported": 0},
                  "limits": list(LIMITS)}
    report["live_fetch"] = {"feeds": fetch_meta, "fetches": fetcher.fetches,
                            "bytes_read": fetcher.bytes_read}
    report["live_limits"] = list(LIMITS)
    return report


def urlsplit_host(url):
    from urllib.parse import urlsplit
    try:
        return urlsplit(url).hostname
    except ValueError:
        _err("NOSOURCE", "feed-host")
