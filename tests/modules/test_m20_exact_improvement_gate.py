import pytest
from app.modules.m20_general_cognitive_worker.metacognition import ImprovementLoop,PromptRegistry,PromptTemplate
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import ApprovalGateDecision


def setup():
 r=PromptRegistry();r.register(PromptTemplate(name='orient',content='v1'));g=InMemoryApprovalGate();return r,g,ImprovementLoop(r,g)
def propose(loop,content='v2'):return loop.propose('orient',content,evidence={'failures':1},expected_gain=.1)


def test_caller_yes_pending_or_foreign_token_cannot_apply_exact_revision():
 r,g,loop=setup();a=propose(loop);b=propose(loop,'other')
 with pytest.raises(PermissionError):loop.apply(a.id,approved=True,approval_id=a.approval_id)
 g.decide(b.approval_id,ApprovalGateDecision.APPROVED)
 with pytest.raises(PermissionError):loop.apply(a.id,approved=True,approval_id=b.approval_id)
 assert r.get('orient').content=='v1'
 assert g.requests[a.approval_id].payload['proposed_content']=='v2'


def test_approved_exact_change_applies_once_and_stale_target_rejected():
 r,g,loop=setup();a=propose(loop);b=propose(loop,'v3')
 for p in (a,b):g.decide(p.approval_id,ApprovalGateDecision.APPROVED)
 assert loop.apply(a.id,approved=True,approval_id=a.approval_id).version==2
 with pytest.raises(PermissionError):loop.apply(a.id,approved=True,approval_id=a.approval_id)
 with pytest.raises(PermissionError):loop.apply(b.id,approved=True,approval_id=b.approval_id)
 assert r.get('orient').content=='v2'


def test_no_gate_never_treats_id_label_as_approval():
 r=PromptRegistry();r.register(PromptTemplate(name='orient',content='v1'));loop=ImprovementLoop(r);p=propose(loop)
 with pytest.raises(PermissionError):loop.apply(p.id,approved=True,approval_id='made-up')


def test_changed_proposal_content_after_review_cannot_apply_unreviewed_prompt():
 r,g,loop=setup();a=propose(loop)
 g.decide(a.approval_id,ApprovalGateDecision.APPROVED)
 a.proposed_content='unreviewed changed prompt'
 with pytest.raises(PermissionError):loop.apply(a.id,approved=True,approval_id=a.approval_id)
 assert r.get('orient').content=='v1'


@pytest.mark.parametrize('field,value', [('target_name','other'),('current_content','changed'),('target_version',99),('approval_id','made-up'),('id','different')])
def test_mutated_reviewed_proposal_fields_fail_closed(field,value):
 r,g,loop=setup();a=propose(loop);token=a.approval_id
 g.decide(token,ApprovalGateDecision.APPROVED);setattr(a,field,value)
 with pytest.raises(PermissionError):loop.apply(next(iter(loop.proposals)),approved=True,approval_id=token)
 assert r.get('orient').content=='v1'


def test_parallel_apply_one_revision_and_reset_display_status_cannot_replay():
 from concurrent.futures import ThreadPoolExecutor
 from app.modules.m20_general_cognitive_worker.metacognition import ProposalStatus
 r,g,loop=setup();a=propose(loop);g.decide(a.approval_id,ApprovalGateDecision.APPROVED)
 def apply(_):
  try:loop.apply(a.id,approved=True,approval_id=a.approval_id);return True
  except PermissionError:return False
 with ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(apply,range(32)))==1
 a.status=ProposalStatus.PROPOSED
 with pytest.raises(PermissionError):loop.apply(a.id,approved=True,approval_id=a.approval_id)
 assert r.get('orient').version==2


def test_target_kind_changed_after_review_is_stale():
 r,g,loop=setup();a=propose(loop);g.decide(a.approval_id,ApprovalGateDecision.APPROVED)
 r.register(PromptTemplate(name='orient',content='v1',kind='algorithm_parameter'))
 with pytest.raises(PermissionError):loop.apply(a.id,approved=True,approval_id=a.approval_id)
 assert r.get('orient').content=='v1'
