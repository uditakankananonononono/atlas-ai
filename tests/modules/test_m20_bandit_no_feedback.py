import pytest
from app.modules.m20_general_cognitive_worker.bandits import epsilon_greedy

@pytest.mark.parametrize('epsilon',[0,.1,1])
def test_no_feedback_has_no_empirically_greedy_arm(epsilon):
 r=epsilon_greedy({'arms':['a','b','c'],'epsilon':epsilon})
 assert r['greedy_arm'] is None and not r['has_feedback']
 assert r['counts']==[0,0,0] and r['history']==[]
 assert r['action_probabilities']==pytest.approx([1/3]*3)
