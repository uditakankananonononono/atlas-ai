import itertools
import numpy as np
import pytest
from scipy.optimize import linprog
from app.modules.m20_general_cognitive_worker.lp_solvers import benders, lagrangian_binary_knapsack


def test_benders_separates_stages_and_reaches_known_kink_optimum():
 r=benders({'first_stage_cost':[1],'recourse_cost':[3],'recourse_matrix':[[1]],'recourse_rhs':[2],'box_bounds':[[0,3]]})
 assert r['converged'] and r['solution']==pytest.approx([2])
 assert r['objective']==pytest.approx(2) and r['recourse_solution']==pytest.approx([0])
 assert r['iterations']>1 and r['duality_gap']<=1e-7
 assert any(h['cut_gradient']==[-3.] for h in r['history'])


def test_benders_matches_independent_full_two_stage_lp():
 c=np.array([1.,2.]);q=np.array([3.,4.]);T=np.array([[1.,.5],[.2,1.]]);h=np.array([2.,3.])
 p={'first_stage_cost':c.tolist(),'recourse_cost':q.tolist(),'recourse_matrix':T.tolist(),'recourse_rhs':h.tolist(),'box_bounds':[[0,4],[0,4]]}
 oracle=linprog(np.r_[c,q],A_ub=np.c_[-T,-np.eye(2)],b_ub=-h,bounds=[(0,4)]*2+[(0,None)]*2)
 r=benders(p)
 assert r['converged'] and r['objective']==pytest.approx(oracle.fun,abs=1e-7)
 assert r['lower_bound']<=oracle.fun+1e-7


def test_benders_cap_cannot_claim_optimality():
 r=benders({'first_stage_cost':[1],'recourse_cost':[3],'recourse_matrix':[[1]],'recourse_rhs':[2],'box_bounds':[[0,3]],'max_iterations':1})
 assert not r['converged'] and r['status']=='iteration_limit' and r['duality_gap']>0


def test_benders_rejects_costs_that_violate_complete_recourse_bound():
 with pytest.raises(ValueError):benders({'first_stage_cost':[1],'recourse_cost':[-3],'recourse_matrix':[[1]],'recourse_rhs':[2],'box_bounds':[[0,3]]})


def test_lagrangian_dual_recovers_tight_bound_without_false_primal_claim():
 r=lagrangian_binary_knapsack({'objective':[-4,-3],'weights':[2,2],'capacity':2})
 assert r['dual_optimal'] and r['primal_optimal']
 assert r['objective']==-4 and r['lower_bound']==pytest.approx(-4)
 assert r['solution']==[1,0]


def test_lagrangian_integrality_gap_is_preserved_against_enumerated_primal():
 c=[-5,-4,-3];w=[4,3,2];cap=4
 true=min(np.dot(c,x) for x in itertools.product([0,1],repeat=3) if np.dot(w,x)<=cap)
 r=lagrangian_binary_knapsack({'objective':c,'weights':w,'capacity':cap})
 assert r['lower_bound']<=true<=r['objective']
 assert not r['primal_optimal'] and r['status']=='dual_optimal_primal_gap'
 assert r['duality_gap']>0 and r['dual_optimal']
 assert np.dot(w,r['solution'])<=cap


def test_lagrangian_no_capacity_has_zero_feasible_primal():
 r=lagrangian_binary_knapsack({'objective':[-1,-2],'weights':[1,1],'capacity':0})
 assert r['objective']==0 and r['solution']==[0,0] and r['primal_optimal']
