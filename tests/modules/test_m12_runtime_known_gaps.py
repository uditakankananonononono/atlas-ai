"""Hermetic runtime contract gaps. No provider/network calls."""
import asyncio
import pytest
from app.modules.m12_ai_research_lab.models import ModelCapability,ModelResult,RouteRequest,TaskType
from app.modules.m12_ai_research_lab.router import ModelRouter,NoEligibleModel
from app.modules.m12_ai_research_lab.executor import ResearchExecutor,RetryPolicy


def models():
 return [ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.9),ModelCapability('backup',frozenset({TaskType.RESEARCH}),1000,0,100,.8)]


def test_provider_exception_currently_escapes_without_backup_invocation():
 calls=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   calls.append(model_id)
   raise TimeoutError('hermetic timeout, no request made')
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0))
 with pytest.raises(TimeoutError):
  asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'fixture'))
 assert calls==['first']
 # Characterization, not safe-retry advice: a real timeout may hide a billable effect.


def test_hard_latency_tolerance_rejects_slow_only_catalog():
 model=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,2000,.9)
 with pytest.raises(NoEligibleModel):
  ModelRouter([model]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))

@pytest.mark.parametrize('estimate',[101,2000])
def test_over_tolerance_models_excluded_from_primary_and_fallbacks(estimate):
 slow=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,estimate,1)
 boundary=ModelCapability('boundary',frozenset({TaskType.RESEARCH}),1000,0,100,.8)
 fast=ModelCapability('fast',frozenset({TaskType.RESEARCH}),1000,0,99,.7)
 decision=ModelRouter([slow,boundary,fast]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))
 assert decision.primary.model_id=='boundary'
 assert [m.model_id for m in decision.fallbacks]==['fast']
 assert decision.scores['slow']==float('-inf')
 assert decision.reasons['slow']==['latency estimate exceeds tolerance']

@pytest.mark.parametrize('estimate,tolerance',[(0,100),(-1,100),(100,0),(100,-1)])
def test_nonpositive_latency_is_not_eligible(estimate,tolerance):
 model=ModelCapability('invalid',frozenset({TaskType.RESEARCH}),1000,0,estimate,.9)
 with pytest.raises(NoEligibleModel):ModelRouter([model]).route(RouteRequest(TaskType.RESEARCH,100,0,tolerance,'fixture'))

def test_ineligible_catalog_does_not_call_provider():
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','slow',1)
 executor=ResearchExecutor(ModelRouter([ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,2000,.9)]),Provider())
 with pytest.raises(NoEligibleModel):asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert not calls

def test_low_confidence_fallback_cannot_invoke_over_tolerance_model():
 calls=[]
 class Provider:
  async def generate(self,*,model_id,**kwargs):
   calls.append(model_id);return ModelResult('fixture',model_id, .1 if model_id=='first' else .9)
 slow=ModelCapability('slow',frozenset({TaskType.RESEARCH}),1000,0,101,1)
 executor=ResearchExecutor(ModelRouter([*models(),slow]),Provider(),RetryPolicy(base_delay_seconds=0))
 result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert result.model_id=='backup' and calls==['first','backup']

@pytest.mark.parametrize('invalid',[float('nan'),float('inf'),float('-inf'),True,False,'100',None,10**1000])
@pytest.mark.parametrize('field',['estimate','tolerance'])
def test_direct_runtime_latency_rejects_nonfinite_and_wrong_types(invalid,field):
 model=ModelCapability('invalid',frozenset({TaskType.RESEARCH}),1000,0,invalid if field=='estimate' else 100,.9)
 req=RouteRequest(TaskType.RESEARCH,100,0,invalid if field=='tolerance' else 100,'fixture')
 with pytest.raises(NoEligibleModel):ModelRouter([model]).route(req)
 assert ModelRouter([model]).score(model,req)==(float('-inf'),['invalid latency estimate or tolerance'])

def test_invalid_catalog_estimate_does_not_poison_valid_choice():
 invalid=ModelCapability('nan',frozenset({TaskType.RESEARCH}),1000,0,float('nan'),1)
 decision=ModelRouter([invalid,*models()]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))
 assert decision.primary.model_id=='first' and [m.model_id for m in decision.fallbacks]==['backup']

@pytest.mark.parametrize('invalid',[float('nan'),float('inf'),float('-inf'),-.1,True,False,'1',None,10**1000])
@pytest.mark.parametrize('field',['budget','price'])
def test_invalid_budget_price_never_invokes_provider(invalid,field):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 model=ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,invalid if field=='price' else 0,100,.8)
 req=RouteRequest(TaskType.RESEARCH,100,invalid if field=='budget' else 1,100,'fixture')
 router=ModelRouter([model])
 assert router.score(model,req)==(float('-inf'),['invalid budget or unit price'])
 with pytest.raises(NoEligibleModel):asyncio.run(ResearchExecutor(router,Provider()).execute(req,'fixture'))
 assert not calls

def test_invalid_price_excluded_without_poisoning_valid_free_catalog():
 invalid=ModelCapability('nan-price',frozenset({TaskType.RESEARCH}),1000,float('nan'),100,1)
 decision=ModelRouter([invalid,*models()]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))
 assert decision.primary.model_id=='first' and [m.model_id for m in decision.fallbacks]==['backup']

@pytest.mark.parametrize('quality',[float('nan'),float('inf'),float('-inf'),-.1,1.1,True,False,'0.8',None,10**1000])
def test_invalid_catalog_quality_rejected_before_provider(quality):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','invalid',.9)
 model=ModelCapability('invalid',frozenset({TaskType.RESEARCH}),1000,0,100,quality)
 req=RouteRequest(TaskType.RESEARCH,100,0,100,'fixture');router=ModelRouter([model])
 assert router.score(model,req)==(float('-inf'),['invalid catalog quality'])
 with pytest.raises(NoEligibleModel):asyncio.run(ResearchExecutor(router,Provider()).execute(req,'fixture'))
 assert not calls
 decision=ModelRouter([model,*models()]).route(req)
 assert decision.primary.model_id=='first' and [m.model_id for m in decision.fallbacks]==['backup']

@pytest.mark.parametrize('quality',[0,1,.8])
def test_valid_catalog_quality_retains_eligibility(quality):
 model=ModelCapability('fixture',frozenset({TaskType.RESEARCH}),1000,0,100,quality)
 assert ModelRouter([model]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture')).primary==model

@pytest.mark.parametrize('invalid',[float('nan'),float('inf'),0,-1,True,False,'100',None,1.5])
@pytest.mark.parametrize('field',['requested','maximum'])
def test_invalid_output_limits_rejected_before_provider(invalid,field):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 model=ModelCapability('first',frozenset({TaskType.RESEARCH}),invalid if field=='maximum' else 1000,0,100,.8)
 req=RouteRequest(TaskType.RESEARCH,invalid if field=='requested' else 100,0,100,'fixture');router=ModelRouter([model])
 assert router.score(model,req)==(float('-inf'),['invalid output token limits'])
 with pytest.raises(NoEligibleModel):asyncio.run(ResearchExecutor(router,Provider()).execute(req,'fixture'))
 assert not calls

@pytest.mark.parametrize('maximum,tokens,price',[(10**1000,10**1000,0),(10**308,10**308,1e308)])
def test_unrepresentable_estimated_cost_rejected_without_crash(maximum,tokens,price):
 model=ModelCapability('first',frozenset({TaskType.RESEARCH}),maximum,price,100,.8)
 req=RouteRequest(TaskType.RESEARCH,tokens,1e308,100,'fixture');router=ModelRouter([model])
 assert router.score(model,req)==(float('-inf'),['invalid estimated cost'])
 with pytest.raises(NoEligibleModel):router.route(req)

def test_small_output_limit_rejection_precedes_huge_cost_conversion():
 model=ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,1,100,.8)
 assert ModelRouter([model]).score(model,RouteRequest(TaskType.RESEARCH,10**1000,1,100,'fixture'))==(float('-inf'),['output limit'])

@pytest.mark.parametrize('field,invalid',[
 *[('min_confidence',x) for x in [float('nan'),float('inf'),-.1,1.1,True,'0.7',None]],
 *[('max_attempts',x) for x in [0,-1,True,1.5,'3',None]],
 *[('base_delay_seconds',x) for x in [float('nan'),float('inf'),-1,True,'0',None,10**1000]],
 *[('enable_self_critique',x) for x in [0,1,'true',None]],
])
def test_invalid_retry_policy_rejected_before_provider(field,invalid):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 with pytest.raises(ValueError):
  executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(**{field:invalid}))
  asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert not calls

@pytest.mark.parametrize('minimum',[0,1])
def test_valid_policy_confidence_boundaries_remain_constructible(minimum):
 assert RetryPolicy(min_confidence=minimum,max_attempts=1,base_delay_seconds=0,enable_self_critique=False).min_confidence==minimum

@pytest.mark.parametrize('model_count,max_attempts',[(1,3),(2,1),(2,2)])
def test_low_confidence_does_not_sleep_after_final_attempt(monkeypatch,model_count,max_attempts):
 from app.modules.m12_ai_research_lab.executor import ConfidenceThresholdNotReached
 import app.modules.m12_ai_research_lab.executor as module
 calls=[];sleeps=[]
 async def sleep(delay):sleeps.append(delay)
 monkeypatch.setattr(module.asyncio,'sleep',sleep)
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs['model_id']);return ModelResult('candidate',kwargs['model_id'],.1)
 executor=ResearchExecutor(ModelRouter(models()[:model_count]),Provider(),RetryPolicy(max_attempts=max_attempts,base_delay_seconds=.2))
 with pytest.raises(ConfidenceThresholdNotReached):asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert len(calls)==min(model_count,max_attempts)
 assert sleeps==([.2] if len(calls)==2 else [])

@pytest.mark.parametrize('different',[False,True])
def test_duplicate_catalog_identity_stops_before_repeated_model_invocation(different):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture',kwargs['model_id'],.1)
 duplicate=ModelCapability('first',frozenset({TaskType.RESEARCH}),1000,0,100,.7 if different else .9)
 router=ModelRouter([models()[0],duplicate]);executor=ResearchExecutor(router,Provider(),RetryPolicy(base_delay_seconds=0))
 with pytest.raises(NoEligibleModel,match='unique'):asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'fixture'))
 assert not calls

@pytest.mark.parametrize('identity',['',' ',None,1,True,[]])
def test_invalid_catalog_identity_rejected_before_ranking(identity):
 invalid=ModelCapability(identity,frozenset({TaskType.RESEARCH}),1000,0,100,.8)
 with pytest.raises(NoEligibleModel,match='nonempty text'):ModelRouter([invalid,*models()]).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'))

@pytest.mark.parametrize('enabled',['false','true',1,0,None,[],{}])
def test_catalog_enabled_flag_not_inferred_from_truthiness(enabled):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','invalid',.9)
 model=ModelCapability('invalid',frozenset({TaskType.RESEARCH}),1000,0,100,.8,enabled=enabled)
 req=RouteRequest(TaskType.RESEARCH,100,0,100,'fixture');router=ModelRouter([model])
 assert router.score(model,req)==(float('-inf'),['invalid enabled flag'])
 with pytest.raises(NoEligibleModel):asyncio.run(ResearchExecutor(router,Provider()).execute(req,'fixture'))
 assert not calls
 assert ModelRouter([model,*models()]).route(req).primary.model_id=='first'

@pytest.mark.parametrize('allow',['first-backup',['first'],{'first':True},None,frozenset({1}),frozenset({''})])
def test_required_model_allowlist_does_not_use_substring_or_wrong_container(allow):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 req=RouteRequest(TaskType.RESEARCH,100,0,100,'fixture',required_model_ids=allow)
 with pytest.raises(NoEligibleModel,match='set of nonempty text'):asyncio.run(ResearchExecutor(ModelRouter(models()),Provider()).execute(req,'fixture'))
 assert not calls

@pytest.mark.parametrize('allow',[{'backup'},frozenset({'backup'})])
def test_valid_exact_allowlist_excludes_primary_and_other_fallbacks(allow):
 decision=ModelRouter(models()).route(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture',required_model_ids=allow))
 assert decision.primary.model_id=='backup' and decision.fallbacks==()

@pytest.mark.parametrize('supported',['research-code',{'research':True},None,frozenset({'research'}),frozenset({None})])
def test_catalog_task_capabilities_require_exact_task_type_set(supported):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','invalid',.9)
 model=ModelCapability('invalid',supported,1000,0,100,.8)
 req=RouteRequest(TaskType.RESEARCH,100,0,100,'fixture');router=ModelRouter([model])
 assert router.score(model,req)==(float('-inf'),['invalid task capabilities'])
 with pytest.raises(NoEligibleModel):asyncio.run(ResearchExecutor(router,Provider()).execute(req,'fixture'))
 assert not calls
 assert ModelRouter([model,*models()]).route(req).primary.model_id=='first'

@pytest.mark.parametrize('task',['research','research-code',None,1,True])
def test_direct_route_task_type_must_be_declared_enum(task):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 req=RouteRequest(task,100,0,100,'fixture')
 with pytest.raises(NoEligibleModel,match='TaskType'):asyncio.run(ResearchExecutor(ModelRouter(models()),Provider()).execute(req,'fixture'))
 assert not calls

@pytest.mark.parametrize('tenant',['',' ',None,True,1])
def test_direct_executor_requires_nonblank_tenant_before_generation(tenant):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 with pytest.raises(ValueError,match='tenant'):asyncio.run(ResearchExecutor(ModelRouter(models()),Provider()).execute(RouteRequest(TaskType.RESEARCH,100,0,100,tenant),'fixture'))
 assert not calls

@pytest.mark.parametrize('prompt',['',' ',None,{},True])
def test_direct_executor_requires_nonblank_text_prompt_before_generation(prompt):
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 with pytest.raises(ValueError,match='prompt'):asyncio.run(ResearchExecutor(ModelRouter(models()),Provider()).execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),prompt))
 assert not calls

def test_direct_prompt_unencodable_as_utf8_rejected_before_provider():
 calls=[]
 class Provider:
  async def generate(self,**kwargs):calls.append(kwargs);return ModelResult('fixture','first',.9)
 with pytest.raises(ValueError,match='UTF-8'):asyncio.run(ResearchExecutor(ModelRouter(models()),Provider()).execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'unencodable\ud800'))
 assert not calls

@pytest.mark.asyncio
async def test_policy_replacement_mid_generation_only_applies_to_next_execution():
 from app.modules.m12_ai_research_lab.executor import ConfidenceThresholdNotReached
 started=asyncio.Event();release=asyncio.Event();calls=[]
 class Provider:
  async def generate(self,**kwargs):
   calls.append(kwargs['model_id']);started.set();await release.wait();return ModelResult('fixture',kwargs['model_id'],.5)
 executor=ResearchExecutor(ModelRouter(models()[:1]),Provider(),RetryPolicy(min_confidence=.7,max_attempts=1,base_delay_seconds=0))
 req=RouteRequest(TaskType.RESEARCH,100,0,100,'fixture')
 running=asyncio.create_task(executor.execute(req,'fixture'))
 await started.wait();executor.policy=RetryPolicy(min_confidence=.1,max_attempts=1,base_delay_seconds=0);release.set()
 with pytest.raises(ConfidenceThresholdNotReached):await running
 result=await executor.execute(req,'fixture')
 assert result.confidence==.5 and calls==['first','first']

@pytest.mark.asyncio
async def test_policy_attempt_and_critique_replacement_preserves_original_run(monkeypatch):
 import app.modules.m12_ai_research_lab.executor as module
 started=asyncio.Event();release=asyncio.Event();calls=[];sleeps=[]
 async def sleep(delay):sleeps.append(delay)
 monkeypatch.setattr(module.asyncio,'sleep',sleep)
 class Provider:
  async def generate(self,**kwargs):
   calls.append((kwargs['model_id'],kwargs['prompt']))
   if len(calls)==1:started.set();await release.wait()
   return ModelResult('candidate',kwargs['model_id'],.1 if len(calls)==1 else .9)
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(max_attempts=2,base_delay_seconds=.2,enable_self_critique=True))
 running=asyncio.create_task(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,100,'fixture'),'original'))
 await started.wait();executor.policy=RetryPolicy(max_attempts=1,base_delay_seconds=.8,enable_self_critique=False);release.set()
 result=await running
 assert [x[0] for x in calls]==['first','backup']
 assert calls[1][1].startswith('Critique and improve the candidate.') and sleeps==[.2]
 assert result.metadata['attempts']==2

def test_reported_model_identity_mismatch_currently_accepted():
 # Characterization, not authenticity advice: the shipped AtlasProvider maps the
 # provider's raw response.model into ModelResult.model_id while catalog ids are
 # namespaced ('openai:gpt-4o-mini'), so the executor records requested_model_id in
 # metadata but never compares the two. A provider substituting another model is
 # currently accepted as success; source authenticity is not established here.
 calls=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   calls.append(model_id);return ModelResult('fixture','substituted-unrequested-model',.95)
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0))
 result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'fixture'))
 assert calls==['first']
 assert result.model_id=='substituted-unrequested-model'
 assert result.metadata['requested_model_id']=='first'

@pytest.mark.parametrize('bad_usage',[['not','a','dict'],'usage',900,None,{1:12},{'input_tokens':'900'},{'input_tokens':True},{'input_tokens':1.5},{'input_tokens':-900}])
def test_declared_usage_shape_violation_held_unknown_without_fallback(bad_usage):
 # Repair pin: the declared ModelResult usage shape is a string-to-integer mapping.
 # A provider returning any other shape (non-dict, non-string keys, non-integer or
 # boolean values, negative counts) is held as ProviderOutcomeUnknown after the first call, with no
 # fallback invocation, because the generation effect already happened. This replaces
 # the earlier characterization that such results were accepted as success.
 from app.core.providers import ProviderOutcomeUnknown
 calls=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   calls.append(model_id);return ModelResult('fixture',model_id,.95,usage=bad_usage)
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0))
 with pytest.raises(ProviderOutcomeUnknown):asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'fixture'))
 assert calls==['first']

@pytest.mark.parametrize('valid_usage',[{'input_tokens':900,'output_tokens':100},{'input_tokens':0,'output_tokens':0},{}])
def test_valid_usage_mapping_still_accepted_after_shape_guard(valid_usage):
 calls=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   calls.append(model_id);return ModelResult('fixture',model_id,.95,usage=valid_usage)
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0))
 result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'fixture'))
 assert result.usage==valid_usage and calls==['first']

def test_per_request_budget_only_no_aggregate_spend_tracking():
 # Characterization, not billing advice: budget is enforced per request inside router
 # scoring; ResearchExecutor keeps no cumulative spend state, so repeated executions each
 # within the per-request budget all invoke the provider. Aggregate spending limits are
 # not established here.
 calls=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   calls.append(model_id);return ModelResult('fixture',model_id,.95,usage={'input_tokens':900,'output_tokens':100})
 priced=[ModelCapability('paidish',frozenset({TaskType.RESEARCH}),1000,5,100,.9)]
 executor=ResearchExecutor(ModelRouter(priced),Provider(),RetryPolicy(base_delay_seconds=0))
 req=RouteRequest(TaskType.RESEARCH,1000,6,500,'fixture')  # estimated 5 cents per call, budget 6
 for _ in range(3):asyncio.run(executor.execute(req,'fixture'))
 assert calls==['paidish']*3

def test_low_confidence_provider_text_interpolated_verbatim_into_critique_prompt():
 # Characterization, not injection-safety advice: with self-critique enabled, the
 # provider's low-confidence text is interpolated verbatim into the next attempt's
 # prompt. The template does not sanitize or delimit that text. This shows verbatim
 # interpolation only; it does not measure attack success or resistance.
 prompts=[]
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   prompts.append(prompt)
   if model_id=='first':return ModelResult('UNTRUSTED-PROVIDER-MARKER',model_id,.1)
   return ModelResult('fixture',model_id,.95)
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0,enable_self_critique=True))
 result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'original-task'))
 assert result.model_id=='backup'
 assert 'UNTRUSTED-PROVIDER-MARKER' in prompts[1] and 'original-task' in prompts[1]

def test_arbitrary_provider_metadata_flows_through_unfiltered():
 # Characterization, not metadata-schema advice: the envelope guard already requires a
 # ModelResult instance (isinstance, so subclasses pass) with metadata of exact dict
 # type, plus typed text/model_id, UTF-8 encodable text, and confidence/logprob
 # constraints. Within that exact-dict metadata, custom nested values pass through
 # unvetted; this pin tests a nested dict/list example, not every shape, and does not
 # cover the envelope guards.
 class Provider:
  async def generate(self,*,model_id,prompt,context):
   return ModelResult('fixture',model_id,.95,metadata={'unvetted_provider_field':{'nested':[1,2,3]}})
 executor=ResearchExecutor(ModelRouter(models()),Provider(),RetryPolicy(base_delay_seconds=0))
 result=asyncio.run(executor.execute(RouteRequest(TaskType.RESEARCH,100,0,500,'fixture'),'fixture'))
 assert result.metadata['unvetted_provider_field']=={'nested':[1,2,3]}

def test_failed_dag_rerun_reexecutes_completed_nodes_no_durable_replay():
 # Characterization, not replay advice: DagEngine run state is in-memory only.
 # WorkflowNodeFailure retains completed sibling outputs in the raised object, but a
 # later run of the same workflow re-executes every node, including completed ones.
 # This pin shows durable resume/replay is absent; it does not show rollback behavior
 # or any acceptance.
 from app.modules.m12_ai_research_lab.workflow import DagEngine,Workflow,WorkflowNodeFailure
 wf=Workflow.from_yaml("name: replay-check\nnodes:\n  - id: a\n    task: t\n  - id: b\n    task: t\n    depends_on: [a]\n")
 calls=[]
 async def runner(task,config,context):
  node='b' if context['parents'] else 'a';calls.append(node)
  if node=='b' and calls.count('b')==1:raise RuntimeError('first-run failure')
  return {node:1}
 engine=DagEngine(runner)
 with pytest.raises(WorkflowNodeFailure) as failure:asyncio.run(engine.run(wf,{}))
 assert sorted(failure.value.completed)==['a']
 result=asyncio.run(engine.run(wf,{}))
 assert calls==['a','b','a','b'] and sorted(result)==['a','b']
