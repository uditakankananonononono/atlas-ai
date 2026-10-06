"""Explicit finite-domain constraint model enumeration with query entailment.

No copied predictions. This is bounded model checking, not scientific model
learning, natural-language reasoning or independent verification of premises.
"""
from __future__ import annotations
import itertools
import math


def models(p):
    domains=p.get('model_domains');constraints=p.get('model_constraints');queries=p.get('model_queries',[])
    if not isinstance(domains,dict) or not 1<=len(domains)<=10 or not isinstance(constraints,list) or len(constraints)>100:raise ValueError('explicit bounded model_domains/model_constraints required')
    size=1
    for key,values in domains.items():
        if not isinstance(key,str) or not key or not isinstance(values,list) or not values or len(values)>20:raise ValueError('nonempty named finite domains required')
        if any(type(v) not in (bool,int,float,str) or (type(v) is float and not math.isfinite(v)) for v in values):raise ValueError('finite scalar domain values required')
        if len(set((type(v),v) for v in values))!=len(values):raise ValueError('duplicate typed domain values rejected')
        size*=len(values)
    if size>65536:raise ValueError('finite model Cartesian product exceeds65536')
    if not isinstance(queries,list) or len(queries)>100:raise ValueError('bounded model_queries required')
    def compile_test(c):
        if not isinstance(c,dict):raise ValueError('constraint must be object')
        left=c.get('left');op=c.get('operator');right=c.get('right')
        if left not in domains or op not in ('eq','ne','lt','le','gt','ge'):raise ValueError('declared left variable and supported comparison required')
        if not isinstance(right,dict) or len(right)!=1 or next(iter(right)) not in ('variable','value'):raise ValueError('right must explicitly name variable or literal value')
        if 'variable' in right and right['variable'] not in domains:raise ValueError('unknown right variable')
        if 'value' in right and (type(right['value']) not in (bool,int,float,str) or (type(right['value']) is float and not math.isfinite(right['value']))):raise ValueError('finite literal required')
        def check(m):
            a=m[left];b=m[right['variable']] if 'variable' in right else right['value']
            if op in ('eq','ne'):
                equal=type(a) is type(b) and a==b
                return equal if op=='eq' else not equal
            if type(a) not in (int,float) or type(b) not in (int,float):raise ValueError('ordered comparisons require nonboolean numerical operands')
            return {'lt':a<b,'le':a<=b,'gt':a>b,'ge':a>=b}[op]
        return check
    predicates=[compile_test(c) for c in constraints];tests=[compile_test(q) for q in queries];names=list(domains);feasible=[]
    for values in itertools.product(*(domains[k] for k in names)):
        m=dict(zip(names,values))
        if all(test(m) for test in predicates):feasible.append(m)
    answers=[]
    for query,test in zip(queries,tests):
        good=[m for m in feasible if test(m)];bad=[m for m in feasible if not test(m)]
        answers.append({'query':query,'entailed':not bad if feasible else None,'possible':bool(good) if feasible else None,
                        'countermodel':bad[0] if bad else None,'supporting_model':good[0] if good else None})
    return {'status':'satisfiable' if feasible else 'inconsistent','assignments_evaluated':size,'feasible_model_count':len(feasible),
            'example_model':feasible[0] if feasible else None,'possible_values':{k:[v for v in domains[k] if any(type(m[k]) is type(v) and m[k]==v for m in feasible)] for k in names},'queries':answers,
            'boundary':'Exact finite-domain constraint enumeration. Queries checked over all supplied models; inconsistency yields unknown entailment, not false real-world certainty. Premises/domains are caller assumptions, not learned/verified. No continuous simulation or natural-language scientific model inference.'}
