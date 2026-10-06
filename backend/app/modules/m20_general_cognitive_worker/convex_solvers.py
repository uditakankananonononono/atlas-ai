"""Iterative convex solvers with explicit restricted problem classes and certificates."""
from __future__ import annotations
from typing import Any
import numpy as np


def problem(p: dict[str, Any]):
    try:
        Q=np.asarray(p['quadratic'],dtype=float);b=np.asarray(p['linear'],dtype=float)
        tolerance=float(p.get('tolerance',1e-7));limit=p.get('max_iterations',10000)
        x=np.asarray(p.get('initial',np.zeros(b.size)),dtype=float)
    except (ValueError,TypeError,KeyError) as exc:
        raise ValueError('quadratic and linear arrays define the problem') from exc
    if (b.ndim!=1 or not b.size or Q.shape!=(b.size,b.size) or x.shape!=b.shape
        or not all(np.isfinite(a).all() for a in (Q,b,x)) or not np.isfinite(tolerance)
        or tolerance<=0 or type(limit) is not int or not 1<=limit<=100000):
        raise ValueError('finite matching dimensions and positive tolerance/iteration limit required')
    if not np.allclose(Q,Q.T,rtol=0,atol=1e-12) or np.linalg.eigvalsh(Q).min()<-1e-10:
        raise ValueError('quadratic must be symmetric positive semidefinite')
    return Q,b,x,tolerance,limit


def penalty_value(p):
    penalty=float(p.get('l1_penalty',0))
    if not np.isfinite(penalty) or penalty<0:raise ValueError('l1_penalty must be finite and nonnegative')
    return penalty


def soft(v,threshold):return np.sign(v)*np.maximum(np.abs(v)-threshold,0)


def kkt_l1(Q,b,x,penalty,tolerance):
    g=Q@x-b
    return float(np.max(np.where(np.abs(x)>tolerance,np.abs(g+penalty*np.sign(x)),np.maximum(np.abs(g)-penalty,0))))


def result(x,Q,b,iteration,converged,history,scope,penalty=0,**certificate):
    return {'solution':x.tolist(),'objective':float(.5*x@Q@x-b@x+penalty*np.abs(x).sum()),
            'iterations':iteration,'converged':converged,'status':'converged' if converged else 'iteration_limit',
            'history':history,'uncertainty':{'solver_executed':True,'scope':scope},**certificate}


def coordinate_descent(p):
    Q,b,x,tol,limit=problem(p);penalty=penalty_value(p)
    if np.any(np.diag(Q)<=0):raise ValueError('coordinate quadratic curvature must be positive')
    history=[];converged=False
    for sweep in range(1,limit+1):
        for j in range(b.size):
            previous=float(x[j]);partial=b[j]-(Q[j]@x-Q[j,j]*x[j])
            x[j]=soft(partial,penalty)/Q[j,j]
            history.append({'sweep':sweep,'coordinate':j,'previous':previous,'next_value':float(x[j])})
        violation=kkt_l1(Q,b,x,penalty,tol)
        if violation<=tol:converged=True;break
    return result(x,Q,b,sweep,converged,history,'cyclic exact coordinate minimization of convex quadratic plus L1',penalty,kkt_violation=violation,selected_coordinate=b.size-1)


def proximal_gradient(p):
    Q,b,x,tol,limit=problem(p);penalty=penalty_value(p)
    lipschitz=float(np.linalg.eigvalsh(Q).max())
    if lipschitz<=0:raise ValueError('positive quadratic curvature required')
    step=1/lipschitz;history=[];converged=False
    for iteration in range(1,limit+1):
        next_x=soft(x-step*(Q@x-b),step*penalty)
        mapping=float(np.linalg.norm((x-next_x)/step))
        x=next_x
        violation=kkt_l1(Q,b,x,penalty,tol)
        history.append({'iteration':iteration,'gradient_mapping_norm':mapping,'kkt_violation':violation,'objective':float(.5*x@Q@x-b@x+penalty*np.abs(x).sum())})
        if violation<=tol:converged=True;break
    return result(x,Q,b,iteration,converged,history,'proximal gradient for convex quadratic plus L1',penalty,kkt_violation=violation,proximal_point=x.tolist(),gradient_mapping_norm=mapping)


def frank_wolfe(p):
    Q,b,x,tol,limit=problem(p)
    if 'initial' not in p:x=np.ones(b.size)/b.size
    if np.any(x<0) or not np.isclose(x.sum(),1,rtol=0,atol=1e-10):raise ValueError('initial must lie on probability simplex')
    history=[];converged=False
    for iteration in range(1,limit+1):
        gradient=Q@x-b;vertex=int(np.argmin(gradient))
        direction=-x.copy();direction[vertex]+=1
        gap=float(-gradient@direction)
        if gap<=tol:converged=True;break
        curvature=float(direction@Q@direction)
        alpha=min(1.,max(0.,gap/curvature)) if curvature>0 else 1.
        x+=alpha*direction
        history.append({'iteration':iteration,'oracle_vertex':vertex,'step_fraction':alpha,'duality_gap':gap})
    gradient=Q@x-b;gap=float(gradient@x-gradient.min())
    converged=gap<=tol
    return result(x,Q,b,iteration,converged,history,'Frank-Wolfe with exact line search on probability simplex',duality_gap=gap,oracle_vertex=int(gradient.argmin()),step_fraction=history[-1]['step_fraction'] if history else 0.)


def dual_decomposition(p):
    """Separable strongly-convex quadratic with a single sum equality.

    Each coordinate is an independent subproblem given a shared multiplier.
    Exact dual curvature gives a stable ascent step; both residual and gap
    certify the equality-constrained solution, including negative optima.
    """
    Q,b,x,tol,limit=problem(p)
    if not np.allclose(Q,np.diag(np.diag(Q)),rtol=0,atol=1e-12) or np.any(np.diag(Q)<=0):
        raise ValueError('dual decomposition requires separable positive diagonal quadratic')
    total=float(p['equality_total'])
    if not np.isfinite(total):raise ValueError('equality_total must be finite')
    diagonal=np.diag(Q);multiplier=0.;step=1/np.sum(1/diagonal)
    history=[];converged=False
    for iteration in range(1,limit+1):
        # Independent block argmins of L(x,lambda).
        x=(b-multiplier)/diagonal
        residual=float(x.sum()-total)
        feasible=x-residual/b.size
        primal=float(.5*feasible@Q@feasible-b@feasible)
        dual=float(-.5*np.sum((b-multiplier)**2/diagonal)-multiplier*total)
        gap=max(0.,primal-dual)
        history.append({'iteration':iteration,'multiplier':float(multiplier),'equality_residual':residual,'primal_feasible_objective':primal,'dual_bound':dual,'duality_gap':gap})
        if abs(residual)<=tol and gap<=tol:converged=True;break
        multiplier+=step*residual
    return result(x,Q,b,iteration,converged,history,'dual decomposition for separable positive quadratic with sum equality',coupling_residual_norm=abs(residual),duality_gap=gap,dual_multipliers=[float(history[-1]['multiplier'])],block_values=(.5*diagonal*x*x-b*x).tolist())
