from app.modules.m20_general_cognitive_worker.safety import SafetyGate,InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import Risk,ApprovalGateDecision


def test_mutating_approval_receiver_cannot_rewrite_reviewed_effect_binding():
    class Gate(InMemoryApprovalGate):
        def request(self,request):
            request.payload['nested']['recipient']='changed'
            return super().request(request)
    approvals=Gate();gate=SafetyGate(approvals=approvals)
    payload={'nested':{'recipient':'reviewed'}}
    allowed,token,_=gate.preflight('fixture',Risk.EXTERNAL,payload,task_id='task')
    assert not allowed and payload['nested']['recipient']=='reviewed'
    approvals.decide(token,ApprovalGateDecision.APPROVED)
    # Changed receiver data is not silently substituted for the caller effect.
    denied=gate.preflight('fixture',Risk.EXTERNAL,{'nested':{'recipient':'changed'}},task_id='task',granted_approval_id=token)
    assert denied[0] is False
    allowed=gate.preflight('fixture',Risk.EXTERNAL,payload,task_id='task',granted_approval_id=token)
    assert allowed[0] is True
    replay=gate.preflight('fixture',Risk.EXTERNAL,payload,task_id='task',granted_approval_id=token)
    assert replay[0] is False and replay[2][0].rule_id=='approval_consumed'
