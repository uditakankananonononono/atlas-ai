"""Real free conic optimization through CVXPY/SCS with explicit certificates.

No claim of implementing a new interior-point method. This loads and runs
an open-source numerical solver for the stated mathematical program.
"""
from __future__ import annotations
import numpy as np
import cvxpy as cp


def finite(value,name,ndim=None):
    try:a=np.asarray(value,dtype=float)
    except (ValueError,TypeError) as exc:raise ValueError(f'{name} must be numeric') from exc
    if not np.isfinite(a).all() or not a.size or (ndim is not None and a.ndim!=ndim):raise ValueError(f'{name} must have finite nonempty dimensions')
    return a


def symmetric(value,name):
    a=finite(value,name,2)
    if a.shape[0]!=a.shape[1] or not np.allclose(a,a.T,rtol=0,atol=1e-12):raise ValueError(f'{name} must be symmetric square')
    return a


def controls(p):
    tol=float(p.get('tolerance',1e-6));limit=p.get('max_iterations',10000)
    if not np.isfinite(tol) or tol<=0 or type(limit) is not int or not 1<=limit<=1000000:raise ValueError('invalid tolerance or iteration limit')
    return tol,limit


def solve(problem,variable,p,scope):
    tol,limit=controls(p)
    try:problem.solve(solver='SCS',eps=tol,max_iters=limit,verbose=False)
    except cp.error.SolverError as exc:raise ValueError('conic solver failed: '+str(exc)) from exc
    info=(problem.solver_stats.extra_stats or {}).get('info',{})
    has_solution=variable.value is not None and np.isfinite(variable.value).all()
    return {'solution':variable.value.tolist() if has_solution else None,
            'objective':float(problem.value) if problem.value is not None and np.isfinite(problem.value) else None,
            'status':problem.status,'converged':problem.status==cp.OPTIMAL,
            'iterations':problem.solver_stats.num_iters,'solver':'SCS',
            'primal_residual':float(info['res_pri']) if info.get('res_pri') is not None and np.isfinite(info['res_pri']) else None,
            'dual_residual':float(info['res_dual']) if info.get('res_dual') is not None and np.isfinite(info['res_dual']) else None,
            'duality_gap':float(info['gap']) if info.get('gap') is not None and np.isfinite(info['gap']) else None,
            'uncertainty':{'solver_executed':True,'scope':scope,'numerical_tolerance':tol}}


def semidefinite(p):
    """min trace(C*X), X PSD, trace(A_i*X)=b_i."""
    C=symmetric(p['matrix_objective'],'matrix_objective')
    matrices=[symmetric(v,'equality_matrix') for v in p['equality_matrices']]
    rhs=finite(p['equality_rhs'],'equality_rhs',1)
    if len(matrices)!=rhs.size or any(v.shape!=C.shape for v in matrices):raise ValueError('SDP equality dimensions differ')
    X=cp.Variable(C.shape,symmetric=True)
    equalities=[cp.sum(cp.multiply(A,X))==b for A,b in zip(matrices,rhs)]
    cone=X>>0
    prog=cp.Problem(cp.Minimize(cp.sum(cp.multiply(C,X))),[cone,*equalities])
    r=solve(prog,X,p,'linear objective over positive-semidefinite matrix with affine equality constraints')
    if r['solution'] is not None:
        value=np.array(r['solution'])
        r['minimum_eigenvalue']=float(np.linalg.eigvalsh(value).min())
        r['equality_residual']=float(max(abs(np.sum(A*value)-b) for A,b in zip(matrices,rhs)))
    else:r['minimum_eigenvalue']=None;r['equality_residual']=None
    return r


def second_order(p):
    """min c*x with ||A_i*x+b_i||_2 <= d_i*x+e_i, box bounds."""
    c=finite(p['objective'],'objective',1);n=c.size
    box=finite(p['box_bounds'],'box_bounds',2)
    if box.shape!=(n,2) or np.any(box[:,0]>box[:,1]):raise ValueError('box dimensions differ')
    x=cp.Variable(n);constraints=[x>=box[:,0],x<=box[:,1]];specs=[]
    if not isinstance(p.get('cones'),list) or not p['cones']:raise ValueError('nonempty cones required')
    for cone in p['cones']:
        A=finite(cone['matrix'],'cone matrix',2);b=finite(cone['offset'],'cone offset',1);d=finite(cone['axis'],'cone axis',1);e=float(cone['constant'])
        if A.shape!=(b.size,n) or d.shape!=(n,) or not np.isfinite(e):raise ValueError('cone dimensions differ')
        constraints.append(cp.SOC(d@x+e,A@x+b));specs.append((A,b,d,e))
    r=solve(cp.Problem(cp.Minimize(c@x),constraints),x,p,'affine second-order cone constraints and finite box with linear objective')
    if r['solution'] is not None:
        value=np.array(r['solution']);r['cone_slack']=float(min(d@value+e-np.linalg.norm(A@value+b) for A,b,d,e in specs))
        r['box_violation']=float(max(0,np.max(box[:,0]-value),np.max(value-box[:,1])))
    else:r['cone_slack']=None;r['box_violation']=None
    return r


def geometric(p):
    """Posynomial minimization under posynomial <=1 and positive box bounds.

    Monomial term = coefficient * product_j(x_j**exponent_j), coefficient>0.
    Uses CVXPY's explicit log-log convex transformation, not a log label.
    """
    box=finite(p['box_bounds'],'positive box bounds',2)
    if box.shape[1]!=2 or np.any(box<=0) or np.any(box[:,0]>=box[:,1]):raise ValueError('strictly positive nonempty box required')
    n=box.shape[0];x=cp.Variable(n,pos=True)
    def posynomial(terms):
        if not isinstance(terms,list) or not terms:raise ValueError('posynomial must contain monomial terms')
        expressions=[]
        for term in terms:
            coefficient=float(term['coefficient']);exponents=finite(term['exponents'],'monomial exponents',1)
            if coefficient<=0 or not np.isfinite(coefficient) or exponents.size!=n:raise ValueError('positive coefficients and matching exponents required')
            monomial=cp.Constant(coefficient)
            for j,e in enumerate(exponents):monomial*=cp.power(x[j],float(e))
            expressions.append(monomial)
        return sum(expressions)
    objective=posynomial(p['posynomial_objective'])
    restrictions=p.get('posynomial_constraints',[])
    if not isinstance(restrictions,list):raise ValueError('posynomial_constraints must be a list')
    expressions=[posynomial(terms) for terms in restrictions]
    prog=cp.Problem(cp.Minimize(objective),[x>=box[:,0],x<=box[:,1],*(e<=1 for e in expressions)])
    if not prog.is_dgp():raise ValueError('program does not satisfy geometric convexity rules')
    tol,limit=controls(p)
    try:prog.solve(gp=True,solver='SCS',eps=tol,max_iters=limit,verbose=False)
    except cp.error.SolverError as exc:raise ValueError('geometric solver failed: '+str(exc)) from exc
    value=x.value
    success=value is not None and np.isfinite(value).all()
    return {'solution':value.tolist() if success else None,'objective':float(prog.value) if prog.value is not None and np.isfinite(prog.value) else None,
            'status':prog.status,'converged':prog.status==cp.OPTIMAL,'solver':'SCS','iterations':prog.solver_stats.num_iters,
            'constraint_violation':float(max([0.,*(float(e.value)-1 for e in expressions),*list(box[:,0]-value),*list(value-box[:,1])])) if success else None,
            'uncertainty':{'solver_executed':True,'scope':'positive posynomial objective and <=1 posynomial constraints, finite strictly positive box; log-log convex transformation'}}
