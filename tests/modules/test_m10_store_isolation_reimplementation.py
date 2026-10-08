"""Real SQLite isolation checks; no connected mailbox or email effects."""
from datetime import datetime, timezone
from dataclasses import replace
import pytest
from app.modules.m10_email_assistant.lane_store import EmailStore
from app.modules.m10_email_assistant.lane_models import EmailMessage,TriageDecision,TriageLabel

def message(id='msg',tenant='tenant-a',mailbox='box-a'):
    return EmailMessage(id,tenant,mailbox,id,'thread','sender@example.test',('owner@example.test',),'subject','body',datetime.now(timezone.utc),{})

@pytest.mark.parametrize('foreign', [message('foreign','tenant-b','box-a'),message('foreign','tenant-a','box-b')])
def test_mixed_page_refused_before_any_write(foreign):
    store=EmailStore();store.save_sync_page('tenant-a','box-a',[message()], 'old')
    writes=[]
    store._db.set_trace_callback(lambda sql: writes.append(sql) if sql.startswith(('INSERT','UPDATE','DELETE','BEGIN')) else None)
    with pytest.raises(PermissionError,match='tenant.*mailbox'):
        store.save_sync_page('tenant-a','box-a',[replace(message(),subject='changed'),foreign],'new')
    assert not writes
    assert store.cursor('tenant-a','box-a')=='old'
    assert store.get_message('tenant-a','msg').subject=='subject'
    assert store._db.execute('SELECT count(*) FROM messages').fetchone()[0]==1

@pytest.mark.parametrize('foreign_id',['owned-by-other','missing'])
def test_triage_cannot_create_or_overwrite_foreign_message(foreign_id):
    store=EmailStore();store.save_sync_page('tenant-b','box-b',[message('owned-by-other','tenant-b','box-b')],'c')
    original=TriageDecision('owned-by-other',TriageLabel.FYI,.1,('owner',),False)
    store.save_triage('tenant-b',original)
    with pytest.raises(PermissionError,match='owned'):
        store.save_triage('tenant-a',TriageDecision(foreign_id,TriageLabel.URGENT,1,('foreign',),True))
    row=store._db.execute('SELECT * FROM triage').fetchone()
    assert row['tenant_id']=='tenant-b' and row['label']=='fyi'

def test_valid_sync_and_owned_triage_unchanged():
    store=EmailStore();assert store.save_sync_page('tenant-a','box-a',[message()],'c')==(1,0)
    store.save_triage('tenant-a',TriageDecision('msg',TriageLabel.FYI,.1,(),False))
    assert store._db.execute('SELECT tenant_id FROM triage').fetchone()[0]=='tenant-a'
