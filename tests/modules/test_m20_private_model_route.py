import pytest
from app.core import model_catalog as catalog
from app.core.providers import ProviderError
from app.modules.m20_general_cognitive_worker.model_adapters import FreeFirstPlannerModel,FreeFirstExecutiveModel
from app.modules.m20_general_cognitive_worker.htn_planner import PlanError


def test_private_gcw_never_sends_to_hosted_even_when_paid_flag_enabled(monkeypatch):
 monkeypatch.setenv('HF_TOKEN','fixture-token');monkeypatch.setenv('ATLAS_ALLOW_PAID','true');calls=[]
 async def unavailable(prompt,provider,model):
  calls.append(provider)
  if provider in ('huggingface','fugu'):raise AssertionError('private prompt reached hosted provider')
  raise ProviderError('local unavailable')
 monkeypatch.setattr(catalog.providers,'generate',unavailable)
 with pytest.raises(PlanError):FreeFirstPlannerModel().decompose('private-goal',context='private memory')
 assert calls==['ollama','openai_compat']
 calls.clear();r=FreeFirstExecutiveModel().complete('reflect',{'private_fact':'canary'})
 assert not r['available'] and calls==['ollama','openai_compat']


def test_private_named_model_skips_hosted_and_uses_self_hosted(monkeypatch):
 calls=[]
 async def local(prompt,provider,model):
  calls.append(provider)
  assert provider=='openai_compat'
  return model,'[{"title":"Check the supplied evidence","risk":"read"}]'
 monkeypatch.setattr(catalog.providers,'generate',local)
 model=FreeFirstPlannerModel(model_name='inkling')
 assert model.decompose('private task')[0]['title']=='Check the supplied evidence'
 assert calls==['openai_compat']
