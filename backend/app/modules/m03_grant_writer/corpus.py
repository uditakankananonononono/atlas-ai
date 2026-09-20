"""Legal funded-award corpus adapters for NIH and NSF."""
from dataclasses import dataclass
import httpx

@dataclass(frozen=True)
class FundedAward:
    source: str
    award_id: str
    title: str
    abstract: str
    url: str

class NihReporterClient:
    async def search(self, terms: str, limit: int = 500) -> list[FundedAward]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post("https://api.reporter.nih.gov/v2/projects/search", json={"criteria":{"advanced_text_search":{"operator":"and","search_field":"all","search_text":terms}},"offset":0,"limit":min(limit,500)})
        response.raise_for_status()
        return [FundedAward("nih_reporter",str(row.get("project_num","")),row.get("project_title") or "",row.get("abstract_text") or "",f"https://reporter.nih.gov/project-details/{row.get('appl_id','')}") for row in response.json().get("results",[])]

class NsfAwardsClient:
    async def search(self, terms: str, limit: int = 500) -> list[FundedAward]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get("https://www.research.gov/awardapi-service/v1/awards.json", params={"keyword":terms,"printFields":"id,title,abstractText","offset":1,"rpp":min(limit,1000)})
        response.raise_for_status()
        return [FundedAward("nsf_awards",str(row.get("id","")),row.get("title") or "",row.get("abstractText") or "",f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={row.get('id','')}") for row in response.json().get("response",{}).get("award",[])]
