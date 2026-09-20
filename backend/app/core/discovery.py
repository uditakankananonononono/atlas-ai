"""Tenant-scoped discovery staging and explicit promotion into deep tracking."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from app.core.collection import CollectionSourceRow, CollectorType
from app.core.database import Base, SessionLocal

class DiscoveryCandidateRow(Base):
    __tablename__="discovery_candidates"
    __table_args__=(UniqueConstraint("tenant_id","platform","account_key"),)
    id: Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    tenant_id: Mapped[str]=mapped_column(String(120),index=True)
    platform: Mapped[str]=mapped_column(String(30),index=True)
    account_key: Mapped[str]=mapped_column(String(300))
    profile_url: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30),default="pending_review",index=True)
    evidence: Mapped[list[dict]]=mapped_column(JSON,default=list)
    discovered_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    reviewed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

def stage_candidates(tenant_id: str, items: list[dict]) -> int:
    staged=0
    with SessionLocal() as db:
        for item in items:
            platform=item["platform"]; account=item["account_key"]
            row=db.scalar(select(DiscoveryCandidateRow).where(DiscoveryCandidateRow.tenant_id==tenant_id,DiscoveryCandidateRow.platform==platform,DiscoveryCandidateRow.account_key==account))
            evidence={"topic":item["topic"],"url":item["evidence_url"],"text":item["evidence_text"]}
            if row is None:
                row=DiscoveryCandidateRow(tenant_id=tenant_id,platform=platform,account_key=account,profile_url=item["profile_url"],evidence=[evidence]); db.add(row); staged+=1
            elif evidence not in row.evidence:
                row.evidence=[*row.evidence,evidence]
        db.commit()
    return staged

def promote_candidate(tenant_id: str, candidate_id: int) -> int:
    """After owner review, add the account to the matching deep-tracking source."""
    mapping={"instagram":"public_instagram","linkedin":"public_linkedin","x":"x_api"}
    config_keys={"instagram":"accounts","linkedin":"creator_urls","x":"accounts"}
    with SessionLocal() as db:
        candidate=db.get(DiscoveryCandidateRow,candidate_id)
        if candidate is None or candidate.tenant_id != tenant_id: raise LookupError("candidate not found")
        adapter=mapping[candidate.platform]
        source=db.scalar(select(CollectionSourceRow).where(CollectionSourceRow.tenant_id==tenant_id,CollectionSourceRow.source_key==f"tracked:{candidate.platform}"))
        value=candidate.profile_url if candidate.platform=="linkedin" else candidate.account_key
        if source is None:
            now=datetime.now(timezone.utc); source=CollectionSourceRow(tenant_id=tenant_id,source_key=f"tracked:{candidate.platform}",collector_type=CollectorType.PUBLIC_PAGE.value if candidate.platform!="x" else CollectorType.OFFICIAL_API.value,priority=60,cadence_seconds=28800,enabled=True,cost_per_1000_requests_usd=0,daily_request_cap=3,config={"adapter":adapter,config_keys[candidate.platform]:[value]},next_run_at=now); db.add(source); db.flush()
        else:
            config=dict(source.config); values=list(config.get(config_keys[candidate.platform],[]))
            if value not in values: values.append(value)
            config[config_keys[candidate.platform]]=values; source.config=config
        candidate.status="approved"; candidate.reviewed_at=datetime.now(timezone.utc); db.commit(); return source.id
