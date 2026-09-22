"""Trace scientific acceptance criteria to immutable artifacts and test evidence."""
from __future__ import annotations
from hashlib import sha256
from typing import Any

def build_acceptance_matrix(criteria:list[dict[str,Any]],artifacts:list[dict[str,Any]],tests:list[dict[str,Any]])->dict[str,Any]:
 if not criteria:raise ValueError('at least one acceptance criterion is required')
 ids=[str(x.get('id','')).strip() for x in criteria]
 if any(not x for x in ids) or len(ids)!=len(set(ids)):raise ValueError('criterion ids must be present and unique')
 artifact_by={str(x.get('id','')):x for x in artifacts}; test_by={str(x.get('id','')):x for x in tests}
 rows=[]
 for c in criteria:
  cid=str(c['id']);aids=[str(x) for x in c.get('artifact_ids',[])];tids=[str(x) for x in c.get('test_ids',[])]
  missing_a=[x for x in aids if x not in artifact_by];missing_t=[x for x in tids if x not in test_by]
  failed=[x for x in tids if x in test_by and test_by[x].get('status')!='passed']
  unverifiable=[x for x in aids if x in artifact_by and not artifact_by[x].get('sha256')]
  passed=bool(aids and tids) and not (missing_a or missing_t or failed or unverifiable)
  rows.append({'criterion_id':cid,'criterion':str(c.get('criterion','')),'artifact_ids':aids,'test_ids':tids,'passed':passed,'gaps':{'missing_artifacts':missing_a,'missing_tests':missing_t,'failed_tests':failed,'artifacts_without_sha256':unverifiable}})
 referenced={a for r in rows for a in r['artifact_ids']}
 payload='\n'.join(f"{r['criterion_id']}:{r['passed']}:{','.join(r['artifact_ids'])}:{','.join(r['test_ids'])}" for r in rows)
 return {'passed':all(r['passed'] for r in rows),'matrix':rows,'orphan_artifact_ids':sorted(set(artifact_by)-referenced),'matrix_sha256':sha256(payload.encode()).hexdigest(),'boundary':'Passing means supplied evidence is complete and tests report passed; Atlas does not claim the underlying scientific result is true.'}

def build_proof_status(requirements:list[dict[str,Any]])->dict[str,Any]:
 """Separate code, test and live-acceptance proof instead of collapsing them."""
 if not requirements:raise ValueError('at least one requirement is required')
 ids=[str(x.get('id','')).strip() for x in requirements]
 if any(not x for x in ids) or len(ids)!=len(set(ids)):raise ValueError('requirement ids must be present and unique')
 rows=[]
 for item in requirements:
  code=bool(item.get('artifact_sha256'));tests=bool(item.get('test_name')) and item.get('test_status')=='passed';live=bool(item.get('live_receipt_id')) and item.get('live_status')=='passed'
  blockers=[]
  if not code:blockers.append('missing_code_artifact_hash')
  if not tests:blockers.append('missing_or_failed_test_evidence')
  if not live:blockers.append('missing_or_failed_live_acceptance')
  rows.append({'requirement_id':str(item['id']),'code_complete':code,'test_complete':tests,'live_acceptance_complete':live,'fully_verified':code and tests and live,'blockers':blockers})
 payload=json_dumps(rows)
 return {'requirements':rows,'counts':{'total':len(rows),'code_complete':sum(x['code_complete'] for x in rows),'test_complete':sum(x['test_complete'] for x in rows),'live_acceptance_complete':sum(x['live_acceptance_complete'] for x in rows),'fully_verified':sum(x['fully_verified'] for x in rows)},'proof_sha256':sha256(payload.encode()).hexdigest(),'boundary':'Code and test completion are not promoted to live acceptance; receipt presence is validated but receipt authenticity is not.'}

def json_dumps(value):
 import json
 return json.dumps(value,sort_keys=True,separators=(',',':'))
