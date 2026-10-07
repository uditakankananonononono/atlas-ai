import pytest
from app.modules.m20_general_cognitive_worker.schemas import ToolSpec, Risk
from app.modules.m20_general_cognitive_worker.safety import SafetyGate, InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.tools import ToolRegistry, ToolDispatcher, ToolError, ToolBlockedError

@pytest.mark.asyncio
@pytest.mark.parametrize('arguments',[{}, {'n':'2'}, {'n':True}, {'n':2,'extra':1}])
async def test_invalid_schema_arguments_never_reach_handler_or_approval(arguments):
 calls=[]
 async def handler(args):calls.append(args);return {'sum':args['n']+1}
 r=ToolRegistry();r.register(ToolSpec(name='fixture',description='fixture',risk=Risk.EXTERNAL,parameters={'type':'object','properties':{'n':{'type':'integer'}},'required':['n'],'additionalProperties':False}),handler)
 gate=InMemoryApprovalGate()
 with pytest.raises(ToolBlockedError,match='schema'):await ToolDispatcher(r,SafetyGate(approvals=gate)).dispatch('fixture',arguments)
 assert not calls and not gate.requests

@pytest.mark.asyncio
async def test_valid_local_ref_arguments_execute_real_fixture():
 async def handler(args):return {'sum':args['n']+1}
 r=ToolRegistry();r.register(ToolSpec(name='fixture',description='fixture',parameters={'type':'object','$defs':{'number':{'type':'integer','minimum':1}},'properties':{'n':{'$ref':'#/$defs/number'}},'required':['n']}),handler)
 dispatcher=ToolDispatcher(r,SafetyGate())
 with pytest.raises(ToolBlockedError,match='schema'):await dispatcher.dispatch('fixture',{'n':0})
 out=await dispatcher.dispatch('fixture',{'n':4})
 assert out.succeeded and out.result_summary=="{'sum': 5}"

@pytest.mark.parametrize('schema',[{'type':'made_up'}, {'$ref':'https://untrusted.invalid/schema'}, {'$defs':{'x':{'$ref':'file:///etc/passwd'}}}])
def test_bad_or_remote_schema_rejected_at_registration(schema):
 async def handler(args):return {}
 with pytest.raises(ToolError,match='schema'):ToolRegistry().register(ToolSpec(name='fixture',description='fixture',parameters=schema),handler)

@pytest.mark.asyncio
async def test_unresolved_local_ref_blocks_instead_of_retrieval():
 async def handler(args):raise AssertionError('must not run')
 r=ToolRegistry();r.register(ToolSpec(name='fixture',description='fixture',parameters={'$ref':'#/$defs/missing'}),handler)
 with pytest.raises(ToolBlockedError,match='schema'):await ToolDispatcher(r,SafetyGate()).dispatch('fixture',{})

@pytest.mark.asyncio
async def test_invalid_args_do_not_spend_existing_exact_effect_token():
 from app.modules.m20_general_cognitive_worker.safety import ApprovalGateDecision
 from app.modules.m20_general_cognitive_worker.tools import ApprovalPending
 async def handler(args):return {'double':args['n']*2}
 r=ToolRegistry();r.register(ToolSpec(name='fixture',description='fixture',risk=Risk.EXTERNAL,parameters={'type':'object','properties':{'n':{'type':'integer'}},'required':['n']}),handler)
 gate=InMemoryApprovalGate();safety=SafetyGate(approvals=gate);dispatcher=ToolDispatcher(r,safety)
 with pytest.raises(ApprovalPending) as pending:await dispatcher.dispatch('fixture',{'n':3})
 token=pending.value.approval_id;gate.decide(token,ApprovalGateDecision.APPROVED)
 with pytest.raises(ToolBlockedError,match='schema'):await dispatcher.dispatch('fixture',{'n':'3'},granted_approval_id=token)
 out=await dispatcher.dispatch('fixture',{'n':3},granted_approval_id=token)
 assert out.succeeded and out.result_summary=="{'double': 6}"
