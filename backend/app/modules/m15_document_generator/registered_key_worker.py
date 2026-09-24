"""Approved publication worker with registry-backed Ed25519 receipt verification.

Flow, all inside the approved worker:

1. the approval must exist for the calling tenant, be ``approved`` and be bound
   to the exact tenant / version / format / content hash of the job;
2. the approval is consumed atomically: a unique ``(tenant_id, approval_id)``
   row is committed *before* any effect, so a replay can never render or upload;
3. the version is rendered and uploaded through the private-upload adapter;
4. the provider receipt is verified against the tenant's registered Ed25519 key
   (``PublicationProviderKeyRegistry``): the key must be registered, active,
   match its pinned SHA-256 fingerprint, and have been registered before the
   receipt was issued; no shared/HMAC keys are accepted;
5. the verified receipt is stored append-only (``PublicationReceiptStore``
   rejects a second receipt for the same approval or object).
"""
from __future__ import annotations
import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import DateTime, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine
from app.core.models import ApprovalStatus
from .approved_worker import ApprovedPublicationJob
from .asymmetric_provider_receipt import AsymmetricProviderPublicationReceipt
from .provider_key_registry import PublicationProviderKeyRow
from .publication_receipt_store import PublicationReceiptStore


class ConsumedPublicationApprovalRow(Base):
    __tablename__ = 'm15_consumed_publication_approvals'
    __table_args__ = (UniqueConstraint('tenant_id', 'approval_id'),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    approval_id: Mapped[str] = mapped_column(String(200))
    version_id: Mapped[str] = mapped_column(String(200))
    format: Mapped[str] = mapped_column(String(20))
    content_hash: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(1000))
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RenderAdapter(Protocol):
    def render(self, version_id: str, format: str) -> bytes: ...


class SignedPrivateUploadAdapter(Protocol):
    def upload_private(self, object_key: str, data: bytes) -> dict: ...


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _canonical(receipt: AsymmetricProviderPublicationReceipt) -> tuple[dict, bytes]:
    payload = receipt.model_dump(mode='json', exclude={'signature_base64', 'signature_hmac_sha256'})
    return payload, json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()


def verify_registered_receipt(tenant_id: str, receipt: AsymmetricProviderPublicationReceipt,
                              expected_sha256: str, sessions: sessionmaker = SessionLocal) -> dict:
    """Verify a provider receipt with the tenant's registered, pinned, active Ed25519 key."""
    if receipt.published_sha256 != expected_sha256:
        raise ValueError('published hash does not match approved render')
    with sessions() as db:
        row = db.scalar(select(PublicationProviderKeyRow).where(
            PublicationProviderKeyRow.tenant_id == tenant_id,
            PublicationProviderKeyRow.provider == receipt.provider,
            PublicationProviderKeyRow.key_id == receipt.key_id))
        if row is None:
            raise ValueError('provider key is not registered for this tenant')
        raw, pinned, active = bytes(row.public_key), row.fingerprint_sha256, row.active
        created_at, retired_at = _utc(row.created_at), row.retired_at
    if not active or retired_at is not None:
        raise ValueError('provider key is retired')
    if len(raw) != 32 or hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError('registered key bytes do not match the pinned fingerprint')
    if _utc(receipt.uploaded_at) < created_at:
        raise ValueError('receipt was issued before the provider key was registered')
    try:
        sig = base64.b64decode(receipt.signature_base64, validate=True)
    except Exception as exc:
        raise ValueError('invalid signature encoding') from exc
    payload, canonical = _canonical(receipt)
    try:
        Ed25519PublicKey.from_public_bytes(raw).verify(sig, canonical)
    except InvalidSignature as exc:
        raise ValueError('invalid provider receipt signature') from exc
    return {'verified': True, **payload, 'signature_base64': receipt.signature_base64,
            'signature_algorithm': 'Ed25519', 'key_fingerprint_sha256': pinned,
            'receipt_sha256': hashlib.sha256(canonical + sig).hexdigest()}


class RegisteredKeyPublicationWorker:
    def __init__(self, tenant_id: str, approvals: Any, renderer: RenderAdapter,
                 uploader: SignedPrivateUploadAdapter, sessions: sessionmaker = SessionLocal,
                 receipts: PublicationReceiptStore | None = None) -> None:
        self.tenant_id, self.approvals, self.renderer, self.uploader = tenant_id, approvals, renderer, uploader
        self.sessions = sessions
        self.receipts = receipts or PublicationReceiptStore(tenant_id, sessions)
        Base.metadata.create_all(sessions.kw.get('bind') or engine)

    def _check_approval(self, job: ApprovedPublicationJob) -> None:
        approval = self.approvals.get(job.approval_id, user_id=self.tenant_id)
        if approval is None or approval.status != ApprovalStatus.APPROVED:
            raise ValueError('approved tenant-scoped render approval is required')
        expected = {'tenant_id': self.tenant_id, 'version_id': job.version_id, 'format': job.format,
                    'content_hash': job.expected_content_hash}
        if any(approval.payload.get(k) != v for k, v in expected.items()):
            raise ValueError('approval is bound to different render content')

    def _consume(self, job: ApprovedPublicationJob) -> datetime:
        now = datetime.now(timezone.utc)
        try:
            with self.sessions.begin() as db:
                db.add(ConsumedPublicationApprovalRow(
                    tenant_id=self.tenant_id, approval_id=job.approval_id, version_id=job.version_id,
                    format=job.format, content_hash=job.expected_content_hash, object_key=job.object_key,
                    consumed_at=now))
        except IntegrityError as exc:
            raise ValueError('approval was already consumed; replay refused') from exc
        return now

    def is_consumed(self, approval_id: str) -> bool:
        with self.sessions() as db:
            return db.scalar(select(ConsumedPublicationApprovalRow.id).where(
                ConsumedPublicationApprovalRow.tenant_id == self.tenant_id,
                ConsumedPublicationApprovalRow.approval_id == approval_id)) is not None

    def run(self, job: ApprovedPublicationJob) -> dict:
        self._check_approval(job)
        consumed_at = self._consume(job)  # committed before any effect
        rendered = self.renderer.render(job.version_id, job.format)
        if not rendered:
            raise ValueError('renderer returned empty bytes')
        sha = hashlib.sha256(rendered).hexdigest()
        raw = self.uploader.upload_private(job.object_key, rendered)
        try:
            receipt = AsymmetricProviderPublicationReceipt(**raw)
        except Exception as exc:
            raise ValueError(f'provider receipt is malformed: {exc}') from exc
        for field, want in (('approval_id', job.approval_id), ('version_id', job.version_id),
                            ('object_key', job.object_key), ('byte_size', len(rendered))):
            if getattr(receipt, field) != want:
                raise ValueError(f'provider receipt {field} does not match the approved job')
        verified = verify_registered_receipt(self.tenant_id, receipt, sha, self.sessions)
        stored = {**verified, 'consumed_at': consumed_at.isoformat()}
        self.receipts.persist(stored)
        return {'executed': True, 'access': 'private', **stored,
                'boundary': 'Approval consumed before effect; receipt verified with a registered, pinned, '
                            'active Ed25519 key and stored append-only.'}
