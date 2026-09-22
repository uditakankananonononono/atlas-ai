from __future__ import annotations
import base64,hashlib,json
from pydantic import BaseModel,Field
class PersistCaptureRequest(BaseModel):
 session_id:str=Field(min_length=1);destination:str=Field(min_length=1);fields:dict[str,str]=Field(default_factory=dict);captured_at:str=Field(min_length=1);dom_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');screenshot_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');capture_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');dom_base64:str=Field(min_length=1);screenshot_base64:str=Field(min_length=1)
async def persist_capture(body:PersistCaptureRequest,tenant_id:str,store)->dict:
 try:dom=base64.b64decode(body.dom_base64,validate=True);shot=base64.b64decode(body.screenshot_base64,validate=True)
 except Exception as exc:raise ValueError('invalid capture byte encoding') from exc
 if hashlib.sha256(dom).hexdigest()!=body.dom_sha256:raise ValueError('DOM byte hash mismatch')
 if hashlib.sha256(shot).hexdigest()!=body.screenshot_sha256:raise ValueError('screenshot byte hash mismatch')
 artifact={k:getattr(body,k) for k in ('session_id','destination','fields','captured_at','dom_sha256','screenshot_sha256')}
 actual=hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if actual!=body.capture_sha256:raise ValueError('capture artifact hash mismatch')
 row=await store.persist_capture(tenant_id,body.session_id,actual,artifact,dom,shot)
 return {'persisted':True,'capture_sha256':actual,'dom_byte_count':len(dom),'screenshot_byte_count':len(shot),'persisted_at':row.persisted_at.isoformat(),'boundary':'Persists verified capture bytes immutably under tenant and capture hash. It does not approve, bind an approval, click, submit, pay, or establish that captured DOM claims are true.'}
