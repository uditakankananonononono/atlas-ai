"""Finite boolean conjunction induction from labeled observed examples.

Enumerates a bounded declared hypothesis class, preserving its version space.
No copied caller pattern or claim of universal real-world generalization.
"""
from __future__ import annotations
import itertools
from .measured_learning import text


def induce(p):
    features=p.get('features');records=p.get('induction_observations')
    if not isinstance(features,list) or not 1<=len(features)<=8 or any(not isinstance(f,str) or not f for f in features) or len(set(features))!=len(features):raise ValueError('1..8 unique boolean feature names required')
    if not isinstance(records,list) or not records or len(records)>1000:raise ValueError('1..1000 evidence-linked induction_observations required')
    def values(v):
        if not isinstance(v,dict) or set(v)!=set(features) or any(type(x) is not bool for x in v.values()):raise ValueError('complete declared boolean feature vector required')
        return tuple(v[f] for f in features)
    seen=set();observed=[]
    for row in records:
        ev=text(row.get('evidence_id'),'observation evidence')
        if ev in seen or type(row.get('label')) is not bool:raise ValueError('unique evidence and boolean label required')
        seen.add(ev);observed.append((values(row.get('features')),row['label']))
    # -1 excludes a literal; 0 requires false; 1 requires true.
    def predicts(h,v):return all(required==-1 or bool(required)==x for required,x in zip(h,v))
    consistent=[];best_error=len(observed)+1;best=[]
    for h in itertools.product((-1,0,1),repeat=len(features)):
        error=sum(predicts(h,v)!=label for v,label in observed)
        if error==0:consistent.append(h)
        if error<best_error:best_error=error;best=[h]
        elif error==best_error:best.append(h)
    def literals(h):return {f:bool(x) for f,x in zip(features,h) if x!=-1}
    minimum=min((sum(x!=-1 for x in h) for h in consistent),default=None)
    simple=[h for h in consistent if sum(x!=-1 for x in h)==minimum]
    targets=p.get('induction_targets',[])
    if not isinstance(targets,list) or len(targets)>1000:raise ValueError('bounded induction_targets list required')
    def votes(v):
        counts={'false':0,'true':0};witnesses={}
        for h in consistent:
            label=str(predicts(h,v)).lower()
            counts[label]+=1
            witnesses.setdefault(label,literals(h))
        return counts,witnesses
    predictions=[];target_ids=set()
    for target in targets:
        ident=text(target.get('id'),'target id');v=values(target.get('features'))
        if ident in target_ids:raise ValueError('unique target ids required')
        target_ids.add(ident);answers={predicts(h,v) for h in consistent}
        counts,witnesses=votes(v)
        predictions.append({'label_hypothesis_counts':counts,'disagreement_witnesses':witnesses if len(answers)>1 else {},'id':ident,'possible_labels':sorted(answers),'label':next(iter(answers)) if len(answers)==1 else None,
                            'status':'agreed_within_hypothesis_class' if len(answers)==1 else 'ambiguous' if answers else 'inconsistent_evidence'})
    observed_vectors={v for v,label in observed};next_query=None;best_split=0
    # Exact minimax split over all unobserved complete Boolean assignments.
    # Votes count distinct hypotheses, not calibrated label probabilities.
    for v in itertools.product((False,True),repeat=len(features)):
        if v in observed_vectors:continue
        counts,_=votes(v);split=min(counts.values())
        if split>best_split:
            best_split=split
            next_query={'features':dict(zip(features,v)),
                        'label_hypothesis_counts':counts,
                        'worst_case_remaining_hypotheses':max(counts.values()),
                        'guaranteed_eliminated_hypotheses':split}
    return {'next_query':next_query,
            'query_selection_status':'inconsistent_evidence' if not consistent else 'discriminating_query_available' if next_query else 'no_discriminating_query',
            'query_candidates_evaluated':2**len(features)-len(observed_vectors),
            'query_selection_rule':'exact minimum worst-case remaining hypothesis count; lexicographic false-before-true tie break; hypothesis counts are not probabilities',
            'hypothesis_class':'conjunctions of included/negated boolean literals including empty true conjunction',
            'hypotheses_evaluated':3**len(features),'consistent_hypothesis_count':len(consistent),
            'simplest_consistent_rules':[literals(h) for h in simple], 'minimum_literal_count':minimum,
            'minimum_training_errors':best_error,'observed_count':len(observed),'predictions':predictions,
            'status':'consistent' if consistent else 'no_consistent_conjunction',
            'boundary':'Actual finite conjunction version-space search from supplied labeled evidence. Exact training consistency is not real-world truth or future accuracy. Null predictions preserve disagreement/inconsistent evidence; rule simplicity is a declared selection convention, not learned probability. Caller pattern/strength ignored.'}
