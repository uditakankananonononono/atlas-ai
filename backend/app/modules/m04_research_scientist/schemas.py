"""API and domain models for the Research Scientist module."""

from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class PaperInput(BaseModel):
    """A paper collected from an official API, an RSS feed, or user input."""

    paper_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=3, max_length=1000)
    abstract: str = Field(min_length=20, max_length=50_000)
    source: Literal["pubmed", "arxiv", "biorxiv", "crossref", "rss", "user"]
    url: HttpUrl | None = None
    published_at: str | None = None
    keywords: list[str] = Field(default_factory=list, max_length=50)


class Cluster(BaseModel):
    """A transparent, deterministic grouping of related papers."""

    cluster_id: str
    label: str
    paper_ids: list[str]
    shared_terms: list[str]


class SurveillanceRequest(BaseModel):
    papers: list[PaperInput] = Field(min_length=1, max_length=500)
    similarity_threshold: float = Field(default=0.22, ge=0.0, le=1.0)


class SurveillanceResponse(BaseModel):
    clusters: list[Cluster]
    unclustered_paper_ids: list[str]


class HypothesisRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=5000)
    papers: list[PaperInput] = Field(min_length=1, max_length=30)
    provider: str = Field(default="openai", min_length=1, max_length=30)
    model: str | None = Field(default=None, max_length=200)
    dataset_catalogs: list[Literal["huggingface", "kaggle", "ncbi", "zenodo"]] = Field(
        default_factory=lambda: ["huggingface", "kaggle"]
    )


class HypothesisResponse(BaseModel):
    hypothesis: str
    provider: str
    model: str
    evidence_paper_ids: list[str]
    dataset_catalogs: list[str]
    caveats: list[str]


class AnalysisProposalRequest(BaseModel):
    objective: str = Field(min_length=10, max_length=5000)
    language: Literal["python", "r"] = "python"
    code: str = Field(min_length=1, max_length=100_000)
    dataset_urls: list[HttpUrl] = Field(default_factory=list, max_length=20)
    network_access: bool = False


class ProposedAnalysis(BaseModel):
    """An inert proposal. A separate approved sandbox runner must execute it."""

    action_type: Literal["execute_sandboxed_analysis"] = "execute_sandboxed_analysis"
    module_id: Literal[4] = 4
    objective: str
    language: Literal["python", "r"]
    code: str
    dataset_urls: list[str]
    sandbox_policy: Literal["ephemeral-no-network"] = "ephemeral-no-network"
    requires_approval: Literal[True] = True
    status: Literal["proposed"] = "proposed"
