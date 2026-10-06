import numpy as np
import pytest
from app.modules.m20_general_cognitive_worker.learning_optimization import bilevel, stochastic_approximation, online_regression


def test_bilevel_selects_leader_by_actual_follower_optima_not_min_input_coordinate():
 choices=[{'id':'A','follower_cost':[1],'follower_bounds':[[0,2]],'leader_response_cost':[-1],'leader_constant':2},
          {'id':'B','follower_cost':[-1],'follower_bounds':[[0,2]],'leader_response_cost':[-1],'leader_constant':1}]
 r=bilevel({'leader_choices':choices})
 assert r['selected_choice']=='B' and r['objective']==-1 and r['solution']==[2.]
 assert [h['follower_optimum'] for h in r['history']]==[0.,-2.]
 assert all(h['follower_optimality_residual']<1e-8 for h in r['history'])


def test_bilevel_tie_resolution_keeps_follower_optimality():
 r=bilevel({'leader_choices':[{'id':'tie','follower_cost':[0,1],'follower_bounds':[[0,2],[0,2]],'leader_response_cost':[-1,0]}]})
 assert r['solution']==[2.,0.] and r['objective']==-2
 assert r['history'][0]['follower_optimality_residual']==0


def test_bilevel_infeasible_follower_is_not_faked():
 r=bilevel({'leader_choices':[{'id':'bad','follower_cost':[1],'follower_bounds':[[0,1]],'leader_response_cost':[1],'follower_constraints':[[-1]],'follower_rhs':[-2]}]})
 assert r['status']=='infeasible' and r['solution'] is None


def test_robbins_monro_stream_matches_batch_mean_and_observed_sample_variance():
 values=[[1.,3.],[4.,0.],[7.,6.]]
 r=stochastic_approximation({'observations':[{'evidence_id':str(i),'value':v} for i,v in enumerate(values)]})
 assert r['estimate']==pytest.approx(np.mean(values,axis=0))
 assert r['sample_variance']==pytest.approx(np.var(values,axis=0,ddof=1))
 assert r['history'][1]['previous']==[1.,3.]
 assert r['history'][1]['step']==.5


def test_stochastic_missing_or_reused_evidence_cannot_be_synthesized():
 for rows in [[],[{'value':[1]}],[{'evidence_id':'x','value':[1]},{'evidence_id':'x','value':[2]}]]:
  with pytest.raises(ValueError):stochastic_approximation({'observations':rows})


def test_online_learning_predicts_before_seeing_target_and_changes_next_prediction():
 r=online_regression({'initial_weights':[0.],'learning_rate':.5,'observations':[{'evidence_id':'a','features':[1.],'target':2.},{'evidence_id':'b','features':[1.],'target':2.}]})
 assert r['history'][0]['prediction_before_update']==0
 assert r['history'][1]['prediction_before_update']==1
 assert r['history'][1]['loss']<r['history'][0]['loss']
 assert r['weights'][0]>1


def test_online_stream_order_is_respected_not_leaky_batch_fit():
 records=[{'evidence_id':'a','features':[1.],'target':2.},{'evidence_id':'b','features':[1.],'target':-2.}]
 a=online_regression({'initial_weights':[0.],'observations':records})
 b=online_regression({'initial_weights':[0.],'observations':records[::-1]})
 assert a['weights']!=b['weights'] and a['history'][0]['prediction_before_update']==0
