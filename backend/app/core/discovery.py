"""Tenant-scoped discovery staging and explicit promotion into deep tracking."""
from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable
import os
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
    __table_args__ = (UniqueConstraint("candidate_id", "version"),)
    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(index=True)
    version: Mapped[int]
    source_key: Mapped[str] = mapped_column(String(300))
    target_source_id: Mapped[int | None] = mapped_column(nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(120))
    scope_sha256: Mapped[str] = mapped_column(String(64))


class CandidateApprovalUseRow(Base):
    __tablename__ = "discovery_approval_uses"
    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(index=True)
    source_id: Mapped[int]
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# create_all is used only by local tests/development. Production uses Alembic.
for table in (CandidateApprovalBindingRow.__table__, CandidateApprovalUseRow.__table__):
    for operation in ("UPDATE", "DELETE"):
        event.listen(table, "after_create", DDL(
            f"CREATE TRIGGER {table.name}_no_{operation.lower()} BEFORE {operation} "
            f"ON {table.name} BEGIN SELECT RAISE(ABORT, 'immutable discovery approval record'); END"
        ).execute_if(dialect="sqlite"))


# Mirror production migration guards in PostgreSQL create_all test databases.
for table in (CandidateApprovalBindingRow.__table__, CandidateApprovalUseRow.__table__):
    event.listen(table, "before_create", DDL("""CREATE OR REPLACE FUNCTION
        discovery_approval_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'immutable discovery approval record' USING ERRCODE = '23000'; END;
        $$ LANGUAGE plpgsql""").execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL(
        f"CREATE TRIGGER {table.name}_immutable BEFORE UPDATE OR DELETE ON {table.name} "
        "FOR EACH ROW EXECUTE FUNCTION discovery_approval_immutable()"
    ).execute_if(dialect="postgresql"))


@dataclass(frozen=True)
class VerifiedPromotionDecision:
    approval_id: str
    tenant_id: str
    scope_sha256: str
    expires_at: datetime


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


def _scope(candidate, source, source_key, version):
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
             "attempt_version": version, "operation": "update" if source else "add",
             "source_key": source_key, "source_id": source.id if source else None,
             "prior_config": source.config if source else None,
             "prior_enabled": source.enabled if source else None,
             "config": config, "enabled": True, **settings}
    digest = sha256(json.dumps(scope, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return scope, digest


def _identity(candidate):
    # Stable per-account key, not one mutable bucket for an entire platform.
    return f"tracked:{candidate.platform}:{sha256(candidate.account_key.encode()).hexdigest()}"


def _source(db, candidate, source_key):
    return db.scalar(select(CollectionSourceRow).where(
        CollectionSourceRow.tenant_id == candidate.tenant_id,
        CollectionSourceRow.source_key == source_key).with_for_update())


def _lock(db, tenant_id, candidate_id):
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "postgresql":
        key = int.from_bytes(sha256(f"discovery:{tenant_id}:{candidate_id}".encode()).digest()[:8],
                             "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    else:
        raise RuntimeError("promotion requires SQLite or PostgreSQL transaction locking")


def _latest(db, candidate_id):
    return db.scalar(select(CandidateApprovalBindingRow).where(
        CandidateApprovalBindingRow.candidate_id == candidate_id).order_by(
        CandidateApprovalBindingRow.version.desc()).limit(1))


def request_candidate_promotion(tenant_id: str, candidate_id: int, *,
                                approval_service, ttl_seconds: int = 3600,
                                target_source_id: int | None = None) -> str:
    """Atomically create an immutable owner-review attempt and Module 0 request.

    Pending duplicate requests return the same id. Denied, expired or revoked
    attempts can be retried with a fresh id/version. Used permits never rebind.
    Updating an existing source requires its explicit id, not a platform default.
    """
    from app.modules.m00_approval_center.service import ApprovalRequestRow, ApprovalEventRow, Service
    if ttl_seconds <= 0:
        raise ValueError("approval expiry is required")
    if not isinstance(approval_service, Service):
        raise TypeError("native Module 0 service required")
    with SessionLocal() as db:
        # The request and binding must be committed by the same database session.
        with approval_service._sessions() as approval_db:
            if approval_db.get_bind() is not db.get_bind():
                raise ValueError("approval service must use the discovery database")
        _lock(db, tenant_id, candidate_id)
        candidate = db.scalar(select(DiscoveryCandidateRow).where(
            DiscoveryCandidateRow.id == candidate_id).with_for_update())
        if candidate is None or candidate.tenant_id != tenant_id:
            raise LookupError("candidate not found")
        latest = _latest(db, candidate_id)
        if candidate.status != "pending_review":
            if latest and db.get(CandidateApprovalUseRow, latest.approval_id):
                return latest.approval_id  # duplicate request, not another permit
            raise PermissionError("candidate already reviewed")
        if latest:
            row = db.get(ApprovalRequestRow, latest.approval_id)
            revoked = db.scalar(select(ApprovalEventRow.id).where(
                ApprovalEventRow.approval_id == latest.approval_id,
                ApprovalEventRow.event == "revoked"))
            if row and not revoked and row.status in {"pending", "approved"} and (
                    row.expires_at and _utc(row.expires_at) > datetime.now(timezone.utc)):
                if target_source_id != latest.target_source_id:
                    raise PermissionError("active attempt targets a different source")
                return latest.approval_id
        source_key = _identity(candidate)
        if target_source_id is not None:
            target = db.get(CollectionSourceRow, target_source_id)
            if target is None or target.tenant_id != tenant_id:
                raise LookupError("target source not found")
            source_key = target.source_key
        source = _source(db, candidate, source_key)
        if target_source_id is None and source is not None:
            raise PermissionError("existing source requires an explicit update review")
        version = latest.version + 1 if latest else 1
        scope, digest = _scope(candidate, source, source_key, version)
        view = approval_service._submit_in_transaction(db, module_id=0, action_type=PROMOTION_ACTION,
            payload={"scope": scope, "scope_sha256": digest}, user_id=tenant_id, ttl_seconds=ttl_seconds)
        db.add(CandidateApprovalBindingRow(candidate_id=candidate_id, approval_id=view["id"],
            version=version, source_key=source_key, target_source_id=target_source_id,
            tenant_id=tenant_id, scope_sha256=digest))
        db.commit()
    approval_service._publish_request(view)
    return view["id"]


class _PromotionService:
    """Private trusted composition/test seam. Not a request-facing authority API."""
    def __init__(self, sessions, authority):
        self._sessions = sessions
        self._authority = authority

    def promote(self, tenant_id, candidate_id):
        with self._sessions() as db:
            _lock(db, tenant_id, candidate_id)
            candidate = db.scalar(select(DiscoveryCandidateRow).where(
                DiscoveryCandidateRow.id == candidate_id).with_for_update())
            if candidate is None or candidate.tenant_id != tenant_id:
                raise LookupError("candidate not found")
            binding = _latest(db, candidate_id)
            if (binding is None or binding.tenant_id != tenant_id or
                candidate.status != "pending_review" or db.get(CandidateApprovalUseRow, binding.approval_id)):
                raise PermissionError("unused bound approval required")
            if db.get_bind().dialect.name == "postgresql":
                key = int.from_bytes(sha256(f"source:{tenant_id}:{binding.source_key}".encode()).digest()[:8],
                                     "big", signed=True)
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            source = _source(db, candidate, binding.source_key)
            if (source.id if source else None) != binding.target_source_id:
                raise PermissionError("reviewed source configuration changed")
            scope, digest = _scope(candidate, source, binding.source_key, binding.version)
            if digest != binding.scope_sha256:
                raise PermissionError("reviewed source configuration changed")
            now = datetime.now(timezone.utc)
            decision = self._authority.verify(db, binding.approval_id, tenant_id, digest, now)
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


def _configured_promotion_service():
    # Deployment-owned environment only. Never take owner maps from API callers.
    owners = json.loads(os.environ.get("ATLAS_PROMOTION_OWNERS_JSON", "{}"))
    if not isinstance(owners, dict) or any(not isinstance(v, str) or not v for v in owners.values()):
        raise RuntimeError("invalid server promotion owner directory")
    return _PromotionService(SessionLocal, NativePromotionApprovalAuthority(owners.get))


def promote_candidate(tenant_id: str, candidate_id: int) -> int:
    """Resolve the server authority internally and consume one durable permit.

    No authority/approved parameter is accepted. The security boundary excludes
    a malicious process owner or a principal able to rewrite the approval DB.
    """
    return _configured_promotion_service().promote(tenant_id, candidate_id)
