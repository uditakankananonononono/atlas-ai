"""Approval-bound worker adapter for rendering and private object upload."""
from __future__ import annotations
import hashlib
from typing import Protocol
from pydantic import BaseModel,Field
from app.core.models import ApprovalStatus
class RenderAdapter(Protocol):
 def render(self,version_id:str,format:str)->bytes:...
class PrivateUploadAdapter(Protocol):
 def upload_private(self,object_key:str,data:bytes)->dict:...
class ApprovedPublicationJob(BaseModel):
 approval_id:str=Field(min_length=1);version_id:str=Field(min_length=1);format:str=Field(pattern=r'^(latex|docx|pptx|pdf)$');expected_content_hash:str=Field(pattern=r'^[0-9a-f]{64}$');object_key:str=Field(min_length=1)
def execute_approved_publication(job:ApprovedPublicationJob,tenant_id:str,approvals,renderer:RenderAdapter,uploader:PrivateUploadAdapter)->dict:
 approval=approvals.get(job.approval_id,user_id=tenant_id)
 if approval is None or approval.status!=ApprovalStatus.APPROVED:raise ValueError('approved tenant-scoped render approval is required')
 expected={'tenant_id':tenant_id,'version_id':job.version_id,'format':job.format,'content_hash':job.expected_content_hash}
 if any(approval.payload.get(k)!=v for k,v in expected.items()):raise ValueError('approval is bound to different render content')
 rendered=renderer.render(job.version_id,job.format)
 if not rendered:raise ValueError('renderer returned empty bytes')
 published_sha=hashlib.sha256(rendered).hexdigest();receipt=uploader.upload_private(job.object_key,rendered)
 if receipt.get('access')!='private':raise ValueError('uploader did not return private access')
 if receipt.get('published_sha256')!=published_sha or receipt.get('byte_size')!=len(rendered):raise ValueError('upload receipt does not match rendered bytes')
 return {'executed':True,'approval_id':job.approval_id,'version_id':job.version_id,'access':'private','object_key':job.object_key,'published_sha256':published_sha,'byte_size':len(rendered),'provider_receipt':receipt,'boundary':'Executes only through injected renderer and private-upload adapters after exact tenant-scoped approval binding. Provider receipt authentication and approval consumption/replay protection remain separate required controls.'}
