import pytest
import numpy as np
from scipy.optimize import minimize
from app.modules.m20_general_cognitive_worker.admm import solve_quadratic_l1


def test_admm_reaches_analytic_soft_threshold_optimum_not_single_gradient_step():
    r=solve_quadratic_l1(dict(quadratic=[[2,0],[0,4]],linear=[3,-1],l1_penalty=.5,initial=[20,-40]))
    assert r['converged']
    assert r['solution']==pytest.approx([1.25,-.125],abs=1e-5)
    assert r['iterations']>1
    assert r['kkt_violation']<1e-5


def test_admm_correlated_quadratic_matches_independent_scipy_optimizer():
    Q=np.array([[3.,1.],[1.,2.]])
    b=np.array([2.,-1.])
    objective=lambda x: .5*x@Q@x-b@x+.3*np.abs(x).sum()
    oracle=minimize(objective,[0.,0.],method='Powell',options={'xtol':1e-10,'ftol':1e-10})
    r=solve_quadratic_l1(dict(quadratic=Q.tolist(),linear=b.tolist(),l1_penalty=.3))
    assert r['objective']==pytest.approx(oracle.fun,abs=1e-5)
    assert r['kkt_violation']<1e-5


def test_admm_iteration_limit_does_not_claim_convergence():
    r=solve_quadratic_l1(dict(quadratic=[[1]],linear=[10],l1_penalty=1,max_iterations=1))
    assert not r['converged'] and r['status']=='iteration_limit'


@pytest.mark.parametrize('Q',[[[-1]],[[float('nan')]],[[1,2],[0,1]]])
def test_invalid_nonconvex_nonfinite_nonsymmetric_problems_rejected(Q):
    with pytest.raises(ValueError):solve_quadratic_l1(dict(quadratic=Q,linear=[1]*len(Q),l1_penalty=.2))


def test_admm_is_sensitive_to_observed_problem_not_hardcoded():
    a=solve_quadratic_l1(dict(quadratic=[[1]],linear=[1],l1_penalty=.3))
    b=solve_quadratic_l1(dict(quadratic=[[1]],linear=[4],l1_penalty=.3))
    assert a['solution']==pytest.approx([.7],abs=1e-5)
    assert b['solution']==pytest.approx([3.7],abs=1e-5)
