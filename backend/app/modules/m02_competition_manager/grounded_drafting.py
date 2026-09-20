"""Draft fields only from retrieved owner corpus plus official requirements."""
class GroundedApplicationDrafter:
 def __init__(self,generate):self.generate=generate
 async def draft(self,field,question,requirements,corpus_hits,provider='openai'):
  if not corpus_hits:raise ValueError('no owner-authored corpus evidence retrieved')
  evidence='\n'.join(f"[{i+1}] {x['title']} ({x['source_type']}:{x['source_id']} {x['locator']})\n{x['text']}" for i,x in enumerate(corpus_hits))
  prompt=f'''Draft an answer for FIELD: {field}\nQUESTION: {question}\nOFFICIAL REQUIREMENTS: {requirements}\nOWNER-AUTHORED SOURCE MATERIAL:\n{evidence}\nUse only source material and explicit requirements. Cite source markers [1], [2]. Do not invent activities, achievements, dates, metrics, motivations, or commitments. If evidence is missing, write [NEEDS INPUT]. Return only the draft.'''
  model,text=await self.generate(prompt,provider,None)
  return {'field':field,'draft':text.strip(),'model':model,'source_ids':[x['id'] for x in corpus_hits],'source_provenance':[{'source_type':x['source_type'],'source_id':x['source_id'],'locator':x['locator']} for x in corpus_hits],'requires_human_review':True}
