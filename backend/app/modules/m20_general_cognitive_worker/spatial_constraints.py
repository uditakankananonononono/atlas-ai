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
    rows=[expression(rel) for rel in relations];A=np.array([-v for v,g in rows]) if rows else None;b=np.array([-g for v,g in rows]) if rows else None
    feasible=linprog(np.zeros(len(bounds)),A_ub=A,b_ub=b,bounds=bounds,method='highs')
    def point(x):return {ident:{'x':float(x[2*i]),'y':float(x[2*i+1])} for i,ident in enumerate(ids)}
    if feasible.status==2:return {'status':'inconsistent','layout':None,'queries':[],'frame_of_reference':frame,'boundary':'No layout satisfies supplied axis-order constraints and boxes. Inconsistency is not silently dropped.'}
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
    return {'status':'feasible','layout':point(feasible.x),'queries':results,'frame_of_reference':frame,
            'boundary':'Actual LP feasibility/entailment over finite supplied 2D boxes and non-strict axis-order inequalities. Numerical tolerance1e-8. Layout is a witness, not uniquely located objects. No vision, distance/rotation geometry, real-world location or verified frame/relations claim.'}
