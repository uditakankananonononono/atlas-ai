"""Finite zero-order Sugeno fuzzy rules over supplied membership grades.

Degrees of membership are not probabilities or independently verified truth.
Weighted consequents compute one scalar output, with no-rule firing explicit.
"""
from __future__ import annotations
import math
from .measured_learning import text


def infer(p):
    memberships=p.get('memberships');rules=p.get('fuzzy_rules')
    if not isinstance(memberships,dict) or not memberships or len(memberships)>100:raise ValueError('1..100 explicit membership grades required')
    for name,value in memberships.items():
        text(name,'membership name')
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('finite nonboolean membership grades in [0,1] required')
    if not isinstance(rules,list) or not 1<=len(rules)<=100:raise ValueError('1..100 explicit fuzzy_rules required')
    def grade(expression,depth=0):
        if depth>12:raise ValueError('fuzzy expression depth exceeds12')
        if isinstance(expression,str):
            if expression not in memberships:raise ValueError('unknown membership atom')
            return memberships[expression]
        if not isinstance(expression,dict) or len(expression)!=1:raise ValueError('one fuzzy operator required')
        op,args=next(iter(expression.items()))
        if op=='not':return 1-grade(args,depth+1)
        if op not in ('and','or') or not isinstance(args,list) or not 1<=len(args)<=20:raise ValueError('and/or requires1..20 expressions')
        values=[grade(arg,depth+1) for arg in args]
        return min(values) if op=='and' else max(values)
    seen=set();trace=[];weighted=0.;total=0.
    for rule in rules:
        ident=text(rule.get('id'),'rule id');consequence=rule.get('consequent');weight=rule.get('weight',1.)
        if ident in seen or type(consequence) not in (int,float) or not math.isfinite(consequence):raise ValueError('unique rule ids and finite numerical consequents required')
        if type(weight) not in (int,float) or not math.isfinite(weight) or not 0<=weight<=1:raise ValueError('rule weight in [0,1] required')
        seen.add(ident);activation=grade(rule.get('if'));strength=activation*weight
        weighted+=strength*consequence;total+=strength
        trace.append({'id':ident,'antecedent_grade':activation,'weight':weight,'firing_strength':strength,'consequent':consequence,'weighted_contribution':strength*consequence})
    if not math.isfinite(weighted) or not math.isfinite(total):raise ValueError('fuzzy aggregation overflow')
    return {'memberships':memberships,'rules':trace,'total_firing_strength':total,'output':weighted/total if total>0 else None,
            'status':'computed' if total>0 else 'no_firing_rule','and_operator':'minimum','or_operator':'maximum','not_operator':'one minus membership',
            'boundary':'Actual zero-order Sugeno weighted-average consequent inference with min/max/one-minus antecedents. Memberships and rule consequents supplied, not learned, verified or calibrated probabilities. No output invented when no rule fires; no fuzzy-control deployment or causal/truth guarantee.'}
