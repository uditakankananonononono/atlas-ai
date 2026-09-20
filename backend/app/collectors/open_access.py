"""Open-access literature discovery via free official APIs."""
from __future__ import annotations
import os
from .base import CollectionBatch, CollectedItem, HttpCollector

class OpenAccessCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        provider=config.get("provider"); topic=self.require(config,"topic"); limit=min(100,int(config.get("limit",50)))
        if provider == "doaj":
            url=f"https://doaj.org/api/search/articles/{topic}"; response=await self.client.get(url,params={"pageSize":limit}); rows=response.json().get("results",[]) if response.status_code==200 else []
        elif provider == "core":
            key=os.getenv(config.get("key_env","CORE_API_KEY"));
            if not key: raise RuntimeError("CORE_API_KEY is not configured")
            response=await self.client.post("https://api.core.ac.uk/v3/search/works",headers={"Authorization":f"Bearer {key}"},json={"q":topic,"limit":limit}); rows=response.json().get("results",[]) if response.status_code==200 else []
        elif provider == "pmc":
            response=await self.client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",params={"db":"pmc","term":topic,"retmode":"json","retmax":limit}); ids=response.json().get("esearchresult",{}).get("idlist",[]) if response.status_code==200 else []; rows=[{"id":x} for x in ids]
        elif provider == "unpaywall":
            email=self.require(config,"email"); doi=self.require(config,"doi"); response=await self.client.get(f"https://api.unpaywall.org/v2/{doi}",params={"email":email}); rows=[response.json()] if response.status_code==200 else []
        else: raise ValueError("provider must be doaj, core, pmc, or unpaywall")
        response.raise_for_status(); items=[]
        for row in rows:
            ident=str(row.get("id") or row.get("doi") or row.get("DOI")); oa=row.get("best_oa_location") or {}; link=row.get("downloadUrl") or oa.get("url_for_pdf") or row.get("url") or (f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{ident}/" if provider=="pmc" else f"https://doi.org/{ident}")
            items.append(CollectedItem(link,ident,{"provider":f"open_access_{provider}","topic":topic,**row}))
        return CollectionBatch(items,1,detail={"provider":f"open_access_{provider}"})
