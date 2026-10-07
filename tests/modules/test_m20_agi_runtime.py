import sqlite3
import pytest
from app.modules.m20_general_cognitive_worker.agi_runtime import (
    AutonomousGoalEngine, PersistentWorldModel, SelfImprovementLab,
    SynthesizedTool, ToolSynthesisLab,
)
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate
from app.modules.m20_general_cognitive_worker.schemas import ApprovalGateDecision
from app.modules.m20_general_cognitive_worker.tools import ToolRegistry


def test_world_model_preserves_conflicts_tenant_scope_and_hash_chain(tmp_path):
    path=str(tmp_path/'world.sqlite')
    a=PersistentWorldModel(path,'a'); b=PersistentWorldModel(path,'b')
    a.observe(subject='market',predicate='growing',value=True,source='s1',reliability=.9)
    a.observe(subject='market',predicate='growing',value=False,source='s2',reliability=.6)
    b.observe(subject='market',predicate='growing',value='unknown',source='private')
    assert len(a.hypotheses('market','growing')) == 2
    assert b.hypotheses('market','growing')[0]['value'] == 'unknown'
    first=a.snapshot(); second=a.snapshot()
    assert second['previous_hash'] == first['snapshot_hash'] and a.verify_chain()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE world_snapshots SET state_hash='tampered' WHERE id=?",(first['id'],))
    assert not a.verify_chain()


def test_autonomous_goal_is_proposed_but_cannot_self_authorize(tmp_path):
    world=PersistentWorldModel(str(tmp_path/'w.sqlite'),'tenant')
    world.observe(subject='launch',predicate='date',value='Monday',source='a')
    world.observe(subject='launch',predicate='date',value='Tuesday',source='b')
    gate=InMemoryApprovalGate(); engine=AutonomousGoalEngine(gate)
    goal=engine.propose_from_gaps(world,mission='ship safely')[0]
    approval=engine.request_activation(goal.id)
    with pytest.raises(PermissionError): engine.activate(goal.id,approval)
    gate.decide(approval,ApprovalGateDecision.APPROVED)
    assert engine.activate(goal.id,approval).status == 'active'


@pytest.mark.asyncio
async def test_tool_synthesis_requires_safe_ast_passing_tests_and_admission():
    registry=ToolRegistry(); gate=InMemoryApprovalGate(); lab=ToolSynthesisLab(registry,gate)
    with pytest.raises(ValueError,match='forbidden syntax'):
        lab.propose(SynthesizedTool('bad','import os\ndef run(arguments): return {}','bad',{},[{'input':{},'expected':{}}]))
    tool=lab.propose(SynthesizedTool('total','def run(arguments):\n return {"total": sum(arguments["values"])}',
        'Sum numeric values',{'type':'object'},[{'input':{'values':[2,3]},'expected':{'total':5}}]))
    report=lab.test('total')
    assert report['passed'] and report['outputs']==[{'total':5}]
    assert report['tool_admission_available'] is report['model_generation_verified'] is False
    with pytest.raises(PermissionError,match='unavailable'):lab.request_admission('total')
    tool.status='tested';tool.source='def run(arguments): return {"unreviewed":True}'
    with pytest.raises(PermissionError,match='unavailable'):lab.admit('total',approval_id='invented')
    assert registry.describe()==[]


def test_self_improvement_has_immutable_baseline_stale_guard_and_rollback():
    gate=InMemoryApprovalGate(); lab=SelfImprovementLab(gate); score=lambda text: text.count('required')
    v1=lab.establish('planner','required',score)
    report=lab.evaluate('planner','required required',score,min_gain=1)
    approval=lab.request_apply(report['id'])
    with pytest.raises(PermissionError): lab.apply(report['id'],approval_id=approval)
    gate.decide(approval,ApprovalGateDecision.APPROVED)
    v2=lab.apply(report['id'],approval_id=approval)
    assert (v1.version,v2.version,v2.parent_hash)==(1,2,v1.content_hash)
    stale=lab.evaluate('planner','required required required',score,min_gain=1)
    newer=lab.evaluate('planner','required required required required',score,min_gain=1)
    newer_approval=lab.request_apply(newer['id']); gate.decide(newer_approval,ApprovalGateDecision.APPROVED)
    lab.apply(newer['id'],approval_id=newer_approval)
    stale_approval=lab.request_apply(stale['id']); gate.decide(stale_approval,ApprovalGateDecision.APPROVED)
    with pytest.raises(PermissionError): lab.apply(stale['id'],approval_id=stale_approval)
    rollback_approval=lab.request_rollback('planner',1); gate.decide(rollback_approval,ApprovalGateDecision.APPROVED)
    restored=lab.rollback('planner',1,approval_id=rollback_approval)
    assert restored.content == v1.content and restored.version == 4


def test_world_weight_share_not_confidence_and_goal_priority_not_expected_value(tmp_path):
 world=PersistentWorldModel(str(tmp_path/'claim.sqlite'),'t')
 world.observe(subject='x',predicate='p',value='a',source='fake',reliability=.01)
 world.observe(subject='x',predicate='p',value='b',source='other',reliability=.01)
 item=world.hypotheses('x','p')[0]
 assert item['supplied_support_share']==.5 and item['evidence_verified'] is False and 'confidence' not in item
 goals=AutonomousGoalEngine(InMemoryApprovalGate()).propose_from_gaps(world,mission='review')
 assert goals[0].heuristic_gap_priority==.5 and not hasattr(goals[0],'expected_value')
 with pytest.raises(ValueError):world.observe(subject='x',predicate='p',value='a',source='fake',weight=float('inf'))

@pytest.mark.parametrize('field,value',[('objective','unreviewed goal'),('evidence',['invented']),('heuristic_gap_priority',99),('rationale','new rationale')])
def test_autonomous_activation_rejects_mutated_reviewed_goal(tmp_path,field,value):
 world=PersistentWorldModel(str(tmp_path/'g.sqlite'),'t')
 for v in ('a','b'):world.observe(subject='s',predicate='p',value=v,source=v)
 gate=InMemoryApprovalGate();engine=AutonomousGoalEngine(gate);goal=engine.propose_from_gaps(world,mission='m')[0]
 approval=engine.request_activation(goal.id);gate.decide(approval,ApprovalGateDecision.APPROVED)
 setattr(goal,field,value)
 with pytest.raises(PermissionError):engine.activate(goal.id,approval)


def test_autonomous_goal_activation_is_single_consumption(tmp_path):
 world=PersistentWorldModel(str(tmp_path/'g.sqlite'),'t')
 for v in ('a','b'):world.observe(subject='s',predicate='p',value=v,source=v)
 gate=InMemoryApprovalGate();engine=AutonomousGoalEngine(gate);goal=engine.propose_from_gaps(world,mission='m')[0]
 approval=engine.request_activation(goal.id);gate.decide(approval,ApprovalGateDecision.APPROVED)
 assert engine.activate(goal.id,approval).status=='active'
 goal.status='waiting_approval'
 with pytest.raises(PermissionError):engine.activate(goal.id,approval)

@pytest.mark.parametrize('field,value', [('candidate','unreviewed'),('candidate_score',900),('passed',False),('baseline_version',99),('name','other'),('gain',900)])
def test_improvement_rejects_changed_reviewed_or_evaluated_candidate(field,value):
 gate=InMemoryApprovalGate();lab=SelfImprovementLab(gate)
 lab.establish('p','a',len);lab.establish('other','x',len)
 report=lab.evaluate('p','aaa',len)
 report['candidate']='caller copy changed'
 approval=lab.request_apply(report['id']);gate.decide(approval,ApprovalGateDecision.APPROVED)
 lab.candidates[report['id']][field]=value
 with pytest.raises(PermissionError):lab.apply(report['id'],approval_id=approval)
 assert len(lab.history['p'])==1
 with pytest.raises(PermissionError):lab.request_apply(report['id'])

@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'1'])
def test_improvement_rejects_invalid_evaluator_scores(value):
 lab=SelfImprovementLab(InMemoryApprovalGate())
 with pytest.raises(ValueError):lab.establish('p','a',lambda _:value)
 lab.establish('p','a',len)
 with pytest.raises(ValueError):lab.evaluate('p','b',lambda _:value)
 with pytest.raises(ValueError):lab.evaluate('p','b',len,min_gain=value)


def test_improvement_apply_and_rollback_cannot_reuse_approvals_for_equal_content():
 from concurrent.futures import ThreadPoolExecutor
 gate=InMemoryApprovalGate();lab=SelfImprovementLab(gate);lab.establish('p','same',len)
 report=lab.evaluate('p','same',len);approval=lab.request_apply(report['id']);gate.decide(approval,ApprovalGateDecision.APPROVED)
 def apply(_):
  try:lab.apply(report['id'],approval_id=approval);return True
  except PermissionError:return False
 with ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(apply,range(16)))==1
 rollback=lab.request_rollback('p',1);gate.decide(rollback,ApprovalGateDecision.APPROVED)
 lab.rollback('p',1,approval_id=rollback)
 with pytest.raises(PermissionError):lab.rollback('p',1,approval_id=rollback)
 assert len(lab.history['p'])==3


def test_world_state_preserves_dot_colliding_subject_predicate_pairs(tmp_path):
 import json
 world=PersistentWorldModel(str(tmp_path/'keys.sqlite'),'t')
 world.observe(subject='a.b',predicate='c',value=1,source='fixture')
 world.observe(subject='a',predicate='b.c',value=2,source='fixture')
 state=world.state()
 assert len(state)==2
 assert {tuple(json.loads(key)):group[0]['value'] for key,group in state.items()}=={('a.b','c'):1,('a','b.c'):2}
 with pytest.raises(ValueError):world.observe(subject='x',predicate='p',value=float('nan'),source='fixture')


def test_concurrent_world_snapshots_never_fork_hash_chain(tmp_path):
 from concurrent.futures import ThreadPoolExecutor
 path=str(tmp_path/'concurrent.sqlite');world=PersistentWorldModel(path,'t')
 world.observe(subject='x',predicate='p',value='fixture',source='fixture')
 def snapshot(_):return PersistentWorldModel(path,'t').snapshot()
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(snapshot,range(32)))
 assert len({result['snapshot_hash'] for result in results})==32
 assert world.verify_chain()
 assert sum(result['previous_hash']=='GENESIS' for result in results)==1


def test_world_chain_malformed_stored_snapshot_returns_false(tmp_path):
 path=str(tmp_path/'malformed.sqlite');world=PersistentWorldModel(path,'t');snapshot=world.snapshot()
 with sqlite3.connect(path) as db:db.execute("UPDATE world_snapshots SET state_json='not json' WHERE id=?",(snapshot['id'],))
 assert world.verify_chain() is False


def test_isolated_pure_code_rejects_mutated_source_and_reports_failed_cases():
 lab=ToolSynthesisLab(ToolRegistry(),InMemoryApprovalGate())
 lab.propose(SynthesizedTool('wrong','def run(arguments): return 2','fixture',{},[{'input':{},'expected':3}]))
 assert lab.test('wrong')['passed'] is False
 lab.proposals['wrong'].source='import os\ndef run(arguments): return {}'
 with pytest.raises(PermissionError,match='changed'):lab.test('wrong')


def test_isolated_pure_code_backend_unavailable_never_falls_back(monkeypatch):
 from app.modules.m20_general_cognitive_worker.sandbox import SandboxViolation
 from app.modules.m04_research_scientist import approved_sandbox
 def missing():raise approved_sandbox.BackendUnavailableError('fixture missing backend')
 monkeypatch.setattr(approved_sandbox,'select_backend',missing)
 lab=ToolSynthesisLab(ToolRegistry(),InMemoryApprovalGate())
 lab.propose(SynthesizedTool('x','def run(arguments): return 1','fixture',{},[{'input':{},'expected':1}]))
 with pytest.raises(SandboxViolation,match='execution refused'):lab.test('x')


def test_isolated_candidate_input_and_source_snapshot_detach():
 lab=ToolSynthesisLab(ToolRegistry(),InMemoryApprovalGate());candidate=SynthesizedTool('x','def run(arguments): return arguments["x"]','fixture',{},[{'input':{'x':1},'expected':1}])
 returned=lab.propose(candidate);candidate.source='bad';returned.cases[0]['expected']=9
 assert lab.test('x')['passed'] is True
 with pytest.raises(ValueError,match='cases'):lab.propose(SynthesizedTool('bad','def run(arguments): return 1','fixture',{},[{'input':[]}]))


def test_isolated_pure_code_time_limit_and_memory_failure_do_not_pass():
 lab=ToolSynthesisLab(ToolRegistry(),InMemoryApprovalGate())
 loop='def run(arguments):\n for a in arguments["items"]:\n  for b in arguments["items"]:\n   for c in arguments["items"]:\n    for d in arguments["items"]:\n     x=1\n return 1'
 lab.propose(SynthesizedTool('slow',loop,'bounded fixture',{},[{'input':{'items':list(range(200))},'expected':1}]))
 slow=lab.test('slow')
 assert slow['passed'] is False and slow['returncode']!=0
 lab.propose(SynthesizedTool('memory','def run(arguments): return [1]*1000000000','bounded fixture',{},[{'input':{},'expected':1}]))
 assert lab.test('memory')['passed'] is False
