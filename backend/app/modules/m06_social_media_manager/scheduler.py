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
from copy import deepcopy

from app.runtime.guardrails.errors import GuardrailRefusal
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .adapters import AdapterError, PublishRequest, PublishResult
from .compliance import ComplianceIssue, is_blocking, split_x_thread, validate_draft
from .models import ContentPlan, Platform
from .review_binding import publish_snapshot, snapshot_matches
from .publish_targets import valid_target

# -- statuses ------------------------------------------------------------------

STATUS_AWAITING_APPROVAL = "awaiting_approval"
STATUS_APPROVED = "approved"
STATUS_DISPATCHING = "dispatching"
STATUS_DENIED = "denied"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = {STATUS_PUBLISHED, STATUS_FAILED, STATUS_DENIED, STATUS_CANCELLED}
LOCKED_STATUSES = TERMINAL_STATUSES | {STATUS_DISPATCHING}


class _PublishTargetUnverified(Exception):
    """Identity lookup could not prove the publishing account."""


class _PublishTargetChanged(Exception):
    """Current credentials select a different account than the reviewed one."""


class _DispatchClaimLost(Exception):
    """Another worker or a changed record won; never save this stale copy."""

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
    publish_target: dict[str, str] | None = None


@dataclass(frozen=True)
class PublishRecord:
    """Receipt of a platform write performed by the execution gate."""

    schedule_id: str
    platform: str
    external_id: str
    external_url: str | None
    draft_only: bool
    published_at: datetime


class ScheduleRepository(Protocol):
    """Persistence boundary for schedule entries and publish receipts."""

    def save_schedule(self, entry: ScheduleEntry) -> ScheduleEntry: ...
    def get_schedule(self, schedule_id: str) -> ScheduleEntry | None: ...
    def list_schedules(self, plan_id: str | None = None) -> list[ScheduleEntry]: ...
    def claim_publish(self, expected: ScheduleEntry) -> bool: ...
    def save_publish_record(self, record: PublishRecord) -> PublishRecord: ...
    def list_publish_records(self, schedule_id: str | None = None) -> list[PublishRecord]: ...


class ApprovalDecisionLookup(Protocol):
    """Read-only view of the shared Approval Center's decisions."""

    def reviewed_payload(self, approval_id: str) -> dict | None:
        """Return approved, tenant-checked M06 schedule_post payload, else None."""

    def status_of(self, approval_id: str) -> str | None:
        """Return 'pending' | 'approved' | 'denied' | 'expired', or None if unknown."""


class AdapterFactory(Protocol):
    """Builds the official platform adapter for one entry's platform."""

    def for_platform(self, platform: Platform) -> Any:
        """Return an adapter exposing async ``publish(PublishRequest) -> PublishResult``."""


class NaivePublishTimeError(ValueError):
    """A publish time without a UTC offset was supplied; it would be guessed as UTC."""


def require_aware(moment: datetime) -> datetime:
    """Reject a naive datetime instead of silently reading it as UTC."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise NaivePublishTimeError(
            "publish_at needs an explicit UTC offset or timezone (for example 2026-10-08T17:30:00+05:30)"
        )
    return moment


def _aware(moment: datetime) -> datetime:
    # Legacy rows saved before the guard may be naive; they are read as UTC.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


class _ApprovalAuthority:
    """authority_check hook: the schedule entry's approval must be approved NOW and bound.

    Binds approval_id -> action digest just before dispatch; unbound refs, a
    non-approved decision or a digest mismatch reject (fail closed). Trusts the
    decision lookup (M00); it does not authenticate the approver or prove the
    owner reviewed this digest. Scheduler separately compares the stored M00 publish snapshot first.
    """

    def __init__(self, decisions) -> None:
        self._decisions = decisions
        self._bound: dict[str, str] = {}

    def bind(self, approval_id: str, digest: str) -> None:
        self._bound[approval_id] = digest

    def __call__(self, authority_ref, action_digest) -> bool:
        try:
            return (self._bound.get(authority_ref) == action_digest
                    and self._decisions.status_of(authority_ref) == "approved")
        except Exception:
            return False


# Declared (NOT verified) platform rules for the official-API publish adapters in
# adapters.py. Owner-overridable via Scheduler(outbound_declarations=...). These
# are a policy declaration, not a legal or ToS compliance finding.
_PUBLISH_PLATFORMS = ("instagram", "twitter", "tiktok", "linkedin")


def default_outbound_declarations() -> dict:
    return {
        "tos": {p: {"allowed_kinds": ["post"], "automation_allowed": True} for p in _PUBLISH_PLATFORMS},
        "rate_limits": {p: {"post": {"max": 25, "window_seconds": 86400}} for p in _PUBLISH_PLATFORMS},
        "consent": [], "recent_actions": [],
    }


class Scheduler:
    """Decision sync, due-scan, and the approval-verified execution gate."""

    def __init__(
        self,
        *,
        repository: ScheduleRepository,
        decisions: ApprovalDecisionLookup,
        adapter_factory: AdapterFactory,
        clock: Callable[[], datetime] | None = None,
        enforcer=None,
        outbound_declarations: dict | None = None,
    ) -> None:
        from app.runtime.guardrails.enforcer import GuardrailEnforcer
        self._authority = _ApprovalAuthority(decisions)
        # Fail closed by default: every platform write goes through the
        # guardrail outbound gate. A caller-supplied enforcer must carry its own
        # authority_check; this scheduler binds approval digests only on the default.
        self._enforcer = enforcer or GuardrailEnforcer(authority_check=self._authority)
        self._declarations = (default_outbound_declarations() if outbound_declarations is None
                              else {"tos": {}, "rate_limits": {}, "consent": [], "recent_actions": [],
                                    **outbound_declarations})
        self._repository = repository
        self._decisions = decisions
        self._adapters = adapter_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve_publish_target(self, platform: Platform) -> dict[str, str]:
        """Read the target using current credentials; never perform a write."""
        adapter = self._adapters.for_platform(platform)
        identity = getattr(adapter, "account_identity", None)
        if not callable(identity):
            raise ScheduleStateError("adapter cannot resolve a publishing account")
        target = asyncio.run(identity())
        if not valid_target(platform.value, target):
            raise ScheduleStateError("adapter returned an invalid publishing account")
        return deepcopy(target)

    # -- entry creation ------------------------------------------------------

    def create_entries(
        self,
        plan: ContentPlan,
        *,
        publish_at: datetime,
        approval_ids: dict[Platform, str],
        sponsored: bool = False,
        publish_targets: dict[Platform, dict[str, str]] | None = None,
        draft_approval_ids: list[str] | None = None,
    ) -> list[ScheduleEntry]:
        """Persist one awaiting-approval entry per draft.

        All drafts are compliance-checked first; a single blocking finding
        aborts the whole batch before anything is persisted (fail closed).
        ``approval_ids`` maps each draft's platform to the approval request
        already filed for it by the caller. For repeated platforms, pass
        draft_approval_ids in exact draft order; ambiguous ID reuse is refused.
        """
        require_aware(publish_at)
        ids = (list(draft_approval_ids) if draft_approval_ids is not None
               else [approval_ids.get(draft.platform) for draft in plan.drafts])
        if (len(ids) != len(plan.drafts) or any(type(key) is not str or not key for key in ids)
                or len(set(ids)) != len(ids)):
            raise ScheduleStateError("each draft requires its own schedule_post approval")
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
        for draft_index, draft in enumerate(plan.drafts):
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
                        approval_id=ids[draft_index],
                        thread_chunks=thread_chunks,
                        sponsored=sponsored,
                        publish_target=deepcopy((publish_targets or {}).get(draft.platform)),
                    )
                )
            )
        return entries

    # -- media attachment (asset render pipeline hook) -------------------------

    def attach_media(self, schedule_id: str, media_urls: list[str], alt_texts: list[str] | None = None) -> ScheduleEntry:
        """Attach rendered media URLs produced by the asset render pipeline."""
        entry = self._entry(schedule_id)
        if entry.status in LOCKED_STATUSES:
            raise ScheduleStateError(f"cannot attach media to an entry in state {entry.status}")
        self._invalidate_review(entry)
        entry.media_urls = list(media_urls)
        entry.alt_texts = list(alt_texts or [])
        return self._repository.save_schedule(entry)

    # -- decision sync ---------------------------------------------------------

    def sync_decisions(self) -> list[ScheduleEntry]:
        """Fold Approval Center decisions into entry state. Idempotent."""
        changed: list[ScheduleEntry] = []
        for entry in self._repository.list_schedules():
            if entry.status != STATUS_AWAITING_APPROVAL or not entry.approval_id:
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
        """Approved entries due at an explicit instant, never a guessed timezone.

        Historical/direct repository writes may contain naive times despite the
        current creation guards. Validate the entire approved batch before any
        dispatch can start; an ambiguous row requires explicit rescheduling.
        Pending/terminal rows do not participate in the effect candidate batch.
        """
        moment = require_aware(now if now is not None else self._clock())
        approved = [entry for entry in self._repository.list_schedules()
                    if entry.status == STATUS_APPROVED]
        for entry in approved:
            require_aware(entry.publish_at)
        return [entry for entry in approved if entry.publish_at <= moment]

    def execute_due(self, now: datetime | None = None) -> list[PublishRecord]:
        """Publish due entries - only after re-verifying each approval.

        The decision lookup is consulted again immediately before every
        platform write, so an approval revoked, denied, or expired after the
        last sync can never publish. GuardrailRefusal and AdapterError mark the
        entry failed with the reason. Unexpected factory/adapter exceptions,
        malformed canonical data and repository errors may propagate.
        """
        records: list[PublishRecord] = []
        for entry in self.due_entries(now):
            expected_entry = deepcopy(entry)
            approval_id = entry.approval_id
            if self._decisions.status_of(approval_id) != "approved":
                entry.status = STATUS_DENIED
                entry.decided_at = self._clock()
                entry.failure = "approval was not in the approved state at execution time"
                self._repository.save_schedule(entry)
                continue
            snapshot = publish_snapshot(entry)
            lookup = getattr(self._decisions, "reviewed_payload", None)
            try:
                reviewed = lookup(approval_id) if callable(lookup) else None
            except Exception:
                reviewed = None
            if not snapshot_matches(snapshot, reviewed) or not valid_target(snapshot["platform"], snapshot["publish_target"]):
                self._invalidate_review(entry)
                self._repository.save_schedule(entry)
                continue
            if snapshot["platform"] in MEDIA_REQUIRED_PLATFORMS and not snapshot["media_urls"]:
                entry.status = STATUS_FAILED
                entry.failure = (
                    f"{entry.platform.value} requires rendered media; the asset render pipeline "
                    "must attach media URLs before execution"
                )
                self._repository.save_schedule(entry)
                continue
            try:
                moment = _aware(self._clock())
                action = {"id": f"{entry.id}-{int(moment.timestamp())}", "platform": snapshot["platform"],
                          "kind": "post", "at": int(moment.timestamp()), "count": 1,
                          "schedule_id": entry.id, "approval_id": approval_id,
                          "publish_target": deepcopy(snapshot["publish_target"]),
                          "text": snapshot["text"], "format": snapshot["format"], "link": snapshot["link"],
                          "alt_texts": list(snapshot["alt_texts"]),
                          "media_urls": list(snapshot["media_urls"]), "thread_chunks": list(snapshot["thread_chunks"])}
                from app.runtime.guardrails._fields import payload_sha256
                self._authority.bind(approval_id,
                                     payload_sha256({k: v for k, v in action.items() if k != "id"}))
                def publish(a):
                    request = PublishRequest(
                        platform=a["platform"], text=a["text"], format=a["format"],
                        link=a["link"], media_urls=tuple(a["media_urls"]),
                        alt_texts=tuple(a["alt_texts"]), thread_chunks=tuple(a["thread_chunks"]))
                    adapter = self._adapters.for_platform(Platform(request.platform))
                    identity = getattr(adapter, "account_identity", None)
                    if not callable(identity):
                        raise _PublishTargetUnverified()
                    try:
                        target = asyncio.run(identity())
                    except AdapterError:
                        raise _PublishTargetUnverified() from None
                    if not valid_target(request.platform, target) or target != a["publish_target"]:
                        raise _PublishTargetChanged()
                    claim = getattr(self._repository, "claim_publish", None)
                    if not callable(claim):
                        raise ScheduleStateError("repository requires durable publish claims")
                    if not claim(expected_entry):
                        raise _DispatchClaimLost()
                    entry.status = STATUS_DISPATCHING
                    entry.failure = "publish_outcome_unconfirmed"
                    outcome = asyncio.run(adapter.publish(request))
                    # Return the actual request platform, never the entry or provider result label.
                    return request.platform, outcome

                published_platform, result = self._enforcer.dispatch_outbound(
                    action, self._declarations, effect=publish,
                    now=moment.strftime("%Y-%m-%dT%H:%M:%SZ"), authority_ref=approval_id)
            except (_PublishTargetChanged, _PublishTargetUnverified) as target_error:
                self._invalidate_review(entry)
                entry.failure = ("publish_target_unverified" if isinstance(target_error, _PublishTargetUnverified)
                                 else "publish_target_changed")
                self._repository.save_schedule(entry)
                continue
            except _DispatchClaimLost:
                continue
            except GuardrailRefusal as refusal:
                entry.status = STATUS_FAILED
                entry.failure = f"guardrail refused publish: {refusal.code}"
                self._repository.save_schedule(entry)
                continue
            except AdapterError as error:
                entry.status = STATUS_FAILED
                entry.failure = str(error)
                self._repository.save_schedule(entry)
                continue
            published_at = self._clock()
            entry.status = STATUS_PUBLISHED
            entry.published_at = published_at
            entry.external_id = result.external_id
            entry.external_url = result.url
            entry.draft_only = result.draft_only
            entry.failure = None
            self._repository.save_schedule(entry)
            records.append(
                self._repository.save_publish_record(
                    PublishRecord(
                        schedule_id=entry.id,
                        platform=published_platform,
                        external_id=result.external_id,
                        external_url=result.url,
                        draft_only=result.draft_only,
                        published_at=published_at,
                    )
                )
            )
        return records

    # -- human operations ---------------------------------------------------------

    def cancel(self, schedule_id: str) -> ScheduleEntry:
        entry = self._entry(schedule_id)
        if entry.status in LOCKED_STATUSES:
            raise ScheduleStateError(f"cannot cancel an entry in state {entry.status}")
        entry.status = STATUS_CANCELLED
        return self._repository.save_schedule(entry)

    def reschedule(self, schedule_id: str, publish_at: datetime) -> ScheduleEntry:
        require_aware(publish_at)
        entry = self._entry(schedule_id)
        if entry.status in LOCKED_STATUSES:
            raise ScheduleStateError(f"cannot reschedule an entry in state {entry.status}")
        self._invalidate_review(entry)
        entry.publish_at = publish_at
        return self._repository.save_schedule(entry)

    @staticmethod
    def _invalidate_review(entry):
        # Old approval stays immutable in M00 but no longer authorizes this row.
        entry.approval_id = ""
        entry.status = STATUS_AWAITING_APPROVAL
        entry.decided_at = None
        entry.failure = "review_required"

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
