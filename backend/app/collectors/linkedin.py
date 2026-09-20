"""Conservative no-login indexing of named creators' public LinkedIn pages."""
from __future__ import annotations
import asyncio, re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from .base import CollectionBatch, CollectedItem, HttpCollector

USER_AGENT="AtlasPublicIndexer/1.0 (+respectful public indexing)"

class PublicLinkedInCollector(HttpCollector):
    async def _robots_allowed(self, url: str, user_agent: str) -> bool:
        parsed=urlparse(url); robots=f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        response=await self.client.get(robots,headers={"User-Agent":user_agent})
        if response.status_code in (403,429): raise RuntimeError("LinkedIn robots check blocked or throttled collection")
        if response.status_code >= 400: return False
        parser=RobotFileParser(); parser.set_url(robots); parser.parse(response.text.splitlines())
        return parser.can_fetch(user_agent,url)

    async def collect(self, config: dict) -> CollectionBatch:
        delay=max(10.0,float(config.get("delay_seconds",15)))
        max_items=min(25,max(1,int(config.get("items_per_creator",10))))
        user_agent=config.get("user_agent",USER_AGENT); items=[]; requests=0
        for creator in config.get("creator_urls",[]):
            parsed=urlparse(creator)
            if parsed.scheme != "https" or parsed.netloc not in ("www.linkedin.com","linkedin.com"):
                raise ValueError("creator URLs must be public linkedin.com HTTPS URLs")
            if not await self._robots_allowed(creator,user_agent):
                continue
            response=await self.client.get(creator,headers={"User-Agent":user_agent}); requests+=2
            if response.status_code in (403,429): raise RuntimeError("public LinkedIn collection stopped on block/throttle")
            response.raise_for_status(); soup=BeautifulSoup(response.text,"html.parser"); seen=set()
            for anchor in soup.select("a[href]"):
                url=urljoin(str(response.url),anchor.get("href"))
                if not re.search(r"linkedin\.com/(?:posts|pulse)/",url): continue
                url=url.split("?")[0]
                if url in seen: continue
                seen.add(url); text=" ".join(anchor.get_text(" ",strip=True).split())
                items.append(CollectedItem(url,url,{"provider":"linkedin_public","platform":"linkedin","creator_url":creator,"title":text,"url":url}))
                if len(seen)>=max_items: break
            await asyncio.sleep(delay)
        return CollectionBatch(items,requests,detail={"provider":"linkedin_public","creators":len(config.get("creator_urls",[])),"pacing_seconds":delay,"robots_aware":True})
