import base64
from pydantic import BaseModel,Field
class PersistSourceMessage(BaseModel):message_id:str=Field(min_length=1);content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');content_base64:str=Field(min_length=1)
def persist_source_message(body:PersistSourceMessage,store):
 try:data=base64.b64decode(body.content_base64,validate=True)
 except Exception as exc:raise ValueError('invalid source-message encoding') from exc
 row=store.persist(body.message_id,body.content_sha256,data);return {'persisted':True,'message_id':row.message_id,'content_sha256':row.content_sha256,'byte_count':len(row.content_bytes),'persisted_at':row.persisted_at.isoformat(),'boundary':'Persists verified source-message bytes tenant-scoped and immutable by message ID. It does not establish authorship, authenticate reviewers, reconcile promises, create tasks, draft, remind, or send.'}
