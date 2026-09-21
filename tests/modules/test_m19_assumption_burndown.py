import pytest
from app.modules.m19_idea_incubator.assumption_tests import rank_assumption_tests
def test_burndown_prioritizes_information_per_cost_and_selects_budget():
 assumptions=[{'id':'demand','statement':'labs will pay','probability_true':.5}]
 tests=[{'id':'interviews','assumption_id':'demand','positive_result_probability':.5,'posterior_if_positive':.9,'posterior_if_negative':.1,'cost':0,'hours':2,'method':'5 interviews','success_metric':'3 commitments'},{'id':'ad','assumption_id':'demand','positive_result_probability':.5,'posterior_if_positive':.7,'posterior_if_negative':.3,'cost':100,'hours':1}]
 out=rank_assumption_tests(assumptions,tests,budget=0)
 assert out['ranked_tests'][0]['test_id']=='interviews' and out['selected_within_budget']==['interviews']
 assert 'not business success' in out['boundary']
def test_burndown_rejects_unknown_assumptions_and_invalid_probabilities():
 with pytest.raises(ValueError,match='unknown'):rank_assumption_tests([{'id':'a'}],[{'id':'t','assumption_id':'x'}])
 with pytest.raises(ValueError,match='probabilities'):rank_assumption_tests([{'id':'a','probability_true':2}],[{'id':'t','assumption_id':'a'}])
