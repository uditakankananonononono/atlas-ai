"""Tenant-scoped discovery staging and explicit promotion into deep tracking."""
from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable, Protocol
from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint, select, text, event, DDL
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

PROMOTION_ACTION = "promote_discovery_source"


class CandidateApprovalBindingRow(Base):
    """Append-only binding. Consumption is separate so this record never changes."""
    __tablename__ = "discovery_approval_bindings"
    candidate_id: Mapped[int] = mapped_column(primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(36), unique=True)
    tenant_id: Mapped[str] = mapped_column(String(120))
    scope_sha256: Mapped[str] = mapped_column(String(64))


class CandidateApprovalUseRow(Base):
    __tablename__ = "discovery_approval_uses"
    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(unique=True)
    source_id: Mapped[int]
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# create_all is used only by local tests/development. Production uses Alembic.
for table in (CandidateApprovalBindingRow.__table__, CandidateApprovalUseRow.__table__):
    for operation in ("UPDATE", "DELETE"):
        event.listen(table, "after_create", DDL(
            f"CREATE TRIGGER {table.name}_no_{operation.lower()} BEFORE {operation} "
            f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'immutable discovery approval record'); END"
        ).execute_if(dialect="sqlite"))


@dataclass(frozen=True)
class VerifiedPromotionDecision:
    approval_id: str
    tenant_id: str
    scope_sha256: str
    expires_at: datetime


class PromotionApprovalAuthority(Protocol):
    """Server dependency, never deserialized from a caller's request/approved flag.

    Implementations must read current approval, owner identity, expiry and
    revocation under the same transaction/lock as promotion.
    """
    def verify(self, db, approval_id: str, tenant_id: str,
               scope_sha256: str, now: datetime) -> VerifiedPromotionDecision: ...


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


class NativePromotionApprovalAuthority:
    """Verify Module 0's persisted decision against a server-owned owner directory.

    owner_for_tenant must come from trusted server configuration/auth state,
    not request input. Revocation is an append-only Module 0 'revoked' event.
    No 'approved: true' payload or arbitrary actor label is treated as consent.
    """
    def __init__(self, owner_for_tenant: Callable[[str], str | None]):
        self._owner_for_tenant = owner_for_tenant

    def verify(self, db, approval_id, tenant_id, scope_sha256, now):
        from app.modules.m00_approval_center.service import ApprovalRequestRow, ApprovalEventRow
        row = db.scalar(select(ApprovalRequestRow).where(
            ApprovalRequestRow.id == approval_id).with_for_update())
        owner = self._owner_for_tenant(tenant_id)
        if (row is None or not owner or row.user_id != tenant_id or
            row.module_id != 0 or row.action_type != PROMOTION_ACTION or
            row.status != "approved" or row.approved_by != owner or
            row.decided_at is None or row.expires_at is None or
            _utc(row.decided_at) > now or _utc(row.expires_at) <= now or
            row.payload.get("scope_sha256") != scope_sha256):
            raise PermissionError("current owner approval required")
        reviewed_scope = row.payload.get("scope")
        if not isinstance(reviewed_scope, dict) or sha256(json.dumps(
                reviewed_scope, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest() != scope_sha256:
            raise PermissionError("approval review payload changed")
        events = list(db.scalars(select(ApprovalEventRow).where(
            ApprovalEventRow.approval_id == approval_id)))
        if (not any(e.event == "approved" and e.actor == owner for e in events) or
            any(e.event == "revoked" for e in events)):
            raise PermissionError("owner approval missing or revoked")
        return VerifiedPromotionDecision(approval_id, tenant_id, scope_sha256, _utc(row.expires_at))


def _scope(candidate, source):
    mapping = {"instagram": "public_instagram", "linkedin": "public_linkedin", "x": "x_api"}
    keys = {"instagram": "accounts", "linkedin": "creator_urls", "x": "accounts"}
    if candidate.platform not in mapping:
        raise ValueError("unsupported discovery platform")
    key = keys[candidate.platform]
    value = candidate.profile_url if candidate.platform == "linkedin" else candidate.account_key
    if not isinstance(value, str) or not value.strip():
        raise ValueError("candidate requires a nonempty source identity")
    config = dict(source.config) if source else {"adapter": mapping[candidate.platform]}
    if config.get("adapter") != mapping[candidate.platform]:
        raise ValueError("existing source adapter mismatch")
    values = list(config.get(key, []))
    if value not in values:
        values.append(value)
    config[key] = values
    settings = {
        "collector_type": source.collector_type if source else (
            CollectorType.OFFICIAL_API.value if candidate.platform == "x" else CollectorType.PUBLIC_PAGE.value),
        "priority": source.priority if source else 60,
        "cadence_seconds": source.cadence_seconds if source else 28800,
        "cost_per_1000_requests_usd": source.cost_per_1000_requests_usd if source else 0,
        "daily_request_cap": source.daily_request_cap if source else 3,
    }
    scope = {"action": PROMOTION_ACTION, "tenant_id": candidate.tenant_id,
             "candidate_id": candidate.id, "platform": candidate.platform,
             "account_key": candidate.account_key, "profile_url": candidate.profile_url,
             "source_key": f"tracked:{candidate.platform}", "source_id": source.id if source else None,
             "prior_config": source.config if source else None,
             "prior_enabled": source.enabled if source else None,
             "config": config, "enabled": True, **settings}
    digest = sha256(json.dumps(scope, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return scope, digest


def _source(db, candidate):
    return db.scalar(select(CollectionSourceRow).where(
        CollectionSourceRow.tenant_id == candidate.tenant_id,
        CollectionSourceRow.source_key == f"tracked:{candidate.platform}").with_for_update())


def request_candidate_promotion(tenant_id: str, candidate_id: int, *,
                                approval_service, ttl_seconds: int = 3600) -> str:
    """Prepare a Module 0 review request and bind its exact scope, without enabling.

    A candidate is bound once. A stale/rejected request cannot be rebound to
    different authority. Restaging a changed candidate requires a new identity.
    An orphan pending request after a crash cannot authorize promotion.
    """
    if ttl_seconds <= 0:
        raise ValueError("approval expiry is required")
    with SessionLocal() as db:
        candidate = db.get(DiscoveryCandidateRow, candidate_id)
        if candidate is None or candidate.tenant_id != tenant_id:
            raise LookupError("candidate not found")
        if candidate.status != "pending_review" or db.get(CandidateApprovalBindingRow, candidate_id):
            raise PermissionError("candidate already reviewed or bound")
        scope, digest = _scope(candidate, _source(db, candidate))
        view = approval_service.submit(module_id=0, action_type=PROMOTION_ACTION,
            payload={"scope": scope, "scope_sha256": digest}, user_id=tenant_id, ttl_seconds=ttl_seconds)
        db.add(CandidateApprovalBindingRow(candidate_id=candidate_id, approval_id=view["id"],
            tenant_id=tenant_id, scope_sha256=digest))
        db.commit()
        return view["id"]


def promote_candidate(tenant_id: str, candidate_id: int, *,
                      approval_authority: PromotionApprovalAuthority | None = None) -> int:
    """Consume the candidate's immutable owner approval and enable exactly once.

    The authority is supplied by trusted server composition, never HTTP JSON.
    Denials roll back every source/candidate/use change. SQLite serializes writes;
    PostgreSQL serializes the tenant/platform source key, including absent rows.
    """
    if approval_authority is None:
        raise PermissionError("trusted server approval authority required")
    with SessionLocal() as db:
        dialect = db.get_bind().dialect.name
        if dialect not in {"sqlite", "postgresql"}:
            raise RuntimeError("promotion requires SQLite or PostgreSQL transaction locking")
        if dialect == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        candidate = db.scalar(select(DiscoveryCandidateRow).where(
            DiscoveryCandidateRow.id == candidate_id).with_for_update())
        if candidate is None or candidate.tenant_id != tenant_id:
            raise LookupError("candidate not found")
        if dialect == "postgresql":
            # Stable signed int64 key, not Python's per-process hash().
            lock_key = int.from_bytes(sha256(f"{tenant_id}:{candidate.platform}".encode()).digest()[:8],
                                      "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        binding = db.get(CandidateApprovalBindingRow, candidate_id)
        if (binding is None or binding.tenant_id != tenant_id or
            candidate.status != "pending_review" or db.get(CandidateApprovalUseRow, binding.approval_id)):
            raise PermissionError("unused bound approval required")
        source = _source(db, candidate)
        scope, digest = _scope(candidate, source)
        if digest != binding.scope_sha256:
            raise PermissionError("reviewed source configuration changed")
        now = datetime.now(timezone.utc)
        decision = approval_authority.verify(db, binding.approval_id, tenant_id, digest, now)
        if (not isinstance(decision, VerifiedPromotionDecision) or
            decision.approval_id != binding.approval_id or decision.tenant_id != tenant_id or
            decision.scope_sha256 != digest or _utc(decision.expires_at) <= datetime.now(timezone.utc)):
            raise PermissionError("verified approval does not match binding")
        if source is None:
            source = CollectionSourceRow(tenant_id=tenant_id, source_key=scope["source_key"],
                **{key: scope[key] for key in ("collector_type", "priority", "cadence_seconds",
                    "cost_per_1000_requests_usd", "daily_request_cap")},
                enabled=True, config=scope["config"], next_run_at=now)
            db.add(source)
            db.flush()
        else:
            source.config = scope["config"]
            source.enabled = True
        db.add(CandidateApprovalUseRow(approval_id=binding.approval_id, candidate_id=candidate_id,
                                      source_id=source.id, used_at=now))
        candidate.status = "approved"
        candidate.reviewed_at = now
        db.commit()
        return source.id
