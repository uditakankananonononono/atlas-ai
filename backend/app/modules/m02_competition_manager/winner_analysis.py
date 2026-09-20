"""Source-provenanced winner/tip aggregation. No prediction without real evidence."""
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class WinnerEvidence:
    source_url: str
    source_type: str
    competition: str
    published_at: str | None
    content: str
    attributes: dict[str,Any]

def aggregate_winner_tips(records: list[WinnerEvidence]) -> dict:
    seen=set(); evidence=[]
    for row in records:
        key=(row.source_url,row.content.strip())
        if key in seen: continue
        seen.add(key); evidence.append({"source_url":row.source_url,"source_type":row.source_type,"competition":row.competition,"published_at":row.published_at,"content":row.content,"attributes":row.attributes})
    return {"evidence_count":len(evidence),"evidence":evidence,"prediction_ready":False,"note":"Human review and real labeled outcomes are required before calibrated prediction."}
