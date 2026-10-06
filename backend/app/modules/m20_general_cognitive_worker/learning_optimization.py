"""Observed-data learning and finite hierarchical optimization.

No generated observations. Replay tests are fixtures, not production data.
Each learning update records the observation evidence id and pre-update state.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import linprog
from .conic_solvers import finite


def bilevel(p):
    """Exact enumeration of finite leader choices, LP follower, optimistic tie.

    Each leader choice specifies follower objective and constraints, plus the
    leader's affine payoff of the follower decision. A second LP selects the
    leader-minimizing response among exactly follower-optimal ties. Not a
    general continuous/nonconvex bilevel solver.
    """
    choices=p.get('leader_choices')
    if not isinstance(choices,list) or not choices:raise ValueError('nonempty explicit leader_choices required')
    ids=set();history=[];best=None
    for choice in choices:
        ident=choice.get('id')
        if not isinstance(ident,str) or not ident or ident in ids:raise ValueError('leader choice ids must be nonempty and unique')
        ids.add(ident)
        f=finite(choice['follower_cost'],'follower_cost',1)
        leader=finite(choice['leader_response_cost'],'leader_response_cost',1)
        box=finite(choice['follower_bounds'],'follower_bounds',2)
        constant=float(choice.get('leader_constant',0))
        if leader.shape!=f.shape or box.shape!=(f.size,2) or np.any(box[:,0]>box[:,1]) or not np.isfinite(constant):raise ValueError('matching finite follower dimensions required')
        A=choice.get('follower_constraints');b=choice.get('follower_rhs')
        if (A is None)!=(b is None):raise ValueError('follower matrix and rhs required together')
        if A is not None:
            A=finite(A,'follower_constraints',2);b=finite(b,'follower_rhs',1)
            if A.shape!=(b.size,f.size):raise ValueError('follower constraint dimensions differ')
        bounds=[tuple(v) for v in box]
        follower=linprog(f,A_ub=A,b_ub=b,bounds=bounds,method='highs')
        if follower.status==2:
            history.append({'id':ident,'status':'infeasible_follower'});continue
        if not follower.success:raise ValueError('follower LP failed: '+follower.message)
        tie=linprog(leader,A_ub=A,b_ub=b,A_eq=[f.tolist()],b_eq=[float(follower.fun)],bounds=bounds,method='highs')
        if not tie.success:raise ValueError('follower optimal-response LP failed: '+tie.message)
        value=float(leader@tie.x+constant)
        row={'id':ident,'status':'evaluated','follower_solution':tie.x.tolist(),'follower_optimum':float(follower.fun),
             'follower_optimality_residual':float(abs(f@tie.x-follower.fun)),'leader_value':value}
        history.append(row)
        if best is None or value<best['leader_value']:best=row
    return {'selected_choice':best['id'] if best else None,'solution':best['follower_solution'] if best else None,
            'objective':best['leader_value'] if best else None,'status':'optimal' if best else 'infeasible',
            'converged':True,'history':history,'tie_rule':'optimistic exact follower-optimal response, then input order for leader ties',
            'uncertainty':{'solver_executed':True,'scope':'finite explicit leader catalog with bounded affine LP followers and affine leader objective'}}


def observed_records(p):
    records=p.get('observations')
    if not isinstance(records,list) or not records:raise ValueError('nonempty evidence-linked observations required')
    seen=set()
    for row in records:
        ident=row.get('evidence_id') if isinstance(row,dict) else None
        if not isinstance(ident,str) or not ident or ident in seen:raise ValueError('observation evidence ids must be unique and nonempty')
        seen.add(ident)
    return records


def stochastic_approximation(p):
    """Robbins-Monro for the mean root E[Y]-theta=0, alpha_t=1/t.

    The production input is actual caller observations, never random noise
    synthesized to make the algorithm look effective. Empirical variance
    describes the observed sample, not a calibrated population uncertainty.
    """
    rows=observed_records(p)
    estimate=None;history=[];mean=None;m2=None
    for t,row in enumerate(rows,1):
        value=finite(row['value'],'observation value',1)
        if estimate is None:estimate=np.zeros_like(value);mean=np.zeros_like(value);m2=np.zeros_like(value)
        if value.shape!=estimate.shape:raise ValueError('observed value dimensions must remain constant')
        previous=estimate.copy();step=1/t
        estimate+=step*(value-estimate)
        delta=value-mean;mean+=delta/t;m2+=delta*(value-mean)
        history.append({'evidence_id':row['evidence_id'],'step':step,'previous':previous.tolist(),'innovation':(value-previous).tolist(),'estimate':estimate.tolist()})
    return {'estimate':estimate.tolist(),'observations':len(rows),'sample_variance':(m2/(len(rows)-1)).tolist() if len(rows)>1 else None,
            'history':history,'uncertainty':{'solver_executed':True,'scope':'Robbins-Monro observed-vector mean root with 1/t schedule; no claim of arbitrary stochastic function optimization or independent sample provenance validation'}}


def online_regression(p):
    """Prequential online gradient descent for observed squared-loss stream."""
    rows=observed_records(p);weights=finite(p['initial_weights'],'initial_weights',1)
    rate=float(p.get('learning_rate',.1))
    if not np.isfinite(rate) or rate<=0:raise ValueError('learning_rate must be positive finite')
    history=[];total=0.
    for t,row in enumerate(rows,1):
        x=finite(row['features'],'features',1);target=float(row['target'])
        if x.shape!=weights.shape or not np.isfinite(target):raise ValueError('finite matching stream dimensions required')
        prediction=float(weights@x);error=prediction-target;loss=.5*error**2;total+=loss
        step=rate/np.sqrt(t);weights-=step*error*x
        if not np.isfinite(weights).all():raise ValueError('online update diverged to nonfinite weights')
        history.append({'evidence_id':row['evidence_id'],'prediction_before_update':prediction,'target':target,'loss':loss,'step':float(step),'weights_after_update':weights.tolist()})
    return {'weights':weights.tolist(),'cumulative_loss':total,'observations':len(rows),'history':history,
            'uncertainty':{'solver_executed':True,'scope':'prequential linear squared-loss gradient learning on observed stream; no future accuracy guarantee'}}
