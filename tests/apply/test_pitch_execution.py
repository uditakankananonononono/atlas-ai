from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m00_approval_center import impact
from app.modules.m00_approval_center.service import Service
from app.apply.pitch_drafts import make_org_pitch_draft
from app.apply.pitch_execution import PitchExecution, descriptor

@pytest.fixture
def setup(tmp_path):
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    service=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False),
                    clock=lambda:datetime(2026,10,12,tzinfo=timezone.utc))
    registry=impact.ProbeRegistry(); state={'recipient_verified':True,'sender_connected':True}
    registry.register('outreach',lambda payload:dict(state),module_id=10)
    draft=make_org_pitch_draft({'name':'Research Org','recipient':'editor@example.invalid'},
                              {'name':'Example Author','summary':'We have results.'},'a meeting')
    effect=descriptor(draft,tenant_id='tenant',sender='author@example.invalid',send_at='immediate')
    view=service.submit(module_id=10,action_type='outreach',payload=effect['payload'],user_id='tenant')
    impact.capture_review_state(service,view['id'],registry=registry)
    class Sender:
        def __init__(self):self.calls=0;self.fail=False
        def send(self,effect,approval_id):
            self.calls+=1
            if self.fail:raise TimeoutError('unknown outcome')
            return {'message_id':'provider-1','status':'provider_accepted'}
    sender=Sender()
    executor=PitchExecution(tmp_path/'receipts.sqlite',service=service,registry=registry,sender=sender)
    return executor,service,state,sender,view,effect

def test_approved_pitch_consumes_real_m00_and_records_once(setup):
    ex,service,state,sender,view,effect=setup
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner')
    assert ex.execute(effect,view['id'],actor='worker')['message_id']=='provider-1'
    assert ex.receipts()[0]['status']=='provider_accepted'
    with pytest.raises(RuntimeError):ex.execute(effect,view['id'],actor='worker')
    assert sender.calls==1

def test_pending_and_no_snapshot_cannot_send(setup):
    ex,service,state,sender,view,effect=setup
    with pytest.raises(PermissionError):ex.execute(effect,view['id'],actor='worker')
    assert sender.calls==0

def test_reviewed_state_drift_cannot_send(setup):
    ex,service,state,sender,view,effect=setup
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner')
    state['sender_connected']=False
    with pytest.raises(PermissionError):ex.execute(effect,view['id'],actor='worker')
    assert sender.calls==0

def test_recipient_or_body_tamper_cannot_send(setup):
    import copy,hashlib
    ex,service,state,sender,view,effect=setup
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner')
    changed=copy.deepcopy(effect);changed['payload']['to']=['other@example.invalid']
    with pytest.raises(RuntimeError):ex.execute(changed,view['id'],actor='worker')
    assert sender.calls==0

def test_timeout_retains_started_and_refuses_replay(setup):
    ex,service,state,sender,view,effect=setup
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner');sender.fail=True
    with pytest.raises(TimeoutError):ex.execute(effect,view['id'],actor='worker')
    assert ex.receipts()[0]['status']=='started'
    with pytest.raises(RuntimeError):ex.execute(effect,view['id'],actor='worker')
    assert sender.calls==1

def test_gmail_transport_checks_profile_and_posts_real_mime(monkeypatch, setup):
    import base64,json
    from email import policy as email_policy
    from email.parser import BytesParser
    from io import BytesIO
    from app.apply import pitch_execution as module
    calls=[]
    def fake_open(request,timeout):
        calls.append(request)
        if request.full_url.endswith('/profile'):
            return BytesIO(json.dumps({'emailAddress':'author@example.invalid'}).encode())
        return BytesIO(json.dumps({'id':'real-transport-fixture-id','threadId':'thread'}).encode())
    monkeypatch.setattr(module,'urlopen',fake_open)
    executor,service,state,old_sender,view,effect=setup
    sender=module.GmailPitchSender('author@example.invalid',lambda:'test-only-nonsecret-token',approval_store=executor)
    executor.sender=sender
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner')
    receipt=executor.execute(effect,view['id'],actor='worker')
    assert receipt['delivered']=='unverified' and len(calls)==2
    raw=json.loads(calls[1].data)['raw']
    msg=BytesParser(policy=email_policy.default).parsebytes(base64.urlsafe_b64decode(raw))
    assert msg['To']==effect['payload']['to'][0] and msg['Subject']==effect['payload']['subject']
    assert msg.get_content().rstrip('\n')==effect['payload']['body']

def test_wrong_token_profile_refuses_before_send(monkeypatch, setup):
    from io import BytesIO
    from app.apply import pitch_execution as module
    calls=[]
    def fake_open(request,timeout):
        calls.append(request);return BytesIO(b'{"emailAddress":"different@example.invalid"}')
    monkeypatch.setattr(module,'urlopen',fake_open)
    executor,service,state,old_sender,view,effect=setup
    sender=module.GmailPitchSender('author@example.invalid',lambda:'fixture',approval_store=executor)
    executor.sender=sender
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner')
    with pytest.raises(ValueError,match='different sending account'):
        executor.execute(effect,view['id'],actor='worker')
    assert len(calls)==1
    assert executor.receipts()[0]['status']=='dispatching'

def test_direct_transport_without_store_fails_closed():
    from app.apply.pitch_execution import GmailPitchSender
    with pytest.raises(PermissionError,match='approval store'):
        GmailPitchSender('author@example.invalid',lambda:'fixture')
    with pytest.raises(PermissionError,match='approval store'):
        GmailPitchSender('author@example.invalid',lambda:'fixture',approval_store={'approved':True})

def test_direct_transport_pending_or_fabricated_claim_cannot_send(setup,monkeypatch):
    from app.apply import pitch_execution as module
    ex,service,state,old_sender,view,effect=setup
    calls=[]
    monkeypatch.setattr(module,'urlopen',lambda *a,**kw:calls.append(a))
    sender=module.GmailPitchSender('author@example.invalid',lambda:'fixture',approval_store=ex)
    with pytest.raises(PermissionError,match='M00 consumption'):
        sender.send(effect,view['id'])
    import hashlib,json
    digest=hashlib.sha256(json.dumps(effect,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    # Even writing a fake local claim does not supply a real consumed M00 record.
    with ex._db() as db:
        db.execute('INSERT INTO pitch_sends VALUES (?,?,?,?,?)',('pitch-'+digest,view['id'],digest,'started',None))
    with pytest.raises(PermissionError,match='M00 consumption'):
        sender.send(effect,view['id'])
    assert calls==[]

def test_transport_requires_exact_consumed_payload_and_unused_durable_claim(setup,monkeypatch):
    from app.apply import pitch_execution as module
    from app.modules.c30 import policy
    import copy,hashlib,json
    from io import BytesIO
    ex,service,state,old_sender,view,effect=setup
    service.decide(view['id'],ApprovalStatus.APPROVED,decided_by='owner')
    digest=hashlib.sha256(json.dumps(effect,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    policy.execute(effect,view['id'],actor='worker',effect_id='pitch-'+digest,service=service,registry=ex.registry)
    sender=module.GmailPitchSender('author@example.invalid',lambda:'fixture',approval_store=ex)
    with pytest.raises(PermissionError,match='execution claim'):
        sender.send(effect,view['id'])
    with ex._db() as db:
        db.execute('INSERT INTO pitch_sends VALUES (?,?,?,?,?)',('pitch-'+digest,view['id'],digest,'started',None))
    changed=copy.deepcopy(effect);changed['payload']['to']=['other@example.invalid']
    with pytest.raises(PermissionError,match='M00 consumption'):sender.send(changed,view['id'])
    calls=[]
    def fake_open(request,timeout):
        calls.append(request)
        return BytesIO(b'{"emailAddress":"author@example.invalid"}' if request.full_url.endswith('profile') else b'{"id":"sent"}')
    monkeypatch.setattr(module,'urlopen',fake_open)
    assert sender.send(effect,view['id'])['message_id']=='sent'
    with pytest.raises(PermissionError,match='execution claim'):sender.send(effect,view['id'])
    assert len(calls)==2

def test_wire_preview_has_deterministic_reconciliation_id_and_no_send(setup):
    from app.apply.pitch_execution import wire_preview
    import base64
    from email.parser import BytesParser
    from email import policy as email_policy
    ex,service,state,sender,view,effect=setup
    first=wire_preview(effect);second=wire_preview(effect)
    assert first==second
    msg=BytesParser(policy=email_policy.default).parsebytes(base64.urlsafe_b64decode(first['raw']))
    assert msg['Message-ID']==first['message_id']
    assert msg['To']==effect['payload']['to'][0]
    assert msg['Subject']==effect['payload']['subject']
    assert msg['Message-ID'] is not None
    assert first['status']=='preview_only_not_authority'
    assert ex.receipts()==[]

def test_wire_exact_hash_changes_with_descriptor_and_preserves_input(setup):
    import base64,copy,hashlib
    from app.apply.pitch_execution import wire_preview
    ex,service,state,sender,view,effect=setup
    original=copy.deepcopy(effect)
    one=wire_preview(effect)
    assert one['wire_sha256']==hashlib.sha256(base64.urlsafe_b64decode(one['raw'])).hexdigest()
    other=descriptor(make_org_pitch_draft({'name':'Research Org','recipient':'editor@example.invalid'},
                     {'name':'Example Author','summary':'Different supported results.'},'a meeting'),
                     tenant_id='tenant',sender='author@example.invalid',send_at='immediate')
    two=wire_preview(other)
    assert one['message_id']!=two['message_id']
    assert one['raw']!=two['raw']
    assert effect==original and sender.calls==0 and ex.receipts()==[]

def test_wire_preview_refuses_attachment_descriptor_even_without_transport(setup):
    import copy
    from app.apply.pitch_execution import wire_preview
    *_,effect=setup
    effect=copy.deepcopy(effect)
    effect['payload']['attachment_hashes']=['a'*64]
    with pytest.raises(ValueError,match='attachment-free'):wire_preview(effect)
