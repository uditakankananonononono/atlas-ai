"""Chunk 2 tests: HTN planner, MCTS ruminator, context scheduler."""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.m20_general_cognitive_worker.executive import MCTSRuminator, MetaReasoner
from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner, PlanError
from app.modules.m20_general_cognitive_worker.scheduler import ContextScheduler
from app.modules.m20_general_cognitive_worker.schemas import (
    HTNMethod, MethodSource, PlanNode, Risk, TaskContext, TaskState,
)


class FakePlannerModel:
    def __init__(self, steps):
        self.steps = steps
        self.calls = 0

    def decompose(self, goal, *, context=""):
        self.calls += 1
        return self.steps


def library_method():
    return HTNMethod(
        name="market-entry", goal_pattern="prepare market entry strategy analysis",
        subtasks=[
            PlanNode(title="research market", tool="web_search", risk=Risk.READ),
            PlanNode(title="draft report", tool="write_document", risk=Risk.REVERSIBLE,
                     depends_on=["research market"]),
        ],
    )


def test_library_method_match_and_reuse():
    planner = HTNPlanner()
    planner.register_method(library_method())
    plan = planner.decompose("prepare a market entry strategy for product X")
    assert len(plan) == 2
    assert plan[1].depends_on == [plan[0].id]
    assert planner.methods["market-entry"].times_used == 1


def test_de_novo_decomposition_learned_and_validated():
    model = FakePlannerModel([
        {"id": "a", "title": "gather data", "tool": "web_search", "risk": "read"},
        {"id": "b", "title": "analyze", "tool": "python_sandbox", "risk": "reversible", "depends_on": ["a"]},
    ])
    planner = HTNPlanner(model=model)
    plan = planner.decompose("analyze competitor pricing for textbooks")
    assert model.calls == 1
    assert plan[1].depends_on == ["a"]
    learned = [m for m in planner.methods.values() if m.source == MethodSource.LEARNED]
    assert len(learned) == 1
    plan2 = planner.decompose("analyze competitor pricing for textbooks")
    assert model.calls == 1  # second time hits the learned method
    assert len(plan2) == 2


def test_decompose_rejects_bad_models():
    planner = HTNPlanner(model=FakePlannerModel([]))
    with pytest.raises(PlanError):
        planner.decompose("goal")
    planner = HTNPlanner(model=FakePlannerModel([{"title": "x", "depends_on": ["ghost"]}]))
    with pytest.raises(PlanError):
        planner.decompose("goal")
    planner = HTNPlanner(model=FakePlannerModel([
        {"id": "a", "title": "a", "depends_on": ["b"]},
        {"id": "b", "title": "b", "depends_on": ["a"]},
    ]))
    with pytest.raises(PlanError):
        planner.decompose("goal")
    planner = HTNPlanner()
    with pytest.raises(PlanError):
        planner.decompose("goal with no method and no model")


def test_ready_nodes_and_deadlock():
    a = PlanNode(title="a")
    b = PlanNode(title="b", depends_on=[a.id])
    c = PlanNode(title="c", depends_on=[b.id], max_attempts=1)
    plan = [a, b, c]
    assert [n.title for n in HTNPlanner.ready_nodes(plan)] == ["a"]
    a.state = TaskState.SUCCEEDED
    assert [n.title for n in HTNPlanner.ready_nodes(plan)] == ["b"]
    b.state = TaskState.FAILED
    assert HTNPlanner.ready_nodes(plan) == []
    assert HTNPlanner.is_deadlocked(plan) is True
    c.state = TaskState.CANCELLED
    b.state = TaskState.SUCCEEDED
    assert HTNPlanner.is_complete(plan) is True


def test_meta_reasoner_prefers_high_gain_low_cost():
    meta = MetaReasoner()
    research = PlanNode(title="research competitors", tool="web_search", risk=Risk.READ)
    send = PlanNode(title="email results", tool="send_email", risk=Risk.EXTERNAL)
    scored = meta.score_candidates([send, research], wm_context="", ltm_hits=2)
    assert scored[0].node.title == "research competitors"
    assert scored[0].score > scored[1].score


def test_mcts_rumination_returns_ordering():
    a = PlanNode(title="research", risk=Risk.READ)
    b = PlanNode(title="draft", risk=Risk.REVERSIBLE, depends_on=[a.id])
    c = PlanNode(title="publish", risk=Risk.EXTERNAL, depends_on=[b.id])
    ruminator = MCTSRuminator(simulations=16, seed=1)
    result = ruminator.ruminate([a, b, c])
    assert result["simulations"] == 16
    assert result["best_ordering"] == ["research", "draft", "publish"]
    assert result["expected_success"] is None and result["status"]=="random_ordering_heuristic_only"
    a.state = b.state = c.state = TaskState.SUCCEEDED
    assert ruminator.ruminate([a, b, c])["expected_success"] is None


def test_scheduler_priority_and_round_robin():
    scheduler = ContextScheduler()
    now = datetime.now(timezone.utc)
    urgent = TaskContext(goal="urgent", importance=3, deadline=now + timedelta(minutes=10))
    important = TaskContext(goal="important", importance=5)
    background = TaskContext(goal="background", importance=1)
    for ctx in (urgent, important, background):
        scheduler.add(ctx)
    order = scheduler.order(now=now)
    assert order[0].goal == "urgent"  # deadline proximity beats importance delta
    assert order[-1].goal == "background"
    first = scheduler.next_context(now=now)
    assert first.goal == "urgent"
    urgent.state = TaskState.SUCCEEDED
    nxt = scheduler.next_context(now=now)
    assert nxt.goal == "important"
    load = scheduler.cognitive_load()
    assert abs(sum(load.values()) - 1.0) < 1e-6
    assert load[important.id] > load[background.id]
    done = TaskContext(goal="done", state=TaskState.SUCCEEDED)
    scheduler.add(done)
    assert done not in scheduler.active()


def test_generated_plan_cache_never_reuses_different_goal_or_context():
 class ContextModel:
  def __init__(self):self.calls=0
  def decompose(self,goal,*,context=''):
   self.calls+=1
   return [{'title':'read fixture','tool':'read_fixture','arguments':{'goal':goal,'context':context}}]
 model=ContextModel();planner=HTNPlanner(model)
 a='summarize colored blocks for alice';b='summarize colored blocks for bob'
 planner.decompose(a,context='red')
 assert planner.decompose(b,context='red')[0].arguments['goal']==b
 assert planner.decompose(a,context='blue')[0].arguments['context']=='blue'
 assert model.calls==3
 planner.decompose(a,context='red');assert model.calls==3
 assert len(planner.methods)==3


def test_legacy_generated_method_without_scope_binding_never_matches():
 planner=HTNPlanner()
 planner.register_method(HTNMethod(name='learned:legacy',goal_pattern='read fixture',source=MethodSource.LEARNED,subtasks=[PlanNode(title='stale')]))
 with pytest.raises(PlanError):planner.decompose('read fixture')

@pytest.mark.parametrize('field,value', [('title',1),('title',' '),('tool',12),('arguments',[]),('arguments',None),('depends_on','a'),('depends_on',[1]),('max_attempts',True),('max_attempts',1.9),('max_attempts',0),('max_attempts',101),('id',False)])
def test_planner_rejects_coerced_or_unbounded_step_fields(field,value):
 step={'title':'fixture',field:value}
 with pytest.raises(PlanError):HTNPlanner(FakePlannerModel([step])).decompose('goal')


def test_planner_rejects_ambiguous_title_dependency():
 steps=[{'id':'a','title':'same'},{'id':'b','title':'same'},{'title':'final','depends_on':['same']}]
 with pytest.raises(PlanError,match='ambiguous'):HTNPlanner(FakePlannerModel(steps)).decompose('goal')
 steps[-1]['depends_on']=['a']
 assert len(HTNPlanner(FakePlannerModel(steps)).decompose('goal'))==3


def test_library_instantiation_resets_unearned_terminal_states_and_approval():
 planner=HTNPlanner()
 planner.register_method(HTNMethod(name='fixture',goal_pattern='fixture',subtasks=[PlanNode(title='compute',state=TaskState.SUCCEEDED,attempts=2,approval_id='old',result_summary='not actually executed')]))
 node=planner.decompose('fixture')[0]
 assert node.state==TaskState.PENDING and node.attempts==0 and node.approval_id is None and node.result_summary==''


@pytest.mark.parametrize('subtasks',[
 [PlanNode(id='same',title='a'),PlanNode(id='same',title='b')],
 [PlanNode(title='a',depends_on=['missing'])],
 [PlanNode(id='a',title='a',depends_on=['b']),PlanNode(id='b',title='b',depends_on=['a'])],
 [PlanNode(title='same'),PlanNode(title='same'),PlanNode(title='c',depends_on=['same'])],
])
def test_registered_library_rejects_invalid_or_ambiguous_dag(subtasks):
 planner=HTNPlanner()
 with pytest.raises(PlanError):planner.register_method(HTNMethod(name='fixture',goal_pattern='fixture',subtasks=subtasks))
 assert not planner.methods


def test_scheduler_deadline_selection_uses_one_clock_snapshot(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.modules.m20_general_cognitive_worker import scheduler as module
    base = datetime(2026, 10, 7, tzinfo=timezone.utc)
    class TickingClock:
        calls = 0
        @classmethod
        def now(cls, tz=None):
            cls.calls += 1
            return base + timedelta(seconds=cls.calls)
    scheduler = ContextScheduler()
    context = TaskContext(goal="deadline", deadline=base + timedelta(days=1))
    scheduler.add(context)
    monkeypatch.setattr(module, "datetime", TickingClock)
    assert scheduler.next_context().id == context.id
    assert TickingClock.calls == 1


def test_legacy_rumination_retains_low_scoring_long_order():
    plan = [PlanNode(title=str(i), risk=Risk.IRREVERSIBLE) for i in range(5)]
    result = MCTSRuminator(simulations=3, seed=1).ruminate(plan)
    assert len(result["best_ordering"]) == 5
    assert result["simulations"] == 3


def test_legacy_rumination_blocked_counts_actual_attempts():
    plan = [PlanNode(title="blocked", depends_on=["missing"])]
    result = MCTSRuminator(simulations=16).ruminate(plan)
    assert result["simulations"] == 1
    assert result["heuristic_order_score"] is None
