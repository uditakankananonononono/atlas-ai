import itertools
import numpy as np
import pytest
from scipy.optimize import linprog, minimize
from app.modules.m20_general_cognitive_worker.lp_solvers import branch_and_bound, cutting_planes, column_generation


def test_branch_and_bound_matches_exhaustive_binary_optimum_and_actually_branches():
 p={'objective':[-5,-4,-3],'constraint_matrix':[[4,3,2]],'bounds':[4]}
 feasible=[(sum(c*v for c,v in zip(p['objective'],x)),x) for x in itertools.product([0,1],repeat=3) if np.dot(p['constraint_matrix'][0],x)<=4]
 optimum=min(feasible)[0]
 r=branch_and_bound(p)
 assert r['status']=='optimal' and r['objective']==optimum
 assert r['absolute_gap']==0
 assert any(h['status']=='branched' for h in r['history'])
 assert any(h['status'].startswith('pruned') for h in r['history'])
 assert set(r['solution'])<= {0,1}


def test_branch_limit_does_not_claim_an_optimum():
 r=branch_and_bound({'objective':[-5,-4,-3],'constraint_matrix':[[4,3,2]],'bounds':[4],'max_nodes':1})
 assert not r['converged'] and r['status']=='node_limit' and r['solution'] is None


def test_proven_infeasible_binary_problem_reports_no_solution():
 r=branch_and_bound({'objective':[1],'constraint_matrix':[[-1]],'bounds':[-2]})
 assert r['converged'] and r['status']=='infeasible' and r['solution'] is None


def test_cutting_planes_match_analytic_optimum_and_refine_bounds():
 r=cutting_planes({'quadratic':[[2]],'linear':[1],'box_bounds':[[0,2]],'tolerance':1e-7})
 assert r['converged'] and r['solution']==pytest.approx([.5],abs=.001)
 assert r['objective']==pytest.approx(-.25,abs=1e-7)
 assert r['duality_gap']<=1e-7 and r['iterations']>1
 lower=[h['lower_bound'] for h in r['history']]
 assert all(b>=a-1e-10 for a,b in zip(lower,lower[1:]))
 assert all(h['lower_bound']<=-.25+1e-10<=h['upper_bound']+1e-10 for h in r['history'])


def test_cutting_planes_correlated_box_problem_matches_independent_optimizer():
 Q=np.array([[3.,1.],[1.,2.]]);b=np.array([2.,-1.])
 objective=lambda x:.5*x@Q@x-b@x
 oracle=minimize(objective,[0,0],bounds=[(-2,2)]*2)
 r=cutting_planes({'quadratic':Q.tolist(),'linear':b.tolist(),'box_bounds':[[-2,2],[-2,2]],'tolerance':1e-6})
 assert r['converged'] and r['objective']==pytest.approx(oracle.fun,abs=1e-6)
 assert r['duality_gap']<=1e-6


def test_cutting_plane_limit_remains_unconverged():
 r=cutting_planes({'quadratic':[[2]],'linear':[1],'box_bounds':[[0,2]],'max_iterations':1})
 assert not r['converged'] and r['status']=='iteration_limit'


def test_column_generation_prices_new_column_and_matches_full_master():
 p={'objective':[3.,3.,1.],'constraint_matrix':[[1,0,1],[0,1,1]],'bounds':[1,1],'initial_columns':[0,1]}
 r=column_generation(p)
 oracle=linprog(p['objective'],A_eq=p['constraint_matrix'],b_eq=p['bounds'],bounds=(0,None))
 assert r['converged'] and r['objective']==pytest.approx(oracle.fun)
 assert r['solution']==pytest.approx([0,0,1])
 assert r['iterations']==2 and r['history'][0]['minimum_reduced_cost']==pytest.approx(-5)
 assert r['history'][0]['entering_column']==2
 assert r['equality_residual']<1e-9


def test_column_iteration_cap_preserves_restricted_solution_without_optimum_claim():
 r=column_generation({'objective':[3,3,1],'constraint_matrix':[[1,0,1],[0,1,1]],'bounds':[1,1],'initial_columns':[0,1],'max_iterations':1})
 assert r['objective']==6 and not r['converged'] and r['solution']==[1,1,0]


def test_column_master_infeasibility_is_not_a_placeholder_success():
 with pytest.raises(ValueError,match='feasible'):column_generation({'objective':[1,1],'constraint_matrix':[[1,0],[0,1]],'bounds':[1,1],'initial_columns':[0]})
