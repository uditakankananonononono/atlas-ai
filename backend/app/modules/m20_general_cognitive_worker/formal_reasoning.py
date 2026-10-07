"""Restricted formal reasoning with countermodels and explicit structural models.

The code does not infer causality from correlation, validate supplied causal
assumptions, or turn a caller's validity boolean into a proof.
"""
from __future__ import annotations
import itertools
import math


def argument_validity(p):
    premises=p.get('formulas');conclusion=p.get('conclusion')
    if not isinstance(premises,list) or not premises:raise ValueError('nonempty formulas required')
    atoms=set();nodes=0
    def inspect(expr,depth=0):
        nonlocal nodes
        nodes+=1
        if depth>50 or nodes>1000:raise ValueError('formula complexity limit exceeded')
        if isinstance(expr,str) and expr:atoms.add(expr);return
        if type(expr) is bool:return
        if not isinstance(expr,dict) or len(expr)!=1:raise ValueError('formula must be atom, bool or single logical operator')
        op,args=next(iter(expr.items()))
        if op=='not':inspect(args,depth+1);return
        if op not in ('and','or','implies','iff') or not isinstance(args,list) or len(args)!=2:raise ValueError('binary and/or/implies/iff or unary not required')
        for child in args:inspect(child,depth+1)
    for expr in [*premises,conclusion]:inspect(expr)
    if len(atoms)>12:raise ValueError('at most 12 distinct propositional atoms supported')
    def evaluate(expr,values):
        if isinstance(expr,str):return values[expr]
        if type(expr) is bool:return expr
        op,args=next(iter(expr.items()))
        if op=='not':return not evaluate(args,values)
        a,b=(evaluate(child,values) for child in args)
        return {'and':a and b,'or':a or b,'implies':not a or b,'iff':a==b}[op]
    max_checks=p.get('support_max_checks',64)
    if type(max_checks) is not int or not 1<=max_checks<=256:raise ValueError('support_max_checks must be integer1..256')
    satisfying=0;counter=None;premise_models=[]
    premise_masks=[0]*len(premises);conclusion_mask=0;model_count=0
    for bits in itertools.product([False,True],repeat=len(atoms)):
        model=dict(zip(sorted(atoms),bits))
        bit=1<<model_count;model_count+=1
        premise_values=[evaluate(expr,model) for expr in premises]
        for i,value in enumerate(premise_values):
            if value:premise_masks[i]|=bit
        conclusion_value=evaluate(conclusion,model)
        if conclusion_value:conclusion_mask|=bit
        if all(premise_values):
            satisfying+=1
            if len(premise_models)<3:premise_models.append(model)
            if not conclusion_value and counter is None:counter=model
    support=None
    if counter is None:
        full_mask=(1<<model_count)-1
        def models(indices):
            mask=full_mask
            for i in indices:mask&=premise_masks[i]
            return mask
        retained=list(range(len(premises)));cursor=0;checks=1
        while cursor<len(retained) and checks<max_checks:
            candidate=retained[:cursor]+retained[cursor+1:];checks+=1
            if not (models(candidate)&(full_mask^conclusion_mask)):retained=candidate
            else:cursor+=1
        mask=models(retained);irreducible=cursor==len(retained)
        support={'premise_indices':retained,'verified_entailment':True,
                 'premises_satisfiable':bool(mask),'premise_model_count':mask.bit_count(),
                 'kind':'entailing_premise_subset' if mask else 'inconsistent_premise_subset',
                 'irreducible':irreducible,'minimum_cardinality':False,'subset_checks':checks,
                 'stopped_by':'irreducible' if irreducible else 'check_budget'}
    return {'premise_support':support,'validity':counter is None,'premises_satisfiable':satisfying>0,'premise_model_count':satisfying,
            'countermodel':counter,'sample_premise_models':premise_models,'atoms':sorted(atoms),
            'soundness':None,'validity_does_not_establish_premise_truth':True,
            'boundary':'Exhaustive propositional entailment only. Real-world premise truth is unverified; inconsistent premises entail vacuously and are flagged.'}


def structural_model(p):
    equations=p.get('equations')
    if not isinstance(equations,dict) or not equations:raise ValueError('nonempty linear structural equations required')
    def number(value):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('finite numeric structural values required')
        return float(value)
    parsed={}
    for variable,spec in equations.items():
        if not isinstance(variable,str) or not variable or not isinstance(spec,dict):raise ValueError('named equation objects required')
        weights=spec.get('parents',{})
        if not isinstance(weights,dict) or any(parent not in equations for parent in weights):raise ValueError('parents must name known variables')
        parsed[variable]={'intercept':number(spec.get('intercept',0)), 'parents':{k:number(v) for k,v in weights.items()}}
    order=[];active=set();seen=set()
    def visit(variable):
        if variable in active:raise ValueError('causal structural graph must be acyclic')
        if variable in seen:return
        active.add(variable)
        for parent in parsed[variable]['parents']:visit(parent)
        active.remove(variable);seen.add(variable);order.append(variable)
    for variable in parsed:visit(variable)
    def execute(noise,interventions):
        if not isinstance(noise,dict) or not isinstance(interventions,dict) or any(k not in parsed for k in set(noise)|set(interventions)):raise ValueError('noise/interventions must name known variables')
        values={}
        for variable in order:
            spec=parsed[variable]
            values[variable]=number(interventions[variable]) if variable in interventions else spec['intercept']+sum(w*values[k] for k,w in spec['parents'].items())+number(noise.get(variable,0))
            if not math.isfinite(values[variable]):raise ValueError('structural evaluation overflow')
        return values
    return parsed,order,number,execute


def causal_effect(p):
    parsed,order,number,execute=structural_model(p)
    exposure=p.get('exposure');outcome=p.get('outcome')
    if exposure not in parsed or outcome not in parsed:raise ValueError('known exposure and outcome required')
    values=p.get('intervention_values')
    if not isinstance(values,list) or len(values)!=2:raise ValueError('two intervention_values required')
    low,high=map(number,values)
    if low==high:raise ValueError('intervention values must differ')
    noise=p.get('exogenous',{})
    baseline=execute(noise,{exposure:low});changed=execute(noise,{exposure:high})
    return {'exposure':exposure,'outcome':outcome,'interventions':[baseline,changed],
            'effect':changed[outcome]-baseline[outcome],'effect_per_unit':(changed[outcome]-baseline[outcome])/(high-low),
            'topological_order':order,'association_is_not_causation':True,
            'boundary':'Computed do-intervention effect under caller-supplied acyclic linear structural equations. Not causal discovery, not an observed or experimentally identified effect.'}


def counterfactual(p):
    parsed,order,number,execute=structural_model(p)
    factual=p.get('factual');intervention=p.get('intervention')
    if not isinstance(factual,dict) or set(factual)!=set(parsed):raise ValueError('complete factual assignment to all variables required for noise abduction')
    if not isinstance(intervention,dict) or not intervention:raise ValueError('nonempty intervention required')
    observed={k:number(v) for k,v in factual.items()};noise={}
    for variable in order:
        spec=parsed[variable]
        noise[variable]=observed[variable]-spec['intercept']-sum(w*observed[k] for k,w in spec['parents'].items())
    predicted=execute(noise,intervention)
    differences={k:predicted[k]-observed[k] for k in order}
    return {'factual':observed,'abduced_noise':noise,'intervention':intervention,'result':predicted,'differences':differences,
            'held_constant':noise,'changed_variables':[k for k,v in differences.items() if v!=0],
            'boundary':'Abduction, intervention and prediction under supplied acyclic additive linear structural model with fully observed unit. Same exogenous noise held fixed; model truth is unverified.'}
