"""Interest-led public-web discovery: find candidates first, track only after review."""
from __future__ import annotations
import asyncio, re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from bs4 import BeautifulSoup
from .base import CollectionBatch, CollectedItem, HttpCollector

@dataclass(frozen=True)
class Candidate:
    platform: str
    account_key: str
    profile_url: str
    topic: str
    evidence_url: str
    evidence_text: str

PLATFORMS={
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/([^/?#]+)",re.I),
    "x": re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)",re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([^/?#]+)",re.I),
}
RESERVED={"share","intent","search","explore","accounts","p","reel","stories","home","i"}

def candidate_from_result(topic: str, url: str, evidence: str) -> Candidate | None:
    for platform, pattern in PLATFORMS.items():
        match=pattern.search(url)
        if not match: continue
        account=match.group(1).lower().strip()
        if account in RESERVED: return None
        host={"linkedin":"www.linkedin.com","x":"x.com","instagram":"www.instagram.com"}[platform]
        prefix="in/" if platform == "linkedin" else ""
        return Candidate(platform,account,f"https://{host}/{prefix}{account}",topic,url,evidence[:1000])
    return None

class InterestWebDiscoveryCollector(HttpCollector):
    """Free no-login DuckDuckGo HTML discovery with slow pacing and block stops."""
    async def collect(self, config: dict) -> CollectionBatch:
        topics=config.get("topics",[]); platforms=config.get("platforms",list(PLATFORMS))
        delay=max(8.0,float(config.get("delay_seconds",12))); max_results=min(30,max(1,int(config.get("results_per_query",15))))
        items=[]; requests=0; seen=set()
        for topic in topics:
            for platform in platforms:
                site={"linkedin":"linkedin.com","x":"x.com OR twitter.com","instagram":"instagram.com"}[platform]
                response=await self.client.get("https://html.duckduckgo.com/html/",params={"q":f'"{topic}" site:{site}'},headers={"User-Agent":config.get("user_agent","AtlasDiscovery/1.0")})
                requests+=1
                if response.status_code in (403,429) or "captcha" in response.text.lower(): raise RuntimeError("public-web discovery stopped on block/challenge")
                response.raise_for_status(); soup=BeautifulSoup(response.text,"html.parser"); count=0
                for result in soup.select(".result"):
                    link=result.select_one("a.result__a")
                    if not link: continue
                    url=link.get("href","")
                    if "uddg=" in url: url=unquote(parse_qs(urlparse(url).query).get("uddg",[url])[0])
                    snippet=result.select_one(".result__snippet"); evidence=" ".join((snippet or result).get_text(" ",strip=True).split())
                    candidate=candidate_from_result(str(topic),url,evidence)
                    if not candidate or candidate.platform != platform: continue
                    key=(candidate.platform,candidate.account_key,str(topic),candidate.evidence_url)
                    if key in seen: continue
                    seen.add(key); count+=1
                    items.append(CollectedItem(candidate.profile_url,"|".join(key),{"provider":"public_interest_discovery","platform":candidate.platform,"account_key":candidate.account_key,"profile_url":candidate.profile_url,"topic":candidate.topic,"evidence_url":candidate.evidence_url,"evidence_text":candidate.evidence_text,"status":"pending_review"}))
                    if count>=max_results: break
                await asyncio.sleep(delay)
        return CollectionBatch(items,requests,detail={"provider":"public_interest_discovery","topics":topics,"pacing_seconds":delay,"candidates":len(items)})
