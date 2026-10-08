"""A14 product-path acceptance with a fixture provider, not live cognition."""
import pytest
from sqlalchemy import create_engine
from app.core import model_catalog
from app.core.providers import ProviderOutcomeUnknown
from app.modules.m20_general_cognitive_worker.model_adapters import FreeFirstPlannerModel
from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
from app.modules.m20_general_cognitive_worker.schemas import Risk, TaskState, ToolSpec


class ObservedPlanner(FreeFirstPlannerModel):
    def __init__(self):
        super().__init__(model_name='fixture-local')
        self.stages = []

    def _prepare_stage(self, state):
        self.stages.append(('prepare', dict(state)))
        return super()._prepare_stage(state)

    def _generate_stage(self, state):
        self.stages.append(('generate', dict(state)))
        return super()._generate_stage(state)

    def _decode_stage(self, state):
        self.stages.append(('decode', dict(state)))
        return super()._decode_stage(state)

    def _validate_stage(self, state):
        self.stages.append(('validate', dict(state)))
        return super()._validate_stage(state)


def runtime_at(path, model):
    engine = create_engine(f'sqlite:///{path}')
    repo = GCWRepository(engine, tenant_id='a14-fixture')
    repo.create_schema()
    return engine, repo, GCWRuntime(repo, planner_model=model, require_method_review=True)


def test_langchain_actual_runtime_persists_proposed_plan_and_never_dispatches(tmp_path, monkeypatch):
    calls = []
    async def fixture(prompt, model_name=None, *, private=False):
        assert private is True and model_name == 'fixture-local'
        calls.append(prompt)
        return 'fixture', 'local', '[{"id":"one","title":"Review external draft","tool":"fixture_send","risk":"read"}]'
    monkeypatch.setattr(model_catalog, 'generate_free_first', fixture)
    model = ObservedPlanner()
    path = tmp_path / 'runtime.sqlite'
    engine, repo, runtime = runtime_at(path, model)
    effects = []
    async def send(args):
        effects.append(args)
        return 'should not execute'
    runtime.tools.register(ToolSpec(name='fixture_send', description='fixture external', risk=Risk.EXTERNAL), send)
    model.bind_registry(runtime.tools)
    context = runtime.submit_goal('a14 novel fixture goal', run_immediately=False)
    assert [name for name, _ in model.stages] == ['prepare', 'generate', 'decode', 'validate']
    for _, state in model.stages:
        assert state['goal'] == context.goal and 'context' in state
    assert 'Tools:' in model.stages[1][1]['prompt']
    assert model.stages[2][1]['text'].startswith('[')
    assert isinstance(model.stages[3][1]['data'], list)
    assert context.plan[0].risk == Risk.EXTERNAL
    methods = repo.list_methods()
    assert len(methods) == 1 and methods[0][1] == 'proposed'
    assert methods[0][0].activation_review is None
    assert not effects and len(calls) == 1
    assert not repo.list_actions(task_id=context.id)
    engine.dispose()
    fresh_engine = create_engine(f'sqlite:///{path}')
    fresh_repo = GCWRepository(fresh_engine, tenant_id='a14-fixture')
    fresh = GCWRuntime(fresh_repo, planner_model=model, require_method_review=True)
    assert fresh_repo.load_task(context.id).plan[0].risk == Risk.EXTERNAL
    assert fresh.planner.method_status(methods[0][0].name) == 'proposed'
    assert fresh.planner._match_method(context.goal) is None
    assert not effects and len(calls) == 1
    fresh_engine.dispose()


@pytest.mark.parametrize('failure', ['unknown', 'malformed', 'duplicate_keys', 'unregistered'])
def test_langchain_runtime_failure_stops_stages_and_persists_no_method(tmp_path, monkeypatch, failure):
    calls = []
    async def fixture(prompt, model_name=None, *, private=False):
        assert private is True
        calls.append(prompt)
        if failure == 'unknown':
            raise ProviderOutcomeUnknown('fixture dispatched unknown')
        texts = {'malformed':'not json', 'duplicate_keys':'{"steps":[],"steps":[]}',
                 'unregistered':'[{"title":"bad","tool":"not_registered"}]'}
        return 'fixture', 'local', texts[failure]
    monkeypatch.setattr(model_catalog, 'generate_free_first', fixture)
    model = ObservedPlanner()
    path = tmp_path / 'failure.sqlite'
    engine, repo, runtime = runtime_at(path, model)
    context = runtime.submit_goal('novel failure fixture', run_immediately=False)
    assert len(calls) == 1 and repo.list_methods() == []
    assert repo.list_actions(task_id=context.id) == [] and context.plan == []
    names = [name for name, _ in model.stages]
    assert names == (['prepare','generate'] if failure == 'unknown' else
                     ['prepare','generate','decode','validate'] if failure == 'unregistered' else
                     ['prepare','generate','decode'])
    stored = repo.load_task(context.id)
    assert stored.model_outcome_unknown == (failure == 'unknown')
    if failure == 'unknown':
        engine.dispose()
        fresh_engine = create_engine(f'sqlite:///{path}')
        fresh = GCWRuntime(GCWRepository(fresh_engine, tenant_id='a14-fixture'), planner_model=model)
        assert fresh.run_task(context.id).state == TaskState.BLOCKED
        assert len(calls) == 1
        fresh_engine.dispose()
    else:
        engine.dispose()
