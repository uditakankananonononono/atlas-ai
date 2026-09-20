"""Free public research, news, and venture source adapters."""
from __future__ import annotations
import os, xml.etree.ElementTree as ET
from urllib.parse import quote
from bs4 import BeautifulSoup
from .base import CollectionBatch, CollectedItem, HttpCollector

def tagged(provider: str, topic: str, row: dict) -> dict:
    return {"provider":provider,"topic":topic,"source_tags":[topic],**row}

class ArxivCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        items=[]; requests=0
        for topic in config.get("topics",[]):
            response=await self.client.get("https://export.arxiv.org/api/query",params={"search_query":f'all:"{topic}"',"start":0,"max_results":min(100,int(config.get("max_results",50))),"sortBy":"submittedDate","sortOrder":"descending"}); requests+=1; response.raise_for_status()
            root=ET.fromstring(response.text); ns={"a":"http://www.w3.org/2005/Atom"}
            for entry in root.findall("a:entry",ns):
                ident=(entry.findtext("a:id",default="",namespaces=ns)); title=" ".join(entry.findtext("a:title",default="",namespaces=ns).split())
                items.append(CollectedItem(ident,ident,tagged("arxiv",topic,{"title":title,"summary":entry.findtext("a:summary",default="",namespaces=ns),"published":entry.findtext("a:published",default="",namespaces=ns)})))
        return CollectionBatch(items,requests,detail={"provider":"arxiv","topics":config.get("topics",[])})

class BioMedRxivCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        server=config.get("server","biorxiv")
        if server not in ("biorxiv","medrxiv"): raise ValueError("server must be biorxiv or medrxiv")
        response=await self.client.get(f"https://api.biorxiv.org/details/{server}/{config.get('from_date','2020-01-01')}/{config.get('to_date','3000-01-01')}/0",params={"cursor":config.get("cursor",0)}); response.raise_for_status(); data=response.json(); items=[]
        topics=[str(x).lower() for x in config.get("topics",[])]
        for row in data.get("collection",[]):
            text=f"{row.get('title','')} {row.get('abstract','')}".lower(); matched=[t for t in topics if t in text]
            if topics and not matched: continue
            doi=row.get("doi"); url=f"https://doi.org/{doi}" if doi else row.get("jatsxml","")
            items.append(CollectedItem(url,str(doi or row.get("title")),tagged(f"{server}_api",matched[0] if matched else "unclassified",row)))
        return CollectionBatch(items,1,cursor=str(data.get("messages",[{}])[0].get("cursor","")),detail={"provider":f"{server}_api"})

class PubMedCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        items=[]; requests=0; key=os.getenv(config.get("key_env","NCBI_API_KEY"))
        for topic in config.get("topics",[]):
            params={"db":"pubmed","term":topic,"retmode":"json","retmax":min(200,int(config.get("max_results",100))),"sort":"pub date"}
            if key: params["api_key"]=key
            search=await self.client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",params=params); requests+=1; search.raise_for_status(); ids=search.json().get("esearchresult",{}).get("idlist",[])
            if not ids: continue
            summary=await self.client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",params={"db":"pubmed","id":",".join(ids),"retmode":"json",**({"api_key":key} if key else {})}); requests+=1; summary.raise_for_status(); rows=summary.json().get("result",{})
            for ident in ids:
                row=rows.get(ident,{})
                items.append(CollectedItem(f"https://pubmed.ncbi.nlm.nih.gov/{ident}/",ident,tagged("pubmed_eutils",topic,row)))
        return CollectionBatch(items,requests,detail={"provider":"pubmed_eutils"})

class SemanticScholarCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        items=[]; requests=0; key=os.getenv(config.get("key_env","SEMANTIC_SCHOLAR_API_KEY")); headers={"x-api-key":key} if key else {}
        for topic in config.get("topics",[]):
            response=await self.client.get("https://api.semanticscholar.org/graph/v1/paper/search",headers=headers,params={"query":topic,"limit":min(100,int(config.get("max_results",50))),"fields":"title,abstract,authors,year,url,externalIds,citationCount"}); requests+=1; response.raise_for_status()
            for row in response.json().get("data",[]):
                ident=row["paperId"]; items.append(CollectedItem(row.get("url") or f"https://www.semanticscholar.org/paper/{ident}",ident,tagged("semantic_scholar",topic,row)))
        return CollectionBatch(items,requests,detail={"provider":"semantic_scholar"})

class FeedCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        items=[]; requests=0
        for feed in config.get("feeds",[]):
            response=await self.client.get(feed["url"] if isinstance(feed,dict) else feed); requests+=1
            if response.status_code in (403,429): raise RuntimeError("feed collection stopped on block/throttle")
            response.raise_for_status(); root=ET.fromstring(response.content)
            entries=root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
            for entry in entries[:min(200,int(config.get("max_results",100)))]:
                def text(name): return entry.findtext(name) or entry.findtext(f"{{http://www.w3.org/2005/Atom}}{name}") or ""
                link=text("link"); link_node=entry.find("{http://www.w3.org/2005/Atom}link")
                if not link and link_node is not None: link=link_node.get("href","")
                title=text("title"); summary=text("description") or text("summary")
                topic=(feed.get("topic","unclassified") if isinstance(feed,dict) else "unclassified")
                items.append(CollectedItem(link,link or title,tagged("rss_atom",topic,{"title":title,"summary":BeautifulSoup(summary,"html.parser").get_text(" ",strip=True)})))
        return CollectionBatch(items,requests,detail={"provider":"rss_atom"})

class HackerNewsCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        items=[]; requests=0
        for topic in config.get("topics",[]):
            response=await self.client.get("https://hn.algolia.com/api/v1/search_by_date",params={"query":topic,"tags":"story","hitsPerPage":min(100,int(config.get("max_results",50)))}); requests+=1; response.raise_for_status()
            for row in response.json().get("hits",[]):
                ident=str(row["objectID"]); url=row.get("url") or f"https://news.ycombinator.com/item?id={ident}"
                items.append(CollectedItem(url,ident,tagged("hacker_news_algolia",topic,row)))
        return CollectionBatch(items,requests,detail={"provider":"hacker_news_algolia"})

class ProductHuntCollector(FeedCollector):
    """Free public Product Hunt RSS, avoiding private/paid GraphQL access."""
    async def collect(self, config: dict) -> CollectionBatch:
        copied={**config,"feeds":config.get("feeds") or [{"url":"https://www.producthunt.com/feed","topic":"entrepreneurship"}]}
        batch=await super().collect(copied); batch.detail={"provider":"product_hunt_feed"}
        for item in batch.items: item.payload["provider"]="product_hunt_feed"
        return batch
