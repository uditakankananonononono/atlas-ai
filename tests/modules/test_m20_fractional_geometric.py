import numpy as np
import pytest
from app.modules.m20_general_cognitive_worker.conic_solvers import geometric
from app.modules.m20_general_cognitive_worker.lp_solvers import fractional_linear


def test_geometric_program_minimizes_positive_posynomial_not_just_logs():
 p={'box_bounds':[[.1,10]],'posynomial_objective':[{'coefficient':1,'exponents':[1]},{'coefficient':1,'exponents':[-1]}]}
 r=geometric(p)
 assert r['converged'] and r['solution']==pytest.approx([1],abs=1e-5)
 assert r['objective']==pytest.approx(2,abs=1e-5)


def test_geometric_constraint_changes_optimum_and_is_verified():
 p={'box_bounds':[[.1,10]],'posynomial_objective':[{'coefficient':1,'exponents':[1]},{'coefficient':1,'exponents':[-1]}],
    'posynomial_constraints':[[{'coefficient':2,'exponents':[-1]}]]}
 r=geometric(p)
 assert r['converged'] and r['solution']==pytest.approx([2],abs=1e-4)
 assert r['objective']==pytest.approx(2.5,abs=1e-4) and r['constraint_violation']<1e-5


def test_nonpositive_geometric_coefficient_rejected():
 with pytest.raises(ValueError):geometric({'box_bounds':[[.1,10]],'posynomial_objective':[{'coefficient':-1,'exponents':[1]}]})


def test_dinkelbach_reaches_known_maximum_and_solves_more_than_one_subproblem():
 r=fractional_linear({'numerator':[2],'denominator_coefficients':[1],'denominator_constant':1,'box_bounds':[[0,2]]})
 assert r['converged'] and r['solution']==[2.] and r['objective']==pytest.approx(4/3)
 assert r['iterations']>=2 and abs(r['dinkelbach_residual'])<1e-8


def test_fractional_two_dimensional_maximum_matches_vertex_enumeration():
 p={'numerator':[2,1],'numerator_constant':1,'denominator_coefficients':[1,2],'denominator_constant':1,
    'box_bounds':[[0,2],[0,2]],'fractional_constraints':[[1,1]],'fractional_bounds':[2]}
 ratios=[(np.dot(p['numerator'],x)+1)/(np.dot(p['denominator_coefficients'],x)+1) for x in [[0,0],[2,0],[0,2]]]
 r=fractional_linear(p)
 assert r['converged'] and r['ratio']==pytest.approx(max(ratios))
 assert r['solution']==pytest.approx([2,0])


def test_denominator_positive_only_at_one_point_is_insufficient():
 with pytest.raises(ValueError,match='entire feasible domain'):
  fractional_linear({'numerator':[1],'denominator_coefficients':[1],'denominator_constant':-.5,'box_bounds':[[0,2]]})


def test_fractional_iteration_cap_never_claims_optimality():
 r=fractional_linear({'numerator':[2],'denominator_coefficients':[1],'denominator_constant':1,'box_bounds':[[0,2]],'max_iterations':1})
 assert not r['converged'] and r['status']=='iteration_limit'
