"""Group 68: public-feed ingestion (RSS/Atom) into a sqlite store,
with robots.txt respect, dedupe, and JSONL export as inner-model training data.

Cursor semantics: the cursor marks a feed as imported once. ingest() skips
feeds already marked done (a one-shot import that is safe to re-run after an
interruption, since feeds are marked only after a full parse and store). For
continuing ingestion call with skip_done=False; dedupe by link/title hash
keeps repeats out. There is no per-item cursor or scheduler here.
robots.txt: only HTTP 404 (or 410) means no robots.txt, so no restrictions.
401, 403, 429, 5xx and any other failure deny.
default_fetch: https only, public addresses only, redirects must stay on the
same host and pass the same checks (DNS rebinding is not fully closed).

Fetching is injected (fetch(url)->bytes) so it is testable offline; the default
fetcher uses urllib on PUBLIC feeds only. No auth walls, no paywalls, no
CAPTCHA handling. This builds the data pipeline; it does not train a model.
"""
from __future__ import annotations
import hashlib, ipaddress, json, socket, sqlite3, time, urllib.error, urllib.request, urllib.robotparser, urllib.parse
import xml.etree.ElementTree as ET

UA = "atlas-ingest/1.0"


def _check_url(url):
    """https only; every resolved address must be public (no private, loopback,
    link-local, reserved or multicast). Resolution happens again at connect
    time, so DNS rebinding is not fully closed by this check."""
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError("FETCH_REFUSED_SCHEME")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("FETCH_REFUSED_UNRESOLVED")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError("FETCH_REFUSED_NONPUBLIC_ADDRESS")
    return p


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = _check_url(newurl)
        if p.hostname != self.host:
            raise ValueError("FETCH_REFUSED_REDIRECT_HOST")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_fetch(url, timeout=20, max_bytes=5_000_000):
    p = _check_url(url)
    opener = urllib.request.build_opener(_SameHostRedirect(p.hostname))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(req, timeout=timeout) as r:
        return r.read(max_bytes)


def parse_feed(raw):
    root = ET.fromstring(raw)
    out = []
    for it in root.iter():
        tag = it.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        d = {}
        for ch in it:
            t = ch.tag.rsplit("}", 1)[-1]
            if t == "link":
                d["link"] = (ch.text or ch.attrib.get("href") or "").strip()
            elif t in ("title", "description", "summary", "content", "pubDate", "published", "updated"):
                d.setdefault({"description": "summary", "content": "summary", "pubDate": "published",
                              "updated": "published"}.get(t, t), (ch.text or "").strip())
        if d.get("title") or d.get("link"):
            out.append(d)
    return out


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS docs(h TEXT PRIMARY KEY, feed TEXT, title TEXT, link TEXT, summary TEXT, published TEXT, ts REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cursor(feed TEXT PRIMARY KEY, done INTEGER, ts REAL)")

    def add(self, feed, d):
        h = hashlib.sha256((d.get("link") or d.get("title", "")).encode()).hexdigest()
        cur = self.db.execute("INSERT OR IGNORE INTO docs VALUES(?,?,?,?,?,?,?)",
                              (h, feed, d.get("title", ""), d.get("link", ""), d.get("summary", ""), d.get("published", ""), time.time()))
        return cur.rowcount == 1

    def count(self):
        return self.db.execute("SELECT count(*) FROM docs").fetchone()[0]

    def export_jsonl(self, path):
        n = 0
        with open(path, "w") as f:
            for title, summary, link in self.db.execute("SELECT title,summary,link FROM docs ORDER BY h"):
                f.write(json.dumps({"text": (title + "\n" + summary).strip(), "source": link}) + "\n")
                n += 1
        return n


def robots_ok(url, fetch):
    p = urllib.parse.urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(fetch("%s://%s/robots.txt" % (p.scheme, p.netloc)).decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as e:
        return e.code in (404, 410)  # only a genuine absence; 401/403/429/5xx deny
    except Exception:
        return False  # unreachable or unreadable robots.txt: deny
    return rp.can_fetch(UA, url)


def ingest(feeds, store, fetch=default_fetch, skip_done=True):
    report = {"feeds": {}, "new": 0, "dup": 0}
    for url in feeds:
        if skip_done and store.db.execute("SELECT done FROM cursor WHERE feed=?", (url,)).fetchone():
            report["feeds"][url] = "already_done"
            continue
        if not robots_ok(url, fetch):
            report["feeds"][url] = "blocked_by_robots"
            continue
        try:
            docs = parse_feed(fetch(url))
        except Exception as e:
            report["feeds"][url] = "error:%s" % type(e).__name__
            continue
        for d in docs:
            if store.add(url, d):
                report["new"] += 1
            else:
                report["dup"] += 1
        store.db.execute("INSERT OR REPLACE INTO cursor VALUES(?,1,?)", (url, time.time()))
        store.db.commit()
        report["feeds"][url] = "ok:%d" % len(docs)
    return report
