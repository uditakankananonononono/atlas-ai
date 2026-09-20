"""Pydantic contracts for the Grant & Fellowship Writer module."""

from typing import Literal
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A user-supplied or licensed research item used to ground a proposal."""

    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=10_000)
    source_url: str | None = Field(default=None, max_length=2_000)


class ProposalRequest(BaseModel):
    """Inputs for the bounded proposal-writing pipeline."""

    opportunity_name: str = Field(min_length=2, max_length=500)
    guidelines: str = Field(min_length=20, max_length=50_000)
    applicant_profile: str = Field(min_length=20, max_length=30_000)
    project_summary: str = Field(min_length=20, max_length=30_000)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=100)
    provider: Literal["openai", "anthropic"] = "openai"
    draft_provider: Literal["openai", "anthropic"] = "anthropic"


class StageResult(BaseModel):
    """One auditable model stage in the proposal pipeline."""

    stage: str
    provider: str
    model: str
    text: str


class ProposalResponse(BaseModel):
    """A generated proposal and its auditable intermediate stages."""

    opportunity_name: str
    proposal: str
    stages: list[StageResult]
    requires_human_review: bool = True


class BudgetItem(BaseModel):
    """A single proposed budget line item."""

    category: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1_000)
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    source_note: str | None = Field(default=None, max_length=2_000)


class BudgetRequest(BaseModel):
    """Inputs for deterministic budget calculation."""

    currency: str = Field(default="USD", min_length=3, max_length=3)
    items: list[BudgetItem] = Field(min_length=1, max_length=200)
    indirect_rate_percent: float = Field(default=0, ge=0, le=100)


class BudgetLine(BaseModel):
    category: str
    description: str
    quantity: float
    unit_cost: float
    total: float
    source_note: str | None = None


class BudgetResponse(BaseModel):
    currency: str
    lines: list[BudgetLine]
    direct_total: float
    indirect_total: float
    grand_total: float
    requires_rate_verification: bool = True


class SuccessAnalysisRequest(BaseModel):
    """Proposal and permissioned comparison documents for gap analysis."""

    proposal: str = Field(min_length=20, max_length=100_000)
    funded_examples: list[str] = Field(default_factory=list, max_length=50)


class SuccessAnalysisResponse(BaseModel):
    comparable_examples: int
    shared_language: list[str]
    missing_common_terms: list[str]
    caveat: str


class ExportRequest(BaseModel):
    """Request to stage document generation behind human approval."""

    proposal: str = Field(min_length=20, max_length=100_000)
    title: str = Field(min_length=1, max_length=500)
    formats: list[Literal["docx", "pdf"]] = Field(default_factory=lambda: ["docx", "pdf"], min_length=1)


class ProposedExportResponse(BaseModel):
    approval_id: str
    status: str
    action_type: str
    formats: list[str]


class CorpusIngestRequest(BaseModel):
    query: str = Field(min_length=2,max_length=500)
    target: int = Field(default=1000,ge=1000,le=10000)

class CorpusIngestResponse(BaseModel):
    requested_target:int
    fetched:int
    created:int
    providers:dict[str,int]
    complete:bool
    caveat:str

class CorpusSearchResult(BaseModel):
    source:str; award_id:str; title:str; abstract:str; url:str
