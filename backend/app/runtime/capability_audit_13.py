"""Live verifier for the 13 assistant-capability audit surfaces."""
from __future__ import annotations
import json,os
from pathlib import Path
from app.modules.registry import BY_IMPLEMENTED_ID
ROOT=Path(__file__).resolve().parents[3]
LEDGER=ROOT/'audits'/'assistant-capability-13.json'
def load_ledger():
 data=json.loads(LEDGER.read_text())
 if data.get('schema_version')!=1 or data.get('row_count')!=13 or len(data.get('rows',[]))!=13:raise RuntimeError('invalid capability ledger shape')
 ids=[x.get('id') for x in data['rows']]
 if ids!=list(range(1,14)):raise RuntimeError('capability ledger ids must be exactly 1..13')
 return data
def verify_row(row,production_attestations=None):
 missing_files=[p for p in row['required_evidence'] if not (ROOT/p).is_file()]
 missing_modules=[m for m in row['module_ids'] if m not in BY_IMPLEMENTED_ID]
 result={'id':row['id'],'surface':row['surface'],'mounted_modules':row['module_ids'],'evidence':row['required_evidence'],'failure_contract':row['failure_contract'],'missing_files':missing_files,'missing_modules':missing_modules,'code_verified':not missing_files and not missing_modules}
 if row['id']==13:
  required={'secrets','tls','migrations','observability','backups'};att=set(production_attestations or [])
  result['production_required_attestations']=sorted(required);result['production_missing_attestations']=sorted(required-att);result['production_ready']=result['code_verified'] and required<=att
 return result
def audit(production_attestations=None):
 rows=[verify_row(x,production_attestations) for x in load_ledger()['rows']]
 return {'schema_version':1,'rows':rows,'code_verified_count':sum(x['code_verified'] for x in rows),'all_code_verified':all(x['code_verified'] for x in rows),'production_ready':next(x for x in rows if x['id']==13)['production_ready']}
