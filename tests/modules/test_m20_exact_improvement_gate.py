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
