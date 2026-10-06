import numpy as np
import pytest
from app.modules.m20_general_cognitive_worker.conic_solvers import semidefinite, second_order


def test_sdp_optimizes_psd_matrix_to_analytic_minimum_eigenvalue():
 C=np.array([[2.,1.],[1.,2.]])
 r=semidefinite({'matrix_objective':C.tolist(),'equality_matrices':[np.eye(2).tolist()],'equality_rhs':[1]})
 assert r['converged'] and r['solver']=='SCS'
 assert r['objective']==pytest.approx(np.linalg.eigvalsh(C).min(),abs=1e-5)
 assert r['minimum_eigenvalue']>=-1e-5 and r['equality_residual']<1e-5
 assert r['solution'][0][1]==pytest.approx(-.5,abs=1e-5)
 assert abs(r['duality_gap'])<1e-5


def test_sdp_detects_infeasibility_not_false_matrix_optimization():
 r=semidefinite({'matrix_objective':[[1]],'equality_matrices':[[[1]]],'equality_rhs':[-1]})
 assert r['status']=='infeasible' and not r['converged'] and r['solution'] is None


def test_sdp_rejects_nonsymmetric_matrix():
 with pytest.raises(ValueError):semidefinite({'matrix_objective':[[1,2],[0,1]],'equality_matrices':[[[1,0],[0,1]]],'equality_rhs':[1]})


def test_socp_disk_optimum_matches_cauchy_schwarz_closed_form():
 r=second_order({'objective':[-3,-4],'box_bounds':[[-2,2],[-2,2]],'cones':[{'matrix':[[1,0],[0,1]],'offset':[0,0],'axis':[0,0],'constant':1}]})
 assert r['converged'] and r['solution']==pytest.approx([.6,.8],abs=1e-5)
 assert r['objective']==pytest.approx(-5,abs=1e-5) and r['cone_slack']>=-1e-5
 assert r['box_violation']<1e-6


def test_socp_infeasibility_cannot_be_presented_as_valid_solution():
 r=second_order({'objective':[1],'box_bounds':[[2,3]],'cones':[{'matrix':[[1]],'offset':[0],'axis':[0],'constant':1}]})
 assert r['status']=='infeasible' and not r['converged'] and r['solution'] is None


def test_conic_iteration_limit_does_not_promote_inaccurate_result():
 r=semidefinite({'matrix_objective':[[2,1],[1,2]],'equality_matrices':[[[1,0],[0,1]]],'equality_rhs':[1],'max_iterations':1})
 assert not r['converged'] and r['status']!='optimal'
