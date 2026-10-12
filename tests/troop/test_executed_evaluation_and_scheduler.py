import threading
import pytest
from app.troop.roles import Plan, Step, ActionWorker, RuleReviewer, TemplatePlanner, Verdict
from app.troop.runner import TroopRunner, PlanError
from app.troop.evaluation import evaluate

@pytest.mark.parametrize('name', ['max_attempts','max_workers','max_steps'])
@pytest.mark.parametrize('value', [0, -1, True, 1.5])
def test_config_bounds(name,value):
    with pytest.raises(PlanError):
        TroopRunner(TemplatePlanner(),ActionWorker(),RuleReviewer(),**{name:value})

def test_dependent_starts_before_unrelated_slow_step_finishes():
    dependent = threading.Event()
    worker = ActionWorker()
    worker.register('fast',lambda *a: 1)
    def slow(*a):
        assert dependent.wait(2), 'old layer barrier stalls ready dependent'
        return 1
    def next_step(*a):
        dependent.set(); return 2
    worker.register('slow',slow); worker.register('next',next_step)
    class Planner:
        def plan(self,task):
            return Plan('t',(Step('a','fast'),Step('b','slow'),Step('c','next',depends_on=('a',))))
    result = TroopRunner(Planner(),worker,RuleReviewer(),max_workers=2,max_attempts=1).run({'id':'t'})
    assert result.status == 'completed' and result.outputs['c'] == 2

def test_reviewer_exception_is_retried_without_losing_independent_branch():
    class Reviewer:
        def __init__(self): self.calls=0
        def review(self,step,out):
            self.calls += 1
            if self.calls == 1: raise RuntimeError('temporarily unavailable')
            return Verdict(True)
    result = TroopRunner(TemplatePlanner(),ActionWorker(),Reviewer()).run({'id':'t','kind':'sum_table','rows':[{'x':3}]})
    assert result.status == 'completed' and result.attempts['totals'] == 2

def test_evaluation_executes_and_recomputes_failures():
    actual = TroopRunner(TemplatePlanner(),ActionWorker(),RuleReviewer())
    class Broken:
        def run(self,task): raise RuntimeError('fails')
    cases = [{'task':{'id':'s','kind':'sum_table','rows':[{'x':3},{'x':2}]},'expected':{'totals':{'x':5}}}]
    report = evaluate({'actual':actual,'broken':Broken()},cases)
    assert [r['passed'] for r in report['results']] == [1,0]
    cases[0]['expected']['totals']['x'] = 6
    assert evaluate({'a':actual,'b':actual},cases)['results'][0]['passed'] == 0

def test_mutating_runner_cannot_change_following_runners_case():
    class Mutator:
        def run(self,task): task['rows'][0]['x']=999; raise RuntimeError()
    actual = TroopRunner(TemplatePlanner(),ActionWorker(),RuleReviewer())
    cases=[{'task':{'id':'s','kind':'sum_table','rows':[{'x':3}]},'expected':{'totals':{'x':3}}}]
    assert evaluate({'a':Mutator(),'b':actual},cases)['results'][1]['passed'] == 1
    assert cases[0]['task']['rows'][0]['x'] == 3
