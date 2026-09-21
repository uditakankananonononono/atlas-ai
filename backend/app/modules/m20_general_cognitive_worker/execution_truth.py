"""Roll up outcome claims without collapsing plans, simulations and observations."""
from __future__ import annotations
from typing import Any
STATES={'planned','simulated','externally_executed','independently_verified'}
ORDER={x:i for i,x in enumerate(('planned','simulated','externally_executed','independently_verified'))}
def execution_truth_ledger(items:list[dict[str,Any]])->dict[str,Any]:
 rows=[];counts={x:0 for x in STATES}
 for item in items:
  state=str(item.get('state',''))
  if state not in STATES:raise ValueError(f'unsupported execution state: {state}')
  evidence=[str(x) for x in item.get('evidence_ids',[]) if str(x)]
  if state in {'externally_executed','independently_verified'} and not evidence:raise ValueError(f'{state} requires evidence_ids')
  if state=='independently_verified' and not item.get('verifier'):raise ValueError('independently_verified requires verifier')
  row={'id':str(item.get('id','')),'claim':str(item.get('claim','')),'state':state,'evidence_ids':evidence,'verifier':item.get('verifier'),'source_module':item.get('source_module')}
  if not row['id'] or not row['claim']:raise ValueError('every ledger item needs id and claim')
  rows.append(row);counts[state]+=1
 if len({x['id'] for x in rows})!=len(rows):raise ValueError('ledger item ids must be unique')
 highest=max((x['state'] for x in rows),key=lambda x:ORDER[x],default=None)
 return {'counts':counts,'highest_observed_state':highest,'items':rows,'verified_fraction':round(counts['independently_verified']/len(rows),4) if rows else 0,'boundary':'Higher state applies only to its own item. Plans and simulations are never promoted by aggregate roll-up.'}
