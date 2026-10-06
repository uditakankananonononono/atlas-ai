import numpy as np
import pytest
from scipy.optimize import linprog
from app.modules.m20_general_cognitive_worker.strategic_learning import hedge, regret_matching, fictitious_play, game_regret_matching


def test_hedge_learns_from_prior_round_not_current_loss():
 r=hedge({'observations':[{'evidence_id':'a','expert_losses':[0,1]},{'evidence_id':'b','expert_losses':[0,1]}],'learning_rate':1})
 assert r['history'][0]['weights_before_observation']==[.5,.5]
 assert r['history'][1]['weights_before_observation'][0]==pytest.approx(1/(1+np.exp(-1)))
 assert r['normalized_weights'][0]>r['history'][1]['weights_before_observation'][0]
 assert r['cumulative_regret']==pytest.approx(r['cumulative_loss'])


def test_regret_matching_updates_policy_not_just_subtracts_loss_arrays():
 r=regret_matching({'observations':[{'evidence_id':'a','action_payoffs':[1,0]},{'evidence_id':'b','action_payoffs':[1,0]}]})
 assert r['history'][0]['policy_before_observation']==[.5,.5]
 assert r['history'][1]['policy_before_observation']==[1,0]
 assert r['cumulative_regret']==.5 and r['action_probabilities']==[1,0]


def test_hedge_stable_with_many_rounds_and_rejects_duplicate_evidence():
 rows=[{'evidence_id':str(i),'expert_losses':[0,1]} for i in range(2000)]
 r=hedge({'observations':rows,'learning_rate':10})
 assert np.isfinite(r['normalized_weights']).all() and sum(r['normalized_weights'])==pytest.approx(1)
 with pytest.raises(ValueError):hedge({'observations':[rows[0],rows[0]]})


@pytest.mark.parametrize('solver',[fictitious_play,game_regret_matching])
def test_zero_sum_matching_pennies_reaches_analytic_equilibrium(solver):
 tolerance=.03 if solver is fictitious_play else .001
 r=solver({'payoff_matrix':[[1,-1],[-1,1]],'tolerance':tolerance})
 assert r['converged'] and r['equilibrium_gap']<=tolerance
 assert r['row_strategy']==pytest.approx([.5,.5],abs=tolerance)
 assert r['column_strategy']==pytest.approx([.5,.5],abs=tolerance)


@pytest.mark.parametrize('solver',[fictitious_play,game_regret_matching])
def test_nonuniform_game_value_bounds_include_independent_lp_equilibrium(solver):
 M=np.array([[3.,0.],[0.,1.]])
 oracle=linprog([0,0,-1],A_ub=np.c_[-M.T,np.ones(2)],b_ub=[0,0],A_eq=[[1,1,0]],b_eq=[1],bounds=[(0,None),(0,None),(None,None)])
 value=-oracle.fun
 r=solver({'payoff_matrix':M.tolist(),'tolerance':.03,'max_iterations':10000})
 assert r['lower_value']<=value+1e-9<=r['upper_value']+1e-9
 assert r['converged'] and r['equilibrium_gap']<=.03
 assert r['row_strategy']==pytest.approx([.25,.75],abs=.03)


@pytest.mark.parametrize('solver',[fictitious_play,game_regret_matching])
def test_single_iteration_does_not_claim_general_equilibrium(solver):
 r=solver({'payoff_matrix':[[3,0],[0,1]],'max_iterations':1,'tolerance':1e-8})
 assert not r['converged'] and r['status']=='iteration_limit'


def test_fictitious_play_tight_gap_at_default_budget_is_not_falsely_converged():
 r=fictitious_play({'payoff_matrix':[[1,-1],[-1,1]],'tolerance':.001,'max_iterations':10000})
 assert not r['converged'] and r['status']=='iteration_limit' and r['equilibrium_gap']>.001
