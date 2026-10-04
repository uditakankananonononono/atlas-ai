"""Executable core-spec capabilities for audit rows owned by module 3.

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
    76: 'Google Docs/Sheets access',
    77: 'Report generation',
    78: 'Micro/macro economics and broad idea browsing',
    79: '500,000 fields / constant internet browsing',
    80: 'Venture/company/story/people/failure analysis',
    81: 'Prediction markets',
    82: 'Heavy stock analysis / 1M variables',
    83: 'Gemini guideline research',
    85: '1000+ successful proposals',
    86: 'Claude full draft',
    87: 'GPT critique for clarity/impact/feasibility',
    88: 'Revision from critique',
    90: 'Useful tools/extensions/advice research',
    91: 'Budget template + LLM reasoning',
    92: 'Current market-rate web lookup',
    93: 'Budget table',
    95: 'Multipart ~20-part structure'
}

SOURCE_ROWS={1,2,3,4,5,6,7,9,10,11,12,15,16,17,18,19,20,21,22,23,24,25,26,27,69,70,71,72,73,74,75,76,81,83,92,103,104,105,109,114,115,117,118,120}
APPROVAL_ROWS={37,57,60,61,65,67,118,119}
SCALE_ROWS={27,31,32,79,82,85,102}
ARTIFACT_ROWS={36,45,46,47,48,49,50,51,52,53,54,58,62,63,64,66,77,86,87,88,91,93,95,98,106,107,108,110,112,113,119,128}

class CapabilityRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=4000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list, max_length=100)
    approved: bool = False

class CapabilityResult(BaseModel):
    row: int
    requirement: str
    module: int = 3
    status: str  # plan_only | approval_required | configuration_required. Never "ready"/"done": no row here performs the capability itself.
    executed: bool = False
    adapter: str
    operations: list[str]
    provenance: dict[str, Any]
    requires_approval: bool
    artifact: dict[str, Any]

def _valid_source_url(url)->bool:
    """Format check only (scheme, hostname, no userinfo, no whitespace/control chars). It does not prove the source exists."""
    from urllib.parse import urlsplit
    if not isinstance(url,str) or len(url)>2048 or any(ord(c)<=32 or ord(c)==127 for c in url):
        return False
    try:
        u=urlsplit(url); host=u.hostname; u.port
    except ValueError:
        return False
    return u.scheme in ("http","https") and bool(host) and u.username is None and u.password is None

def _budget_table(request:CapabilityRequest)->dict[str,Any]:
    """Row 93 REAL path: runs GrantWriterService.build_budget over caller-supplied, dated, sourced rates.
    inputs: rates=[{code,label,unit,amount,currency,effective_from,[effective_to],source_url (http/https),observed_at}], lines=[{rate_code,quantity,description}],
    as_of (YYYY-MM-DD), optional indirect_rate. No rate is invented: a missing/expired rate raises ValueError (HTTP 422)."""
    from datetime import date
    from decimal import Decimal, InvalidOperation
    from .lane_models import BudgetRate, BudgetRequestLine
    from .lane_repository import GrantCorpus
    from .lane_service import GrantWriterService
    i=request.inputs
    try:
        if not isinstance(i["rates"],list) or not isinstance(i["lines"],list) or not i["rates"] or not i["lines"]:
            raise TypeError("rates and lines must be non-empty lists")
        if not all(isinstance(x,dict) for x in i["rates"]) or not all(isinstance(x,dict) for x in i["lines"]):
            raise TypeError("each rate and line must be an object")
        import re
        from decimal import Decimal as _D
        if len(i["rates"])>200 or len(i["lines"])>200:
            raise TypeError("too many rates or lines")
        code_ok=lambda v:isinstance(v,str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",v) is not None
        text_ok=lambda v,n:isinstance(v,str) and 1<=len(v)<=n and all(c.isprintable() for c in v)
        num_ok=lambda v:isinstance(v,(str,int,float)) and not isinstance(v,bool) and _D(str(v)).is_finite() and abs(_D(str(v)))<_D("1e12")
        for r in i["rates"]:
            if not (code_ok(r.get("code")) and text_ok(r.get("label"),120) and text_ok(r.get("unit"),40)
                    and isinstance(r.get("currency"),str) and re.fullmatch(r"[A-Z]{3}",r["currency"]) and num_ok(r.get("amount"))):
                raise TypeError("rate field format")
        for l in i["lines"]:
            if not (code_ok(l.get("rate_code")) and text_ok(l.get("description"),500) and num_ok(l.get("quantity"))):
                raise TypeError("line field format")
        if "indirect_rate" in i and not num_ok(i["indirect_rate"]):
            raise TypeError("indirect_rate format")
        for r in i["rates"]:
            url=r.get("source_url")
            if not _valid_source_url(url):
                raise ValueError("row 93 rate source_url must be an http(s) URL with a hostname, no credentials or control characters")
        rates=[BudgetRate(code=r["code"],label=r["label"],unit=r["unit"],amount=Decimal(str(r["amount"])),currency=r["currency"],
                          effective_from=date.fromisoformat(r["effective_from"]),source_url=r["source_url"],
                          effective_to=date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None,
                          observed_at=datetime.fromisoformat(r["observed_at"])) for r in i["rates"]]
        lines=[BudgetRequestLine(l["rate_code"],Decimal(str(l["quantity"])),l["description"]) for l in i["lines"]]
        as_of=date.fromisoformat(i["as_of"]); ind=Decimal(str(i.get("indirect_rate","0")))
        b=GrantWriterService(GrantCorpus(),rates).build_budget(lines,as_of=as_of,observed_by=datetime.now(timezone.utc),indirect_rate=ind)
    except (KeyError,TypeError,AttributeError,ValueError,InvalidOperation) as exc:
        # Fixed categories only: never echo caller input (it may hold secrets or be unbounded) into the error or the log.
        from .lane_models import ValidationError
        if isinstance(exc,ValidationError):
            m=str(exc)
            cat=("no current, observed rate for the requested code and date" if m.startswith("no current, observed rate") else
                 "quantity must be positive" if "quantity" in m else
                 "mixed-currency budgets are not supported" if "mixed-currency" in m else
                 "indirect_rate must be between 0 and 1" if "indirect_rate" in m else
                 "a rate or line was rejected by the budget rules")
        elif isinstance(exc,KeyError):
            cat="a required field is missing"
        elif str(exc).startswith("row 93 rate source_url"):
            raise ValueError("row 93 rate source_url must be an http(s) URL with a hostname, no credentials or control characters") from None
        else:
            cat="a field has the wrong type or format"
        raise ValueError(f"row 93 budget inputs invalid: {cat}") from None
    zero=[l.rate_code for l in b.lines if l.total==0]
    out={"provenance_note":"rates, dates and source URLs are CALLER-ASSERTED; this engine did not fetch or verify them",
            "currency":b.currency,"direct_total":str(b.direct_total),"indirect_total":str(b.indirect_total),
            "grand_total":str(b.grand_total),"as_of":b.as_of.isoformat(),
            "lines":[{"rate_code":l.rate_code,"description":l.description,"quantity":str(l.quantity),"unit":l.unit,
                      "unit_amount":str(l.unit_amount),"total":str(l.total),"source_url":l.source_url} for l in b.lines]}
    if zero: out["warnings"]=[{"code":"line_rounds_to_zero","rate_codes":zero,"note":"line total rounds to 0.00 at 2 decimals; quantity or rate is below one cent"}]
    return out

def execute(row:int, request:CapabilityRequest) -> CapabilityResult:
    if row not in ROWS:
        raise KeyError(f"unsupported module-3 core-spec row: {row}")
    objective=request.objective.strip()
    if not objective:
        raise ValueError("objective cannot be blank")
    if any(not u.startswith(("https://","http://")) for u in request.source_urls):
        raise ValueError("source_urls must use http or https")
    requires=row in APPROVAL_ROWS
    status="plan_only"  # PLAN ONLY: validates input and records provenance; performs no collection, drafting, export or external call
    if requires and not request.approved:
        status="approval_required"
    adapter=("authorized-source-connector" if row in SOURCE_ROWS else
             "bounded-scale-worker" if row in SCALE_ROWS else
             "versioned-artifact-pipeline" if row in ARTIFACT_ROWS else
             "deterministic-domain-service")
    operations=["validate_inputs","deduplicate","execute_"+adapter.replace("-","_"),"record_provenance"]
    if requires: operations.append("approval_gate")
    digest=sha256((str(row)+objective+repr(sorted(request.inputs.items()))).encode()).hexdigest()
    artifact={
      "id":f"m3-r{row}-{digest[:12]}", "objective":objective,
      "input_count":len(request.inputs), "source_count":len(request.source_urls),
      "bounded": row not in SCALE_ROWS or bool(request.inputs.get("batch_limit")),
      "effect_executed": bool(request.approved) if requires else False,
    }
    if row in SCALE_ROWS and not request.inputs.get("batch_limit"):
        artifact["warning"]="batch_limit required before production execution"
        status="configuration_required"
    executed=False
    if row==85:
        artifact["real_operation"]={"ingest":"POST /grant-writer/corpus/ingest","search":"GET /grant-writer/corpus/search?query=",
            "note":"The funded-award corpus is real (NIH RePORTER / NSF Awards clients, per-tenant, authenticated). This core-spec row performs none of it; it is plan_only. Corpus size depends on what was ingested for the tenant."}
    if row==93 and {"rates","lines","as_of"}<=request.inputs.keys():
        artifact["budget"]=_budget_table(request); executed=True; status="executed"
        adapter="grant-writer-budget-engine"; operations[2]="execute_build_budget"
    return CapabilityResult(row=row,requirement=ROWS[row],status=status,adapter=adapter,executed=executed,
      operations=operations,requires_approval=requires,artifact=artifact,
      provenance={"request_sha256":digest,"source_urls":request.source_urls,
        "generated_at":datetime.now(timezone.utc).isoformat(),"implementation":"core-spec-round6-v1"})

router=APIRouter(prefix="/core-spec",tags=["Module 3 core spec"])
@router.get("/capabilities")
def capabilities():
    return [{"row":r,"requirement":ROWS[r]} for r in sorted(ROWS)]
@router.post("/capabilities/{row}",response_model=CapabilityResult)
def run_capability(row:int,request:CapabilityRequest):
    try:return execute(row,request)
    except (KeyError,ValueError) as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc
