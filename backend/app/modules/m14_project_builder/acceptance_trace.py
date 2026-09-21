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
