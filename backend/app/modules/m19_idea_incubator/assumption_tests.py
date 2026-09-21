"""Rank assumption tests by expected information gain per unit cost."""
from __future__ import annotations
from math import log2
from typing import Any

def _entropy(p:float)->float:
 if p in {0,1}:return 0.0
 return -p*log2(p)-(1-p)*log2(1-p)
def rank_assumption_tests(assumptions:list[dict[str,Any]],tests:list[dict[str,Any]],budget:float=0)->dict[str,Any]:
 if budget<0:raise ValueError('budget cannot be negative')
 by={str(a.get('id','')):a for a in assumptions};ranked=[]
 for t in tests:
  aid=str(t.get('assumption_id',''));a=by.get(aid)
  if not a:raise ValueError(f'unknown assumption_id: {aid}')
  prior=float(a.get('probability_true',.5));positive=float(t.get('positive_result_probability',.5));posterior_pos=float(t.get('posterior_if_positive',prior));posterior_neg=float(t.get('posterior_if_negative',prior));cost=float(t.get('cost',0));hours=float(t.get('hours',0))
  if not all(0<=x<=1 for x in (prior,positive,posterior_pos,posterior_neg)):raise ValueError('probabilities must be between 0 and 1')
  if cost<0 or hours<0:raise ValueError('cost and hours cannot be negative')
  gain=max(0,_entropy(prior)-(positive*_entropy(posterior_pos)+(1-positive)*_entropy(posterior_neg)))
  burden=cost+max(hours,0.25);score=gain/burden
  ranked.append({'test_id':str(t.get('id','')),'assumption_id':aid,'assumption':str(a.get('statement','')),'expected_information_bits':round(gain,6),'cost':cost,'hours':hours,'information_per_burden':round(score,6),'within_budget':cost<=budget,'method':str(t.get('method','')),'success_metric':str(t.get('success_metric',''))})
 ranked.sort(key=lambda x:(not x['within_budget'],-x['information_per_burden'],x['cost'],x['test_id']))
 remaining=budget;selected=[]
 for item in ranked:
  if item['cost']<=remaining:selected.append(item['test_id']);remaining-=item['cost']
 return {'ranked_tests':ranked,'selected_within_budget':selected,'unallocated_budget':round(remaining,2),'boundary':'Scores prioritize learning, not business success. Priors and posteriors are caller-supplied assumptions.'}
