import pytest
from app.modules.m20_general_cognitive_worker.safety import SafetyGate,InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import Risk,ApprovalGateDecision


def test_approved_effect_token_cannot_authorize_different_recipient_payload_or_task():
 gate=InMemoryApprovalGate();safety=SafetyGate(approvals=gate)
 _,token,_=safety.preflight('send_email',Risk.EXTERNAL,{'to':'a@example.org','body':'reviewed'},task_id='task-a')
 gate.decide(token,ApprovalGateDecision.APPROVED)
 for action,payload,task in [('send_email',{'to':'b@example.org','body':'reviewed'},'task-a'),
                             ('send_email',{'to':'a@example.org','body':'changed'},'task-a'),
                             ('publish',{'to':'a@example.org','body':'reviewed'},'task-a'),
                             ('send_email',{'to':'a@example.org','body':'reviewed'},'task-b')]:
  allowed,_,_=safety.preflight(action,Risk.EXTERNAL,payload,task_id=task,granted_approval_id=token)
  assert not allowed


def test_exact_effect_token_works_once_and_replay_does_not():
 gate=InMemoryApprovalGate();safety=SafetyGate(approvals=gate);payload={'to':'a@example.org','body':'reviewed'}
 _,token,_=safety.preflight('send_email',Risk.EXTERNAL,payload,task_id='a');gate.decide(token,ApprovalGateDecision.APPROVED)
 assert safety.preflight('send_email',Risk.EXTERNAL,payload,task_id='a',granted_approval_id=token)[0]
 assert not safety.preflight('send_email',Risk.EXTERNAL,payload,task_id='a',granted_approval_id=token)[0]
