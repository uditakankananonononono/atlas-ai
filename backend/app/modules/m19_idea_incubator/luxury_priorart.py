"""Prior-art check for generated luxury ideas.

Searches a free public index (Wikipedia search API by default) for each idea's
lever phrase plus the brand sector, scores each hit's title and snippet against
the idea's mechanism terms, and labels the idea:
  done-before            a hit overlaps the mechanism strongly (hit evidence kept)
  possible-prior-art     weaker overlap, needs human read
  no-prior-art-found     on-topic hits exist but none overlap the mechanism. Not proof it is novel.
  inconclusive           index returned nothing on-topic for the sector
An unreachable index returns 'unchecked', never 'no-prior-art-found'.
"""
from __future__ import annotations
import asyncio, re
from typing import Awaitable, Callable
import httpx
from .luxury_ideation import tokens

Fetcher = Callable[[str], Awaitable[list[dict]]]  # query -> [{title,snippet,url}]
_STOP = {"the","a","an","of","for","and","to","with","that","in","on","its","their","before","early","each","own"}
STRONG, WEAK = 0.34, 0.18

async def wikipedia_fetch(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "AtlasAI/1.0 (prior-art research client)"}) as c:
        r = await c.get("https://en.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 8})
        r.raise_for_status()
    return [{"title": h["title"], "snippet": re.sub("<[^>]+>", "", h.get("snippet", "")),
             "url": "https://en.wikipedia.org/wiki/" + h["title"].replace(" ", "_")} for h in r.json()["query"]["search"]]

LEVER_QUERY = {
 "provenance": "digital product passport luxury authenticity provenance",
 "ownership_care": "owner lifecycle care program maintenance restoration",
 "personalization": "consent based personalization concierge loyalty luxury",
 "scarcity_access": "limited edition allocation fair queue waitlist",
 "sustainability_proof": "traceability sustainability proof luxury product",
 "digital_world": "brand fan digital experience licensing game",
 "operations_quality": "service quality analytics staffing reviews",
 "pricing_demand": "luxury demand price sensitivity monitoring",
}
SECTOR_WORDS = {
 "automotive": {"car","cars","vehicle","vehicles","automotive","motor","automaker","driver","owner"},
 "hotel": {"hotel","hotels","guest","guests","resort","hospitality","stay"},
 "luxury_hospitality": {"hotel","hotels","guest","guests","resort","hospitality","stay","luxury"},
 "fashion": {"fashion","brand","luxury","apparel","designer","maison","handbag"},
 "jewelry": {"jewelry","jewellery","watch","watches","diamond","luxury","gem"},
 "character_ip": {"character","licensing","fans","franchise","brand","game","merchandise"},
 "other": {"brand","luxury","customer","product"},
}

def query_for(idea: dict, sector: str) -> str:
    """One phrase per lever in the idea, plus the sector word."""
    phrases = [LEVER_QUERY[l] for l in idea.get("levers", []) if l in LEVER_QUERY]
    return (" ".join(phrases) + " " + sector.replace("_", " ")).strip()

def overlap(idea_terms: set[str], text: str) -> float:
    t = tokens(text) - _STOP
    return round(len(idea_terms & t) / len(idea_terms), 3) if idea_terms else 0.0

async def news_fetch(query: str) -> list[dict]:
    from .luxury_sources import GOOGLE_NEWS_RSS, parse_rss
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "AtlasAI/1.0 (prior-art research client)"}) as c:
        r = await c.get(GOOGLE_NEWS_RSS, params={"q": " ".join(query.split()[:5]), "hl": "en-US", "gl": "US", "ceid": "US:en"})
        r.raise_for_status()
    return [{"title": i["title"], "snippet": i.get("summary", ""), "url": i["url"]} for i in parse_rss(r.text, "google_news", "Google News", 10)]

async def combined_fetch(query: str) -> list[dict]:
    res = await asyncio.gather(wikipedia_fetch(query), news_fetch(query), return_exceptions=True)
    ok = [r for r in res if not isinstance(r, Exception)]
    if not ok: raise RuntimeError("all prior-art indexes failed")
    return [h for r in ok for h in r]

async def check_idea(idea: dict, sector: str, fetch: Fetcher = combined_fetch) -> dict:
    q = query_for(idea, sector)
    idea_terms = (tokens(q) | tokens(idea["mechanism"])) - _STOP
    brand_terms = set()  # brand name must not count as overlap
    try:
        hits = await fetch(q)
    except Exception as error:
        return {"idea_id": idea["idea_id"], "label": "unchecked", "query": q, "hits": [], "error": type(error).__name__}
    scored = sorted(({**h, "overlap": overlap(idea_terms - brand_terms, h["title"] + " " + h["snippet"])} for h in hits),
                    key=lambda h: -h["overlap"])
    top = scored[0]["overlap"] if scored else 0.0
    words = SECTOR_WORDS.get(sector, SECTOR_WORDS["other"])
    on_topic = [h for h in scored if tokens(h["title"] + " " + h["snippet"]) & words]
    if top < WEAK and not on_topic:
        return {"idea_id": idea["idea_id"], "label": "inconclusive", "query": q, "top_overlap": top, "hits": scored[:3],
                "caveat": "index returned no on-topic results; this says nothing about novelty"}
    # a strong label needs an on-topic hit; an off-topic overlap on common words is noise
    top = max((h["overlap"] for h in on_topic), default=0.0)
    label = "done-before" if top >= STRONG else "possible-prior-art" if top >= WEAK else "no-prior-art-found"
    return {"idea_id": idea["idea_id"], "label": label, "query": q, "top_overlap": top, "hits": scored[:3],
            "caveat": "searched one public index; absence of hits is not proof of novelty"}

async def check_ideas(ideas: list[dict], sector: str, fetch: Fetcher = combined_fetch) -> list[dict]:
    return list(await asyncio.gather(*(check_idea(i, sector, fetch) for i in ideas)))
