"""Curated draft -> natural voice -> exact owner-review package."""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json,uuid
from app.core.models import ApprovalRequest
class ApplicationAnswerPipeline:
 def __init__(self,humanizer,approvals,tenant_id="local"):
  if not tenant_id.strip():raise ValueError("tenant_id is required")
  self.humanizer,self.approvals,self.tenant_id=humanizer,approvals,tenant_id.strip()
 async def prepare_review(self,competition_id,answers,provider='openai'):
  revised=[]
  for field,answer in answers.items():revised.append(await self.humanizer.humanize(field,answer,provider))
  if not all(x.facts_preserved for x in revised):raise ValueError('natural-voice pass changed factual anchors; manual correction required')
  preview={x.field:x.humanized for x in revised};digest=sha256(json.dumps(preview,sort_keys=True).encode()).hexdigest()
  req=self.approvals.put(ApprovalRequest(id=str(uuid.uuid4()),module_id=2,action_type='review_humanized_application_answers',payload={'competition_id':competition_id,'tenant_id':self.tenant_id,'pipeline':['ai_curated_draft','natural_voice_pass','owner_review','browser_stage','separate_final_submit_approval'],'exact_answers':preview,'answer_sha256':digest,'submission_enabled':False,'humanization_purpose':'clarity_and_natural_voice','prohibitions':['detector_evasion','authorship_misrepresentation','fabricated_content']}),user_id=self.tenant_id)
  return {'approval_id':req.id,'status':'pending','exact_answers':preview,'answer_sha256':digest,'stages':req.payload['pipeline'],'submission_enabled':False}
