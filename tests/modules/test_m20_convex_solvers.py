import numpy as np
import pytest
from scipy.optimize import minimize
from app.modules.m20_general_cognitive_worker.convex_solvers import coordinate_descent, proximal_gradient, frank_wolfe, dual_decomposition


@pytest.mark.parametrize('solver',[coordinate_descent,proximal_gradient])
def test_l1_iterative_solvers_match_known_optimum_and_kkt(solver):
 r=solver({'quadratic':[[2,0],[0,4]],'linear':[3,-1],'l1_penalty':.5,'initial':[12,9]})
 assert r['converged'] and r['solution']==pytest.approx([1.25,-.125],abs=1e-5)
 assert r['kkt_violation']<1e-6


@pytest.mark.parametrize('solver',[coordinate_descent,proximal_gradient])
def test_correlated_l1_problem_matches_independent_optimizer(solver):
 Q=np.array([[3.,1.],[1.,2.]]);b=np.array([2.,-1.]);penalty=.3
 oracle=minimize(lambda x:.5*x@Q@x-b@x+penalty*np.abs(x).sum(),[0.,0.],method='Powell',options={'xtol':1e-10,'ftol':1e-10})
 r=solver({'quadratic':Q.tolist(),'linear':b.tolist(),'l1_penalty':penalty})
 assert r['objective']==pytest.approx(oracle.fun,abs=1e-5)
 assert r['kkt_violation']<1e-6


def test_coordinate_descent_updates_only_the_named_coordinate_each_subproblem():
 r=coordinate_descent({'quadratic':[[3,1],[1,2]],'linear':[2,-1],'l1_penalty':.3})
 assert r['history'][0]['coordinate']==0 and r['history'][1]['coordinate']==1
 assert r['history'][0]['next_value']==pytest.approx((2-.3)/3)


def test_proximal_solver_monotonically_reduces_nonsmooth_objective():
 r=proximal_gradient({'quadratic':[[3,1],[1,2]],'linear':[2,-1],'l1_penalty':.3})
 losses=[h['objective'] for h in r['history']]
 assert all(b<=a+1e-12 for a,b in zip(losses,losses[1:]))
 assert r['iterations']>1


def test_frank_wolfe_simplex_optimum_with_gap_certificate():
 r=frank_wolfe({'quadratic':[[2,0],[0,2]],'linear':[1,0]})
 assert r['converged'] and r['solution']==pytest.approx([.75,.25],abs=1e-5)
 assert r['duality_gap']<1e-6
 assert sum(r['solution'])==pytest.approx(1)
 assert r['history'][0]['step_fraction']==pytest.approx(.5)


def test_frank_wolfe_correlated_problem_matches_slsqp():
 Q=np.array([[3,1,0],[1,2,.1],[0,.1,1.]])
 b=np.array([1.,0.,.2])
 oracle=minimize(lambda x:.5*x@Q@x-b@x,[1/3]*3,method='SLSQP',bounds=[(0,None)]*3,constraints=[{'type':'eq','fun':lambda x:x.sum()-1}],options={'ftol':1e-12})
 r=frank_wolfe({'quadratic':Q.tolist(),'linear':b.tolist(),'tolerance':1e-4})
 assert r['objective']==pytest.approx(oracle.fun,abs=1e-4)
 assert r['duality_gap']<=1e-4
 assert r['converged']


def test_dual_decomposition_solves_coupling_instead_of_labeling_residuals():
 r=dual_decomposition({'quadratic':[[2,0],[0,4]],'linear':[3,-1],'equality_total':1})
 assert r['converged'] and r['iterations']>=2
 assert r['solution']==pytest.approx([4/3,-1/3],abs=1e-6)
 assert r['coupling_residual_norm']<1e-7 and r['duality_gap']<1e-7
 assert r['dual_multipliers']==pytest.approx([1/3])


@pytest.mark.parametrize('solver',[coordinate_descent,proximal_gradient,frank_wolfe])
def test_invalid_nonconvex_problem_rejected(solver):
 with pytest.raises(ValueError):solver({'quadratic':[[-1]],'linear':[1]})


def test_decomposition_rejects_coupled_and_singular_blocks():
 for Q in [[[2,1],[1,2]],[[0,0],[0,2]]]:
  with pytest.raises(ValueError):dual_decomposition({'quadratic':Q,'linear':[1,2],'equality_total':1})


@pytest.mark.parametrize('solver',[coordinate_descent,proximal_gradient,frank_wolfe])
def test_iteration_limit_remains_unconverged(solver):
 r=solver({'quadratic':[[3,1,0],[1,2,.1],[0,.1,1]],'linear':[1,1,1],'initial':[.2,.3,.5],'l1_penalty':.3,'max_iterations':1,'tolerance':1e-14})
 assert not r['converged'] and r['status']=='iteration_limit'
