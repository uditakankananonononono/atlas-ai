"""Bounded, provenance-preserving public RSS/Atom ingestion for Claire.

Designed for specific public feeds, not crawling the entire web. Network access is
opt-in at the caller. HTTPS, public IP DNS answers, byte/timeout limits and redirect
revalidation are enforced. Platform-specific social data should use official APIs.
"""
from __future__ import annotations
import ipaddress, socket, ssl, http.client, urllib.parse
from collections import Counter
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable

MAX_BYTES=2_000_000
MAX_REDIRECTS=3


def _resolve_public_https(url: str) -> tuple[str,str,int,list[str]]:
    p=urllib.parse.urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("only credential-free HTTPS URLs are supported")
    host=p.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
        raise ValueError("local/internal hostnames are not allowed")
    port=p.port or 443
    if port != 443:
        raise ValueError("only HTTPS on port 443 is supported")
    try:
        literal=ipaddress.ip_address(host)
        ips=[str(literal)]
    except ValueError:
        try: ips=sorted({item[4][0] for item in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)})
        except OSError as e: raise ValueError("hostname could not be resolved") from e
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("host resolves to a non-public address")
    normalized=urllib.parse.urlunsplit((p.scheme,p.netloc,p.path or "/",p.query,""))
    return normalized,host,port,ips


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to a previously resolved IP while validating TLS for the original hostname."""
    def __init__(self, host: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(host,port,timeout=timeout,context=ssl.create_default_context())
        self._pinned_ip=pinned_ip
    def connect(self):
        raw=socket.create_connection((self._pinned_ip,self.port),self.timeout,self.source_address)
        try:
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except Exception:
            raw.close()
            raise


@dataclass(frozen=True)
class Signal:
    source_url: str
    source_domain: str
    item_id: str
    title: str
    summary: str
    link: str
    published_at: str | None
    ingested_at: str
    content_hash: str
    provenance: str = "public_feed"


def _clean(s: Any, n: int=10000) -> str:
    if not isinstance(s,str): return ""
    return " ".join(s.replace("\x00", " ").split())[:n]


def _published(raw: str | None) -> str | None:
    if not raw: return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        try:
            dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception: return None


def parse_feed(xml_data: bytes, feed_url: str, *, item_limit: int=200) -> list[Signal]:
    if len(xml_data)>MAX_BYTES: raise ValueError("feed exceeds byte limit")
    # Parsing an already-supplied document must work offline; live fetching has the
    # stricter DNS/public-IP checks in fetch_public_feed().
    parsed_url=urllib.parse.urlsplit(feed_url)
    if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
        raise ValueError("feed reference must be credential-free HTTPS")
    feed_url=urllib.parse.urlunsplit(("https",parsed_url.netloc,parsed_url.path or "/","",""))
    try: root=ET.fromstring(xml_data)
    except ET.ParseError as exc: raise ValueError("invalid feed XML") from exc
    domain=urllib.parse.urlsplit(feed_url).hostname or "unknown"
    def text_of(el, names):
        for e in el.iter():
            tag=e.tag.rsplit("}",1)[-1].lower()
            if tag in names and e.text: return _clean(e.text)
        return ""
    entries=[]
    # RSS <item> / Atom <entry>, namespace-agnostic.
    for el in root.iter():
        if el.tag.rsplit("}",1)[-1].lower() in {"item","entry"}:
            title=text_of(el,{"title"}); summary=text_of(el,{"description","summary","content"})
            link=text_of(el,{"link"});
            if not link:
                for sub in el.iter():
                    if sub.tag.rsplit("}",1)[-1].lower()=="link" and sub.attrib.get("href"):
                        link=sub.attrib["href"]; break
            if link:
                link=urllib.parse.urljoin(feed_url,link)
                lp=urllib.parse.urlsplit(link)
                if lp.scheme not in {"http", "https"} or not lp.hostname or lp.username or lp.password:
                    link=""
            rawdate=text_of(el,{"pubdate","published","updated","date"})
            uid=text_of(el,{"guid","id"}) or link or title
            if not title and not summary: continue
            import hashlib
            content_hash=hashlib.sha256((domain+"\n"+title+"\n"+summary).encode()).hexdigest()
            entries.append(Signal(feed_url,domain,uid[:1000],title,summary,link,_published(rawdate),
                                  datetime.now(timezone.utc).isoformat(),content_hash))
            if len(entries)>=max(1,min(item_limit,1000)): break
    return entries


def fetch_public_feed(url: str, *, timeout: float=8.0, max_bytes: int=MAX_BYTES,
                      user_agent: str="ClaireResearchBot/1.0 (bounded public feed reader)") -> tuple[bytes,str]:
    """Fetch a configured public feed with DNS pinning, TLS validation and redirect checks."""
    if not 0.5 <= timeout <= 30: raise ValueError("timeout must be in [0.5,30]")
    if not 1 <= max_bytes <= MAX_BYTES: raise ValueError("max_bytes must be in [1,2MB]")
    current=url
    for _ in range(MAX_REDIRECTS+1):
        current,host,port,ips=_resolve_public_https(current)
        p=urllib.parse.urlsplit(current)
        target=p.path or "/"
        if p.query: target += "?"+p.query
        connection=None
        try:
            # Use the very IP address we validated, avoiding a second DNS lookup / rebinding.
            connection=_PinnedHTTPSConnection(host,port,ips[0],timeout)
            connection.request("GET",target,headers={"User-Agent":user_agent,
                "Accept":"application/atom+xml,application/rss+xml,application/xml,text/xml;q=0.8,*/*;q=0.1",
                "Accept-Encoding":"identity","Host":p.netloc,"Connection":"close"})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader("Location")
                response.read(1024)
                if not location: raise ValueError("redirect missing Location")
                current=urllib.parse.urljoin(current,location)
                continue
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"feed request failed with HTTP {response.status}")
            data=response.read(max_bytes+1)
            if len(data)>max_bytes: raise ValueError("feed exceeds byte limit")
            return data,current
        except (OSError,ssl.SSLError,http.client.HTTPException) as exc:
            raise ValueError("feed request failed") from exc
        finally:
            if connection is not None: connection.close()
    raise ValueError("too many redirects")


class SignalLedger:
    """In-memory provenance-preserving deduplicator; persist externally for production."""
    def __init__(self): self._signals: dict[str, Signal]={}
    def add(self, signals: Iterable[Signal]) -> dict[str, Any]:
        new=0; duplicates=0
        for s in signals:
            key=s.content_hash
            if key in self._signals: duplicates+=1
            else: self._signals[key]=s; new+=1
        return {"new":new,"duplicates":duplicates,"total":len(self._signals)}
    def items(self, limit: int=500) -> list[dict[str, Any]]:
        if not 1<=limit<=5000: raise ValueError("limit must be in [1,5000]")
        return [asdict(s) for s in list(self._signals.values())[-limit:]]


def analyze_signals(signals: Iterable[dict[str, Any]], *, top_k: int=20) -> dict[str, Any]:
    """Lightweight trend surfacing; outputs leads with evidence, not factual conclusions."""
    import re, math
    docs=[]
    stop={"this","that","with","from","have","will","your","into","about","after","were","their","they","what","when","where","which","than","then","using","used","more","less","over","under","study","research","news","says","said","new"}
    for s in signals:
        title=_clean(s.get("title",""),500); summary=_clean(s.get("summary",""),2000)
        tokens=[w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}",title+" "+summary) if w.lower() not in stop]
        if not tokens: continue
        docs.append({"source_domain":s.get("source_domain","unknown"),"title":title,"link":s.get("link",s.get("source_url","")),
                     "content_hash":s.get("content_hash",""),"tokens":tokens,"text":(title+" "+summary)[:2500]})
    df=Counter(w for d in docs for w in set(d["tokens"]))
    tf=Counter(w for d in docs for w in d["tokens"])
    n=max(1,len(docs)); scored=[]
    for term,count in tf.items():
        if len(term)<4 or count<2: continue
        sources={d["source_domain"] for d in docs if term in d["tokens"]}
        ids=[i for i,d in enumerate(docs) if term in d["tokens"]]
        evidence=[{"title":docs[i]["title"],"link":docs[i]["link"],"source_domain":docs[i]["source_domain"],"content_hash":docs[i]["content_hash"]} for i in ids[:5]]
        diversity=min(1.0,len(sources)/max(1,min(5,len(ids))))
        score=math.log1p(count)*math.log((1+n)/(1+df[term]))*diversity
        scored.append({"term":term,"mentions":count,"document_count":df[term],"source_diversity":len(sources),
                       "score":round(score,5),"evidence":evidence,"status":"signal_to_investigate"})
    scored.sort(key=lambda x:(x["score"],x["document_count"]),reverse=True)
    return {"document_count":n,"unique_domains":len({d["source_domain"] for d in docs}),"trends":scored[:max(1,min(top_k,100))],
            "method":"term frequency x inverse document frequency x source diversity; no semantic causal inference",
            "caveats":["feed selection bias","duplicate/syndicated articles may inflate signal","a high score is not proof of importance","verify against primary sources"]}
