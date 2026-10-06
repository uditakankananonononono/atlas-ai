"""Actual LP-backed iterative algorithms, each with an explicit problem class."""
from __future__ import annotations
import heapq
import itertools
import numpy as np
from scipy.optimize import linprog
from .convex_solvers import problem


def linear_problem(p):
    try:
        c=np.asarray(p['objective'],dtype=float)
        A=np.asarray(p['constraint_matrix'],dtype=float)
        b=np.asarray(p['bounds'],dtype=float)
    except (KeyError,ValueError,TypeError) as exc:raise ValueError('objective, constraint_matrix and bounds required') from exc
    if c.ndim!=1 or not c.size or A.ndim!=2 or A.shape!=(b.size,c.size) or b.ndim!=1 or not all(np.isfinite(v).all() for v in (c,A,b)):
        raise ValueError('finite matching linear dimensions required')
    if p.get('constraint_sense',['<=']*b.size)!=['<=']*b.size:raise ValueError('only <= constraints supported by binary branch and bound')
    return c,A,b


def branch_and_bound(p):
    """Minimize a linear objective over binary variables with A*x<=b."""
    c,A,b=linear_problem(p)
    limit=p.get('max_nodes',10000)
    if type(limit) is not int or not 1<=limit<=100000:raise ValueError('max_nodes must be integer in [1,100000]')
    serial=itertools.count();pending=[(-float('inf'),next(serial),[(0.,1.)]*c.size)]
    best=float('inf');solution=None;history=[];visited=0
    while pending and visited<limit:
        inherited,_,bounds=heapq.heappop(pending);visited+=1
        if inherited>=best-1e-9:
            history.append({'node':visited,'status':'pruned_bound','lower_bound':inherited});continue
        relaxation=linprog(c,A_ub=A,b_ub=b,bounds=bounds,method='highs')
        if relaxation.status==2:
            history.append({'node':visited,'status':'pruned_infeasible'});continue
        if not relaxation.success:raise ValueError('LP relaxation failed: '+relaxation.message)
        value=float(relaxation.fun)
        if value>=best-1e-9:
            history.append({'node':visited,'status':'pruned_bound','lower_bound':value});continue
        fractional=np.flatnonzero(np.abs(relaxation.x-np.round(relaxation.x))>1e-8)
        if not fractional.size:
            solution=np.round(relaxation.x);best=float(c@solution)
            history.append({'node':visited,'status':'incumbent','objective':best});continue
        j=int(fractional[np.argmax(np.minimum(relaxation.x[fractional],1-relaxation.x[fractional]))])
        history.append({'node':visited,'status':'branched','coordinate':j,'lower_bound':value})
        for fixed in (0.,1.):
            child=bounds.copy();child[j]=(fixed,fixed)
            heapq.heappush(pending,(value,next(serial),child))
    done=not pending
    bound=min((v[0] for v in pending),default=best)
    return {'solution':solution.tolist() if solution is not None else None,'objective':best if solution is not None else None,
            'status':('optimal' if solution is not None else 'infeasible') if done else 'node_limit',
            'converged':done,'nodes':visited,'history':history,'lower_bound':bound if np.isfinite(bound) else None,
            'absolute_gap':max(0.,best-bound) if solution is not None and np.isfinite(bound) else None,
            'uncertainty':{'solver_executed':True,'scope':'binary linear minimization with <= constraints only'}}


def cutting_planes(p):
    """Kelley lower-approximation cuts for convex quadratic on a bounded box."""
    Q,b,x,tol,limit=problem(p)
    box=np.asarray(p['box_bounds'],dtype=float)
    if box.shape!=(b.size,2) or not np.isfinite(box).all() or np.any(box[:,0]>=box[:,1]):raise ValueError('finite nonempty box bounds required')
    if 'initial' not in p:x=box.mean(axis=1)
    if np.any(x<box[:,0]) or np.any(x>box[:,1]):raise ValueError('initial must lie in box')
    objective=lambda v:float(.5*v@Q@v-b@v)
    cuts=[];right=[];history=[];upper=objective(x);best=x.copy();converged=False
    for iteration in range(1,limit+1):
        fx=objective(x);gradient=Q@x-b
        cuts.append([*gradient.tolist(),-1.]);right.append(float(gradient@x-fx))
        master=linprog([0.]*b.size+[1.],A_ub=cuts,b_ub=right,bounds=[tuple(v) for v in box]+[(None,None)],method='highs')
        if not master.success:raise ValueError('cutting-plane master failed: '+master.message)
        lower=float(master.fun);x=master.x[:-1];fx=objective(x)
        if fx<upper:upper=fx;best=x.copy()
        gap=max(0.,upper-lower)
        history.append({'iteration':iteration,'lower_bound':lower,'upper_bound':upper,'gap':gap,'cuts':len(cuts)})
        if gap<=tol:converged=True;break
    return {'solution':best.tolist(),'objective':upper,'lower_bound':lower,'duality_gap':gap,'iterations':iteration,
            'converged':converged,'status':'converged' if converged else 'iteration_limit','history':history,'cut_added':bool(cuts),
            'uncertainty':{'solver_executed':True,'scope':'Kelley cutting planes for convex quadratic on bounded box'}}


def column_generation(p):
    """Restricted master and exact pricing over caller-supplied finite catalog.

    Minimize c*x subject to A*x=b, x>=0. Catalog columns may be numerous;
    this implementation scans the explicit catalog rather than claiming an
    implicit combinatorial pricing oracle or inventing new columns.
    """
    try:
        c=np.asarray(p['objective'],dtype=float);A=np.asarray(p['constraint_matrix'],dtype=float);b=np.asarray(p['bounds'],dtype=float)
        active=list(p['initial_columns']);tol=float(p.get('tolerance',1e-8));limit=p.get('max_iterations',1000)
    except (ValueError,TypeError,KeyError) as exc:raise ValueError('explicit column catalog and initial_columns required') from exc
    if (c.ndim!=1 or not c.size or A.ndim!=2 or b.ndim!=1 or not b.size or A.shape!=(b.size,c.size)
        or not all(np.isfinite(v).all() for v in (c,A,b)) or not np.isfinite(tol) or tol<=0
        or not active or len(set(active))!=len(active) or any(type(v) is not int or not 0<=v<c.size for v in active)
        or type(limit) is not int or not 1<=limit<=100000):raise ValueError('invalid finite catalog, active columns, tolerance or iteration limit')
    history=[];converged=False
    for iteration in range(1,limit+1):
        master=linprog(c[active],A_eq=A[:,active],b_eq=b,bounds=(0,None),method='highs')
        if not master.success:raise ValueError('initial/restricted master must be feasible and bounded: '+master.message)
        dual=master.eqlin.marginals;reduced=c-A.T@dual
        candidates=[j for j in range(c.size) if j not in active]
        entering=min(candidates,key=lambda j:reduced[j]) if candidates else None
        history.append({'iteration':iteration,'active_columns':active.copy(),'objective':float(master.fun),
                        'entering_column':entering,'minimum_reduced_cost':float(reduced[entering]) if entering is not None else 0.})
        if entering is None or reduced[entering]>=-tol:converged=True;break
        if iteration<limit:active.append(entering)
    solution=np.zeros(c.size);solution[active]=master.x
    return {'solution':solution.tolist(),'objective':float(master.fun),'iterations':iteration,'converged':converged,
            'status':'optimal' if converged else 'iteration_limit','history':history,'reduced_costs':reduced.tolist(),
            'entering_column':entering,'equality_residual':float(np.linalg.norm(A@solution-b)),
            'uncertainty':{'solver_executed':True,'scope':'finite explicit column catalog, feasible initial restricted master, nonnegative equality-form LP'}}


def benders(p):
    """Continuous two-stage LP with complete simple recourse.

    min c*x+q*y; box-bounded x, y>=h-T*x and y>=0, q>=0.
    The master chooses x and recourse lower bound. Exact LP duals produce
    optimality cuts. Complete recourse means no feasibility-cut claim.
    """
    try:
        c=np.asarray(p['first_stage_cost'],dtype=float);q=np.asarray(p['recourse_cost'],dtype=float)
        T=np.asarray(p['recourse_matrix'],dtype=float);h=np.asarray(p['recourse_rhs'],dtype=float)
        box=np.asarray(p['box_bounds'],dtype=float);tol=float(p.get('tolerance',1e-7));limit=p.get('max_iterations',1000)
    except (KeyError,ValueError,TypeError) as exc:raise ValueError('two-stage cost, recourse and box arrays required') from exc
    if (c.ndim!=1 or q.ndim!=1 or not c.size or not q.size or h.shape!=q.shape or T.shape!=(q.size,c.size)
        or box.shape!=(c.size,2) or np.any(box[:,0]>=box[:,1]) or np.any(q<0)
        or not all(np.isfinite(v).all() for v in (c,q,T,h,box)) or not np.isfinite(tol) or tol<=0
        or type(limit) is not int or not 1<=limit<=100000):raise ValueError('invalid finite two-stage dimensions, costs, box or iteration controls')
    cuts=[];rhs=[];history=[];upper=float('inf');solution=None;recourse=None;converged=False
    for iteration in range(1,limit+1):
        master=linprog([*c,1.],A_ub=cuts or None,b_ub=rhs or None,bounds=[tuple(v) for v in box]+[(0,None)],method='highs')
        if not master.success:raise ValueError('Benders master failed: '+master.message)
        x=master.x[:-1];lower=float(master.fun)
        residual=h-T@x
        sub=linprog(q,A_ub=-np.eye(q.size),b_ub=-residual,bounds=(0,None),method='highs')
        if not sub.success:raise ValueError('Benders recourse failed: '+sub.message)
        value=float(c@x+sub.fun)
        if value<upper:upper=value;solution=x.copy();recourse=sub.x.copy()
        gap=max(0.,upper-lower)
        pi=-sub.ineqlin.marginals;gradient=-T.T@pi
        history.append({'iteration':iteration,'lower_bound':lower,'upper_bound':upper,'gap':gap,'dual_recourse':pi.tolist(),'cut_gradient':gradient.tolist()})
        if gap<=tol:converged=True;break
        cuts.append([*gradient,-1.]);rhs.append(float(gradient@x-sub.fun))
    return {'solution':solution.tolist(),'recourse_solution':recourse.tolist(),'objective':upper,'lower_bound':lower,
            'duality_gap':gap,'iterations':iteration,'converged':converged,'status':'optimal' if converged else 'iteration_limit',
            'history':history,'cut_type':'optimality','uncertainty':{'solver_executed':True,'scope':'continuous box-bounded first stage, complete nonnegative simple linear recourse only'}}


def lagrangian_binary_knapsack(p):
    """Exact scalar Lagrangian dual of binary single-capacity minimization.

    Each lambda makes binary coordinates independent. The dual is concave
    piecewise linear; every slope breakpoint is evaluated, not a pretend
    multiplier update. The dual can have an integrality gap; it is never
    advertised as solving the primal integer problem when that gap remains.
    """
    try:
        c=np.asarray(p['objective'],dtype=float);w=np.asarray(p['weights'],dtype=float);capacity=float(p['capacity'])
    except (KeyError,TypeError,ValueError) as exc:raise ValueError('objective, positive weights and capacity required') from exc
    if (c.ndim!=1 or not c.size or w.shape!=c.shape or not np.isfinite(c).all() or not np.isfinite(w).all()
        or np.any(w<=0) or not np.isfinite(capacity) or capacity<0):raise ValueError('finite matching costs, positive weights and nonnegative capacity required')
    candidates=sorted({0.,*(float(-cost/weight) for cost,weight in zip(c,w) if cost<0)})
    history=[];lower=-float('inf');best_lambda=0.;upper=0.;best=np.zeros(c.size)
    for multiplier in candidates:
        adjusted=c+multiplier*w
        x=(adjusted<0).astype(float)
        value=float(np.minimum(adjusted,0).sum()-multiplier*capacity)
        if value>lower:lower=value;best_lambda=multiplier
        for trial in (x,(adjusted<=0).astype(float)):
            if w@trial<=capacity+1e-9 and c@trial<upper:best=trial.copy();upper=float(c@trial)
        history.append({'multiplier':multiplier,'dual_bound':value,'relaxed_solution':x.tolist(),'capacity_residual':float(w@x-capacity)})
    gap=max(0.,upper-lower)
    return {'solution':best.tolist(),'objective':upper,'lower_bound':lower,'duality_gap':gap,'multiplier':best_lambda,
            'dual_optimal':True,'primal_optimal':gap<=1e-8,'status':'optimal' if gap<=1e-8 else 'dual_optimal_primal_gap',
            'history':history,'lagrangian_value':lower,'uncertainty':{'solver_executed':True,'scope':'exact scalar dual for binary single positive-capacity constraint; primal candidate only when gap remains'}}


def fractional_linear(p):
    """Dinkelbach iterations for maximum linear ratio on a finite box + Ax<=b.

    The denominator is proven strictly positive by a separate LP before any
    division. Each iteration solves the full parametric LP, not a residual
    over an arbitrary caller-supplied point. Unbounded/nonpositive rejects.
    """
    try:
        numerator=np.asarray(p['numerator'],dtype=float);denominator=np.asarray(p['denominator_coefficients'],dtype=float)
        n0=float(p.get('numerator_constant',0));d0=float(p['denominator_constant'])
        box=np.asarray(p['box_bounds'],dtype=float);tol=float(p.get('tolerance',1e-8));limit=p.get('max_iterations',1000)
    except (KeyError,ValueError,TypeError) as exc:raise ValueError('numerator, denominator and box arrays required') from exc
    n=numerator.size
    if (numerator.ndim!=1 or not n or denominator.shape!=numerator.shape or box.shape!=(n,2) or np.any(box[:,0]>box[:,1])
        or not all(np.isfinite(v).all() for v in (numerator,denominator,box)) or not np.isfinite([n0,d0,tol]).all()
        or tol<=0 or type(limit) is not int or not 1<=limit<=100000):raise ValueError('invalid finite fractional dimensions, box and controls')
    A=p.get('fractional_constraints');b=p.get('fractional_bounds')
    if (A is None)!=(b is None):raise ValueError('fractional constraint matrix and bounds must occur together')
    if A is not None:
        A=np.asarray(A,dtype=float);b=np.asarray(b,dtype=float)
        if A.ndim!=2 or b.ndim!=1 or A.shape!=(b.size,n) or not np.isfinite(A).all() or not np.isfinite(b).all():raise ValueError('invalid fractional constraints')
    bounds=[tuple(row) for row in box]
    check=linprog(denominator,A_ub=A,b_ub=b,bounds=bounds,method='highs')
    if not check.success:raise ValueError('fractional feasible domain cannot be established: '+check.message)
    minimum_denominator=float(check.fun+d0)
    if minimum_denominator<=0:raise ValueError('denominator must be strictly positive over entire feasible domain')
    parameter=0.;history=[];converged=False
    for iteration in range(1,limit+1):
        sub=linprog(-(numerator-parameter*denominator),A_ub=A,b_ub=b,bounds=bounds,method='highs')
        if not sub.success:raise ValueError('fractional parametric LP failed: '+sub.message)
        x=sub.x;top=float(numerator@x+n0);bottom=float(denominator@x+d0)
        residual=top-parameter*bottom;ratio=top/bottom
        history.append({'iteration':iteration,'parameter':parameter,'ratio':ratio,'dinkelbach_residual':residual,'solution':x.tolist()})
        if abs(residual)<=tol:converged=True;break
        parameter=ratio
    return {'solution':x.tolist(),'objective':ratio,'ratio':ratio,'dinkelbach_residual':residual,'converged':converged,
            'status':'optimal' if converged else 'iteration_limit','iterations':iteration,'history':history,'minimum_denominator':minimum_denominator,
            'uncertainty':{'solver_executed':True,'scope':'linear fractional maximization on bounded linear feasible set with globally positive denominator'}}
