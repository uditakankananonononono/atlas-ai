"""Free/public market source adapters with explicit provenance."""
from dataclasses import dataclass
from typing import Any, Protocol
import httpx

@dataclass(frozen=True)
class MarketRecord:
    source: str
    external_id: str
    observed_at: str
    payload: dict[str, Any]
    source_url: str

class MarketSource(Protocol):
    async def fetch(self, query: str, limit: int) -> list[MarketRecord]: ...

class SecEdgarSource:
    async def fetch(self, query: str, limit: int = 40) -> list[MarketRecord]:
        headers = {"User-Agent": "Atlas AI research contact: operator-configured"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get("https://efts.sec.gov/LATEST/search-index", params={"q": query, "dateRange": "custom", "startdt": "2001-01-01", "from": 0, "size": limit}, headers=headers)
        response.raise_for_status()
        records=[]
        for hit in response.json().get("hits", {}).get("hits", []):
            source=hit.get("_source", {}); accession=source.get("adsh", hit.get("_id", "")); url=f"https://www.sec.gov/Archives/edgar/data/{accession.replace('-', '')}"
            records.append(MarketRecord("sec_edgar", accession, source.get("file_date", ""), source, url))
        return records

class ArxivEconomicsSource:
    async def fetch(self, query: str, limit: int = 40) -> list[MarketRecord]:
        url="https://export.arxiv.org/api/query"
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.get(url,params={"search_query":f"cat:econ.* AND all:{query}","start":0,"max_results":limit}); response.raise_for_status()
        # Feed normalization is delegated to the common RSS/Atom parser in Module 1.
        return [MarketRecord("arxiv_econ", f"query:{query}", "", {"atom_xml": response.text}, str(response.url))]

class PublicJsonSource:
    """Configured official/free JSON endpoint for prediction or stock-market data."""
    def __init__(self, source_name: str, url: str, params: dict[str, str] | None = None) -> None:
        self.source_name, self.url, self.params = source_name, url, params or {}
    async def fetch(self, query: str, limit: int = 100) -> list[MarketRecord]:
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.get(self.url,params={**self.params,"query":query,"limit":str(limit)}); response.raise_for_status()
        payload=response.json(); rows=payload if isinstance(payload,list) else payload.get("data", payload.get("results", []))
        return [MarketRecord(self.source_name,str(row.get("id",i)),str(row.get("timestamp",row.get("date",""))),row,str(response.url)) for i,row in enumerate(rows[:limit])]
