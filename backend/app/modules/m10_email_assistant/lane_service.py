from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Callable
from uuid import uuid4

from .lane_models import (Approval, Draft, DraftStatus, EmailMessage, FollowUp,
                     FollowUpStatus, MailboxRef, SyncResult)
from .lane_provider import MailProvider
from .lane_policy import OutboundPolicy
from .lane_composer import ComposeRequest, DraftComposer
from .lane_store import EmailStore
from .lane_triage import RuleBasedTriage


class EmailAssistant:
    def __init__(self, store: EmailStore, provider: MailProvider, triage: RuleBasedTriage | None = None, clock: Callable[[], datetime] | None = None, outbound_policy: OutboundPolicy | None = None) -> None:
        self.store, self.provider = store, provider
        self.triage = triage or RuleBasedTriage()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.outbound_policy = outbound_policy or OutboundPolicy()

    def sync(self, mailbox: MailboxRef, limit: int = 100) -> SyncResult:
        if not 1 <= limit <= 500: raise ValueError("limit must be between 1 and 500")
        page=self.provider.sync(mailbox,self.store.cursor(mailbox.tenant_id,mailbox.mailbox_id),limit)
        messages=[EmailMessage(self._message_id(mailbox,m.provider_id),mailbox.tenant_id,mailbox.mailbox_id,m.provider_id,m.thread_id,m.sender,m.recipients,m.subject,m.body_text,m.received_at,m.headers,m.in_reply_to) for m in page.messages]
        imported,updated=self.store.save_sync_page(mailbox.tenant_id,mailbox.mailbox_id,messages,page.next_cursor)
        for message in messages:
            self.store.save_triage(mailbox.tenant_id,self.triage.classify(message))
            self.store.complete_followups_for_thread(mailbox.tenant_id,mailbox.mailbox_id,message.thread_id,message.received_at)
        return SyncResult(imported,updated,page.next_cursor,tuple(m.id for m in messages))

    def create_reply_draft(self, mailbox: MailboxRef, source_message_id: str, body_text: str) -> Draft:
        message=self.store.get_message(mailbox.tenant_id,source_message_id)
        if not message or message.mailbox_id != mailbox.mailbox_id: raise KeyError("message not found")
        if not body_text.strip(): raise ValueError("draft body cannot be empty")
        now=self.clock(); subject=message.subject if message.subject.lower().startswith("re:") else f"Re: {message.subject}"
        draft=Draft(str(uuid4()),mailbox.tenant_id,mailbox.mailbox_id,message.thread_id,(message.sender,),(),subject,body_text,DraftStatus.DRAFT,1,now,now,message.id)
        self.store.save_draft(draft); return draft

    def compose_reply(self, mailbox: MailboxRef, source_message_id: str, request: ComposeRequest, composer: DraftComposer) -> Draft:
        message=self.store.get_message(mailbox.tenant_id,source_message_id)
        if not message or message.mailbox_id != mailbox.mailbox_id: raise KeyError("message not found")
        thread=self.store.thread(mailbox.tenant_id,mailbox.mailbox_id,message.thread_id)
        return self.create_reply_draft(mailbox,source_message_id,composer.compose(thread,request))

    def revise_draft(self, tenant_id: str, draft_id: str, body_text: str, expected_revision: int) -> Draft:
        d=self.store.get_draft(tenant_id,draft_id)
        if not d: raise KeyError("draft not found")
        if d.status not in (DraftStatus.DRAFT,DraftStatus.REJECTED): raise RuntimeError("only editable drafts may be revised")
        if not body_text.strip(): raise ValueError("draft body cannot be empty")
        return self.store.update_draft(tenant_id,draft_id,body_text=body_text,status=DraftStatus.DRAFT,expected_revision=expected_revision)

    def request_approval(self, tenant_id: str, draft_id: str, requested_by: str) -> Approval:
        d=self.store.get_draft(tenant_id,draft_id)
        if not d: raise KeyError("draft not found")
        if d.status not in (DraftStatus.DRAFT,DraftStatus.REJECTED): raise RuntimeError("draft cannot be submitted")
        a=Approval(str(uuid4()),tenant_id,draft_id,requested_by,"pending",self.clock(),draft_revision=d.revision)
        self.store.save_approval(a); self.store.update_draft(tenant_id,draft_id,status=DraftStatus.PENDING_APPROVAL)
        return a

    def decide(self, tenant_id: str, approval_id: str, actor: str, approve: bool, reason: str | None=None) -> Approval:
        status="approved" if approve else "rejected"; a=self.store.decide_approval(tenant_id,approval_id,status,actor,reason)
        d=self.store.get_draft(tenant_id,a.draft_id)
        if not d: raise RuntimeError("approval draft disappeared")
        if d.revision != a.draft_revision: raise RuntimeError("draft changed after approval request")
        self.store.update_draft(tenant_id,d.id,status=DraftStatus.APPROVED if approve else DraftStatus.REJECTED)
        return a

    def send_approved(self, mailbox: MailboxRef, draft_id: str) -> Draft:
        d=self.store.get_draft(mailbox.tenant_id,draft_id)
        if not d or d.mailbox_id != mailbox.mailbox_id: raise KeyError("draft not found")
        receipt=self.store.send_receipt(mailbox.tenant_id,draft_id)
        if receipt: return self.store.update_draft(mailbox.tenant_id,draft_id,status=DraftStatus.SENT,provider_message_id=receipt['provider_message_id'])
        if d.status != DraftStatus.APPROVED: raise PermissionError("an approved draft is required before sending")
        self.outbound_policy.assert_sendable(d)
        key=sha256(f"{d.tenant_id}:{d.id}:{d.revision}".encode()).hexdigest()
        result=self.provider.send(mailbox,to=d.to,cc=d.cc,subject=d.subject,body_text=d.body_text,thread_id=d.thread_id,idempotency_key=key,headers={"X-Atlas-Draft-ID":d.id})
        self.store.record_send(d.tenant_id,d.id,key,result.provider_message_id,result.sent_at)
        return self.store.update_draft(d.tenant_id,d.id,status=DraftStatus.SENT,provider_message_id=result.provider_message_id)

    def schedule_followup(self, mailbox: MailboxRef, thread_id: str, *, due_at: datetime | None=None, delay: timedelta=timedelta(days=3), reason: str="No reply received", source_message_id: str | None=None) -> FollowUp:
        due=due_at or self.clock()+delay
        if due <= self.clock(): raise ValueError("follow-up due time must be in the future")
        f=FollowUp(str(uuid4()),mailbox.tenant_id,mailbox.mailbox_id,thread_id,due,FollowUpStatus.OPEN,reason,self.clock(),source_message_id)
        self.store.save_followup(f); return f

    @staticmethod
    def _message_id(mailbox: MailboxRef, provider_id: str) -> str:
        return sha256(f"{mailbox.tenant_id}\0{mailbox.mailbox_id}\0{provider_id}".encode()).hexdigest()[:32]
