import pytest
from app.modules.m20_general_cognitive_worker.bandits import epsilon_greedy, ucb, thompson, contextual_ucb


def record(ident,arm,reward,context=None):
 d={'evidence_id':ident,'arm':arm,'reward':reward}
 if context is not None:d['context']=context
 return d


def test_epsilon_policy_balances_exploration_in_actual_action_probabilities():
 r=epsilon_greedy({'arms':['a','b'],'epsilon':.2,'feedback':[record('1','a',0),record('2','b',1)]})
 assert r['action_probabilities']==pytest.approx([.1,.9])
 assert r['counts']==[1,1] and r['arm_means']==[0,1]
 assert sum(r['action_probabilities'])==pytest.approx(1)


def test_ucb_explicitly_selects_untried_arm_without_nonjson_infinity():
 r=ucb({'arms':['a','b'],'feedback':[record('1','a',1)]})
 assert r['selected_arm']=='b' and r['ucb_scores'][1] is None


def test_ucb_exploration_can_select_lower_mean_underobserved_arm():
 rows=[record(str(i),'a',.8) for i in range(100)]+[record('b','b',.5)]
 r=ucb({'arms':['a','b'],'feedback':rows})
 assert r['selected_arm']=='b' and r['arm_means'][0]>r['arm_means'][1]


def test_thompson_updates_beta_posterior_and_really_samples_not_argmax_mean():
 p={'arms':['a','b'],'feedback':[record('1','a',1),record('2','a',0)]}
 first=thompson({**p,'seed':1});second=thompson({**p,'seed':2})
 assert first['beta_posterior']==[[2.,2.],[1.,1.]]
 assert first['posterior_means']==[.5,.5]
 assert first['posterior_samples']!=second['posterior_samples']
 assert first['selected_arm']==first['arms'][first['posterior_samples'].index(max(first['posterior_samples']))]
 assert thompson({**p,'seed':1})['posterior_samples']==first['posterior_samples']


def test_linucb_learns_context_specific_weights_from_observed_rewards():
 rows=[record('a1','a',1,[1,0]),record('a2','a',0,[0,1]),record('b1','b',0,[1,0]),record('b2','b',1,[0,1])]
 a=contextual_ucb({'arms':['a','b'],'feedback':rows,'context':[1,0],'exploration':0})
 b=contextual_ucb({'arms':['a','b'],'feedback':rows,'context':[0,1],'exploration':0})
 assert a['learned_weights']==[[.5,0],[0,.5]] and a['selected_arm']=='a' and b['selected_arm']=='b'
 assert a['history'][0]['prediction_before_update']==0


@pytest.mark.parametrize('policy',[epsilon_greedy,ucb,thompson,contextual_ucb])
def test_feedback_duplicates_and_invalid_rewards_rejected(policy):
 for rows in [[record('x','a',1),record('x','a',0)],[record('x','a',float('nan'))]]:
  with pytest.raises(ValueError):policy({'arms':['a','b'],'feedback':rows,'context':[1]})


def test_nonbinary_thompson_reward_not_faked_as_count():
 with pytest.raises(ValueError,match='binary'):thompson({'arms':['a'],'feedback':[record('x','a',.5)]})
