"""Tests for the scheduling + approval-verified execution gate.

Covers the success path (approve -> due -> publish with receipts), the
safety paths (pending/denied/revoked approvals never publish; adapter
failures mark entries failed; Instagram/TikTok fail closed without rendered
media), and human operations (cancel/reschedule/attach_media).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m06_social_media_manager.adapters import AdapterAuthError, PublishResult
from app.modules.m06_social_media_manager.models import AssetPrompt, ContentPlan, Platform, PlatformDraft
from app.modules.m06_social_media_manager.scheduler import (
    STATUS_APPROVED,
    STATUS_AWAITING_APPROVAL,
    STATUS_CANCELLED,
    STATUS_DENIED,
    STATUS_FAILED,
    STATUS_PUBLISHED,
    ScheduleNotFoundError,
    ScheduleStateError,
    Scheduler,
)
from app.modules.m06_social_media_manager.service import MemorySocialRepository


class FakeDecisions:
    def authorizes(self, entry, *, account_id):
        return account_id == "fixture-account" and self.status_of(entry.approval_id) == "approved"

    def __init__(self) -> None:
        self.statuses: dict[str, str] = {}

    def status_of(self, approval_id: str) -> str | None:
        return self.statuses.get(approval_id)


class FakeAdapter:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, request) -> PublishResult:
        self.published.append(request)
        return PublishResult(platform=request.platform, external_id="ext-1", url="https://x.example/1")


class FailingAdapter:
    async def publish(self, request) -> PublishResult:
        raise AdapterAuthError("token expired")


class FakeAdapterFactory:
    def account_id(self, platform):return "fixture-account"

    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def for_platform(self, platform: Platform):
        return self.adapter


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
DUE = NOW - timedelta(hours=1)
FUTURE = NOW + timedelta(hours=1)


def make_scheduler(adapter=None) -> tuple[Scheduler, MemorySocialRepository, FakeDecisions]:
    repository = MemorySocialRepository()
    decisions = FakeDecisions()
    scheduler = Scheduler(
        repository=repository,
        decisions=decisions,
        adapter_factory=FakeAdapterFactory(adapter or FakeAdapter()),
        clock=lambda: NOW,
    )
    return scheduler, repository, decisions


def make_plan(platform: Platform = Platform.TWITTER, text: str = "Launch thread", format: str = "thread") -> ContentPlan:
    return ContentPlan(
        id="plan-1",
        brief="brief",
        drafts=[PlatformDraft(platform=platform, format=format, post_copy=text)],
        created_at=NOW,
    )


def create_entry(scheduler: Scheduler, plan: ContentPlan, publish_at=DUE, sponsored: bool = False):
    entries = scheduler.create_entries(
        plan, publish_at=publish_at, approval_ids={plan.drafts[0].platform: "approval-1"}, sponsored=sponsored
    )
    return entries[0]


def test_full_success_path_approve_then_publish():
    scheduler, repository, decisions = make_scheduler()
    entry = create_entry(scheduler, make_plan())
    assert entry.status == STATUS_AWAITING_APPROVAL
    # No approval yet: nothing is due, nothing publishes.
    assert scheduler.execute_due(NOW) == []
    decisions.statuses["approval-1"] = "approved"
    changed = scheduler.sync_decisions()
    assert [e.id for e in changed] == [entry.id]
    assert repository.get_schedule(entry.id).status == STATUS_APPROVED
    records = scheduler.execute_due(NOW)
    assert len(records) == 1
    record = records[0]
    assert record.schedule_id == entry.id
    assert record.external_id == "ext-1"
    final = repository.get_schedule(entry.id)
    assert final.status == STATUS_PUBLISHED
    assert final.external_id == "ext-1"
    assert final.published_at == NOW


def test_thread_entry_carries_numbered_chunks_into_publish():
    adapter = FakeAdapter()
    scheduler, _repository, decisions = make_scheduler(adapter)
    text = " ".join(["word"] * 300)
    entry = create_entry(scheduler, make_plan(text=text))
    assert len(entry.thread_chunks) > 1
    assert all(len(chunk) <= 280 for chunk in entry.thread_chunks)
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    scheduler.execute_due(NOW)
    request = adapter.published[0]
    assert tuple(entry.thread_chunks) == request.thread_chunks


def test_denied_approval_never_publishes():
    adapter = FakeAdapter()
    scheduler, repository, decisions = make_scheduler(adapter)
    entry = create_entry(scheduler, make_plan())
    decisions.statuses["approval-1"] = "denied"
    scheduler.sync_decisions()
    assert repository.get_schedule(entry.id).status == STATUS_DENIED
    assert scheduler.execute_due(NOW) == []
    assert adapter.published == []


def test_approval_revoked_between_sync_and_execution_blocks_publish():
    adapter = FakeAdapter()
    scheduler, repository, decisions = make_scheduler(adapter)
    entry = create_entry(scheduler, make_plan())
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    # The approval flips to denied after sync but before the gate runs.
    decisions.statuses["approval-1"] = "denied"
    assert scheduler.execute_due(NOW) == []
    assert adapter.published == []
    assert repository.get_schedule(entry.id).status == STATUS_DENIED


def test_not_yet_due_entries_wait():
    adapter = FakeAdapter()
    scheduler, _repository, decisions = make_scheduler()
    create_entry(scheduler, make_plan(), publish_at=FUTURE)
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    assert scheduler.execute_due(NOW) == []
    assert adapter.published == []


def test_adapter_failure_marks_entry_failed_without_raising():
    scheduler, repository, decisions = make_scheduler(FailingAdapter())
    entry = create_entry(scheduler, make_plan())
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    records = scheduler.execute_due(NOW)
    assert records == []
    final = repository.get_schedule(entry.id)
    assert final.status == 'outcome_unknown'
    assert "token expired" in final.failure


def test_instagram_fails_closed_without_rendered_media():
    adapter = FakeAdapter()
    scheduler, repository, decisions = make_scheduler(adapter)
    entry = create_entry(scheduler, make_plan(platform=Platform.INSTAGRAM, format="carousel"))
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    assert scheduler.execute_due(NOW) == []
    final = repository.get_schedule(entry.id)
    assert final.status == STATUS_FAILED
    assert "rendered media" in final.failure
    assert adapter.published == []


def test_attach_media_unblocks_instagram_publish():
    adapter = FakeAdapter()
    scheduler, _repository, decisions = make_scheduler(adapter)
    entry = create_entry(scheduler, make_plan(platform=Platform.INSTAGRAM, format="carousel"))
    decisions.statuses["approval-1"] = "approved"
    scheduler.sync_decisions()
    scheduler.attach_media(entry.id, ["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg"], ["a", "b"])
    records = scheduler.execute_due(NOW)
    assert len(records) == 1
    assert adapter.published[0].media_urls == ("https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg")


def test_compliance_blocking_draft_aborts_entry_creation():
    scheduler, repository, _decisions = make_scheduler()
    from app.modules.m06_social_media_manager.scheduler import DraftComplianceError

    plan = make_plan(platform=Platform.INSTAGRAM, format="image", text="x" * 2300)
    with pytest.raises(DraftComplianceError):
        create_entry(scheduler, plan)
    assert repository.list_schedules() == []


def test_cancel_and_reschedule_rules():
    scheduler, repository, decisions = make_scheduler()
    entry = create_entry(scheduler, make_plan())
    moved = scheduler.reschedule(entry.id, FUTURE)
    assert moved.publish_at == FUTURE
    cancelled = scheduler.cancel(entry.id)
    assert cancelled.status == STATUS_CANCELLED
    with pytest.raises(ScheduleStateError):
        scheduler.cancel(entry.id)
    with pytest.raises(ScheduleStateError):
        scheduler.reschedule(entry.id, DUE)
    with pytest.raises(ScheduleNotFoundError):
        scheduler.cancel("nope")


def test_sync_is_idempotent():
    scheduler, repository, decisions = make_scheduler()
    create_entry(scheduler, make_plan())
    decisions.statuses["approval-1"] = "approved"
    assert len(scheduler.sync_decisions()) == 1
    assert scheduler.sync_decisions() == []


def test_concurrent_due_scans_publish_only_one_claim(monkeypatch):
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 adapter=FakeAdapter();scheduler,repository,decisions=make_scheduler(adapter)
 entry=create_entry(scheduler,make_plan());decisions.statuses['approval-1']='approved';scheduler.sync_decisions()
 original=scheduler.due_entries;barrier=Barrier(2)
 def due(now=None):
  rows=original(now);barrier.wait(timeout=5);return rows
 monkeypatch.setattr(scheduler,'due_entries',due)
 with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:scheduler.execute_due(NOW),[1,2]))
 assert len(adapter.published)==1
 assert len(repository.list_publish_records(entry.id))==1


def test_timeout_after_write_is_unknown_and_not_due_again():
 class Adapter(FakeAdapter):
  async def publish(self,request):
   self.published.append(request);raise TimeoutError('fixture ambiguous timeout after write')
 adapter=Adapter();scheduler,repository,decisions=make_scheduler(adapter)
 entry=create_entry(scheduler,make_plan());decisions.statuses['approval-1']='approved';scheduler.sync_decisions()
 assert scheduler.execute_due(NOW)==[]
 assert repository.get_schedule(entry.id).status=='outcome_unknown'
 assert scheduler.execute_due(NOW)==[] and len(adapter.published)==1
 with pytest.raises(ScheduleStateError):scheduler.reschedule(entry.id,FUTURE)


def test_receipt_persistence_failure_leaves_claim_without_replay(monkeypatch):
 adapter=FakeAdapter();scheduler,repository,decisions=make_scheduler(adapter)
 entry=create_entry(scheduler,make_plan());decisions.statuses['approval-1']='approved';scheduler.sync_decisions()
 def fail(*args,**kwargs):raise RuntimeError('fixture receipt save failed')
 monkeypatch.setattr(repository,'save_publish_record',fail)
 with pytest.raises(RuntimeError,match='receipt save failed'):scheduler.execute_due(NOW)
 assert repository.get_schedule(entry.id).status=='publishing'
 assert repository.list_publish_records(entry.id)==[]
 assert scheduler.execute_due(NOW)==[] and len(adapter.published)==1


def test_status_only_grant_and_unverified_account_do_not_publish():
 adapter=FakeAdapter();scheduler,repository,decisions=make_scheduler(adapter)
 entry=create_entry(scheduler,make_plan());decisions.statuses['approval-1']='approved';scheduler.sync_decisions()
 decisions.authorizes=lambda *args,**kwargs:False
 assert scheduler.execute_due(NOW)==[] and adapter.published==[]
 assert repository.get_schedule(entry.id).status=='denied'


def test_rendered_media_final_review_snapshot_binds_current_payload_and_account():
 scheduler,repository,decisions=make_scheduler()
 entry=create_entry(scheduler,make_plan(platform=Platform.INSTAGRAM,format='carousel'))
 with pytest.raises(ScheduleStateError,match='rendered media'):scheduler.final_review_payload(entry.id,'tenant-fixture')
 scheduler.attach_media(entry.id,['https://fixture.invalid/image'],['Fixture alt'])
 payload=scheduler.final_review_payload(entry.id,'tenant-fixture')
 assert payload['account_id']=='fixture-account' and payload['tenant_id']=='tenant-fixture'
 assert payload['media_urls']==['https://fixture.invalid/image'] and payload['alt_texts']==['Fixture alt']
 assert payload['schedule_id']==entry.id and payload['copy']==entry.text
 payload['media_urls'].append('https://wrong.invalid')
 assert repository.get_schedule(entry.id).media_urls==['https://fixture.invalid/image']
 scheduler._adapters.account_id=lambda platform:None
 with pytest.raises(ScheduleStateError,match='identity unavailable'):scheduler.final_review_payload(entry.id,'tenant-fixture')
