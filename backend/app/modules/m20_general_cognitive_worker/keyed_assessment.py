"""Exact answer-key assessment with observed per-objective scores.

No essay grading, psychometric validity, learned misconception diagnosis or
independent evidence verification. Keys/weights/thresholds are explicit inputs.
"""
from __future__ import annotations
import math
from .measured_learning import text,normalized

PURPOSE={829:'feedback during learning',830:'judgment after instruction',831:'prerequisite and misconception diagnosis'}


def assess(row,p):
    items=p.get('assessment_items');answers=p.get('assessment_responses')
    if not isinstance(items,list) or not items or not isinstance(answers,list):raise ValueError('explicit assessment_items and assessment_responses required')
    cutoff=p.get('needs_threshold',.7)
    if type(cutoff) not in (int,float) or not math.isfinite(cutoff) or not 0<=cutoff<=1:raise ValueError('needs_threshold must be finite in [0,1]')
    catalog={};groups={}
    for item in items:
        ident=text(item.get('id'),'item id');objective=text(item.get('objective_id'),'objective id');keys=item.get('accepted_answers');weight=item.get('points',1)
        if ident in catalog or not isinstance(keys,list) or not keys:raise ValueError('unique keyed assessment items required')
        if type(weight) not in (int,float) or not math.isfinite(weight) or not 0<weight<=10000:raise ValueError('positive finite item points <=10000 required')
        catalog[ident]={'id':ident,'objective_id':objective,'keys':[normalized(k) for k in keys],'points':weight}
        group=groups.setdefault(objective,{'possible_points':0.,'earned_points':0.,'answered_points':0.,'items':0,'answered':0});group['possible_points']+=weight;group['items']+=1
    seen=set();results=[];responded=set()
    for answer in answers:
        ev=text(answer.get('evidence_id'),'response evidence id');ident=answer.get('item_id')
        if ev in seen or ident not in catalog or ident in responded:raise ValueError('unique evidence and one response per known item required')
        seen.add(ev);responded.add(ident);item=catalog[ident];correct=normalized(answer.get('response')) in item['keys'];earned=item['points'] if correct else 0.
        group=groups[item['objective_id']];group['earned_points']+=earned;group['answered_points']+=item['points'];group['answered']+=1
        result={'item_id':ident,'evidence_id':ev,'objective_id':item['objective_id'],'correct':correct,'earned_points':earned,'possible_points':item['points']}
        if row==829:result['feedback']={'accepted_answers':item['keys'],'next_step':'review this objective and retry' if not correct else 'continue practice'}
        results.append(result)
    objective_scores=[]
    for objective,g in sorted(groups.items()):
        score=g['earned_points']/g['answered_points'] if g['answered_points'] else None
        objective_scores.append({'objective_id':objective,**g,'observed_score':score,'coverage':g['answered']/g['items'],
                                 'needs_review':score<cutoff if score is not None else None})
    complete=len(responded)==len(catalog);earned=sum(r['earned_points'] for r in results);possible=sum(i['points'] for i in catalog.values());answered=sum(r['possible_points'] for r in results)
    out={'purpose':PURPOSE[row],'items':results,'objective_scores':objective_scores,'missing_item_ids':[ident for ident in catalog if ident not in responded],
         'complete':complete,'earned_points':earned,'possible_points':possible,'observed_score':earned/answered if answered else None,
         'final_score':earned/possible if complete else None,'needs_threshold':cutoff,'alignment_to_objective':True,
         'consequence':'revise teaching and learner next step' if row!=830 else 'report achievement with rubric and uncertainty',
         'boundary':'Exact normalized keyed grading only. Caller keys, responses, evidence identifiers, weights and thresholds are not independently verified. Missing responses are unknown, not wrong or mastered. No semantic essay grading, pass/fail award, test validity or inferred misconception claim.'}
    if row==831:out['needs']=[r['objective_id'] for r in objective_scores if r['needs_review'] is True];out['unassessed_objectives']=[r['objective_id'] for r in objective_scores if r['observed_score'] is None]
    return out
