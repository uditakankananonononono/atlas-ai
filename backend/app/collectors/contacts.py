"""Official outreach enrichment APIs. These discover data; they never send messages."""
import os
from .base import CollectionBatch, CollectedItem, HttpCollector

class HunterDomainCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        key=os.getenv(config.get("key_env","HUNTER_API_KEY"))
        if not key: raise RuntimeError("HUNTER_API_KEY is not configured")
        response=await self.client.get("https://api.hunter.io/v2/domain-search",params={"api_key":key,"domain":self.require(config,"domain"),"limit":min(100,int(config.get("limit",100)))})
        response.raise_for_status(); data=response.json().get("data",{}); items=[]
        for row in data.get("emails",[]):
            email=row.get("value");
            if email: items.append(CollectedItem(f"mailto:{email}",email,{"provider":"hunter","organization":data.get("organization"),**row}))
        return CollectionBatch(items,1,detail={"provider":"hunter"})

class ApolloPeopleCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        key=os.getenv(config.get("key_env","APOLLO_API_KEY"))
        if not key: raise RuntimeError("APOLLO_API_KEY is not configured")
        response=await self.client.post("https://api.apollo.io/api/v1/mixed_people/search",headers={"X-Api-Key":key,"Content-Type":"application/json"},json={"q_organization_domains":config.get("domains",[]),"person_titles":config.get("titles",[]),"page":int(config.get("page",1)),"per_page":min(100,int(config.get("limit",100)))})
        response.raise_for_status(); data=response.json(); items=[]
        for row in data.get("people",[]):
            ident=str(row.get("id") or row.get("email") or row.get("linkedin_url"))
            if ident and ident != "None": items.append(CollectedItem(row.get("linkedin_url") or (f"mailto:{row['email']}" if row.get("email") else f"apollo:{ident}"),ident,{"provider":"apollo",**row}))
        pagination=data.get("pagination",{})
        return CollectionBatch(items,1,cursor=str(pagination.get("page") or ""),detail={"provider":"apollo","total":pagination.get("total_entries")})
