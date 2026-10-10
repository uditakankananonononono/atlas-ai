import asyncio
import pytest
from app.modules.m14_project_builder.budgets import BudgetLedger, BudgetLimits
from app.modules.m14_project_builder.concurrent_runner import ConcurrentTaskRunner, TaskReservation
from app.modules.m14_project_builder.runner import RunnerError, TaskOutput
from app.modules.m14_project_builder.schemas import ProjectPlan, ProjectTask


def task(id, dependencies=()):
    return ProjectTask(id=id, title='Task '+id, objective='Execute '+id, agent_kind='coder', dependencies=list(dependencies), acceptance_criteria=['verified'])


def plan(*tasks):
    return ProjectPlan(goal='bounded local test', tasks=list(tasks), quality_gates=['review'])


def make(executor, *, parallel=2, calls=10, runtime=100, cost=1, auto=False, bound=None, attempts=1):
    ledger=BudgetLedger(BudgetLimits(max_agent_calls=calls,max_runtime_seconds=runtime,max_cost_usd=cost,max_iterations=10))
    return ConcurrentTaskRunner(ledger,executor,bound or (lambda t:TaskReservation(0,1)),max_parallel=parallel,auto_approve=auto,max_task_attempts=attempts),ledger


def test_overlap_dependency_and_input_isolation():
    async def scenario():
        seen=[];active=0;peak=0
        async def execute(t):
            nonlocal active,peak
            if t.id=='join':assert set(seen)=={'a','b'}
            active+=1;peak=max(peak,active);await asyncio.sleep(.01);active-=1;seen.append(t.id)
            t.dependencies.append('must-not-leak')
            return TaskOutput(True)
        runner,ledger=make(execute,auto=True)
        original=plan(task('a'),task('b'),task('join',('a','b')))
        report=await runner.run(original)
        assert report.stopped_reason=='completed' and peak==2
        assert original.tasks[0].status=='ready' or original.tasks[0].status=='blocked'
        assert all('must-not-leak' not in t.dependencies for t in report.plan.tasks)
        assert ledger.status().agent_calls_used==3
    asyncio.run(scenario())


def test_review_barrier():
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(True)
        runner,_=make(execute)
        report=await runner.run(plan(task('a'),task('b',('a',))))
        assert seen==['a'] and report.stopped_reason=='awaiting_review'
        report=await runner.run(runner.approve_reviewed(report.plan,'a'))
        assert seen==['a','b'] and report.tasks_in_review==('b',)
    asyncio.run(scenario())


@pytest.mark.parametrize('dimension', ['calls','cost','runtime'])
def test_pre_dispatch_budget_reservations(dimension):
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(True)
        args={'calls':1} if dimension=='calls' else {'cost':.15} if dimension=='cost' else {'runtime':1}
        runner,ledger=make(execute,auto=True,bound=lambda t:TaskReservation(.1,1),**args)
        report=await runner.run(plan(task('a'),task('b')))
        assert seen==['a'] and report.stopped_reason=='budget_exhausted'
        assert ledger.status().agent_calls_used==1
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['exception','timeout','overcost','overruntime','invalid'])
def test_failure_isolation(mode):
    async def scenario():
        async def execute(t):
            if t.id=='good':return TaskOutput(True)
            if mode=='exception':raise RuntimeError('private secret must not be exposed')
            if mode=='timeout':await asyncio.sleep(10)
            if mode=='overcost':return TaskOutput(True,cost_usd=1)
            if mode=='overruntime':return TaskOutput(True,runtime_seconds=1)
            return None
        runner,_=make(execute,auto=True,bound=lambda t:TaskReservation(0,.02))
        report=await runner.run(plan(task('bad'),task('good'),task('dependent',('bad',))))
        assert report.tasks_completed==('good',) and report.tasks_failed==('bad',)
        assert report.stopped_reason=='blocked_failures'
    asyncio.run(scenario())


def test_500_local_coroutines_with_1000_config_not_deployment():
    async def scenario():
        entered=0;release=asyncio.Event()
        async def execute(t):
            nonlocal entered
            entered+=1
            if entered==500:release.set()
            await release.wait()
            return TaskOutput(True)
        runner,_=make(execute,parallel=1000,calls=1000,runtime=10000,auto=True,bound=lambda t:TaskReservation(0,5))
        report=await runner.run(plan(*(task(str(i)) for i in range(500))))
        assert entered==500 and len(report.tasks_completed)==500 and report.stopped_reason=='completed'
    asyncio.run(scenario())


@pytest.mark.parametrize('value',[0,1001,True,1.5])
def test_parallel_validation(value):
    with pytest.raises(RunnerError):make(lambda t:None,parallel=value)


@pytest.mark.parametrize('cost,runtime',[(True,1),(float('nan'),1),(0,0),(0,float('inf')),(-1,1)])
def test_reservation_validation(cost,runtime):
    with pytest.raises(RunnerError):TaskReservation(cost,runtime)


def test_cancel_and_reentry():
    async def scenario():
        entered=asyncio.Event();closed=[]
        async def execute(t):
            entered.set()
            try:await asyncio.sleep(100)
            finally:closed.append(t.id)
        runner,ledger=make(execute,bound=lambda t:TaskReservation(0,10))
        job=asyncio.create_task(runner.run(plan(task('a'))));await entered.wait()
        with pytest.raises(RunnerError):await runner.run(plan(task('b')))
        job.cancel()
        with pytest.raises(asyncio.CancelledError):await job
        assert closed==['a'] and not runner._running and ledger.status().agent_calls_used==1
    asyncio.run(scenario())


def test_retry_success_and_charges_each_attempt():
    async def scenario():
        count=0
        async def execute(t):
            nonlocal count
            count+=1
            return TaskOutput(success=count==2)
        runner,ledger=make(execute,auto=True,attempts=2)
        report=await runner.run(plan(task('a')))
        assert count==2 and report.tasks_completed==('a',)
        assert ledger.status().agent_calls_used==2 and ledger.status().iterations_used==1
    asyncio.run(scenario())


def test_parallel_cap_multiple_waves():
    async def scenario():
        active=0;peak=0
        async def execute(t):
            nonlocal active,peak
            active+=1;peak=max(peak,active);await asyncio.sleep(.002);active-=1
            return TaskOutput(True)
        runner,_=make(execute,parallel=3,auto=True,calls=20)
        report=await runner.run(plan(*(task(str(i)) for i in range(11))))
        assert peak==3 and len(report.tasks_completed)==11
    asyncio.run(scenario())


def test_invalid_reservation_prevents_entire_wave_dispatch():
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(True)
        runner,ledger=make(execute,bound=lambda t:TaskReservation(0,1) if t.id=='a' else None)
        with pytest.raises(RunnerError):await runner.run(plan(task('a'),task('b')))
        assert seen==[] and ledger.status().agent_calls_used==0
    asyncio.run(scenario())


def test_plan_schema_500_limit_remains():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):plan(*(task(str(i)) for i in range(501)))


def test_multi_child_cancellation_drains_all_started_tasks():
    async def scenario():
        entered=set();closed=set();all_started=asyncio.Event()
        async def execute(t):
            entered.add(t.id)
            if len(entered)==3:all_started.set()
            try:await asyncio.sleep(100)
            finally:closed.add(t.id)
        runner,ledger=make(execute,parallel=3,bound=lambda t:TaskReservation(0,10))
        job=asyncio.create_task(runner.run(plan(task('a'),task('b'),task('c'))))
        await all_started.wait();job.cancel()
        with pytest.raises(asyncio.CancelledError):await job
        assert closed==entered=={'a','b','c'} and not runner._running
        assert ledger.status().agent_calls_used==3
    asyncio.run(scenario())


def test_reservation_callback_exception_before_dispatch_resets_runner():
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(True)
        def bound(t):
            if t.id=='b':raise LookupError('private callback diagnostic')
            return TaskReservation(0,1)
        runner,ledger=make(execute,bound=bound)
        with pytest.raises(LookupError):await runner.run(plan(task('a'),task('b')))
        assert not seen and ledger.status().agent_calls_used==0 and not runner._running
    asyncio.run(scenario())


def test_runtime_exhaustion_prevents_retry_dispatch():
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(False)
        runner,ledger=make(execute,runtime=1,attempts=2)
        report=await runner.run(plan(task('a')))
        assert seen==['a'] and report.stopped_reason=='budget_exhausted'
        assert ledger.status().runtime_seconds_used==1 and ledger.status().agent_calls_used==1
        assert report.plan.tasks[0].attempt==1
    asyncio.run(scenario())


def test_timeout_is_enforced_not_just_a_late_output_check():
    async def scenario():
        closed=[]
        async def execute(t):
            try:await asyncio.sleep(.2);return TaskOutput(True)
            finally:closed.append(t.id)
        runner,ledger=make(execute,auto=True,bound=lambda t:TaskReservation(0,.01))
        report=await runner.run(plan(task('a')))
        assert report.tasks_failed==('a',) and report.tasks_completed==()
        assert closed==['a'] and ledger.status().agent_calls_used==1
    asyncio.run(scenario())


def test_iteration_exhaustion_blocks_retry_even_with_call_capacity():
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(False)
        runner,ledger=make(execute,attempts=3)
        for _ in range(10):ledger.record_iteration()
        report=await runner.run(plan(task('a')))
        assert seen==['a'] and report.stopped_reason=='budget_exhausted'
        assert report.tasks_failed==('a',) and ledger.status().agent_calls_used==1
    asyncio.run(scenario())


def test_nonempty_wave_partial_budget_break_only_funded_task_runs():
    async def scenario():
        seen=[]
        async def execute(t):seen.append(t.id);return TaskOutput(True)
        runner,ledger=make(execute,parallel=3,calls=10,runtime=100,cost=.15,
                           auto=True,bound=lambda t:TaskReservation(.1,1))
        report=await runner.run(plan(task('a'),task('b'),task('c')))
        assert seen==['a'] and report.tasks_completed==('a',)
        assert [t.status for t in report.plan.tasks]==['completed','blocked','blocked']
        assert report.stopped_reason=='budget_exhausted' and ledger.status().agent_calls_used==1
    asyncio.run(scenario())
