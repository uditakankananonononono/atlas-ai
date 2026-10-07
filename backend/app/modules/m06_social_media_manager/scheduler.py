"""Scheduling + approval-verified execution for the Social Media Manager.

Lifecycle of one scheduled post:

    awaiting_approval -> approved -> published
                      -> denied            -> failed (adapter error)
                      -> cancelled (human)

Drafting routes only ever CREATE entries in ``awaiting_approval`` and file
the matching approval request with the shared Approval Center. The
execution gate in ``execute_due`` re-verifies the approval decision
immediately before every platform write: an entry whose approval is
missing, pending, denied, or expired is never published. This is the
module's effect gate - platform write APIs are called from nowhere else.

Media flow: drafts carry render PROMPTS for the self-hosted asset engines
(ComfyUI/Bark), not rendered files. The asset render pipeline attaches the
rendered media URLs to an entry via ``attach_media`` before its publish
time; Instagram and TikTok entries fail closed at the gate when no rendered
media is attached, instead of posting empty containers.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .adapters import AdapterError, PublishRequest, PublishResult
from .compliance import ComplianceIssue, is_blocking, split_x_thread, validate_draft
from .models import ContentPlan, Platform

# -- statuses ------------------------------------------------------------------

STATUS_AWAITING_APPROVAL = "awaiting_approval"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_PUBLISHING = "publishing"
STATUS_UNKNOWN = "outcome_unknown"

TERMINAL_STATUSES = {STATUS_PUBLISHED, STATUS_FAILED, STATUS_DENIED, STATUS_CANCELLED, STATUS_PUBLISHING, STATUS_UNKNOWN}

#: Platforms whose official APIs reject posts without media.
MEDIA_REQUIRED_PLATFORMS = {"instagram", "tiktok"}


class ScheduleNotFoundError(KeyError):
    """Raised when a caller references an unknown schedule entry."""


class ScheduleStateError(RuntimeError):
    """Raised when a state transition is not allowed (e.g. cancel after publish)."""


class DraftComplianceError(ValueError):
    """Drafts failed blocking compliance checks; carries every finding."""

    def __init__(self, issues: list[ComplianceIssue]) -> None:
        super().__init__("one or more drafts have blocking compliance issues")
        self.issues = issues


@dataclass
class ScheduleEntry:
    """One platform post queued behind human approval."""

    id: str
    plan_id: str
    platform: Platform
    format: str
    text: str
    publish_at: datetime
    approval_id: str
    status: str = STATUS_AWAITING_APPROVAL
    media_urls: list[str] = field(default_factory=list)
    alt_texts: list[str] = field(default_factory=list)
    thread_chunks: list[str] = field(default_factory=list)
    link: str | None = None
    sponsored: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    published_at: datetime | None = None
    external_id: str | None = None
    external_url: str | None = None
    draft_only: bool = False
    failure: str | None = None


@dataclass(frozen=True)
class PublishRecord:
    """Receipt of a platform write performed by the execution gate."""

    schedule_id: str
    platform: str
    external_id: str
    external_url: str | None
    draft_only: bool
    published_at: datetime


def validate_publish_receipt(entry: ScheduleEntry,receipt: PublishRecord)->None:
    if entry.status != STATUS_PUBLISHED or not entry.external_id:
        raise ValueError('finalization requires published positive receipt')
    expected=PublishRecord(schedule_id=entry.id,platform=entry.platform.value,external_id=entry.external_id,
        external_url=entry.external_url,draft_only=entry.draft_only,published_at=entry.published_at)
    if receipt != expected:raise ValueError('receipt does not match claim outcome')


class ScheduleRepository(Protocol):
    """Persistence boundary for schedule entries and publish receipts."""

    def finalize_publish(self, entry: ScheduleEntry, record: PublishRecord) -> PublishRecord: ...
    def claim_publish(self, entry: ScheduleEntry) -> ScheduleEntry | None: ...
    def save_schedule(self, entry: ScheduleEntry) -> ScheduleEntry: ...
    def get_schedule(self, schedule_id: str) -> ScheduleEntry | None: ...
    def list_schedules(self, plan_id: str | None = None) -> list[ScheduleEntry]: ...
    def save_publish_record(self, record: PublishRecord) -> PublishRecord: ...
    def list_publish_records(self, schedule_id: str | None = None) -> list[PublishRecord]: ...


class ApprovalDecisionLookup(Protocol):
    """Read-only view of the shared Approval Center's decisions."""

    def status_of(self, approval_id: str) -> str | None:
        """Return 'pending' | 'approved' | 'denied' | 'expired', or None if unknown."""


class AdapterFactory(Protocol):
    """Builds the official platform adapter for one entry's platform."""

    def for_platform(self, platform: Platform) -> Any:
        """Return an adapter exposing async ``publish(PublishRequest) -> PublishResult``."""


def _aware(moment: datetime) -> datetime:
    # Legacy-read shim only: rows stored before the aware-input policy may hold
    # a naive publish_at whose provenance is unknowable; the documented
    # convention treats it as UTC. New naive writes are rejected at the
    # schema boundary (ScheduleIn/RescheduleIn) and at the direct-caller
    # boundary (_require_aware) below.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _require_aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("publish_at must be timezone-aware")
    return moment


class Scheduler:
    """Decision sync, due-scan, and the approval-verified execution gate."""

    def __init__(
        self,
        *,
        repository: ScheduleRepository,
        decisions: ApprovalDecisionLookup,
        adapter_factory: AdapterFactory,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._decisions = decisions
        self._adapters = adapter_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- entry creation ------------------------------------------------------

    def create_entries(
        self,
        plan: ContentPlan,
        *,
        publish_at: datetime,
        approval_ids: dict[Platform, str],
        sponsored: bool = False,
    ) -> list[ScheduleEntry]:
        """Persist one awaiting-approval entry per draft.

        All drafts are compliance-checked first; a single blocking finding
        aborts the whole batch before anything is persisted (fail closed).
        ``approval_ids`` maps each draft's platform to the approval request
        already filed for it by the caller.
        """
        _require_aware(publish_at)
        findings: list[ComplianceIssue] = []
        for draft in plan.drafts:
            issues = validate_draft(
                draft.platform.value,
                draft.format,
                draft.post_copy,
                sponsored=sponsored,
                media_count=len([p for p in draft.asset_prompts if p.kind == "image"]),
                alt_texts=len([p for p in draft.asset_prompts if p.kind == "image" and p.prompt.strip()]),
            )
            findings.extend(issue for issue in issues if issue.severity == "error")
        if findings:
            raise DraftComplianceError(findings)

        entries: list[ScheduleEntry] = []
        for draft in plan.drafts:
            thread_chunks: list[str] = []
            if draft.platform == Platform.TWITTER and draft.format == "thread":
                thread_chunks = split_x_thread(draft.post_copy)
            entries.append(
                self._repository.save_schedule(
                    ScheduleEntry(
                        id=str(uuid.uuid4()),
                        plan_id=plan.id,
                        platform=draft.platform,
                        format=draft.format,
                        text=draft.post_copy,
                        publish_at=publish_at,
                        approval_id=approval_ids[draft.platform],
                        thread_chunks=thread_chunks,
                        sponsored=sponsored,
                    )
                )
            )
        return entries

    # -- media attachment (asset render pipeline hook) -------------------------

    def attach_media(self, schedule_id: str, media_urls: list[str], alt_texts: list[str] | None = None) -> ScheduleEntry:
        """Attach rendered media URLs produced by the asset render pipeline."""
        entry = self._entry(schedule_id)
        if entry.status in TERMINAL_STATUSES:
            raise ScheduleStateError(f"cannot attach media to an entry in state {entry.status}")
        entry.media_urls = list(media_urls)
        entry.alt_texts = list(alt_texts or [])
        return self._repository.save_schedule(entry)

    def final_review_payload(self,schedule_id:str,tenant_id:str,*,snapshot=None)->dict[str,Any]:
        """Snapshot for a new owner review after rendering. Does not approve/publish.

        Account identity comes only from a trusted connected-account resolver;
        environment credentials alone cannot supply it.
        """
        entry=snapshot if snapshot is not None else self._entry(schedule_id)
        if entry.status in TERMINAL_STATUSES:
            raise ScheduleStateError('cannot prepare final review for terminal/claimed schedule')
        resolve=getattr(self._adapters,'account_id',None)
        account_id=resolve(entry.platform) if resolve else None
        if not tenant_id or not account_id:
            raise ScheduleStateError('verified tenant/account identity unavailable for final review')
        if entry.platform.value in MEDIA_REQUIRED_PLATFORMS and not entry.media_urls:
            raise ScheduleStateError('rendered media required before final review')
        return {'tenant_id':tenant_id,'schedule_id':entry.id,'plan_id':entry.plan_id,
            'platform':entry.platform.value,'format':entry.format,'copy':entry.text,
            'publish_at':entry.publish_at.isoformat(),'sponsored':entry.sponsored,
            'media_urls':list(entry.media_urls),'alt_texts':list(entry.alt_texts),
            'thread_chunks':list(entry.thread_chunks),'link':entry.link,'account_id':account_id}

    def request_final_review(self,schedule_id:str,tenant_id:str,approval_service,ttl_seconds:int=3600)->dict:
        """Propose only. Exact rendered media/account snapshot, durable M00.

        Binding uses compare-and-swap. A changed schedule leaves a harmless
        unmatched pending card, never a publish grant for the changed payload.
        """
        entry=self._entry(schedule_id)
        payload=self.final_review_payload(schedule_id,tenant_id,snapshot=entry)
        atomic=getattr(self._repository,'propose_final_review',None)
        if atomic is None:raise ScheduleStateError('atomic durable final-review proposal unavailable')
        try:return atomic(entry,payload,tenant_id,approval_service,ttl_seconds)
        except Exception as error:
            raise ScheduleStateError(f'final review not bound: {error}') from error

    # -- decision sync ---------------------------------------------------------

    def sync_decisions(self) -> list[ScheduleEntry]:
        """Fold Approval Center decisions into entry state. Idempotent."""
        changed: list[ScheduleEntry] = []
        for entry in self._repository.list_schedules():
            if entry.status != STATUS_AWAITING_APPROVAL:
                continue
            decision = self._decisions.status_of(entry.approval_id)
            if decision == "approved":
                entry.status = STATUS_APPROVED
                entry.decided_at = self._clock()
            elif decision in {"denied", "expired"}:
                entry.status = STATUS_DENIED
                entry.decided_at = self._clock()
            else:
                continue
            changed.append(self._repository.save_schedule(entry))
        return changed

    # -- execution gate ---------------------------------------------------------

    def due_entries(self, now: datetime | None = None) -> list[ScheduleEntry]:
        """Approved entries whose publish time has arrived."""
        moment = _aware(now or self._clock())
        return [
            entry
            for entry in self._repository.list_schedules()
            if entry.status == STATUS_APPROVED and _aware(entry.publish_at) <= moment
        ]

    def execute_due(self, now: datetime | None = None) -> list[PublishRecord]:
        """Publish due entries - only after re-verifying each approval.

        The decision lookup is consulted again immediately before every
        platform write, so an approval revoked, denied, or expired after the
        last sync can never publish. Adapter failures mark the entry failed
        with the reason; they never propagate as exceptions.
        """
        records: list[PublishRecord] = []
        for entry in self.due_entries(now):
            if self._decisions.status_of(entry.approval_id) != "approved":
                entry.status = STATUS_DENIED
                entry.decided_at = self._clock()
                entry.failure = "approval was not in the approved state at execution time"
                self._repository.save_schedule(entry)
                continue
            if entry.platform.value in MEDIA_REQUIRED_PLATFORMS and not entry.media_urls:
                entry.status = STATUS_FAILED
                entry.failure = (
                    f"{entry.platform.value} requires rendered media; the asset render pipeline "
                    "must attach media URLs before execution"
                )
                self._repository.save_schedule(entry)
                continue
            authorizes = getattr(self._decisions, 'authorizes', None)
            account = getattr(self._adapters, 'account_id', None)
            account_id = account(entry.platform) if account else None
            if authorizes is None or not authorizes(entry, account_id=account_id):
                # Status alone is not a reviewed grant. Leave pending re-review, not due.
                entry.status = STATUS_DENIED
                entry.failure = 'approval does not bind exact content, media, schedule and verified account'
                self._repository.save_schedule(entry)
                continue
            entry = self._repository.claim_publish(entry)
            if entry is None:
                continue
            try:
                adapter = self._adapters.for_platform(entry.platform)
                result = asyncio.run(
                    adapter.publish(
                        PublishRequest(
                            platform=entry.platform.value,
                            text=entry.text,
                            format=entry.format,
                            link=entry.link,
                            media_urls=tuple(entry.media_urls),
                            alt_texts=tuple(entry.alt_texts),
                            thread_chunks=tuple(entry.thread_chunks),
                        )
                    )
                )
            except Exception as error:
                entry.status = STATUS_UNKNOWN
                entry.failure = str(error)
                self._repository.save_schedule(entry)
                continue
            if not result.external_id:
                entry.status = STATUS_UNKNOWN
                entry.failure = 'adapter returned no positive external receipt; do not retry'
                self._repository.save_schedule(entry)
                continue
            published_at = self._clock()
            entry.status = STATUS_PUBLISHED
            entry.published_at = published_at
            entry.external_id = result.external_id
            entry.external_url = result.url
            entry.draft_only = result.draft_only
            entry.failure = None
            record = PublishRecord(schedule_id=entry.id,platform=entry.platform.value,
                external_id=result.external_id,external_url=result.url,draft_only=result.draft_only,published_at=published_at)
            records.append(self._repository.finalize_publish(entry,record))
        return records

    # -- human operations ---------------------------------------------------------

    def cancel(self, schedule_id: str) -> ScheduleEntry:
        entry = self._entry(schedule_id)
        if entry.status in TERMINAL_STATUSES:
            raise ScheduleStateError(f"cannot cancel an entry in state {entry.status}")
        entry.status = STATUS_CANCELLED
        return self._repository.save_schedule(entry)

    def reschedule(self, schedule_id: str, publish_at: datetime) -> ScheduleEntry:
        _require_aware(publish_at)
        entry = self._entry(schedule_id)
        if entry.status in TERMINAL_STATUSES:
            raise ScheduleStateError(f"cannot reschedule an entry in state {entry.status}")
        entry.publish_at = publish_at
        return self._repository.save_schedule(entry)

    def get_entry(self, schedule_id: str) -> ScheduleEntry:
        return self._entry(schedule_id)

    def list_entries(self, plan_id: str | None = None) -> list[ScheduleEntry]:
        return self._repository.list_schedules(plan_id)

    def list_publish_records(self, schedule_id: str | None = None) -> list[PublishRecord]:
        return self._repository.list_publish_records(schedule_id)

    def _entry(self, schedule_id: str) -> ScheduleEntry:
        entry = self._repository.get_schedule(schedule_id)
        if entry is None:
            raise ScheduleNotFoundError(schedule_id)
        return entry
