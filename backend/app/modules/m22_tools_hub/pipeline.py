"""Durable, tenant-scoped Tools Hub install pipeline.

Replaces the "caller supplies a receipt" path with a pipeline Atlas runs itself:

1. ``propose`` - the artifact (ZIP) and manifest are scanned before anything is
   queued, the bytes are stored content-addressed, and a Module 0 approval is
   submitted whose payload binds the exact install subject
   (tool id, version, artifact SHA-256, manifest digest).
2. ``enqueue_install`` - refuses unless that Module 0 approval belongs to the
   tenant, is ``approved``, and still binds the same subject. One live install
   job per proposal; failed jobs may be retried.
3. ``run_job`` (worker) - re-reads the stored bytes and re-verifies their hash,
   re-scans, issues a single-use installer grant bound to the subject (approver =
   the human who decided in Module 0, requester = the proposer) and lets
   ``ToolInstaller`` consume it. The receipt is the installer's own output.
4. ``propose_rollback`` / rollback job - rollback needs its own Module 0
   approval bound to the stored receipt, and restores the backed-up version.

Nothing here downloads software from the internet; the artifact comes from the
proposer and is checked against its manifest provenance digest.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from app.core.models import ApprovalStatus

from .approvals import ApprovalStore
from .installer import InstallError, ToolInstaller, _install_subject, _rollback_subject
from .models import InstallReceipt, ManifestError, ReviewDecision, ReviewRecord, ToolManifest
from .security import ArtifactRejected, SecurityScanner

MODULE_ID = 22
INSTALL_ACTION = "integrate_tool"
ROLLBACK_ACTION = "rollback_tool"
MAX_ATTEMPTS = 3


class PipelineError(ValueError):
    """Input or state error the caller can fix (maps to HTTP 422)."""


class PipelineConflict(RuntimeError):
    """The requested transition conflicts with current state (HTTP 409)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(moment: datetime | None) -> datetime | None:
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=timezone.utc)


class ProposalRow(Base):
    __tablename__ = "m22_install_proposals"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    tool_id: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(80))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    manifest_digest: Mapped[str] = mapped_column(String(64))
    manifest_json: Mapped[dict] = mapped_column(JSON)
    install_subject: Mapped[str] = mapped_column(Text)
    scan_json: Mapped[dict] = mapped_column(JSON)
    candidate_json: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(200))
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobRow(Base):
    __tablename__ = "m22_install_jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    proposal_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # install | rollback
    approval_id: Mapped[str] = mapped_column(String(36))
    operation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(16), index=True)  # queued|running|succeeded|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioRow(Base):
    __tablename__ = "m22_tool_portfolio"
    __table_args__ = (UniqueConstraint("tenant_id", "operation_id"),)
    pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    operation_id: Mapped[str] = mapped_column(String(64))
    proposal_id: Mapped[str] = mapped_column(String(36), index=True)
    tool_id: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(80))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    manifest_digest: Mapped[str] = mapped_column(String(64))
    installed_path: Mapped[str] = mapped_column(Text)
    backup_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), index=True)  # active|superseded|rolled_back
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactStore:
    """Content-addressed artifact bytes; reads re-verify the digest."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / f"{digest}.zip"
        if not path.exists():
            tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return digest

    def get(self, digest: str) -> bytes:
        path = self.root / f"{digest}.zip"
        if not path.exists():
            raise PipelineError("stored artifact is missing")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise PipelineError("stored artifact failed its integrity check")
        return data


def _scan_view(report) -> dict[str, Any]:
    return {
        "artifact_sha256": report.artifact_sha256, "passed": report.passed,
        "scanned_files": report.scanned_files, "scanned_bytes": report.scanned_bytes,
        "findings": [asdict(f) for f in report.findings],
    }


def _receipt_view(receipt: InstallReceipt) -> dict[str, Any]:
    value = asdict(receipt)
    value["installed_at"] = receipt.installed_at.isoformat()
    return value


def _proposal_view(row: ProposalRow) -> dict[str, Any]:
    return {
        "id": row.id, "tenant_id": row.tenant_id, "tool_id": row.tool_id, "version": row.version,
        "artifact_sha256": row.artifact_sha256, "manifest_digest": row.manifest_digest,
        "install_subject": row.install_subject, "scan": row.scan_json, "candidate": row.candidate_json,
        "requested_by": row.requested_by, "approval_id": row.approval_id, "status": row.status,
        "created_at": _aware(row.created_at).isoformat(), "updated_at": _aware(row.updated_at).isoformat(),
    }


def _job_view(row: JobRow) -> dict[str, Any]:
    return {
        "id": row.id, "proposal_id": row.proposal_id, "kind": row.kind, "approval_id": row.approval_id,
        "operation_id": row.operation_id, "state": row.state, "attempts": row.attempts,
        "error": row.error, "receipt": row.receipt_json,
        "created_at": _aware(row.created_at).isoformat(), "updated_at": _aware(row.updated_at).isoformat(),
    }


def _portfolio_view(row: PortfolioRow) -> dict[str, Any]:
    return {
        "operation_id": row.operation_id, "proposal_id": row.proposal_id, "tool_id": row.tool_id,
        "version": row.version, "artifact_sha256": row.artifact_sha256,
        "manifest_digest": row.manifest_digest, "installed_path": row.installed_path,
        "backup_id": row.backup_id, "rollback_available": bool(row.backup_id) and row.status == "active",
        "approved_by": row.approved_by, "status": row.status,
        "installed_at": _aware(row.installed_at).isoformat(),
        "execution_claim": "installed by the Atlas pipeline worker from a hash-verified, scanned artifact; the tool's runtime behavior is not exercised here",
    }


class InstallPipeline:
    """One tenant's view of the durable install pipeline."""

    def __init__(
        self, tenant_id: str, *, root: Path | None = None, center: Any = None,
        session_factory: sessionmaker = SessionLocal, scanner: SecurityScanner | None = None,
        create_schema: bool = True,
    ) -> None:
        if not tenant_id or not tenant_id.strip():
            raise PipelineError("tenant_id is required")
        if center is None:
            from app.modules.m00_approval_center.service import default_service
            center = default_service()
        root = root or Path(os.getenv("ATLAS_TOOLS_ROOT", "/tmp/atlas-tools"))
        safe_tenant = hashlib.sha256(tenant_id.encode()).hexdigest()[:24]
        self.tenant_id = tenant_id
        self.center = center
        self.sessions = session_factory
        self.scanner = scanner or SecurityScanner()
        self.artifacts = ArtifactStore(root / "artifacts")
        tenant_root = root / "tenants" / safe_tenant
        self.grants = ApprovalStore(state_path=tenant_root / "grants.json")
        self.installer = ToolInstaller(tenant_root, self.grants, self.scanner)
        self._lock = threading.Lock()
        if create_schema:
            bind = session_factory.kw.get("bind") or engine
            Base.metadata.create_all(bind, tables=[ProposalRow.__table__, JobRow.__table__, PortfolioRow.__table__])

    # -- proposals ---------------------------------------------------------
    def propose(self, *, artifact: bytes, manifest: dict[str, Any], requested_by: str,
                candidate: dict[str, Any] | None = None, ttl_seconds: int | None = 7 * 24 * 3600) -> dict[str, Any]:
        if not requested_by or not requested_by.strip():
            raise PipelineError("requested_by is required")
        try:
            parsed = ToolManifest.from_dict(manifest)
            report = self.scanner.scan(artifact, parsed)
        except (ManifestError, ArtifactRejected) as exc:
            raise PipelineError(str(exc)) from exc
        scan = _scan_view(report)
        if not report.passed:
            raise PipelineError("security scan failed: " + ", ".join(
                f"{f['code']}@{f['path']}" for f in scan["findings"] if f["severity"] in {"high", "critical"}))
        digest = self.artifacts.put(artifact)
        subject = _install_subject(parsed)
        candidate = {k: v for k, v in (candidate or {}).items()
                     if "secret" not in k.lower() and "token" not in k.lower() and "password" not in k.lower()}
        approval = self.center.submit(
            module_id=MODULE_ID, action_type=INSTALL_ACTION, user_id=self.tenant_id, ttl_seconds=ttl_seconds,
            payload={
                "tool_id": parsed.tool_id, "version": parsed.version, "publisher": parsed.provenance.publisher,
                "source_url": parsed.provenance.source_url, "permissions": list(parsed.permissions),
                "artifact_sha256": digest, "manifest_digest": parsed.digest, "install_subject": subject,
                "scan": {"passed": True, "findings": scan["findings"], "scanned_files": scan["scanned_files"]},
                "rollback_plan": {"strategy": "restore_previous_version_from_backup",
                                  "note": "available only when a prior version was installed"},
                "candidate": candidate,
            })
        now = _now()
        row = ProposalRow(
            tenant_id=self.tenant_id, id=str(uuid.uuid4()), tool_id=parsed.tool_id, version=parsed.version,
            artifact_sha256=digest, manifest_digest=parsed.digest, manifest_json=dict(manifest),
            install_subject=subject, scan_json=scan, candidate_json=candidate, requested_by=requested_by,
            approval_id=approval["id"], status="awaiting_approval", created_at=now, updated_at=now)
        with self.sessions.begin() as db:
            db.add(row)
        return _proposal_view(row)

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.sessions() as db:
            return _proposal_view(self._proposal(db, proposal_id))

    def list_proposals(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.sessions() as db:
            q = select(ProposalRow).where(ProposalRow.tenant_id == self.tenant_id)
            if status:
                q = q.where(ProposalRow.status == status)
            return [_proposal_view(r) for r in db.scalars(q.order_by(ProposalRow.pk.desc()))]

    def _proposal(self, db, proposal_id: str) -> ProposalRow:
        row = db.scalar(select(ProposalRow).where(ProposalRow.tenant_id == self.tenant_id, ProposalRow.id == proposal_id))
        if row is None:
            raise KeyError("installation proposal not found")
        return row

    # -- approval checks -----------------------------------------------------
    def _approved(self, approval_id: str, action: str, expected: dict[str, Any]) -> dict[str, Any]:
        view = self.center.get(approval_id)
        if view.get("user_id") != self.tenant_id:
            raise KeyError("approval not found")
        if str(view.get("action_type")) != action or int(view.get("module_id")) != MODULE_ID:
            raise PermissionError("approval is for a different action")
        status = view.get("status")
        status = status.value if isinstance(status, ApprovalStatus) else str(status)
        if status != ApprovalStatus.APPROVED.value:
            raise PermissionError(f"approval is {status}, not approved")
        payload = view.get("payload") or {}
        for key, value in expected.items():
            if payload.get(key) != value:
                raise PermissionError(f"approval does not bind this {key}")
        if not view.get("approved_by"):
            raise PermissionError("approval has no recorded approver")
        return view

    def _enqueue(self, db, *, proposal_id: str, kind: str, approval_id: str, operation_id: str | None) -> JobRow:
        live = db.scalar(select(JobRow).where(
            JobRow.tenant_id == self.tenant_id, JobRow.proposal_id == proposal_id, JobRow.kind == kind,
            JobRow.approval_id == approval_id, JobRow.state.in_(("queued", "running", "succeeded"))))
        if live is not None:
            raise PipelineConflict(f"{kind} job already {live.state} ({live.id})")
        failed = db.scalar(select(JobRow).where(
            JobRow.tenant_id == self.tenant_id, JobRow.proposal_id == proposal_id, JobRow.kind == kind,
            JobRow.approval_id == approval_id, JobRow.state == "failed"))
        now = _now()
        if failed is not None:
            if failed.attempts >= MAX_ATTEMPTS:
                raise PipelineConflict(f"{kind} job failed {failed.attempts} times; submit a new proposal")
            failed.state = "queued"; failed.updated_at = now
            return failed
        job = JobRow(tenant_id=self.tenant_id, id=str(uuid.uuid4()), proposal_id=proposal_id, kind=kind,
                     approval_id=approval_id, operation_id=operation_id, state="queued", attempts=0,
                     created_at=now, updated_at=now)
        db.add(job)
        return job

    def enqueue_install(self, proposal_id: str) -> dict[str, Any]:
        with self.sessions.begin() as db:
            p = self._proposal(db, proposal_id)
            self._approved(p.approval_id, INSTALL_ACTION, {
                "install_subject": p.install_subject, "artifact_sha256": p.artifact_sha256,
                "manifest_digest": p.manifest_digest})
            job = self._enqueue(db, proposal_id=p.id, kind="install", approval_id=p.approval_id, operation_id=None)
            p.status = "queued"; p.updated_at = _now()
            db.flush()
            return _job_view(job)

    def propose_rollback(self, operation_id: str, requested_by: str) -> dict[str, Any]:
        with self.sessions() as db:
            entry = db.scalar(select(PortfolioRow).where(PortfolioRow.tenant_id == self.tenant_id, PortfolioRow.operation_id == operation_id))
            if entry is None:
                raise KeyError("installed operation not found")
            if entry.status != "active" or not entry.backup_id:
                raise PipelineError("no prior version to restore for this install")
        receipt = self.installer.get_receipt(operation_id)
        subject = _rollback_subject(receipt)
        approval = self.center.submit(
            module_id=MODULE_ID, action_type=ROLLBACK_ACTION, user_id=self.tenant_id,
            payload={"operation_id": operation_id, "tool_id": entry.tool_id, "version": entry.version,
                     "rollback_subject": subject, "requested_by": requested_by,
                     "effect": "restore the previously installed version from backup"})
        return {"operation_id": operation_id, "approval_id": approval["id"], "rollback_subject": subject,
                "status": "awaiting_approval"}

    def enqueue_rollback(self, operation_id: str, approval_id: str) -> dict[str, Any]:
        receipt = self.installer.get_receipt(operation_id)
        self._approved(approval_id, ROLLBACK_ACTION, {"operation_id": operation_id,
                                                      "rollback_subject": _rollback_subject(receipt)})
        with self.sessions.begin() as db:
            entry = db.scalar(select(PortfolioRow).where(PortfolioRow.tenant_id == self.tenant_id, PortfolioRow.operation_id == operation_id))
            if entry is None:
                raise KeyError("installed operation not found")
            job = self._enqueue(db, proposal_id=entry.proposal_id, kind="rollback", approval_id=approval_id,
                                operation_id=operation_id)
            db.flush()
            return _job_view(job)

    # -- worker --------------------------------------------------------------
    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.sessions() as db:
            row = db.scalar(select(JobRow).where(JobRow.tenant_id == self.tenant_id, JobRow.id == job_id))
            if row is None:
                raise KeyError("job not found")
            return _job_view(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self.sessions() as db:
            return [_job_view(r) for r in db.scalars(select(JobRow).where(JobRow.tenant_id == self.tenant_id).order_by(JobRow.pk.desc()))]

    def _claim(self, job_id: str) -> JobRow | None:
        with self._lock, self.sessions.begin() as db:
            row = db.scalar(select(JobRow).where(JobRow.tenant_id == self.tenant_id, JobRow.id == job_id))
            if row is None:
                raise KeyError("job not found")
            if row.state != "queued":
                return None
            row.state = "running"; row.attempts += 1; row.updated_at = _now()
            db.flush()
            db.expunge(row)
            return row

    def _finish(self, job_id: str, *, state: str, error: str | None = None, receipt: dict | None = None,
                operation_id: str | None = None, after: Callable[[Any], None] | None = None) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(JobRow).where(JobRow.tenant_id == self.tenant_id, JobRow.id == job_id))
            row.state = state; row.error = error; row.receipt_json = receipt; row.updated_at = _now()
            if operation_id:
                row.operation_id = operation_id
            if after:
                after(db)

    def run_job(self, job_id: str) -> dict[str, Any]:
        job = self._claim(job_id)
        if job is None:
            return self.get_job(job_id)
        try:
            if job.kind == "install":
                self._run_install(job)
            else:
                self._run_rollback(job)
        except Exception as exc:  # recorded, never swallowed silently
            reason = f"{type(exc).__name__}: {exc}"
            proposal_id = job.proposal_id
            kind = job.kind

            def mark(db):
                if kind == "install":
                    p = self._proposal(db, proposal_id); p.status = "failed"; p.updated_at = _now()
            self._finish(job_id, state="failed", error=reason, after=mark)
        return self.get_job(job_id)

    def _run_install(self, job: JobRow) -> None:
        with self.sessions() as db:
            p = self._proposal(db, job.proposal_id)
            manifest_json, digest, subject = p.manifest_json, p.artifact_sha256, p.install_subject
        view = self._approved(job.approval_id, INSTALL_ACTION, {"install_subject": subject, "artifact_sha256": digest})
        artifact = self.artifacts.get(digest)
        manifest = ToolManifest.from_dict(manifest_json)
        if _install_subject(manifest) != subject:
            raise PipelineError("stored manifest no longer matches the approved subject")
        report = self.scanner.scan(artifact, manifest)
        if not report.passed:
            raise InstallError("security re-scan did not pass")
        review = ReviewRecord(reviewer=f"atlas-scanner+{view['approved_by']}", decision=ReviewDecision.PASS,
                              artifact_sha256=report.artifact_sha256, manifest_digest=manifest.digest)
        approver = str(view["approved_by"])
        worker = f"m22-worker:{job.id}"  # the grant is single-use and bound to this job's worker identity
        grant = self.grants.issue(action="tool.install", subject_digest=subject, approved_by=approver, requested_by=worker)
        receipt = self.installer.install(artifact=artifact, manifest=manifest, review=review,
                                         approval_token=grant.token, actor=worker)
        now = _now()

        def record(db):
            for old in db.scalars(select(PortfolioRow).where(PortfolioRow.tenant_id == self.tenant_id,
                                                             PortfolioRow.tool_id == receipt.tool_id,
                                                             PortfolioRow.status == "active")):
                old.status = "superseded"; old.updated_at = now
            db.add(PortfolioRow(tenant_id=self.tenant_id, operation_id=receipt.operation_id, proposal_id=job.proposal_id,
                                tool_id=receipt.tool_id, version=receipt.version, artifact_sha256=receipt.artifact_sha256,
                                manifest_digest=receipt.manifest_digest, installed_path=receipt.installed_path,
                                backup_id=receipt.backup_id, approved_by=approver, status="active",
                                installed_at=receipt.installed_at, updated_at=now))
            p = self._proposal(db, job.proposal_id); p.status = "installed"; p.updated_at = now
        self._finish(job.id, state="succeeded", receipt=_receipt_view(receipt), operation_id=receipt.operation_id, after=record)

    def _run_rollback(self, job: JobRow) -> None:
        receipt = self.installer.get_receipt(job.operation_id)
        subject = _rollback_subject(receipt)
        view = self._approved(job.approval_id, ROLLBACK_ACTION, {"operation_id": job.operation_id, "rollback_subject": subject})
        approver = str(view["approved_by"])
        grant = self.grants.issue(action="tool.rollback", subject_digest=subject, approved_by=approver,
                                  requested_by=f"m22-worker:{job.id}")
        self.installer.rollback(operation_id=job.operation_id, approval_token=grant.token, actor=f"m22-worker:{job.id}")
        now = _now()

        def record(db):
            entry = db.scalar(select(PortfolioRow).where(PortfolioRow.tenant_id == self.tenant_id, PortfolioRow.operation_id == job.operation_id))
            entry.status = "rolled_back"; entry.updated_at = now
            prior = db.scalars(select(PortfolioRow).where(
                PortfolioRow.tenant_id == self.tenant_id, PortfolioRow.tool_id == entry.tool_id,
                PortfolioRow.status == "superseded").order_by(PortfolioRow.pk.desc())).first()
            if prior is not None:
                prior.status = "active"; prior.updated_at = now
        self._finish(job.id, state="succeeded", receipt={**_receipt_view(receipt), "rolled_back_at": now.isoformat()}, after=record)

    def drain(self, limit: int = 50) -> list[dict[str, Any]]:
        """Run queued jobs for this tenant (what the Celery beat task calls)."""
        with self.sessions() as db:
            ids = list(db.scalars(select(JobRow.id).where(JobRow.tenant_id == self.tenant_id, JobRow.state == "queued")
                                  .order_by(JobRow.pk).limit(limit)))
        return [self.run_job(i) for i in ids]

    # -- portfolio -----------------------------------------------------------
    def portfolio(self, include_history: bool = False) -> list[dict[str, Any]]:
        with self.sessions() as db:
            q = select(PortfolioRow).where(PortfolioRow.tenant_id == self.tenant_id)
            if not include_history:
                q = q.where(PortfolioRow.status == "active")
            return [_portfolio_view(r) for r in db.scalars(q.order_by(PortfolioRow.pk.desc()))]


def tenants_with_queued_jobs(session_factory: sessionmaker = SessionLocal) -> list[str]:
    Base.metadata.create_all(session_factory.kw.get("bind") or engine, tables=[JobRow.__table__])
    with session_factory() as db:
        return sorted(set(db.scalars(select(JobRow.tenant_id).where(JobRow.state == "queued"))))


__all__ = ["InstallPipeline", "PipelineConflict", "PipelineError", "tenants_with_queued_jobs",
           "INSTALL_ACTION", "ROLLBACK_ACTION"]
