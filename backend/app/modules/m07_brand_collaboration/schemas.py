"""Contracts for Module 7, Brand Collaboration Manager."""
from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl

class BrandDiscoveryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mission: str = Field(min_length=3, max_length=4000)
    public_url: HttpUrl
    contact_api: Literal["brand_api", "public_website", "user_supplied"] = "public_website"
    audience_tags: list[str] = Field(default_factory=list, max_length=50)

class BrandCandidate(BrandDiscoveryIn):
    id: str; alignment_score: float; alignment_reasons: list[str]; created_at: datetime

class MediaKitIn(BaseModel):
    brand_id: str; creator_name: str = Field(min_length=1, max_length=200)
    creator_mission: str = Field(min_length=3, max_length=4000)
    audience: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    case_studies: list[dict[str, Any]] = Field(default_factory=list, max_length=20)

class SponsorshipPackageIn(BaseModel):
    brand_id: str; currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    tiers: list[dict[str, Any]] = Field(min_length=1, max_length=10)

class InvoiceIn(BaseModel):
    brand_id: str; invoice_number: str = Field(min_length=1, max_length=80)
    issued_on: date; due_on: date; currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    line_items: list[dict[str, Any]] = Field(min_length=1, max_length=100)

class ArtifactOut(BaseModel):
    id: str; kind: Literal["media_kit", "sponsorship_package", "invoice", "performance_report"]
    brand_id: str; content_type: str; sha256: str; created_at: datetime; metadata: dict[str, Any]

class PartnershipEventIn(BaseModel):
    brand_id: str; kind: Literal["communication", "deal", "deliverable", "metric"]
    occurred_at: datetime; data: dict[str, Any]

class PartnershipEventOut(PartnershipEventIn):
    id: str; created_at: datetime

class ReportIn(BaseModel):
    brand_id: str; period_start: date; period_end: date; metrics: dict[str, float]
    narrative_notes: list[str] = Field(default_factory=list, max_length=100)

class ApprovalProposal(BaseModel):
    approval_id: str; action_type: Literal["send_brand_report", "send_brand_collateral", "send_invoice"]
    payload: dict[str, Any]; status: Literal["pending"] = "pending"
