"""Registry-driven, compliant discovery inputs for brands and partnership announcements."""
from dataclasses import dataclass
from typing import Any, Protocol
import httpx
class PublicSource(Protocol):
    id: str
    async def discover(self,query:str)->list[dict[str,Any]]: ...
@dataclass
class JsonApiSource:
    id:str; endpoint:str
    async def discover(self,query:str)->list[dict[str,Any]]:
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
            response=await client.get(self.endpoint,params={"q":query});response.raise_for_status();body=response.json()
        rows=body if isinstance(body,list) else body.get("results",[])
        return [{"source_id":self.id,"source_url":self.endpoint,**row} for row in rows if isinstance(row,dict)]
@dataclass
class RssAnnouncementSource:
    id:str; feed_url:str
    async def discover(self,query:str)->list[dict[str,Any]]:
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
            response=await client.get(self.feed_url);response.raise_for_status()
        import xml.etree.ElementTree as ET
        root=ET.fromstring(response.content);needle=query.casefold();out=[]
        for item in root.findall(".//item"):
            title=item.findtext("title") or "";description=item.findtext("description") or ""
            if needle in (title+" "+description).casefold():out.append({"source_id":self.id,"source_url":item.findtext("link") or self.feed_url,"title":title,"summary":description})
        return out
class DiscoveryRegistry:
    def __init__(self):self._sources={}
    def register(self,source:PublicSource):
        if source.id in self._sources:raise ValueError(f"duplicate source: {source.id}")
        self._sources[source.id]=source
    async def discover(self,query:str,source_ids:list[str]|None=None):
        selected=source_ids or list(self._sources);rows=[]
        for ident in selected:
            if ident not in self._sources:raise KeyError(ident)
            rows.extend(await self._sources[ident].discover(query))
        return rows
