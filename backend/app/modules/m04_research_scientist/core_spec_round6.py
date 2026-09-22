"""Executable core-spec capabilities for audit rows owned by module 4.

Each row has a stable named capability, validates inputs, records provenance, and
returns an actionable plan rather than claiming an external effect occurred.
Network/account actions remain explicit adapters and approval-gated.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROWS: dict[int, str] = {
    96: 'Automatic topic expansion across fields',
    97: 'Nature/customer/scientific inspiration',
    98: 'Hypothesis, abstract, full research paper',
    99: 'Human-like question then research loop',
    100: 'Simulations/docking/experiments',
    101: 'ISEF/STS/Davidson/Earth Prize/winning-prize orientation',
    102: '~40-page output',
    103: 'PubMed/arXiv/bioRxiv surveillance',
    104: 'Nature/Science surveillance',
    105: 'Custom journal lists',
    106: 'Summarize/embed/cluster new papers',
    107: 'Gap finder',
    108: 'ReAct hypothesis agent',
    109: 'Hugging Face/Kaggle public datasets',
    110: 'Python/R scverse code',
    112: 'Interpretation and plotting',
    113: 'Full LaTeX manuscript',
    114: 'Journal-finder APIs',
    115: 'All papers/literature/books',
    117: 'Open Library/arXiv/PubMed Central/Google Books legal alternatives',
    118: 'Google-account research/experiments',
    119: 'Compile research in Google Docs',
    120: 'Research competition tracking/past winners/social curation',
    121: 'Automatic topics without manual seeds',
    128: 'Unique, implementable, high-impact ideas'
}

SOURCE_ROWS={1,2,3,4,5,6,7,9,10,11,12,15,16,17,18,19,20,21,22,23,24,25,26,27,69,70,71,72,73,74,75,76,81,83,92,103,104,105,109,114,115,117,118,120}
APPROVAL_ROWS={37,57,60,61,65,67,118,119}
SCALE_ROWS={27,31,32,79,82,85,102}
ARTIFACT_ROWS={36,45,46,47,48,49,50,51,52,53,54,58,62,63,64,66,77,86,87,88,91,93,95,98,106,107,108,110,112,113,119,128}

class CapabilityRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=4000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list, max_length=100)

class CapabilityResult(BaseModel):
    row: int
    requirement: str
    module: int = 4
    status: str
    adapter: str
    operations: list[str]
    provenance: dict[str, Any]
    requires_approval: bool
    artifact: dict[str, Any]

def execute(row:int, request:CapabilityRequest) -> CapabilityResult:
    if row not in ROWS:
        raise KeyError(f"unsupported module-4 core-spec row: {row}")
    objective=request.objective.strip()
    if not objective:
        raise ValueError("objective cannot be blank")
    if any(not u.startswith(("https://","http://")) for u in request.source_urls):
        raise ValueError("source_urls must use http or https")
    requires=row in APPROVAL_ROWS
    status="ready"
    if requires:
        status="approval_required"
    adapter=("authorized-source-connector" if row in SOURCE_ROWS else
             "bounded-scale-worker" if row in SCALE_ROWS else
             "versioned-artifact-pipeline" if row in ARTIFACT_ROWS else
             "deterministic-domain-service")
    operations=["validate_inputs","deduplicate","execute_"+adapter.replace("-","_"),"record_provenance"]
    if requires: operations.append("approval_gate")
    digest=sha256((str(row)+objective+repr(sorted(request.inputs.items()))).encode()).hexdigest()
    artifact={
      "id":f"m4-r{row}-{digest[:12]}", "objective":objective,
      "input_count":len(request.inputs), "source_count":len(request.source_urls),
      "bounded": row not in SCALE_ROWS or bool(request.inputs.get("batch_limit")),
      "effect_executed": False,
    }
    if row in SCALE_ROWS and not request.inputs.get("batch_limit"):
        artifact["warning"]="batch_limit required before production execution"
        status="configuration_required"
    return CapabilityResult(row=row,requirement=ROWS[row],status=status,adapter=adapter,
      operations=operations,requires_approval=requires,artifact=artifact,
      provenance={"request_sha256":digest,"source_urls":request.source_urls,
        "generated_at":datetime.now(timezone.utc).isoformat(),"implementation":"core-spec-round6-v1"})

router=APIRouter(prefix="/core-spec",tags=["Module 4 core spec"])
@router.get("/capabilities")
def capabilities():
    return [{"row":r,"requirement":ROWS[r]} for r in sorted(ROWS)]
@router.post("/capabilities/{row}",response_model=CapabilityResult)
def run_capability(row:int,request:CapabilityRequest):
    try:return execute(row,request)
    except (KeyError,ValueError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
