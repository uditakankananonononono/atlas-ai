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
        lab.propose(SynthesizedTool('bad','import os\ndef run(arguments): return {}','bad',{},[]))
    tool=lab.propose(SynthesizedTool('total','def run(arguments):\n return {"total": sum(arguments["values"])}',
        'Sum numeric values',{'type':'object'},[{'input':{'values':[2,3]},'expected':{'total':5}}]))
    assert lab.test('total') == {'total':1,'passed':1,'failures':[]}
    approval=lab.request_admission('total')
    with pytest.raises(PermissionError): lab.admit('total',approval_id=approval)
    gate.decide(approval,ApprovalGateDecision.APPROVED)
    assert lab.admit('total',approval_id=approval).source_hash == tool.source_hash
    assert (await registry.get('total').handler({'values':[4,5]})) == {'total':9}


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
