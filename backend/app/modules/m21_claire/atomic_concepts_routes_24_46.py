from typing import Any
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .atomic_concepts_24_46 import AtomicError,AtomicService,ROWS
router=APIRouter(prefix='/atomic-concepts-24-46',tags=['claire-atomic-24-46']);service=AtomicService()
class Request(BaseModel):atomic_row_id:str;tenant_id:str=Field(min_length=1);data:dict[str,Any]=Field(default_factory=dict)
@router.get('/capabilities')
def capabilities():return [{'atomic_row_id':k,'requirement':v} for k,v in ROWS.items()]
@router.post('/run')
def run(body:Request):
 try:
  r,d,t=body.atomic_row_id,body.data,body.tenant_id
  if r=='3.2':o=service.retrieve_corrections(t,d['query'],d.get('k',5),d.get('min_similarity',0))
  elif r=='3.3':o=service.few_shot(t,d['query'],d.get('k',3))
  elif r=='3.4':o=service.repeat_error(t,d['candidate'],d['query'],d.get('threshold',.85))
  elif r=='4.1':o=service.add_sample(t,d['text'],d['source'],d['consented'],d.get('owner_authored',True),d.get('license_status','owner'))
  elif r=='4.2':o=service.validate_dataset(t)
  elif r=='4.3':o=service.lora_proposal(t,d['base_model'],d['config'])
  elif r=='4.4':o=service.ollama_target(d['proposal'],d['model_name'])
  elif r=='4.5':o=service.readiness(d['hardware'],d['job'],d.get('cloud_rate_per_hour'),d.get('estimated_hours'))
  elif r=='4.6':o=service.evaluate_voice(d['rows'],d['thresholds'])
  elif r=='5.1':o=service.reasoning_note(t,d['problem'],d['steps'],d['conclusion'],d['owner_authored'],d.get('consented',True))
  elif r in ('5.2','5.3'):o=service.retrieve_reasoning(t,d['problem'],d.get('k',3))
  elif r=='5.4':o=service.decision_template(t,d['problem'])
  elif r=='5.5':o=service.reject_hidden_cot(d['source_type'])
  elif r=='6.1':o=service.generate_options(d['candidates'])
  elif r=='6.2':o=service.capture_ranking(t,d['options'],d['ordered_ids'],d.get('context',''))
  elif r=='6.3':o=service.pairwise(d['ranking'])
  elif r=='6.4':o=service.preference_proposal(d['dataset'],d['features'])
  elif r=='6.5':o=service.evaluate_preference(d['predictions'],d.get('min_accuracy',.6))
  elif r=='7.1':o=service.consent(t,d['scopes'],d['retention_days'],d['granted'])
  elif r in ('7.2','7.3','7.4'):o=service.telemetry_event(t,{'7.2':'link_click','7.3':'opportunity_application','7.4':'draft_edit_duration'}[r],d)
  else:raise AtomicError('unknown atomic row')
  return {'atomic_row_id':r,'requirement':ROWS[r],'result':o,'external_effects':[],'strongest_honest_boundary':'Local records/proposals are real. Training, activation, telemetry capture beyond submitted events, infrastructure readiness and effects are unproven unless explicitly observed.'}
 except (AtomicError,KeyError,TypeError,ValueError) as e:raise HTTPException(422,detail=str(e)) from e
