import pytest
from sqlalchemy import create_engine
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime, RuntimeBusy, PersistenceCheckpointError
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import TaskContext, PlanNode, TaskState, ToolSpec, Risk, ActionRecord, ApprovalGateDecision
from app.modules.m20_general_cognitive_worker.safety import InMemoryApprovalGate


def wire(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "combined.db"}')
    repo = GCWRepository(engine); repo.create_schema()
    gate = InMemoryApprovalGate()
    runtime = GCWRuntime(repo, approval_gate=gate)
    return runtime, repo, gate, engine


def task(runtime, repo, calls, *, risk=Risk.EXTERNAL, raises=True):
    async def handler(args):
        calls.append(args)
        if raises: raise TimeoutError('fixture dispatched, result lost')
        return {'result': 'fixture'}
    runtime.tools.register(ToolSpec(name='fixture_effect', description='fixture', risk=risk), handler)
    context = TaskContext(goal='fixture', plan=[PlanNode(title='effect', tool='fixture_effect', risk=risk)])
    repo.save_task(context)
    return context


def execute(runtime, gate, ctx):
    pending = runtime.run_task(ctx.id)
    gate.decide(pending.plan[0].approval_id, ApprovalGateDecision.APPROVED)
    return runtime.resume(ctx.id, pending.plan[0].id, approved=True)


def test_atomic_execution_flush_retains_every_record_on_rollback(tmp_path, monkeypatch):
    runtime, repo, gate, engine = wire(tmp_path)
    ctx = TaskContext(goal='fixture'); repo.save_task(ctx)
    records = [ActionRecord(tool='fixture', task_id=ctx.id) for _ in range(3)]
    runtime.dispatcher.records.extend(records)
    original = repo.save_action; seen = []
    def fail_second(action):
        seen.append(action.id)
        if len(seen) == 2: raise RuntimeError('fixture write failure')
        return original(action)
    monkeypatch.setattr(repo, 'save_action', fail_second)
    with pytest.raises(RuntimeError): runtime._persist_context(ctx)
    assert repo.list_actions(task_id=ctx.id) == []
    assert runtime.dispatcher.records == records
    assert runtime._persistence_poisoned
    monkeypatch.setattr(repo, 'save_action', original)
    runtime._persist_context(ctx)
    assert len(repo.list_actions(task_id=ctx.id)) == 3
    assert not runtime._persistence_poisoned


def test_post_effect_flush_failure_restart_holds_no_second_effect(tmp_path, monkeypatch):
    runtime, repo, gate, engine = wire(tmp_path); calls = []
    ctx = task(runtime, repo, calls, raises=False)
    pending = runtime.run_task(ctx.id)
    gate.decide(pending.plan[0].approval_id, ApprovalGateDecision.APPROVED)
    def fail(*args): raise RuntimeError('fixture journal commit failed')
    monkeypatch.setattr(repo, 'save_execution', fail)
    with pytest.raises(RuntimeError): runtime.resume(ctx.id, pending.plan[0].id, approved=True)
    assert len(calls) == 1
    loaded = repo.load_task(ctx.id)
    assert loaded.plan[0].outcome_unknown and loaded.state == TaskState.BLOCKED
    with pytest.raises(RuntimeBusy): runtime.run_task(ctx.id)
    fresh = GCWRuntime(GCWRepository(engine), approval_gate=InMemoryApprovalGate())
    fresh.tools = runtime.tools; fresh.dispatcher.registry = runtime.tools
    assert fresh.run_task(ctx.id).plan[0].outcome_unknown
    assert len(calls) == 1


def test_failed_checkpoint_prevents_invocation_not_handler_failure(tmp_path, monkeypatch):
    runtime, repo, gate, engine = wire(tmp_path); calls=[]
    ctx=task(runtime, repo, calls)
    pending=runtime.run_task(ctx.id)
    gate.decide(pending.plan[0].approval_id, ApprovalGateDecision.APPROVED)
    def fail(*args): raise RuntimeError('fixture intent unavailable')
    monkeypatch.setattr(repo, 'save_task', fail)
    with pytest.raises(PersistenceCheckpointError): runtime.resume(ctx.id,pending.plan[0].id,approved=True)
    assert calls == [] and not runtime.dispatcher.records


def test_unknown_close_never_becomes_known_failure_and_remains_durable(tmp_path):
    runtime, repo, gate, engine=wire(tmp_path);calls=[];ctx=task(runtime,repo,calls)
    held=execute(runtime,gate,ctx)
    report=runtime.close(ctx.id)['retrospective']['execution_report']
    assert report['local_unknown_count']==1 and report['local_failure_count']==0
    assert report['unresolved_uncertainty'] and not report['external_outcomes_verified']
    assert repo.load_task(ctx.id).plan[0].outcome_unknown
    assert runtime.run_task(ctx.id).state == TaskState.BLOCKED
    assert len(calls)==1


@pytest.mark.parametrize('operation', ['close','update_task_schedule','add_task_context','prepare_supplied_plan','prepare_read_step_retry','reconcile_unknown','run_mcts'])
def test_mutations_reject_held_runtime_before_any_work(tmp_path, operation):
    runtime, repo, gate, engine=wire(tmp_path)
    runtime._execution_lock.acquire()
    try:
        with pytest.raises(RuntimeBusy): getattr(runtime,operation)('missing')
        assert repo.list_tasks()==[]
    finally: runtime._execution_lock.release()


def test_reconciliation_requires_independent_verifier_and_never_dispatches(tmp_path):
    runtime,repo,gate,engine=wire(tmp_path);calls=[];ctx=task(runtime,repo,calls)
    held=execute(runtime,gate,ctx);node=held.plan[0];action=repo.list_actions(task_id=ctx.id)[0]
    kwargs=dict(node_id=node.id,evidence={'reference':'fixture-independent-receipt'},outcome='failed',expected_action_id=action.id)
    with pytest.raises(ValueError,match='not configured'):runtime.reconcile_unknown(ctx.id,**kwargs)
    runtime.reconciliation_verifier=lambda payload:False
    with pytest.raises(ValueError,match='rejected'):runtime.reconcile_unknown(ctx.id,**kwargs)
    assert repo.load_task(ctx.id).plan[0].outcome_unknown and len(calls)==1
    runtime.reconciliation_verifier=lambda payload:payload['tenant_id']==repo.tenant_id and payload['evidence']['reference']=='fixture-independent-receipt'
    result=runtime.reconcile_unknown(ctx.id,**kwargs)
    assert not result.plan[0].outcome_unknown and result.plan[0].approval_id is None
    assert result.state==TaskState.BLOCKED and len(calls)==1
    assert repo.load_task(ctx.id).reconciliation_evidence[-1]['expected_action_id']==action.id


def test_read_unknown_cannot_use_correction_to_erase_hold(tmp_path):
    from app.core.providers import ProviderOutcomeUnknown
    runtime,repo,gate,engine=wire(tmp_path);calls=[]
    async def handler(args): calls.append(args);raise ProviderOutcomeUnknown('fixture invoked')
    runtime.tools.register(ToolSpec(name='fixture_read',description='fixture',risk=Risk.READ,max_retries=3),handler)
    ctx=TaskContext(goal='fixture',plan=[PlanNode(title='fixture',tool='fixture_read')]);repo.save_task(ctx)
    held=runtime.run_task(ctx.id)
    with pytest.raises(ValueError,match='uncertainty'):runtime.prepare_read_step_retry(ctx.id,held.plan[0].id,arguments={})
    assert len(calls)==1 and repo.load_task(ctx.id).plan[0].outcome_unknown


def test_close_summary_counts_and_selector_agree_on_unknown(tmp_path):
    runtime,repo,gate,engine=wire(tmp_path);calls=[];ctx=task(runtime,repo,calls)
    execute(runtime,gate,ctx)
    repo.save_action(ActionRecord(tool='fixture_effect',task_id=ctx.id,succeeded=True))
    repo.save_action(ActionRecord(tool='fixture_effect',task_id=ctx.id,succeeded=False))
    # Invalid simultaneous true flags are uncertainty, never known success.
    repo.save_action(ActionRecord(tool='fixture_effect',task_id=ctx.id,succeeded=True,outcome_unknown=True))
    report=runtime.close(ctx.id)['retrospective']['execution_report']
    counts=repo.dispatch_outcome_counts()['fixture_effect']
    summary=repo.action_summary()
    assert counts=={'successes':1,'failures':1,'unknowns':2}
    assert summary=={key:report[key] for key in ('local_action_count','local_success_count','local_failure_count','local_unknown_count')}
    assert summary=={'local_action_count':4,'local_success_count':1,'local_failure_count':1,'local_unknown_count':2}
    runtime.selector.use_dispatch_counts(repo.dispatch_outcome_counts())
    candidate=next(c for c in runtime.selector.score_all('fixture effect') if c.tool_name=='fixture_effect')
    assert candidate.supplied_successes==1 and candidate.supplied_failures==1 and candidate.supplied_unknowns==2
    assert candidate.historical_success==0.5
    runtime.selector.use_dispatch_records(repo.list_actions(task_id=ctx.id))
    records_candidate=next(c for c in runtime.selector.score_all('fixture effect') if c.tool_name=='fixture_effect')
    assert records_candidate==candidate
    fresh=GCWRepository(engine)
    assert fresh.action_summary()==summary


def test_legacy_payload_missing_unknown_flag_counts_known_outcomes(tmp_path):
    import sqlalchemy as sa
    from app.modules.m20_general_cognitive_worker.sql_repository import ActionRow
    runtime,repo,gate,engine=wire(tmp_path)
    a=ActionRecord(tool='fixture_legacy',succeeded=True)
    payload=a.model_dump(mode='json');payload.pop('outcome_unknown')
    with repo._session() as session:
        session.add(ActionRow(id=a.id,tenant_id=repo.tenant_id,payload_json=payload,started_at=a.started_at))
        session.commit()
    assert repo.dispatch_outcome_counts()=={'fixture_legacy':{'successes':1,'failures':0,'unknowns':0}}
    other=GCWRepository(engine,tenant_id='other')
    assert other.action_summary()=={'local_action_count':0,'local_success_count':0,'local_failure_count':0,'local_unknown_count':0}
