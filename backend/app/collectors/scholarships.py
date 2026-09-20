"""Free crawler for explicitly registered public scholarship pages."""
from __future__ import annotations
import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from .base import CollectionBatch, CollectedItem, HttpCollector

class ScholarshipSiteCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        delay=max(2.0,float(config.get("delay_seconds",3)))
        max_links=min(100,max(1,int(config.get("max_links_per_site",30))))
        items=[]; requests=0
        for site in config.get("sites",[]):
            base=site if site.startswith("http") else f"https://{site}"
            response=await self.client.get(base,headers={"User-Agent":config.get("user_agent","AtlasScholarshipIndexer/1.0 (+respectful public indexing)")})
            requests+=1
            if response.status_code in (403,429):
                raise RuntimeError(f"public scholarship crawl stopped on throttle/block at {urlparse(base).netloc}")
            response.raise_for_status(); soup=BeautifulSoup(response.text,"html.parser")
            found=0
            for anchor in soup.select("a[href]"):
                text=" ".join(anchor.get_text(" ",strip=True).split())
                href=urljoin(str(response.url),anchor.get("href"))
                if urlparse(href).netloc != urlparse(str(response.url)).netloc: continue
                hay=f"{text} {href}".lower()
                if any(word in hay for word in ("scholarship","fellowship","grant","award","apply","deadline")):
                    items.append(CollectedItem(href,href,{"provider":"public_scholarship_site","site":urlparse(base).netloc,"title":text,"url":href})); found+=1
                    if found>=max_links: break
            await asyncio.sleep(delay)
        return CollectionBatch(items,requests,detail={"provider":"public_scholarship_site","sites":len(config.get("sites",[])),"pacing_seconds":delay})
