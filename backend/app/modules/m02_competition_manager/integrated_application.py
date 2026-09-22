"""One mounted owner-corpus -> draft -> natural voice -> review -> browser staging flow."""
from __future__ import annotations
class IntegratedApplicationFlow:
 def __init__(self,corpus,drafter,humanizer,approvals,tenant_id="local"):
  if not tenant_id.strip():raise ValueError("tenant_id is required")
  self.corpus,self.drafter,self.humanizer,self.approvals,self.tenant_id=corpus,drafter,humanizer,approvals,tenant_id.strip()
 async def prepare(self,competition_id,official_url,fields,provider='openai'):
  exact={};provenance={}
  for field in fields:
   hits=await self.corpus.retrieve(f"{field['question']} {field.get('requirements','')}",field.get('evidence_limit',8))
   if not hits:raise ValueError(f"no owner corpus evidence for field: {field['field']}")
   drafted=await self.drafter.draft(field['field'],field['question'],field.get('requirements',''),hits,provider)
   voiced=await self.humanizer.humanize(field['field'],drafted['draft'],provider)
   if not voiced.facts_preserved:raise ValueError(f"natural-voice pass changed factual anchors for field: {field['field']}")
   exact[field['field']]=voiced.humanized;provenance[field['field']]=drafted['source_provenance']
  from .application_pipeline import ApplicationAnswerPipeline
  package=await ApplicationAnswerPipeline(self.humanizer,self.approvals,self.tenant_id).prepare_review(competition_id,exact,provider)
  package.update({'official_url':official_url,'source_provenance':provenance,'browser_stage_path':'/api/v1/competition-manager/competitions/{competition_id}/form-fill-proposals','final_submit_requires_separate_approval':True})
  return package
