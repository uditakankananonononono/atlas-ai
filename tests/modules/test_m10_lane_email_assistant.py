from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m10_email_assistant.lane_api import (DraftStatus, EmailAssistant,
    EmailStore, MailboxRef, ProviderMessage, ProviderPage, SendResult,
    TriageLabel)

NOW=datetime(2026,9,20,12,tzinfo=timezone.utc)
BOX=MailboxRef("tenant-a","box-a","owner@example.com","fake")

class FakeProvider:
    def __init__(self): self.pages=[]; self.sent=[]
    def sync(self,mailbox,cursor,limit): return self.pages.pop(0)
    def send(self,mailbox,**kwargs):
        self.sent.append(kwargs); return SendResult("sent-1",NOW,{})

def message(pid="p1",thread="t1",subject="Please review",body="Can you approve this?"):
    return ProviderMessage(pid,thread,"sender@example.com",("owner@example.com",),subject,body,NOW,{})

def assistant():
    p=FakeProvider(); s=EmailStore(); return EmailAssistant(s,p,clock=lambda:NOW),p,s

def test_sync_is_cursor_based_idempotent_and_triages():
    a,p,s=assistant(); p.pages=[ProviderPage((message(),),"c1"),ProviderPage((message(body="changed"),),"c2")]
    first=a.sync(BOX); second=a.sync(BOX)
    assert (first.imported,first.updated,first.cursor)==(1,0,"c1")
    assert (second.imported,second.updated)==(0,1)
    assert len(s.thread("tenant-a","box-a","t1"))==1
    row=s._db.execute("SELECT label,needs_reply FROM triage").fetchone()
    assert tuple(row)==(TriageLabel.ACTION.value,1)

def test_tenant_isolation_for_messages():
    a,p,s=assistant(); p.pages=[ProviderPage((message(),),"c")]; result=a.sync(BOX)
    assert s.get_message("other",result.message_ids[0]) is None

def test_rule_triage_urgent_newsletter_and_spam():
    a,p,s=assistant(); p.pages=[ProviderPage((message("u","u","URGENT deadline","reply asap"),message("n","n","News","unsubscribe here"),message("x","x","Winner","crypto giveaway")),"c")]
    a.sync(BOX)
    labels={r[0] for r in s._db.execute("SELECT label FROM triage").fetchall()}
    assert labels=={"urgent","newsletter","spam"}

def test_approval_required_and_send_is_idempotent():
    a,p,s=assistant(); p.pages=[ProviderPage((message(),),"c")]; mid=a.sync(BOX).message_ids[0]
    d=a.create_reply_draft(BOX,mid,"Looks good.")
    with pytest.raises(PermissionError): a.send_approved(BOX,d.id)
    approval=a.request_approval("tenant-a",d.id,"user-1")
    a.decide("tenant-a",approval.id,"manager",True)
    sent=a.send_approved(BOX,d.id); sent_again=a.send_approved(BOX,d.id)
    assert sent.status is DraftStatus.SENT and sent.provider_message_id=="sent-1"
    assert sent_again.status is DraftStatus.SENT and len(p.sent)==1
    assert p.sent[0]["idempotency_key"]

def test_rejected_draft_can_be_revised_and_resubmitted():
    a,p,s=assistant(); p.pages=[ProviderPage((message(),),"c")]; mid=a.sync(BOX).message_ids[0]
    d=a.create_reply_draft(BOX,mid,"First")
    approval=a.request_approval("tenant-a",d.id,"u")
    a.decide("tenant-a",approval.id,"boss",False,"too terse")
    revised=a.revise_draft("tenant-a",d.id,"A fuller response",1)
    assert revised.status is DraftStatus.DRAFT and revised.revision==2
    assert a.request_approval("tenant-a",d.id,"u").draft_revision==2

def test_revision_conflict_blocks_lost_update():
    a,p,s=assistant(); p.pages=[ProviderPage((message(),),"c")]; mid=a.sync(BOX).message_ids[0]
    d=a.create_reply_draft(BOX,mid,"First")
    a.revise_draft("tenant-a",d.id,"Second",1)
    with pytest.raises(RuntimeError,match="revision conflict"): a.revise_draft("tenant-a",d.id,"Third",1)

def test_sync_reply_completes_open_followup_only_same_tenant_thread():
    a,p,s=assistant(); f=a.schedule_followup(BOX,"t1",due_at=NOW+timedelta(days=1))
    other=MailboxRef("tenant-b","box-a","b@example.com","fake")
    a.schedule_followup(other,"t1",due_at=NOW+timedelta(days=1))
    p.pages=[ProviderPage((message(),),"c")]; a.sync(BOX)
    statuses={r[0]:r[1] for r in s._db.execute("SELECT tenant_id,status FROM followups")}
    assert statuses=={"tenant-a":"completed","tenant-b":"open"}

def test_due_followups_are_ordered_and_tenant_scoped():
    a,p,s=assistant()
    a.schedule_followup(BOX,"late",due_at=NOW+timedelta(days=2))
    a.schedule_followup(BOX,"early",due_at=NOW+timedelta(days=1))
    assert [f.thread_id for f in s.due_followups("tenant-a",NOW+timedelta(days=3))]==["early","late"]
    assert s.due_followups("tenant-b",NOW+timedelta(days=3))==[]

def test_cross_tenant_draft_access_is_hidden():
    a,p,s=assistant(); p.pages=[ProviderPage((message(),),"c")]; mid=a.sync(BOX).message_ids[0]
    d=a.create_reply_draft(BOX,mid,"Hi")
    with pytest.raises(KeyError): a.request_approval("tenant-b",d.id,"intruder")
