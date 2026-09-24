"""One mounted owner-corpus -> draft -> natural voice -> review -> browser staging flow."""
from __future__ import annotations
class IntegratedApplicationFlow:
 def __init__(self,corpus,drafter,humanizer,approvals,tenant_id="local"):
  if not tenant_id.strip():raise ValueError("tenant_id is required")
  self.corpus,self.drafter,self.humanizer,self.approvals,self.tenant_id=corpus,drafter,humanizer,approvals,tenant_id.strip()
 async def prepare(self,competition_id,official_url,fields,provider='openai'):
  exact={};provenance={};evidence_inputs={};source_ids={}
  for field in fields:
   hits=await self.corpus.retrieve(f"{field['question']} {field.get('requirements','')}",field.get('evidence_limit',8))
   if not hits:raise ValueError(f"no owner corpus evidence for field: {field['field']}")
   drafted=await self.drafter.draft(field['field'],field['question'],field.get('requirements',''),hits,provider)
   voiced=await self.humanizer.humanize(field['field'],drafted['draft'],provider)
   if not voiced.facts_preserved:raise ValueError(f"natural-voice pass changed factual anchors for field: {field['field']}")
   exact[field['field']]=voiced.humanized;provenance[field['field']]=drafted['source_provenance']
   evidence_inputs[field['field']]={'draft':drafted['draft'],'sources':hits};source_ids[field['field']]=[h['id'] for h in hits if 'id' in h]
  from .application_pipeline import ApplicationAnswerPipeline
  package=await ApplicationAnswerPipeline(self.humanizer,self.approvals,self.tenant_id).prepare_review(competition_id,exact,provider)
  from .evidence import score_package
  package.update({'evidence_completeness':score_package(evidence_inputs),'evidence_source_ids':source_ids,'official_url':official_url,'source_provenance':provenance,'browser_stage_path':'/api/v1/competition-manager/competitions/{competition_id}/form-fill-proposals','final_submit_requires_separate_approval':True})
  return package
