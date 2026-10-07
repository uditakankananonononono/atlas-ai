import pytest
from app.modules.m20_general_cognitive_worker.tools import ToolRegistry,ToolDispatcher,ToolBlockedError
from app.modules.m20_general_cognitive_worker.safety import SafetyGate,InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import ToolSpec,Risk,ApprovalGateDecision


@pytest.mark.asyncio
async def test_external_partial_failure_is_not_retried_under_one_approval():
 calls=[]
 async def effect(args):
  calls.append(args.copy());raise RuntimeError('effect happened, acknowledgement lost')
 r=ToolRegistry();r.register(ToolSpec(name='send_email',description='send',risk=Risk.EXTERNAL,max_retries=5),effect)
 g=InMemoryApprovalGate();s=SafetyGate(approvals=g);args={'to':'a@example.org'}
 _,token,_=s.preflight('send_email',Risk.EXTERNAL,args,task_id='a');g.decide(token,ApprovalGateDecision.APPROVED)
 out=await ToolDispatcher(r,s).dispatch('send_email',args,task_id='a',granted_approval_id=token)
 assert len(calls)==1
 assert not out.succeeded
 assert 'outcome unknown' in out.result_summary


@pytest.mark.asyncio
async def test_denial_without_token_or_violation_still_blocks_handler():
 class DenyingGate:
  def preflight(self,*args,**kwargs):return False,None,[]
 calls=[]
 async def handler(args):calls.append(args);return {}
 r=ToolRegistry();r.register(ToolSpec(name='read',description='read',risk=Risk.READ),handler)
 with pytest.raises(ToolBlockedError):await ToolDispatcher(r,DenyingGate()).dispatch('read',{})
 assert not calls


@pytest.mark.asyncio
async def test_handler_sees_snapshot_not_mutated_caller_payload():
 import asyncio
 entered=asyncio.Event();resume=asyncio.Event();seen=[]
 async def handler(args):
  entered.set();await resume.wait();seen.append(args['nested']['to']);return {}
 r=ToolRegistry();r.register(ToolSpec(name='send_email',description='send',risk=Risk.EXTERNAL),handler)
 g=InMemoryApprovalGate(auto_decision=ApprovalGateDecision.APPROVED)
 d=ToolDispatcher(r,SafetyGate(approvals=g));args={'nested':{'to':'reviewed'}}
 task=asyncio.create_task(d.dispatch('send_email',args));await entered.wait()
 args['nested']['to']='changed';resume.set();await task
 assert seen==['reviewed']
 assert d.records[0].arguments['nested']['to']=='reviewed'


@pytest.mark.asyncio
async def test_consumed_token_is_distinct_blocked_error_not_pending():
 from app.modules.m20_general_cognitive_worker.tools import ApprovalConsumed,ApprovalPending
 calls=[]
 async def handler(args):calls.append(args);return {}
 r=ToolRegistry();r.register(ToolSpec(name='send_email',description='send',risk=Risk.EXTERNAL),handler)
 g=InMemoryApprovalGate();s=SafetyGate(approvals=g);d=ToolDispatcher(r,s)
 _,token,_=s.preflight('send_email',Risk.EXTERNAL,{},task_id='a');g.decide(token,ApprovalGateDecision.APPROVED)
 await d.dispatch('send_email',{},task_id='a',granted_approval_id=token)
 with pytest.raises(ApprovalConsumed) as exc:
  await d.dispatch('send_email',{},task_id='a',granted_approval_id=token)
 assert not isinstance(exc.value,ApprovalPending)
 assert exc.value.approval_id==token and len(calls)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('name',['pay','PAY',' checkout ','order','place_order','send_money','refund','charge'])
async def test_named_money_aliases_gate_even_with_read_risk_and_never_retry(name):
 from app.modules.m20_general_cognitive_worker.tools import ApprovalPending
 calls=[]
 async def handler(args):calls.append(args);raise RuntimeError('ack lost')
 r=ToolRegistry();r.register(ToolSpec(name=name,description='money',risk=Risk.READ,max_retries=4),handler)
 g=InMemoryApprovalGate();s=SafetyGate(approvals=g);d=ToolDispatcher(r,s)
 with pytest.raises(ApprovalPending) as exc:await d.dispatch(name,{})
 assert not calls
 g.decide(exc.value.approval_id,ApprovalGateDecision.APPROVED)
 out=await d.dispatch(name,{},granted_approval_id=exc.value.approval_id)
 assert len(calls)==1 and 'outcome unknown' in out.result_summary


@pytest.mark.parametrize('name',['pay_invoice','buy','wire','payout','pay-now','transfer_funds','checkout_cart','withdraw','send_payment','ＰＡＹ','p\u200bay','рау','subscribe_monthly','donate_now','settle_invoice','tip_driver','upgrade_plan'])
def test_segmented_and_unicode_money_names_gate(name):
 from app.modules.m20_general_cognitive_worker.safety import requires_approval
 assert requires_approval(name,Risk.READ,{})


@pytest.mark.parametrize('name',['payload','orderly','repayment_notes','wireframe','player','research'])
def test_token_matching_does_not_mistake_substrings_for_money(name):
 from app.modules.m20_general_cognitive_worker.safety import requires_approval
 assert not requires_approval(name,Risk.READ,{})


@pytest.mark.parametrize('name',['payInvoice','sendMoney','buyNow','paymentIntent','orders','refunds','bill','topup','cashout','deposit','funds'])
def test_camelcase_and_common_money_aliases_gate(name):
 from app.modules.m20_general_cognitive_worker.safety import requires_approval
 assert requires_approval(name,Risk.READ,{})


@pytest.mark.parametrize('name',['PAYInvoice','pay2','placeOrder2','charges','payments','purchases','billing','invoice','buyer','topUp','cashOut'])
def test_final_name_defense_pass_acronym_digits_and_compounds(name):
 from app.modules.m20_general_cognitive_worker.safety import requires_approval
 assert requires_approval(name,Risk.READ,{})


@pytest.mark.asyncio
async def test_dispatch_risk_floor_cannot_lower_registered_external_risk():
 from app.modules.m20_general_cognitive_worker.tools import ApprovalPending
 calls=[]
 async def handler(args):calls.append(args);return {}
 registry=ToolRegistry();registry.register(ToolSpec(name='fixture',description='fixture',risk=Risk.EXTERNAL),handler)
 with pytest.raises(ApprovalPending):await ToolDispatcher(registry,SafetyGate()).dispatch('fixture',{},risk_floor=Risk.READ)
 assert not calls


@pytest.mark.asyncio
async def test_escalated_risk_failure_is_not_retried_and_token_binds_effective_tier():
 from app.modules.m20_general_cognitive_worker.tools import ApprovalPending
 calls=[]
 async def handler(args):calls.append(args);raise RuntimeError('synthetic uncertainty')
 registry=ToolRegistry();registry.register(ToolSpec(name='fixture',description='fixture',max_retries=5),handler)
 gate=InMemoryApprovalGate();safety=SafetyGate(approvals=gate);dispatcher=ToolDispatcher(registry,safety)
 with pytest.raises(ApprovalPending) as pending:await dispatcher.dispatch('fixture',{},risk_floor=Risk.EXTERNAL)
 token=pending.value.approval_id;gate.decide(token,ApprovalGateDecision.APPROVED)
 with pytest.raises(ApprovalPending):await dispatcher.dispatch('fixture',{},risk_floor=Risk.IRREVERSIBLE,granted_approval_id=token)
 assert not calls
 out=await dispatcher.dispatch('fixture',{},risk_floor=Risk.EXTERNAL,granted_approval_id=token)
 assert len(calls)==1 and not out.succeeded and 'outcome unknown' in out.result_summary
