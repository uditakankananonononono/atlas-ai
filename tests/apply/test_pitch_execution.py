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
        def send(self,payload):
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

def test_gmail_transport_checks_profile_and_posts_real_mime(monkeypatch):
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
    draft=make_org_pitch_draft({'name':'Org','recipient':'editor@example.invalid'},
                              {'name':'Author','summary':'Test findings.'},'research collaboration')
    effect=descriptor(draft,tenant_id='t',sender='author@example.invalid',send_at='immediate')
    sender=module.GmailPitchSender('author@example.invalid',lambda:'test-only-nonsecret-token')
    receipt=sender.send(effect['payload'])
    assert receipt['delivered']=='unverified' and len(calls)==2
    raw=json.loads(calls[1].data)['raw']
    msg=BytesParser(policy=email_policy.default).parsebytes(base64.urlsafe_b64decode(raw))
    assert msg['To']==draft['recipient'] and msg['Subject']==draft['subject']
    assert msg.get_content().rstrip('\n')==draft['body']

def test_wrong_token_profile_refuses_before_send(monkeypatch):
    from io import BytesIO
    from app.apply import pitch_execution as module
    calls=[]
    def fake_open(request,timeout):
        calls.append(request);return BytesIO(b'{"emailAddress":"different@example.invalid"}')
    monkeypatch.setattr(module,'urlopen',fake_open)
    sender=module.GmailPitchSender('author@example.invalid',lambda:'fixture')
    with pytest.raises(ValueError,match='different sending account'):
        sender.send({'sender':'author@example.invalid','channel':'gmail','attachment_hashes':[],
                     'to':['editor@example.invalid'],'cc':[],'bcc':[],'subject':'Test','body':'Test'})
    assert len(calls)==1
