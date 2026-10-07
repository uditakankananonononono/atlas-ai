"""Bounded 2D axis-order spatial constraints with LP counterexamples.

Explicit caller frame/boxes/relations only, not vision, maps or physical geometry.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import linprog
from .conic_solvers import finite
from .measured_learning import text

DIRECTIONS={'east':(0,1),'west':(0,-1),'north':(1,1),'south':(1,-1)}


def solve_spatial(p):
    objects=p.get('spatial_objects');relations=p.get('spatial_relations');frame=text(p.get('frame_of_reference'),'frame_of_reference')
    if not isinstance(objects,list) or not 1<=len(objects)<=64 or not isinstance(relations,list) or len(relations)>1000:raise ValueError('1..64 bounded spatial_objects and <=1000 spatial_relations required')
    ids=[];bounds=[]
    for obj in objects:
        ident=text(obj.get('id'),'object id');box=finite(obj.get('bounds'),'2D bounds',2)
        if ident in ids or box.shape!=(2,2) or np.any(box[:,0]>box[:,1]):raise ValueError('unique objects with finite x/y bounds required')
        ids.append(ident);bounds.extend(map(tuple,box));
    def expression(rel):
        source=rel.get('subject');target=rel.get('reference');direction=rel.get('direction');gap=rel.get('minimum_gap',0.)
        if source not in ids or target not in ids or source==target or direction not in DIRECTIONS:raise ValueError('known distinct objects and east/west/north/south required')
        if type(gap) not in (int,float) or not np.isfinite(gap) or gap<0:raise ValueError('finite nonnegative minimum_gap required')
        axis,sign=DIRECTIONS[direction];v=np.zeros(2*len(ids));v[2*ids.index(source)+axis]=sign;v[2*ids.index(target)+axis]=-sign
        return v,float(gap)
    max_checks=p.get('conflict_max_checks',64)
    if type(max_checks) is not int or not 1<=max_checks<=256:raise ValueError('conflict_max_checks must be integer1..256')
    rows=[expression(rel) for rel in relations];A=np.array([-v for v,g in rows]) if rows else None;b=np.array([-g for v,g in rows]) if rows else None
    feasible=linprog(np.zeros(len(bounds)),A_ub=A,b_ub=b,bounds=bounds,method='highs')
    def point(x):return {ident:{'x':float(x[2*i]),'y':float(x[2*i+1])} for i,ident in enumerate(ids)}
    if feasible.status==2:
        # Flatten relations and each individual box bound for source-linked
        # deletion checks. Irreducible is not minimum cardinality.
        constraints=[(-v,-g,{'source':'relation','relation_index':i,'relation':relations[i]}) for i,(v,g) in enumerate(rows)]
        for i,(lower,upper) in enumerate(bounds):
            axis='x' if i%2==0 else 'y';ident=ids[i//2]
            unit=np.zeros(len(bounds));unit[i]=1
            constraints.append((unit.copy(),upper,{'source':'box','object_id':ident,'axis':axis,'bound':'upper','value':upper}))
            constraints.append((-unit.copy(),-lower,{'source':'box','object_id':ident,'axis':axis,'bound':'lower','value':lower}))
        retained=list(range(len(constraints)));checks=1;cursor=0;solver_failed=False
        while cursor<len(retained) and checks<max_checks:
            candidate=retained[:cursor]+retained[cursor+1:]
            selected=[constraints[i] for i in candidate]
            result=linprog(np.zeros(len(bounds)),A_ub=np.array([v for v,g,meta in selected]) if selected else None,
                           b_ub=np.array([g for v,g,meta in selected]) if selected else None,
                           bounds=[(None,None)]*len(bounds),method='highs')
            checks+=1
            if result.status==2:retained=candidate
            elif result.success or result.status==3:cursor+=1
            else:solver_failed=True;break
        irreducible=cursor==len(retained) and not solver_failed
        witness={'constraints':[constraints[i][2] for i in retained],
                 'verified_infeasible':True,'irreducible':irreducible,'minimum_cardinality':False,
                 'solver_checks':checks,'stopped_by':'irreducible' if irreducible else 'solver_failure' if solver_failed else 'check_budget'}
        return {'status':'inconsistent','layout':None,'queries':[],'conflict_witness':witness,'frame_of_reference':frame,
                'boundary':'Bounded deletion-derived infeasible subset of supplied axis-order and individual box bounds. LP status confirms infeasibility; irreducible only when every retained deletion was checked, never minimum cardinality or real-world source verification.'}
    if not feasible.success:raise ValueError('spatial feasibility solver failed')
    queries=p.get('spatial_queries',[])
    if not isinstance(queries,list) or len(queries)>100:raise ValueError('<=100 spatial_queries required')
    results=[]
    for query in queries:
        v,gap=expression(query);low=linprog(v,A_ub=A,b_ub=b,bounds=bounds,method='highs');high=linprog(-v,A_ub=A,b_ub=b,bounds=bounds,method='highs')
        if not low.success or not high.success:raise ValueError('spatial query LP failed')
        minimum=float(v@low.x);maximum=float(v@high.x);guaranteed=minimum>=gap-1e-8;possible=maximum>=gap-1e-8
        results.append({'query':query,'minimum_signed_separation':minimum,'maximum_signed_separation':maximum,'guaranteed':guaranteed,'possible':possible,
                        'counterexample':None if guaranteed else point(low.x),'supporting_layout':point(high.x) if possible else None})
    return {'status':'feasible','conflict_witness':None,'layout':point(feasible.x),'queries':results,'frame_of_reference':frame,
            'boundary':'Actual LP feasibility/entailment over finite supplied 2D boxes and non-strict axis-order inequalities. Numerical tolerance1e-8. Layout is a witness, not uniquely located objects. No vision, distance/rotation geometry, real-world location or verified frame/relations claim.'}
