"""Executable architecture/reliability design checks for owner rows 635-684."""
from __future__ import annotations
from collections import defaultdict,deque
from math import exp
from typing import Any
NAMES=["SLO/SLI Definition","Error Budgets","Incident Management","Post-Mortem Analysis","Runbook Creation","On-Call Rotation","Capacity Planning","Cost Optimization","Resource Scheduling","Job Queuing","Workflow Orchestration","DAG Scheduling","Cron Jobs","Event Sourcing","CQRS","Saga Pattern","Two-Phase Commit","Idempotency","Exactly-Once Semantics","At-Least-Once Semantics","Dead Letter Queue","Retry Logic","Backoff Strategy","Bulkhead Pattern","Sidecar Pattern","Ambassador Pattern","Adapter Pattern","Facade Pattern","Observer Pattern","Strategy Pattern","Factory Pattern","Singleton Pattern","Dependency Injection","Inversion of Control","Repository Pattern","Unit of Work","Domain-Driven Design","Bounded Context","Ubiquitous Language","Aggregate Design","Entity Design","Value Object Design","Domain Event","Anti-Corruption Layer","Hexagonal Architecture","Clean Architecture","Onion Architecture","Ports and Adapters","Functional Core, Imperative Shell","Event Storming"]
FEATURES={635+i:n for i,n in enumerate(NAMES)}
RELIABILITY=set(range(635,643));SCHED=set(range(643,648));DELIVERY=set(range(648,658));PATTERNS=set(range(658,671));DOMAIN=set(range(671,685))
DISCLAIMER="Architecture decision support only. Validate assumptions with owners, load/failure tests, security review, operational evidence and rollback plans before deployment."
def _base(fid,d):
 if fid not in FEATURES:raise ValueError('feature_id must be 635-684')
 if not d.get('system') or not d.get('decision_owner'):raise ValueError('system and decision_owner are required')
 return {'feature_id':fid,'concept':FEATURES[fid],'system':d['system'],'decision_owner':d['decision_owner'],'assumptions':d.get('assumptions',[]),'unknowns':d.get('unknowns',[]),'review_required':True,'disclaimer':DISCLAIMER}
def _reliability(fid,d):
 o=_base(fid,d);windows=d.get('windows',[]);services=d.get('services',[])
 if not windows or not services:raise ValueError('windows and services are required')
 results=[]
 for w in windows:
  total=float(w.get('total',0));good=float(w.get('good',0));target=float(w.get('target',0));
  if total<=0 or not 0<=good<=total or not 0<target<=1:raise ValueError('invalid SLI window')
  actual=good/total;allowed=round(total*(1-target),12);bad=total-good;results.append({'name':w.get('name'),'actual_sli':actual,'target':target,'allowed_bad_events':allowed,'observed_bad_events':bad,'budget_remaining':allowed-bad,'burn_ratio':bad/allowed if allowed else None})
 o.update({'services':services,'sli_windows':results,'alerts':d.get('alerts',[]),'incident_roles':d.get('incident_roles',[]),'timeline':d.get('timeline',[]),'runbook_steps':d.get('runbook_steps',[]),'on_call':d.get('on_call',[]),'capacity_forecast':d.get('capacity_forecast',[]),'cost_options':d.get('cost_options',[]),'boundary':'Analysis and preparation only. No alert, page, remediation, capacity purchase or cost change executes here. Blameless review separates observed facts, contributing conditions and follow-up ownership.'});return o
def _toposort(nodes,edges):
 adj=defaultdict(list);degree={n:0 for n in nodes}
 for e in edges:
  a,b=e.get('from'),e.get('to')
  if a not in degree or b not in degree:raise ValueError('edge references unknown node')
  adj[a].append(b);degree[b]+=1
 q=deque(sorted(n for n,v in degree.items() if v==0));order=[]
 while q:
  n=q.popleft();order.append(n)
  for m in adj[n]:
   degree[m]-=1
   if degree[m]==0:q.append(m)
 if len(order)!=len(nodes):raise ValueError('workflow contains a cycle')
 return order
def _schedule(fid,d):
 o=_base(fid,d);jobs=d.get('jobs',[])
 if not jobs:raise ValueError('jobs are required')
 ids=[j.get('id') for j in jobs]
 if None in ids or len(set(ids))!=len(ids):raise ValueError('job ids must be unique')
 order=_toposort(ids,d.get('dependencies',[]));queued=sorted(jobs,key=lambda j:(-int(j.get('priority',0)),j.get('enqueued_at',''),j['id']))
 o.update({'dag_order':order,'queue_order':[j['id'] for j in queued],'jobs':jobs,'cron_expressions':d.get('cron_expressions',[]),'resource_limits':d.get('resource_limits',{}),'events':d.get('events',[]),'boundary':'Produces a deterministic plan only. It does not enqueue, execute, cancel or schedule jobs. Operators validate timezone, overlap, fairness, quotas, dependencies, retries and cancellation.'});return o
def _delivery(fid,d):
 o=_base(fid,d);messages=d.get('messages',[]);policy=d.get('delivery_policy',{})
 if not messages or not policy:raise ValueError('messages and delivery_policy are required')
 seen=set();out=[]
 for m in messages:
  key=m.get('idempotency_key');duplicate=key in seen if key else False
  if key:seen.add(key)
  attempt=int(m.get('attempt',1));base=float(policy.get('base_delay_seconds',1));cap=float(policy.get('max_delay_seconds',60));delay=min(cap,base*(2**max(attempt-1,0)));out.append({'message_id':m.get('id'),'idempotency_key':key,'duplicate':duplicate,'attempt':attempt,'next_delay_seconds':delay,'destination':'dead_letter' if attempt>=int(policy.get('max_attempts',3)) else 'retry_or_process'})
 o.update({'delivery_analysis':out,'delivery_semantics':policy.get('semantics'),'transaction_boundaries':d.get('transaction_boundaries',[]),'compensations':d.get('compensations',[]),'event_versions':d.get('event_versions',[]),'boundary':'Simulation only. Exactly-once is not claimed end-to-end without atomic boundaries and deduplication. No transaction, retry, publish, compensation or DLQ move executes here.'});return o
def _pattern(fid,d):
 o=_base(fid,d);components=d.get('components',[]);interfaces=d.get('interfaces',[])
 if not components or not interfaces:raise ValueError('components and interfaces are required')
 names={c.get('id') for c in components};viol=[]
 for i in interfaces:
  if i.get('consumer') not in names or i.get('provider') not in names:viol.append({'interface':i.get('id'),'violation':'unknown_component'})
  if i.get('consumer')==i.get('provider'):viol.append({'interface':i.get('id'),'violation':'self_dependency'})
 o.update({'components':components,'interfaces':interfaces,'structural_violations':viol,'failure_isolation':d.get('failure_isolation',[]),'lifecycle':d.get('lifecycle',{}),'alternatives':d.get('alternatives',[]),'boundary':'Pattern-fit review, not an instruction to force a pattern. Verify ownership, coupling, lifecycle, concurrency, failure isolation, testability and simpler alternatives before implementation.'});return o
def _domain(fid,d):
 o=_base(fid,d);contexts=d.get('contexts',[]);events=d.get('domain_events',[])
 if not contexts:raise ValueError('contexts are required')
 ids={c.get('id') for c in contexts};collisions=[];terms=defaultdict(set)
 for c in contexts:
  for term,meaning in c.get('language',{}).items():terms[term].add(str(meaning))
 for term,meanings in terms.items():
  if len(meanings)>1:collisions.append({'term':term,'meanings':sorted(meanings)})
 invalid=[e for e in events if e.get('context_id') not in ids or not e.get('past_tense_name')]
 o.update({'contexts':contexts,'language_collisions':collisions,'aggregates':d.get('aggregates',[]),'entities':d.get('entities',[]),'value_objects':d.get('value_objects',[]),'domain_events':events,'invalid_events':invalid,'context_mappings':d.get('context_mappings',[]),'ports':d.get('ports',[]),'adapters':d.get('adapters',[]),'event_storm':d.get('event_storm',[]),'boundary':'Collaborative domain model, not settled business truth. Domain experts validate language, invariants, aggregate consistency, ownership, context boundaries, mappings, ports and event chronology.'});return o
def architecture_support_635_684(fid:int,data:dict[str,Any])->dict[str,Any]:
 if fid in RELIABILITY:return _reliability(fid,data)
 if fid in SCHED:return _schedule(fid,data)
 if fid in DELIVERY:return _delivery(fid,data)
 if fid in PATTERNS:return _pattern(fid,data)
 if fid in DOMAIN:return _domain(fid,data)
 raise ValueError('feature_id must be 635-684')
