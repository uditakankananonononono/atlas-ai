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

import base64,sqlite3
from datetime import datetime,timezone
from pathlib import Path
class ArtifactEventStore:
 """Durable tenant-scoped, idempotent provenance-event store."""
 def __init__(self,path:str|Path):
  self.path=str(path);self._db().execute('CREATE TABLE IF NOT EXISTS artifact_events(tenant_id TEXT NOT NULL,event_id TEXT NOT NULL,event_sha256 TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(tenant_id,event_id))').close()
 def _db(self):
  db=sqlite3.connect(self.path);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');return db
 def put(self,event:dict[str,Any],artifact_base64:str|None=None)->dict[str,Any]:
  validated=ingest_artifact_event(event);canonical=validated['event'];bytes_verified=False
  if artifact_base64 is not None:
   try:blob=base64.b64decode(artifact_base64,validate=True)
   except Exception as error:raise ValueError('artifact_base64 is not valid base64') from error
   actual=sha256(blob).hexdigest()
   if actual!=canonical['content_sha256']:raise ValueError(f'artifact byte hash mismatch: expected {canonical["content_sha256"]}, got {actual}')
   bytes_verified=True
  payload=json.dumps(canonical,sort_keys=True,separators=(',',':'));created=datetime.now(timezone.utc).isoformat()
  with self._db() as db:
   prior=db.execute('SELECT event_sha256,payload,created_at FROM artifact_events WHERE tenant_id=? AND event_id=?',(canonical['tenant_id'],canonical['event_id'])).fetchone()
   if prior:
    if prior[0]!=canonical['event_sha256']:raise ValueError('event_id already exists with different content')
    return {'created':False,'bytes_verified':bytes_verified,'event':json.loads(prior[1]),'stored_at':prior[2]}
   db.execute('INSERT INTO artifact_events VALUES(?,?,?,?,?)',(canonical['tenant_id'],canonical['event_id'],canonical['event_sha256'],payload,created))
  return {'created':True,'bytes_verified':bytes_verified,'event':canonical,'stored_at':created}
 def get(self,tenant_id:str,event_id:str)->dict[str,Any]:
  with self._db() as db:row=db.execute('SELECT payload,created_at FROM artifact_events WHERE tenant_id=? AND event_id=?',(tenant_id,event_id)).fetchone()
  if not row:raise KeyError(event_id)
  return {'event':json.loads(row[0]),'stored_at':row[1]}
 def list(self,tenant_id:str,limit:int=100)->list[dict[str,Any]]:
  with self._db() as db:rows=db.execute('SELECT payload,created_at FROM artifact_events WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?',(tenant_id,limit)).fetchall()
  return [{'event':json.loads(x[0]),'stored_at':x[1]} for x in rows]
