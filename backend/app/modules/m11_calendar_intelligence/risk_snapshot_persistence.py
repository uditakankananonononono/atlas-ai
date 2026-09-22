import base64
from pydantic import BaseModel,Field
from .risk_snapshot_store import RiskSnapshotStore
class PersistRiskSnapshot(BaseModel):source_uri:str=Field(min_length=1,max_length=2000);content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');content_base64:str=Field(min_length=1)
def persist_risk_snapshot(body:PersistRiskSnapshot,store:RiskSnapshotStore):
 try:data=base64.b64decode(body.content_base64,validate=True)
 except Exception as exc:raise ValueError('invalid source snapshot encoding') from exc
 row=store.persist(body.source_uri,body.content_sha256,data);return {'persisted':True,'content_sha256':row.content_sha256,'source_uri':row.source_uri,'byte_count':len(row.source_bytes),'persisted_at':row.persisted_at.isoformat(),'boundary':'Persists verified tenant-scoped source bytes immutably by content hash. It does not retrieve the remote source, authenticate the provider, prove route or policy truth, change events, cancel, or spend.'}
