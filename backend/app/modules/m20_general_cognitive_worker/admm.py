"""ADMM solver for convex quadratic plus L1 regularization.

Minimize 0.5*x.T*Q*x - b.T*x + penalty*||x||_1 by splitting x=z.
No claimed support for arbitrary nonconvex or distributed optimization.
"""
from __future__ import annotations
from typing import Any
import numpy as np


def solve_quadratic_l1(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        Q=np.asarray(payload['quadratic'],dtype=float)
        b=np.asarray(payload['linear'],dtype=float)
        penalty=float(payload['l1_penalty'])
        rho=float(payload.get('rho',1))
        tolerance=float(payload.get('tolerance',1e-7))
        max_iterations=payload.get('max_iterations',1000)
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError('quadratic, linear and l1_penalty define the ADMM problem') from exc
    if (b.ndim!=1 or b.size==0 or Q.shape!=(b.size,b.size)
        or not np.isfinite(Q).all() or not np.isfinite(b).all()
        or not np.isfinite([penalty,rho,tolerance]).all()
        or penalty<0 or rho<=0 or tolerance<=0
        or type(max_iterations) is not int or not 1<=max_iterations<=100000):
        raise ValueError('invalid finite dimensions, penalty, rho, tolerance or iteration limit')
    if not np.allclose(Q,Q.T,rtol=0,atol=1e-12):
        raise ValueError('quadratic must be symmetric')
    if np.linalg.eigvalsh(Q).min() < -1e-10:
        raise ValueError('quadratic must be positive semidefinite')
    z=np.zeros(b.size);u=np.zeros(b.size)
    initial=payload.get('initial',z.tolist())
    x=np.asarray(initial,dtype=float)
    if x.shape!=b.shape or not np.isfinite(x).all():
        raise ValueError('initial must be finite and match linear dimensions')
    z=x.copy()
    # Factor once. Solves the exact quadratic subproblem every iteration.
    chol=np.linalg.cholesky(Q+rho*np.eye(b.size))
    history=[];converged=False
    for iteration in range(1,max_iterations+1):
        rhs=b+rho*(z-u)
        x=np.linalg.solve(chol.T,np.linalg.solve(chol,rhs))
        previous=z.copy()
        v=x+u
        z=np.sign(v)*np.maximum(np.abs(v)-penalty/rho,0)
        u+=x-z
        primal=float(np.linalg.norm(x-z))
        dual=float(rho*np.linalg.norm(z-previous))
        primal_limit=float(np.sqrt(b.size)*tolerance+tolerance*max(np.linalg.norm(x),np.linalg.norm(z)))
        dual_limit=float(np.sqrt(b.size)*tolerance+tolerance*np.linalg.norm(rho*u))
        history.append({'iteration':iteration,'primal_residual':primal,'dual_residual':dual,
                        'primal_limit':primal_limit,'dual_limit':dual_limit})
        if primal<=primal_limit and dual<=dual_limit:
            converged=True;break
    gradient=Q@z-b
    kkt=np.where(np.abs(z)>tolerance,np.abs(gradient+penalty*np.sign(z)),np.maximum(np.abs(gradient)-penalty,0))
    return {'solution':z.tolist(),'objective':float(.5*z@Q@z-b@z+penalty*np.abs(z).sum()),
            'iterations':iteration,'converged':converged,'status':'converged' if converged else 'iteration_limit',
            'kkt_violation':float(kkt.max()),'primal_residual_norm':primal,'dual_residual_norm':dual,
            'rho':rho,'history':history,'uncertainty':{'solver_executed':True,'scope':'convex quadratic plus L1 regularization only'}}
