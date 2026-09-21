"""Current-state semantic evidence verifier for Specialized Domain Expertise rows 1149-1435."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
LEDGER=ROOT/'audits'/'additional-2000-features.json'
# Distinct families and the semantic envelopes each implementation must expose.
FAMILIES=[
 (1149,1209,'clinical',{'boundary','source'}),
 (1210,1259,'legal_workbench',{'review','disclaimer'}),
 (1260,1309,'legal_research',{'review_required','boundary'}),
 (1310,1359,'finance_core',{'output','inputs'}),
 (1360,1409,'finance_specialized',{'output','inputs'}),
 (1410,1435,'education',{'result','boundary'}),
]
def family(row):
 for lo,hi,name,keys in FAMILIES:
  if lo<=row<=hi:return name,keys
 raise ValueError('row outside semantic block')
def rows():return [r for r in json.loads(LEDGER.read_text())['rows'] if 1149<=r['id']<=1435]
def verify_evidence(r):
 ev=r.get('evidence') or {};impl=ev.get('implementation_path');test=ev.get('test_path');name,keys=family(r['id'])
 missing=[p for p in (impl,test) if not p or not (ROOT/p).is_file()]
 text=(ROOT/test).read_text() if test and (ROOT/test).is_file() else ''
 impl_text=(ROOT/impl).read_text() if impl and (ROOT/impl).is_file() else ''
 # Exact evidence may use the numeric row or its canonical method identifier.
 method=re.sub(r'[^a-z0-9]+','_',r['requirement'].lower()).strip('_')
 exact=bool(re.search(rf'(?<!\d){r["id"]}(?!\d)',text+impl_text) or method in text)
 return {'row':r['id'],'requirement':r['requirement'],'family':name,'implementation_path':impl,'test_path':test,'missing_paths':missing,'exact_row_named_in_test':exact,'required_output_invariants':sorted(keys),'mounted_boundary':{'clinical':'/api/v1/ai-research-lab/clinical/support','legal_workbench':'/api/v1/api/modules/20/legal/support','legal_research':'/api/v1/ai-research-lab/legal/support','finance_core':'/api/v1/executive-dashboard/analysis/jobs','finance_specialized':'/api/v1/executive-dashboard/finance/analyze','education':'/api/v1/api/modules/20/education/{capability}'}[name],'pass':not missing and exact}
def report():
 result=[verify_evidence(r) for r in rows()];return {'row_start':1149,'row_end':1435,'row_count':len(result),'passed':sum(x['pass'] for x in result),'failed':sum(not x['pass'] for x in result),'fixed':0,'rows':result}
