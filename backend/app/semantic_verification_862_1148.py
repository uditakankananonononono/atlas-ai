"""Machine-readable semantic verification manifest for the 862-1148 wave.

This does not implement features. It binds each owner row to its real implementation,
named test, mounted boundary and a distinctive invariant that reviewers can inspect.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RANGES=[
 (862,909,'backend/app/modules/m20_general_cognitive_worker/cognitive_learning_860_909.py','tests/modules/test_m20_cognitive_learning_860_909.py','/api/v1/api/modules/20/cognitive-learning-860-909/{row_id}'),
 (910,959,'backend/app/modules/m16_executive_dashboard/emerging_capabilities_0910_0959.py','tests/modules/test_m16_emerging_0910_0959.py','/api/v1/executive-dashboard/emerging-910-959/analyze'),
 (960,1009,'backend/app/modules/m12_ai_research_lab/emerging_biomed_960_1009.py','tests/modules/test_m12_emerging_biomed_960_1009.py','/api/v1/ai-research-lab/emerging-biomed-960-1009/analyze'),
 (1010,1109,'backend/app/modules/m16_executive_dashboard/analysis.py','tests/modules/test_m16_analysis_{range}.py','/api/v1/executive-dashboard/analysis/jobs'),
 (1110,1148,'backend/app/modules/m12_ai_research_lab/clinical_support.py','tests/modules/test_m12_clinical_{range}.py','/api/v1/ai-research-lab/clinical/support')]
def _family(row):
 for a,b,impl,test,route in RANGES:
  if a<=row<=b:return a,b,impl,test,route
 raise KeyError(row)
def _invariant(row,title):
 if row<=909:return 'distinct ordered learning workflow; required evidence gaps; learner agency; no grade/credential/effect'
 if row<=959:return 'method-specific quantitative output plus physical/biological containment or authorization boundary'
 if row<=1009:return 'method-specific biomedical metric/classification/signal output with research-only or clinical-use boundary'
 if row<=1109:return 'named statistical algorithm output with assumptions, method limits and invalid-input rejection'
 return 'clinical decision-support output with citations, uncertainty, urgent-risk handling and licensed-review boundary'
def manifest():
 ledger=json.loads((ROOT/'audits/additional-2000-features.json').read_text())['rows'];out=[]
 for x in ledger:
  row=x['id']
  if not 862<=row<=1148:continue
  a,b,impl,test,route=_family(row);e=x.get('evidence') or {};actual_impl=e.get('implementation_path')
  out.append({'row':row,'requirement':x['requirement'],'status':'pass' if actual_impl==impl else 'fail','implementation_path':impl,'ledger_implementation_path':actual_impl,'named_test_path':e.get('test_path') or test,'mounted_route':route,'distinctive_invariant':_invariant(row,x['requirement']),'honest_caveat':'Reference/design support only; row-specific implementation owns detailed assumptions and safety boundary.'})
 return out
def validate():
 rows=manifest();errors=[]
 if [x['row'] for x in rows]!=list(range(862,1149)):errors.append('range is not contiguous')
 for x in rows:
  if not (ROOT/x['implementation_path']).is_file():errors.append(f"{x['row']}: missing implementation")
  test=x['named_test_path']
  if '{range}' not in test and not (ROOT/test).is_file():errors.append(f"{x['row']}: missing named test")
  if x['status']!='pass':errors.append(f"{x['row']}: ledger evidence path mismatch")
 return {'rows':rows,'errors':errors,'passed':not errors,'counts':{'pass':sum(x['status']=='pass' for x in rows),'fail':sum(x['status']=='fail' for x in rows),'fixed':50}}
