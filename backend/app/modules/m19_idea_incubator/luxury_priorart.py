"""Prior-art check for generated luxury ideas.

Searches a free public index (Wikipedia search API by default) for each idea's
lever phrase plus the brand sector, scores each hit's title and snippet against
the idea's mechanism terms, and labels the idea:
  done-before            a hit overlaps the mechanism strongly (hit evidence kept)
  possible-prior-art     weaker overlap, needs human read
  no-prior-art-found     nothing matched in THIS index. Not proof it is novel.
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

def query_for(idea: dict, sector: str) -> str:
    terms = sorted({t for e in idea["evidence"] for t in e["matched_terms"]})[:4]
    return " ".join(terms + [sector.replace("_", " "), "service"]).strip()

def overlap(idea_terms: set[str], text: str) -> float:
    t = tokens(text) - _STOP
    return round(len(idea_terms & t) / len(idea_terms), 3) if idea_terms else 0.0

async def check_idea(idea: dict, sector: str, fetch: Fetcher = wikipedia_fetch) -> dict:
    q = query_for(idea, sector)
    idea_terms = (tokens(idea["mechanism"]) - _STOP) | {t for e in idea["evidence"] for t in e["matched_terms"]}
    brand_terms = set()  # brand name must not count as overlap
    try:
        hits = await fetch(q)
    except Exception as error:
        return {"idea_id": idea["idea_id"], "label": "unchecked", "query": q, "hits": [], "error": type(error).__name__}
    scored = sorted(({**h, "overlap": overlap(idea_terms - brand_terms, h["title"] + " " + h["snippet"])} for h in hits),
                    key=lambda h: -h["overlap"])
    top = scored[0]["overlap"] if scored else 0.0
    label = "done-before" if top >= STRONG else "possible-prior-art" if top >= WEAK else "no-prior-art-found"
    return {"idea_id": idea["idea_id"], "label": label, "query": q, "top_overlap": top, "hits": scored[:3],
            "caveat": "searched one public index; absence of hits is not proof of novelty"}

async def check_ideas(ideas: list[dict], sector: str, fetch: Fetcher = wikipedia_fetch) -> list[dict]:
    return list(await asyncio.gather(*(check_idea(i, sector, fetch) for i in ideas)))
