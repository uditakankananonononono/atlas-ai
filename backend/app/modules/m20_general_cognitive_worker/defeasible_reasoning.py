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


def closure(facts,program,*,metrics=None):
    """Indexed forward agenda preserving ordered-sweep first derivations."""
    import heapq
    known=set(facts);trace=[];watchers={};missing=[];agenda=[]
    counts={'premise_notifications':0,'rules_processed':0}
    for i,rule in enumerate(program):
        missing.append(len(rule['if']))
        for atom in rule['if']:watchers.setdefault(atom,[]).append(i)
        if not rule['if']:heapq.heappush(agenda,(0,i))
    def notify(atom,turn,index):
        for i in watchers.get(atom,[]):
            counts['premise_notifications']+=1;missing[i]-=1
            if missing[i]==0:heapq.heappush(agenda,(turn if i>index else turn+1,i))
    for atom in sorted(known):notify(atom,0,-1)
    while agenda:
        turn,i=heapq.heappop(agenda);counts['rules_processed']+=1;rule=program[i]
        if rule['then'] in known:continue
        known.add(rule['then']);trace.append({'rule':rule['id'],'fact':rule['then']})
        notify(rule['then'],turn,i)
    if metrics is not None:metrics.update(counts)
    return known,trace


def stable_models(facts,program):
    atoms=set(facts)
    for rule in program:atoms|={rule['then']}|rule['if']|rule['unless']
    optional=sorted(atoms-set(facts))
    if len(optional)>12:raise ValueError('stable model search supports at most12 optional atoms')
    models=[];witnesses=[]
    for bits in itertools.product([False,True],repeat=len(optional)):
        candidate=set(facts)|{atom for atom,bit in zip(optional,bits) if bit}
        reduct=[rule for rule in program if not rule['unless']&candidate]
        least,trace=closure(facts,reduct)
        if candidate==least:
            models.append(sorted(candidate))
            witnesses.append({'model':sorted(candidate),'supplied_facts':sorted(facts),'derived_trace':trace,
                              'defeated_rules':[{'rule_id':rule['id'],'blocking_atoms':sorted(rule['unless']&candidate)} for rule in program if rule['unless']&candidate]})
    cautious=set.intersection(*(set(m) for m in models)) if models else set()
    possible=set.union(*(set(m) for m in models)) if models else set()
    return {'model_witnesses':witnesses,'stable_models':models,'model_count':len(models),'cautious_conclusions':sorted(cautious),'possible_conclusions':sorted(possible),
            'ambiguous_conclusions':sorted(possible-cautious),'consistent':bool(models)}


def default_inference(p):
    facts=labels(p.get('facts',[]),'facts');program=rules(p['defaults'])
    before=stable_models(facts,program)
    added=labels(p.get('added_facts',[]),'added_facts');removed=labels(p.get('removed_facts',[]),'removed_facts')
    if not removed<=facts:raise ValueError('removed facts must be present in original facts')
    after=stable_models((facts-removed)|added,program)
    old=set(before['cautious_conclusions']);new=set(after['cautious_conclusions'])
    queries=[]
    for atom in sorted(labels(p.get('query_atoms',[]),'query_atoms')):
        support=next((model for model in after['stable_models'] if atom in model),None)
        counter=next((model for model in after['stable_models'] if atom not in model),None)
        possible=support is not None if after['consistent'] else None
        cautious=atom in new if after['consistent'] else None
        status='inconsistent_program' if not after['consistent'] else 'cautiously_entailed' if cautious else 'ambiguous' if possible else 'not_entailed'
        queries.append({'atom':atom,'status':status,'possible':possible,'cautious':cautious,
                        'supporting_model':support,'countermodel':counter,'not_entailed_does_not_mean_false':True})
    return {**after,'queries':queries,'before':before,'retracted_conclusions':sorted(old-new),'new_conclusions':sorted(new-old),
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
    minimal=[]; evaluated=0; skipped=0
    # Cardinality order makes every proper subset available before its supersets.
    # A superset of any valid explanation cannot be inclusion-minimal, even
    # when additional hypotheses would derive a forbidden atom.
    for size in range(len(choices)+1):
        for indices in itertools.combinations(range(len(choices)),size):
            selected=[choices[i][0] for i in indices]; selected_set=set(selected)
            if any(set(row['hypotheses']) <= selected_set for row in minimal):
                skipped+=1;continue
            known,trace=closure(facts|selected_set,program);evaluated+=1
            if observations<=known and not forbidden&known:
                try:cost=math.fsum(choices[i][1] for i in indices)
                except OverflowError as exc:raise ValueError('hypothesis cost overflow') from exc
                if not math.isfinite(cost):raise ValueError('hypothesis cost overflow')
                minimal.append({'hypotheses':selected,'cost':cost,'derived_facts':sorted(known),'proof_trace':trace})
    minimal.sort(key=lambda r:(r['cost'],len(r['hypotheses']),r['hypotheses']))
    best=min((r['cost'] for r in minimal),default=None)
    probes=sorted(labels(p.get('probe_atoms',[]),'probe_atoms'))
    if len(probes)>1000:raise ValueError('at most1000 supplied probe atoms')
    results=[];next_probe=None;best_split=0
    for atom in probes:
        entailed=[i for i,row in enumerate(minimal) if atom in row['derived_facts']]
        unsupported=[i for i,row in enumerate(minimal) if atom not in row['derived_facts']]
        item={'atom':atom,'entailed_explanation_indices':entailed,
              'not_entailed_explanation_indices':unsupported,
              'entailed_explanation_count':len(entailed),
              'not_entailed_explanation_count':len(unsupported),
              'worst_case_remaining_explanations':max(len(entailed),len(unsupported)),
              'not_entailed_is_not_predicted_false':True}
        results.append(item);split=min(len(entailed),len(unsupported))
        if split>best_split:best_split=split;next_probe=item
    return {'probe_results':results,'next_probe':next_probe,
            'probe_status':'no_explanations' if not minimal else 'discriminating_probe_available' if next_probe else 'no_discriminating_probe',
            'probe_boundary':'Exact formal entailment partition over all inclusion-minimal explanations, not probabilities or real-world predictions. Unsupported is not false; a real observation cannot automatically eliminate unsupported explanations without an additional closed-world/measurement model. No evidence acquisition or action.',
            'subsets_evaluated':evaluated,'nonminimal_supersets_skipped':skipped,'explanations':minimal,'best_explanations':[r for r in minimal if r['cost']==best],'explanation_count':len(minimal),
            'best_explanation_is_not_proof':True,'boundary':'Exact finite minimum-cost symbolic Horn abduction from explicit hypotheses and observations. Costs are supplied, not inferred prior probabilities. Logical explanation does not establish truth.'}
