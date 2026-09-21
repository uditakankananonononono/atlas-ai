"""Common provenance event contract for artifacts produced by any Atlas module."""
from __future__ import annotations
from hashlib import sha256
import json,re
from typing import Any
SHA=re.compile(r'^[0-9a-f]{64}$')
def ingest_artifact_event(event:dict[str,Any])->dict[str,Any]:
 required=('event_id','tenant_id','module_id','artifact_id','artifact_kind','content_sha256','observed_at','producer_version')
 missing=[x for x in required if event.get(x) in (None,'')]
 if missing:raise ValueError('missing required fields: '+', '.join(missing))
 module=int(event['module_id'])
 if not 0<=module<=25:raise ValueError('module_id must be canonical M00-M25')
 digest=str(event['content_sha256']).lower()
 if not SHA.fullmatch(digest):raise ValueError('content_sha256 must be lowercase SHA-256 hex')
 sources=event.get('source_refs',[])
 if not isinstance(sources,list) or any(not isinstance(x,dict) or not x.get('uri') for x in sources):raise ValueError('source_refs must contain objects with uri')
 state=str(event.get('execution_state','planned'))
 if state not in {'planned','simulated','externally_executed','independently_verified'}:raise ValueError('invalid execution_state')
 if state in {'externally_executed','independently_verified'} and not event.get('receipt_ids'):raise ValueError(f'{state} requires receipt_ids')
 canonical={'event_id':str(event['event_id']),'tenant_id':str(event['tenant_id']),'module_id':module,'artifact_id':str(event['artifact_id']),'artifact_kind':str(event['artifact_kind']),'content_sha256':digest,'observed_at':str(event['observed_at']),'producer_version':str(event['producer_version']),'source_refs':sources,'execution_state':state,'receipt_ids':[str(x) for x in event.get('receipt_ids',[])],'metadata':event.get('metadata',{})}
 canonical['event_sha256']=sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'accepted':True,'event':canonical,'boundary':'Schema and hash validated; source authenticity and artifact bytes require separate verification.'}
