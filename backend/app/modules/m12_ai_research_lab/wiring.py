"""Shipped Module 12 runtime using Atlas's configured model providers."""
from __future__ import annotations
from app.core.providers import generate
from .models import ModelCapability,ModelResult,TaskType
from .router import ModelRouter
from .service import Service
from .workflow import DagEngine

CATALOG=[
 ModelCapability('openai:gpt-4o-mini',frozenset(TaskType),16000,.06,2500,.82),
 ModelCapability('anthropic:claude-3-5-haiku-latest',frozenset(TaskType),8192,.10,2500,.84),
 ModelCapability('deepseek:deepseek-chat',frozenset(TaskType),8192,.03,3500,.80),
 ModelCapability('ollama:llama3.2',frozenset(TaskType),4096,0,8000,.70),
 ModelCapability('shared:instinct',frozenset(TaskType),4096,0,12000,.74),  # shared model layer, private routes only
]
class AtlasProvider:
 async def generate(self,*,model_id,prompt,context):
  provider,model=model_id.split(':',1)
  chosen,text=await generate(prompt,provider,model)
  return ModelResult(text=text,model_id=chosen,confidence=.75,metadata={'provider':provider})

def build_service():return Service(ModelRouter(CATALOG),AtlasProvider())
def build_dag_engine(service):
 async def run(task,config,context):
  from .models import RouteRequest
  req=RouteRequest(TaskType(config.get('task_type',task if task in {x.value for x in TaskType} else 'research')),int(config.get('output_tokens',1000)),float(config.get('budget_cents',1)),int(config.get('latency_tolerance_ms',10000)),str(context['workflow_inputs']['tenant_id']))
  result=await service.execute(req,str(config.get('prompt') or context['workflow_inputs'].get('prompt') or task),context)
  return {'text':result.text,'model_id':result.model_id,'usage':result.usage,'metadata':result.metadata}
 return DagEngine(run)
