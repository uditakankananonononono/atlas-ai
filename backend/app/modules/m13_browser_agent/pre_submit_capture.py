"""Immediate pre-submit capture through the browser adapter."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from pydantic import BaseModel,Field
class PreSubmitCaptureRequest(BaseModel):
 session_id:str=Field(min_length=1,max_length=300);selectors:list[str]=Field(default_factory=list,max_length=500)
async def capture_pre_submit(adapter,tenant_id:str,body:PreSubmitCaptureRequest)->dict:
 # All evidence is read in one adapter sequence immediately before any separate submit call.
 page=await adapter.page(tenant_id,body.session_id,True)
 values=await adapter.read_values(tenant_id,body.session_id,sorted(set(body.selectors)))
 html=await adapter.extract(tenant_id,body.session_id)
 screenshot_path=await adapter.screenshot(tenant_id,body.session_id,mask_selectors=sorted(set(body.selectors)))
 shot=Path(screenshot_path)
 if not shot.is_file():raise ValueError('browser adapter screenshot is missing')
 screenshot_sha=hashlib.sha256(shot.read_bytes()).hexdigest();dom_sha=hashlib.sha256(html.encode()).hexdigest()
 captured_at=datetime.now(timezone.utc).isoformat()
 artifact={'session_id':body.session_id,'destination':page.url,'fields':values,'captured_at':captured_at,'dom_sha256':dom_sha,'screenshot_sha256':screenshot_sha}
 return {**artifact,'capture_sha256':hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'boundary':'This capture records adapter-returned URL, field values, DOM text hash, and screenshot bytes immediately before a separate submit decision. It does not establish that DOM claims are true, approve, click, submit, pay, or retain screenshot bytes beyond adapter storage.'}
