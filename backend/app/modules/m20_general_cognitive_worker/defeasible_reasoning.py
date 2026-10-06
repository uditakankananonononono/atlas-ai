"""Finite logic-program stable models and exact abductive hypothesis search.

No natural-language explanation generator or invented truth claims. Negation
is explicit absence in a stable model, not inferred real-world falsehood.
"""
from __future__ import annotations
import itertools
import math


def labels(value,name):
    if not isinstance(value,list) or any(not isinstance(v,str) or not v for v in value):raise ValueError(name+' must contain nonempty symbolic atoms')
    return set(value)


def rules(value):
    if not isinstance(value,list) or not value:raise ValueError('nonempty symbolic rules required')
    result=[];ids=set()
    for i,row in enumerate(value):
        if not isinstance(row,dict) or not isinstance(row.get('then'),str) or not row['then']:raise ValueError('each rule needs a conclusion atom')
        ident=row.get('id',str(i))
        if not isinstance(ident,str) or not ident or ident in ids:raise ValueError('rule ids must be unique nonempty strings')
        ids.add(ident)
        result.append({'id':ident,'then':row['then'],'if':labels(row.get('if',[]),'if'),'unless':labels(row.get('unless',[]),'unless')})
    return result


def closure(facts,program):
    known=set(facts);trace=[];changed=True
    while changed:
        changed=False
        for rule in program:
            if rule['if']<=known and rule['then'] not in known:
                known.add(rule['then']);trace.append({'rule':rule['id'],'fact':rule['then']});changed=True
    return known,trace


def stable_models(facts,program):
    atoms=set(facts)
    for rule in program:atoms|={rule['then']}|rule['if']|rule['unless']
    optional=sorted(atoms-set(facts))
    if len(optional)>12:raise ValueError('stable model search supports at most12 optional atoms')
    models=[]
    for bits in itertools.product([False,True],repeat=len(optional)):
        candidate=set(facts)|{atom for atom,bit in zip(optional,bits) if bit}
        reduct=[rule for rule in program if not rule['unless']&candidate]
        least,_=closure(facts,reduct)
        if candidate==least:models.append(sorted(candidate))
    cautious=set.intersection(*(set(m) for m in models)) if models else set()
    possible=set.union(*(set(m) for m in models)) if models else set()
    return {'stable_models':models,'model_count':len(models),'cautious_conclusions':sorted(cautious),'possible_conclusions':sorted(possible),
            'ambiguous_conclusions':sorted(possible-cautious),'consistent':bool(models)}


def default_inference(p):
    facts=labels(p.get('facts',[]),'facts');program=rules(p['defaults'])
    before=stable_models(facts,program)
    added=labels(p.get('added_facts',[]),'added_facts');removed=labels(p.get('removed_facts',[]),'removed_facts')
    if not removed<=facts:raise ValueError('removed facts must be present in original facts')
    after=stable_models((facts-removed)|added,program)
    old=set(before['cautious_conclusions']);new=set(after['cautious_conclusions'])
    return {**after,'before':before,'retracted_conclusions':sorted(old-new),'new_conclusions':sorted(new-old),
            'beliefs_revisable':True,'boundary':'Exact finite normal logic-program stable models, symbolic Horn rules with unless literals. All alternative stable models preserved; no real-world truth or default-priority claim.'}


def abductive_search(p):
    facts=labels(p.get('facts',[]),'facts');observations=labels(p['observations'],'observations');forbidden=labels(p.get('forbidden',[]),'forbidden')
    if not observations:raise ValueError('observations must be nonempty')
    program=rules(p['rules'])
    if any(rule['unless'] for rule in program):raise ValueError('abduction supports positive Horn rules only')
    hypotheses=p.get('hypotheses')
    if not isinstance(hypotheses,list) or not hypotheses or len(hypotheses)>16:raise ValueError('1..16 explicit hypotheses required')
    choices=[];names=set()
    for row in hypotheses:
        atom=row.get('atom');cost=row.get('cost')
        if not isinstance(atom,str) or not atom or atom in names or isinstance(cost,bool) or not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<0:raise ValueError('unique named hypotheses with finite nonnegative cost required')
        names.add(atom);choices.append((atom,float(cost)))
    valid=[]
    for bits in itertools.product([False,True],repeat=len(choices)):
        selected=[atom for (atom,cost),bit in zip(choices,bits) if bit]
        known,trace=closure(facts|set(selected),program)
        if observations<=known and not forbidden&known:
            valid.append({'hypotheses':selected,'cost':sum(cost for (_,cost),bit in zip(choices,bits) if bit),'derived_facts':sorted(known),'proof_trace':trace})
    # Inclusion-minimal explanations; retain tied alternatives, not arbitrary prose.
    minimal=[r for r in valid if not any(set(s['hypotheses'])<set(r['hypotheses']) for s in valid)]
    minimal.sort(key=lambda r:(r['cost'],len(r['hypotheses']),r['hypotheses']))
    best=min((r['cost'] for r in minimal),default=None)
    return {'explanations':minimal,'best_explanations':[r for r in minimal if r['cost']==best],'explanation_count':len(minimal),
            'best_explanation_is_not_proof':True,'boundary':'Exact finite minimum-cost symbolic Horn abduction from explicit hypotheses and observations. Costs are supplied, not inferred prior probabilities. Logical explanation does not establish truth.'}
