"""Executable architecture/reliability design checks for owner rows 635-684.

Each row is a distinctive algorithm over a typed input contract - not a label
echo. Shared group analyses (SLI math, DAG ordering, delivery simulation,
structure validation, language collision detection) are composed with
per-row computations. Every result carries an evaluation block with
confidence and unknowns. Nothing here executes operations: no pages, no
deploys, no retries, no purchases.
"""
from __future__ import annotations
from collections import defaultdict, deque
from typing import Any

NAMES=["SLO/SLI Definition","Error Budgets","Incident Management","Post-Mortem Analysis","Runbook Creation","On-Call Rotation","Capacity Planning","Cost Optimization","Resource Scheduling","Job Queuing","Workflow Orchestration","DAG Scheduling","Cron Jobs","Event Sourcing","CQRS","Saga Pattern","Two-Phase Commit","Idempotency","Exactly-Once Semantics","At-Least-Once Semantics","Dead Letter Queue","Retry Logic","Backoff Strategy","Bulkhead Pattern","Sidecar Pattern","Ambassador Pattern","Adapter Pattern","Facade Pattern","Observer Pattern","Strategy Pattern","Factory Pattern","Singleton Pattern","Dependency Injection","Inversion of Control","Repository Pattern","Unit of Work","Domain-Driven Design","Bounded Context","Ubiquitous Language","Aggregate Design","Entity Design","Value Object Design","Domain Event","Anti-Corruption Layer","Hexagonal Architecture","Clean Architecture","Onion Architecture","Ports and Adapters","Functional Core, Imperative Shell","Event Storming"]
FEATURES={635+i:n for i,n in enumerate(NAMES)}
RELIABILITY=set(range(635,643));SCHED=set(range(643,648));DELIVERY=set(range(648,658));PATTERNS=set(range(658,671));DOMAIN=set(range(671,685))
DISCLAIMER="Architecture decision support only. Validate assumptions with owners, load/failure tests, security review, operational evidence and rollback plans before deployment."

def _num(x,name,default=None):
    if x is None:return default
    if isinstance(x,bool) or not isinstance(x,(int,float)):raise ValueError(f'{name} must be numeric')
    return float(x)
def _ev(conf,unknowns):return {'confidence':conf,'unknowns':unknowns}

def _base(fid,d):
    if fid not in FEATURES:raise ValueError('feature_id must be 635-684')
    if not d.get('system') or not d.get('decision_owner'):raise ValueError('system and decision_owner are required')
    return {'feature_id':fid,'concept':FEATURES[fid],'system':d['system'],'decision_owner':d['decision_owner'],'assumptions':d.get('assumptions',[]),'unknowns':d.get('unknowns',[]),'review_required':True,'disclaimer':DISCLAIMER}

# ---------------------------------------------------------- shared: reliability
def _sli_windows(d):
    windows=d.get('windows',[])
    if not windows or not d.get('services'):raise ValueError('windows and services are required')
    results=[]
    for w in windows:
        total=_num(w.get('total'),'total',0);good=_num(w.get('good'),'good',0);target=_num(w.get('target'),'target',0)
        if total<=0 or not 0<=good<=total or not 0<target<=1:raise ValueError('invalid SLI window')
        actual=good/total;allowed=round(total*(1-target),12);bad=total-good
        results.append({'name':w.get('name'),'actual_sli':actual,'target':target,'allowed_bad_events':allowed,'observed_bad_events':bad,'budget_remaining':allowed-bad,'burn_ratio':bad/allowed if allowed else None})
    return results

def _row635(d,g):
    verdicts=[{**w,'meets_target':w['actual_sli']>=w['target']} for w in g['sli_windows']]
    compliant=sum(1 for v in verdicts if v['meets_target'])
    return {'slo_assessment':verdicts,'compliant_window_fraction':compliant/len(verdicts) if verdicts else None,'evaluation':_ev(.8,['window data is attested, not scraped from monitoring'])}
def _row636(d,g):
    rows=[]
    for w in g['sli_windows']:
        burn=w['burn_ratio'];exhausted=w['budget_remaining']<=0
        projection=None
        if w['observed_bad_events']>0 and w['allowed_bad_events']>0:
            projection=w['allowed_bad_events']/w['observed_bad_events']
        rows.append({'window':w['name'],'burn_ratio':burn,'classification':'exhausted' if exhausted else 'fast_burn' if burn and burn>0.5 else 'sustainable','projected_windows_to_exhaustion_at_current_rate':projection,'fast_burn_alert':bool(burn and burn>0.5)})
    return {'error_budget_policy':rows,'any_fast_burn_alert':any(r['fast_burn_alert'] for r in rows),'evaluation':_ev(.8,['burn classification uses the supplied window only; multi-window alerting needs longer history'])}
def _row637(d,g):
    roles=[str(r).lower() for r in d.get('incident_roles',[])]
    required={'commander':'commander','communications':'comms','scribe':'scribe'}
    coverage={k:any(v in r for r in roles) for k,v in required.items()}
    timeline=d.get('timeline',[]);durations=[]
    for t in timeline:
        if isinstance(t,dict):
            det=_num(t.get('detected_to_ack_minutes'),'x');fix=_num(t.get('ack_to_resolve_minutes'),'x')
            if det is not None or fix is not None:durations.append({'incident':t.get('id'),'mtta_minutes':det,'mttr_minutes':fix})
    mtta=[x['mtta_minutes'] for x in durations if x['mtta_minutes'] is not None]
    return {'role_coverage':coverage,'role_gaps':sorted(k for k,v in coverage.items() if not v),'incident_metrics':durations,'mean_time_to_ack_minutes':sum(mtta)/len(mtta) if mtta else None,'severity_model':d.get('severity_model','undeclared'),'evaluation':_ev(.7 if mtta else .5,['no timeline metrics supplied; response performance unknown'] if not mtta else [])}
def _row638(d,g):
    items=d.get('action_items',[]);owned=[i for i in items if isinstance(i,dict) and i.get('owner')]
    factors=d.get('contributing_factors',[])
    return {'contributing_factors':factors,'action_items':items,'action_items_with_owners':len(owned),'unowned_action_items':len(items)-len(owned),'blameless_structure':bool(d.get('timeline') is not None and factors is not None),'followup_tracking':d.get('tracking','undeclared'),'evaluation':_ev(.7,['root causes are hypotheses ranked by evidence, not proof'])}
def _row639(d,g):
    steps=d.get('runbook_steps',[]);alerts=d.get('alerts',[])
    indexed=[{'position':i+1,'step':s} for i,s in enumerate(steps)]
    alert_names={str(a.get('name')) if isinstance(a,dict) else str(a) for a in alerts}
    covered={str(a.get('name')) if isinstance(a,dict) else str(a) for a in alerts if isinstance(a,dict) and a.get('runbook')}
    return {'runbook_steps':indexed,'step_count':len(steps),'alert_names':sorted(alert_names),'alerts_with_runbook_link':sorted(covered),'alerts_without_runbook':sorted(alert_names-covered),'coverage_complete':alert_names==covered if alert_names else None,'evaluation':_ev(.7,['steps are reviewed for structure, not executed against the live system'])}
def _row640(d,g):
    people=d.get('on_call',[]);weeks=int(_num(d.get('rotation_weeks'),'rotation_weeks',4) or 4)
    if not people:return {'rotation_schedule':[],'fairness_spread_shifts':None,'coverage_gaps':['no on-call people supplied'],'evaluation':_ev(.3,['on_call roster empty'])}
    schedule=[]
    for w in range(weeks):schedule.append({'week':w+1,'primary':people[w%len(people)],'secondary':people[(w+1)%len(people)] if len(people)>1 else None})
    counts=defaultdict(int)
    for s in schedule:counts[s['primary']]+=1
    spread=max(counts.values())-min(counts.values())
    return {'rotation_schedule':schedule,'shifts_per_person':dict(counts),'fairness_spread_shifts':spread,'single_point_of_failure':len(people)==1,'evaluation':_ev(.75,['timezone and holiday constraints not modeled'])}
def _row641(d,g):
    series=d.get('usage_series',[]);limit=_num(d.get('capacity_limit'),'capacity_limit')
    out={'capacity_forecast':d.get('capacity_forecast',[]),'capacity_limit':limit}
    if isinstance(series,list) and len(series)>=2 and all(isinstance(x,(int,float)) for x in series):
        n=len(series);xs=list(range(n));mx=sum(xs)/n;my=sum(series)/n
        sxx=sum((x-mx)**2 for x in xs);sxy=sum((x-mx)*(y-my) for x,y in zip(xs,series))
        slope=sxy/sxx if sxx else 0.0;intercept=my-slope*mx
        next_value=intercept+slope*n
        days=None
        if limit and slope>0:days=(limit-series[-1])/slope
        out.update({'trend':{'slope_per_period':slope,'intercept':intercept,'next_period_estimate':next_value},'periods_to_capacity_limit':days,'exhaustion_imminent':bool(days is not None and days<30)})
        conf=.7;unknown=['linear trend only; seasonality not modeled']
    else:conf=.4;unknown=['usage_series (2+ numeric points) not supplied; no trend computed']
    out['evaluation']=_ev(conf,unknown);return out
def _row642(d,g):
    options=d.get('cost_options',[]);ranked=[];total_waste=0.0
    for o in options:
        if isinstance(o,dict):
            cost=_num(o.get('monthly_cost'),'monthly_cost',0) or 0;util=_num(o.get('utilization'),'utilization')
            waste=cost*(1-util) if util is not None and 0<=util<=1 else None
            if waste:total_waste+=waste
            ranked.append({'option':o.get('name'),'monthly_cost':cost,'utilization':util,'estimated_monthly_waste':waste})
    ranked.sort(key=lambda r:-(r['estimated_monthly_waste'] or 0))
    return {'cost_options':ranked,'total_estimated_monthly_waste':total_waste if any(r['estimated_monthly_waste'] for r in ranked) else None,'rightsizing_recommended_for':[r['option'] for r in ranked if r['utilization'] is not None and r['utilization']<.3],'evaluation':_ev(.7 if ranked else .4,['cost options not itemized'] if not ranked else ['utilization figures are attested averages'])}

# ---------------------------------------------------------- shared: scheduling
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
def _sched_ctx(d):
    jobs=d.get('jobs',[])
    if not jobs:raise ValueError('jobs are required')
    ids=[j.get('id') for j in jobs]
    if None in ids or len(set(ids))!=len(ids):raise ValueError('job ids must be unique')
    order=_toposort(ids,d.get('dependencies',[]))
    queued=sorted(jobs,key=lambda j:(-int(j.get('priority',0)),j.get('enqueued_at',''),j['id']))
    return jobs,ids,order,queued

def _row643(d,g):
    jobs,ids,order,queued=g
    workers=int(_num(d.get('resource_limits',{}).get('workers'),'workers',1) or 1)
    capacity=_num(d.get('resource_limits',{}).get('cpu_per_worker'),'cpu_per_worker')
    loads=[0.0]*workers;assignment={};unassigned=[]
    for j in queued:
        need=_num(j.get('cpu'),'cpu',1.0) or 1.0
        placed=False
        for i in sorted(range(workers),key=lambda i:loads[i]):
            if capacity is None or loads[i]+need<=capacity:loads[i]+=need;assignment[j['id']]=f'worker-{i+1}';placed=True;break
        if not placed:unassigned.append(j['id'])
    return {'worker_assignment':assignment,'unassigned_jobs':unassigned,'worker_loads':loads,'packing':'least-loaded first-fit in priority order','evaluation':_ev(.7,['durations unknown; assignment is placement, not a schedule'])}
def _row644(d,g):
    jobs,ids,order,queued=g
    waits=[];clock=0.0;known=True
    for j in queued:
        dur=_num(j.get('duration_seconds'),'duration_seconds')
        if dur is None:known=False
        waits.append({'job':j['id'],'estimated_wait_seconds':clock if known else None})
        clock+=dur or 0.0
    return {'queue_wait_estimates':waits,'total_drain_seconds':clock if known else None,'fairness':'strict priority with FIFO tie-break; low-priority starvation possible','evaluation':_ev(.7 if known else .4,['durations missing; wait times unknown'] if not known else ['single-consumer model'])}
def _row645(d,g):
    jobs,ids,order,queued=g
    deps=d.get('dependencies',[]);indeg={i:0 for i in ids};adj=defaultdict(list)
    for e in deps:adj[e['from']].append(e['to']);indeg[e['to']]+=1
    level={i:0 for i in ids};waves=[]
    for n in order:
        level[n]=1+max((level[p] for p in deps and [e['from'] for e in deps if e['to']==n]),default=-1)
    by=defaultdict(list)
    for n,l in level.items():by[l].append(n)
    waves=[{'wave':l+1,'parallel_jobs':sorted(by[l])} for l in sorted(by)]
    return {'execution_waves':waves,'max_parallelism':max((len(w['parallel_jobs']) for w in waves),default=0),'critical_wave_count':len(waves),'evaluation':_ev(.75,['waves assume unlimited workers'])}
def _row646(d,g):
    jobs,ids,order,queued=g
    dur={j['id']:_num(j.get('duration'),'duration',1.0) or 1.0 for j in jobs}
    preds=defaultdict(list)
    for e in d.get('dependencies',[]):preds[e['to']].append(e['from'])
    dist={}
    for n in order:dist[n]=dur[n]+max((dist[p] for p in preds[n]),default=0.0)
    end=max(dist,key=dist.get);path=[end]
    while preds[path[-1]]:path.append(max(preds[path[-1]],key=lambda p:dist[p]))
    path.reverse()
    return {'critical_path':path,'critical_path_duration':dist[end],'per_job_earliest_finish':dist,'evaluation':_ev(.8,['durations are estimates; the critical path shifts with variance'])}
def _row647(d,g):
    exprs=d.get('cron_expressions',[])
    if not exprs:return {'parsed_schedules':[],'overlapping_schedules':[],'timezone':d.get('timezone','UTC (assumed)'),'evaluation':_ev(.3,['no cron_expressions supplied; schedule semantics unverified'])}
    def parse(e):
        parts=str(e).split()
        if len(parts)!=5:raise ValueError(f'invalid cron expression: {e}')
        def field(p,lo,hi):
            vals=set()
            for seg in p.split(','):
                step=1
                if '/' in seg:seg,st=seg.split('/');step=int(st)
                if seg=='*':rng=range(lo,hi+1)
                elif '-' in seg:a,b=seg.split('-');rng=range(int(a),int(b)+1)
                else:rng=[int(seg)]
                for v in rng:
                    if v<lo or v>hi:raise ValueError(f'cron field out of range in {e}')
                    if (v-lo)%step==0:vals.add(v)
            return vals
        return field(parts[0],0,59),field(parts[1],0,23)
    parsed=[]
    for e in exprs:
        minutes,hours=parse(e);parsed.append({'expression':e,'minutes':sorted(minutes),'hours':sorted(hours),'fires_per_day':len(minutes)*len(hours)})
    overlaps=[]
    for i in range(len(parsed)):
        for j in range(i+1,len(parsed)):
            shared=(set(parsed[i]['minutes'])&set(parsed[j]['minutes'])) and (set(parsed[i]['hours'])&set(parsed[j]['hours']))
            if shared:overlaps.append([parsed[i]['expression'],parsed[j]['expression']])
    return {'parsed_schedules':parsed,'overlapping_schedules':overlaps,'timezone':d.get('timezone','UTC (assumed)'),'evaluation':_ev(.8,['day-of-week and day-of-month fields are validated but not expanded into a calendar'])}

# ---------------------------------------------------------- shared: delivery
def _delivery_ctx(d):
    messages=d.get('messages',[]);policy=d.get('delivery_policy',{})
    if not messages or not policy:raise ValueError('messages and delivery_policy are required')
    seen=set();out=[]
    for m in messages:
        key=m.get('idempotency_key');duplicate=key in seen if key else False
        if key:seen.add(key)
        attempt=int(m.get('attempt',1));base=float(policy.get('base_delay_seconds',1));cap=float(policy.get('max_delay_seconds',60))
        delay=min(cap,base*(2**max(attempt-1,0)))
        out.append({'message_id':m.get('id'),'idempotency_key':key,'duplicate':duplicate,'attempt':attempt,'next_delay_seconds':delay,'destination':'dead_letter' if attempt>=int(policy.get('max_attempts',3)) else 'retry_or_process'})
    return messages,policy,out

def _row648(d,g):
    messages,policy,analysis=g
    events=d.get('events',[])
    state={};versions=[]
    for e in events:
        if not isinstance(e,dict) or 'type' not in e:raise ValueError('events need a type')
        versions.append(e.get('version',1))
        payload=e.get('payload',{})
        if isinstance(payload,dict):
            for k,v in payload.items():state[k]=v
    gaps=[i+1 for i in range(len(versions)-1) if isinstance(versions[i],int) and isinstance(versions[i+1],int) and versions[i+1]!=versions[i]+1]
    return {'replayed_state':state,'event_count':len(events),'version_chain':versions,'version_gaps_after_position':gaps,'snapshot_recommended':len(events)>1000,'evaluation':_ev(.7,['generic payload merge; domain-specific event applicators must confirm semantics'])}
def _row649(d,g):
    messages,policy,analysis=g
    writes=d.get('write_models',[]);reads=d.get('read_models',[])
    lag=_num(d.get('projection_lag_seconds'),'projection_lag_seconds')
    overlap=sorted(set(map(str,writes))&set(map(str,reads)))
    return {'write_models':writes,'read_models':reads,'model_overlap':overlap,'separation_clean':not overlap,'projection_lag_seconds':lag,'staleness_bounded':lag is not None and lag<=5,'evaluation':_ev(.7 if lag is not None else .45,['projection lag not supplied; read staleness unbounded'] if lag is None else [])}
def _row650(d,g):
    messages,policy,analysis=g
    steps=d.get('saga_steps',[]);declared={str(c) for c in d.get('compensations',[])}
    completed=[s.get('id') if isinstance(s,dict) else s for s in steps if not isinstance(s,dict) or s.get('status','completed')=='completed']
    order=list(reversed(completed))
    missing=[s for s in completed if str(s) not in declared]
    return {'completed_steps':completed,'compensation_order':order,'steps_missing_compensation':missing,'saga_safe':not missing,'evaluation':_ev(.75,['compensations must be semantic undo, not exact inverse; business review required'])}
def _row651(d,g):
    messages,policy,analysis=g
    votes=[m for m in messages if str(m.get('phase','')).lower()=='prepared']
    all_prepared=bool(messages) and len(votes)==len(messages)
    return {'participant_count':len(messages),'prepared_count':len(votes),'all_prepared':all_prepared,'blocking_window':'participants hold locks between prepare and the coordinator decision','coordinator_failure_blocks_participants':all_prepared,'requires_participant_timeout':True,'heuristic_resolution_declared':bool(d.get('heuristic_policy')),'evaluation':_ev(.75,['2PC availability cost is structural; consider sagas for cross-service work'])}
def _row652(d,g):
    messages,policy,analysis=g
    keyed=sum(1 for a in analysis if a['idempotency_key'])
    return {'dedup_analysis':analysis,'key_coverage':keyed/len(analysis) if analysis else None,'unkeyed_message_ids':[a['message_id'] for a in analysis if not a['idempotency_key']],'duplicate_suppression':'by idempotency_key within this batch only; persistent dedup store required across restarts','evaluation':_ev(.75 if keyed==len(analysis) else .5,['some messages lack idempotency keys'] if keyed<len(analysis) else [])}
def _row653(d,g):
    messages,policy,analysis=g
    boundaries=d.get('transaction_boundaries',[]);keyed=all(a['idempotency_key'] for a in analysis)
    possible=bool(boundaries) and keyed
    return {'atomic_boundaries':boundaries,'all_messages_keyed':keyed,'exactly_once_feasible':possible,'verdict':'achievable within the declared atomic boundary plus dedup' if possible else 'not achievable end-to-end: add an atomic outbox boundary and idempotency keys','evaluation':_ev(.8,['exactly-once is scoped to the declared boundary; cross-system exactly-once is not claimed'])}
def _row654(d,g):
    messages,policy,analysis=g
    redeliveries=[a for a in analysis if a['attempt']>1]
    dupes=[a for a in analysis if a['duplicate']]
    return {'redelivered_messages':redeliveries,'duplicate_deliveries':len(dupes),'at_least_once_holds':True,'downstream_dedup_required':bool(dupes) or any(not a['idempotency_key'] for a in analysis),'evaluation':_ev(.75,['duplicates are expected under at-least-once; consumers must tolerate them'])}
def _row655(d,g):
    messages,policy,analysis=g
    poison=[a for a in analysis if a['destination']=='dead_letter']
    redrive=d.get('redrive_policy',{});max_redrives=int(_num(redrive.get('max_redrives'),'max_redrives',3) or 3)
    return {'dead_letter_messages':poison,'poison_message_count':len(poison),'redrive_policy':redrive,'redrive_bounded':max_redrives>0,'manual_triage_required':bool(poison),'evaluation':_ev(.75,['DLQ contents need human triage before redrive; automatic redrive of poison messages re-fails'])}
def _row656(d,g):
    messages,policy,analysis=g
    max_attempts=int(policy.get('max_attempts',3))
    budget=sum(float(policy.get('base_delay_seconds',1))*(2**a) for a in range(max_attempts))
    jitter=str(policy.get('jitter','none')).lower()
    return {'per_message_schedule':analysis,'retry_budget_seconds_per_message':min(budget,float(policy.get('max_delay_seconds',60))*max_attempts) if policy.get('max_delay_seconds') else budget,'jitter_mode':jitter,'full_jitter_recommended':jitter in {'none',''},'idempotent_operations_only':True,'evaluation':_ev(.75,['retrying non-idempotent operations can duplicate side effects'])}
def _row657(d,g):
    messages,policy,analysis=g
    base=float(policy.get('base_delay_seconds',1));cap=float(policy.get('max_delay_seconds',60));attempts=int(policy.get('max_attempts',3))
    seq=[min(cap,base*(2**a)) for a in range(attempts)]
    decorrelated=[]
    prev=base
    for _ in range(attempts):prev=min(cap,max(base,prev*3));decorrelated.append(prev)
    return {'exponential_sequence_seconds':seq,'total_worst_case_delay_seconds':sum(seq),'decorrelated_jitter_upper_bounds':decorrelated,'cap_reached_at_attempt':next((i+1 for i,x in enumerate(seq) if x>=cap),None),'evaluation':_ev(.8,['jitter draws are random; bounds shown are upper envelopes'])}

# ---------------------------------------------------------- shared: patterns
def _pattern_ctx(d):
    components=d.get('components',[]);interfaces=d.get('interfaces',[])
    if not components or not interfaces:raise ValueError('components and interfaces are required')
    names={c.get('id') for c in components}
    viol=[]
    for i in interfaces:
        if i.get('consumer') not in names or i.get('provider') not in names:viol.append({'interface':i.get('id'),'violation':'unknown_component'})
        if i.get('consumer')==i.get('provider'):viol.append({'interface':i.get('id'),'violation':'self_dependency'})
    return components,interfaces,names,viol

def _row658(d,g):
    components,interfaces,names,viol=g
    pools=d.get('pools')
    if pools:
        mapping={}
        for p in pools:
            for c in p.get('components',[]):mapping[c]=p.get('id')
        blast=defaultdict(list)
        for p in pools:blast[p.get('id')]=p.get('components',[])
        unassigned=sorted(names-set(mapping))
    else:
        blast={'shared_pool':sorted(names)};unassigned=[]
    worst=max((len(v) for v in blast.values()),default=0)
    return {'failure_pools':dict(blast),'components_without_pool':unassigned,'worst_case_blast_radius_components':worst,'isolation_effective':len(blast)>1 and worst<len(names),'evaluation':_ev(.7 if pools else .4,['no pools declared; everything shares one failure domain'] if not pools else [])}
def _row659(d,g):
    components,interfaces,names,viol=g
    sidecars=[c for c in components if str(c.get('kind','')).lower()=='sidecar']
    concerns=sorted({str(c.get('provides')) for c in sidecars if c.get('provides')})
    return {'sidecar_components':[c.get('id') for c in sidecars],'offloaded_concerns':concerns,'host_coupling':'per-host deployment couples sidecar lifecycle to the workload','platform_alternative':'service mesh when offloaded concerns are fleet-wide','evaluation':_ev(.65 if sidecars else .4,['no component marked kind=sidecar'] if not sidecars else [])}
def _row660(d,g):
    components,interfaces,names,viol=g
    policies=defaultdict(set)
    for i in interfaces:
        for k in ('timeout_ms','retries','circuit_breaker'):
            if i.get(k) is not None:policies[k].add(str(i[k]))
    inconsistent={k:sorted(v) for k,v in policies.items() if len(v)>1}
    return {'egress_policy_sets':{k:sorted(v) for k,v in policies.items()},'inconsistent_policies':inconsistent,'ambassador_centralization_recommended':bool(inconsistent),'evaluation':_ev(.7,['only declared interface policies compared; runtime config not inspected'])}
def _row661(d,g):
    components,interfaces,names,viol=g
    findings=[]
    for i in interfaces:
        req=set(i.get('required_methods',[]));prov=set(i.get('provided_methods',[]))
        if req or prov:
            missing=sorted(req-prov)
            findings.append({'interface':i.get('id'),'missing_methods':missing,'conforms':not missing})
    return {'conformance_findings':findings,'non_conforming_interfaces':[f['interface'] for f in findings if not f['conforms']],'evaluation':_ev(.75 if findings else .45,['declare required_methods/provided_methods on interfaces for conformance checking'] if not findings else [])}
def _row662(d,g):
    components,interfaces,names,viol=g
    direct=len(interfaces)
    facades=[c for c in components if str(c.get('kind','')).lower()=='facade']
    mediated=sum(1 for i in interfaces if i.get('provider') in {c.get('id') for c in facades}) if facades else 0
    reduction=(direct-mediated)/direct if direct else 0
    return {'direct_dependency_edges':direct,'facade_mediated_edges':mediated,'coupling_reduction_ratio':reduction,'facade_components':[c.get('id') for c in facades],'evaluation':_ev(.7 if facades else .45,['no facade component declared; coupling unchanged'] if not facades else ['edge count is a coarse coupling proxy'])}
def _row663(d,g):
    components,interfaces,names,viol=g
    edges=[(i.get('provider'),i.get('consumer')) for i in interfaces]
    fanout=defaultdict(int)
    for p,_ in edges:fanout[p]+=1
    try:_toposort(sorted(names),[{'from':a,'to':b} for a,b in edges]);cycle=False
    except ValueError:cycle=True
    return {'notification_fanout':dict(fanout),'max_fanout':max(fanout.values(),default=0),'notification_cycle_detected':cycle,'cascade_risk':'high' if cycle or max(fanout.values(),default=0)>5 else 'moderate','evaluation':_ev(.7,['synchronous observer chains amplify latency and failure; consider async events'])}
def _row664(d,g):
    components,interfaces,names,viol=g
    strategies=d.get('strategies',[]);contexts=d.get('contexts',[])
    mapped={s.get('context') for s in strategies if isinstance(s,dict)}
    uncovered=[c for c in contexts if c not in mapped]
    has_default=any(isinstance(s,dict) and s.get('default') for s in strategies)
    return {'strategies':strategies,'contexts':contexts,'uncovered_contexts':uncovered,'default_strategy_present':has_default,'dispatch_complete':not uncovered and has_default,'evaluation':_ev(.7 if strategies else .4,['declare strategies with context keys for dispatch validation'] if not strategies else [])}
def _row665(d,g):
    components,interfaces,names,viol=g
    registry=d.get('registered_products',[]);requested=d.get('requested_products',[])
    unknown=[r for r in requested if r not in registry]
    return {'registered_products':registry,'requested_products':requested,'unregistered_requests':unknown,'factory_handles_unknown_type':bool(d.get('unknown_type_error')),'evaluation':_ev(.7 if registry else .4,['no product registry declared'] if not registry else [])}
def _row666(d,g):
    components,interfaces,names,viol=g
    singletons=[c for c in components if str(c.get('kind','')).lower()=='singleton']
    lazy=[c.get('id') for c in singletons if c.get('lazy') and not c.get('thread_safe')]
    return {'singleton_components':[c.get('id') for c in singletons],'lazy_initialization_race_hazards':lazy,'enforcement':'constructor private plus single accessor; DI container single lifetime preferred','testability_warning':'global state harms parallel tests; prefer scoped lifetimes','evaluation':_ev(.7 if singletons else .45,['no singleton components declared'] if not singletons else ['lazy init without thread safety is a real race'])}
def _row667(d,g):
    components,interfaces,names,viol=g
    edges=[{'from':i.get('provider'),'to':i.get('consumer')} for i in interfaces if i.get('provider') in names and i.get('consumer') in names]
    order=_toposort(sorted(names),edges)
    return {'resolution_order':order,'circular_dependencies':False,'structural_violations':viol,'evaluation':_ev(.8,['order is construction-safe given interfaces are the only dependencies'])}
def _row668(d,g):
    components,interfaces,names,viol=g
    framework_calls=[i for i in interfaces if str(i.get('consumer','')).lower() in {'framework','container','runtime'}]
    app_calls_framework=[i for i in interfaces if str(i.get('provider','')).lower() in {'framework','container','runtime'}]
    return {'framework_driven_interfaces':len(framework_calls),'application_driving_framework':len(app_calls_framework),'control_inverted':len(framework_calls)>len(app_calls_framework),'hollywood_principle':'do not call us; we call you - handlers registered, framework dispatches','evaluation':_ev(.65,['interface direction inferred from consumer/provider labels'])}
def _row669(d,g):
    components,interfaces,names,viol=g
    leaks=[]
    for i in interfaces:
        text=' '.join(str(v) for v in i.values()).lower()
        for tok in ('sql','orm','cursor','table','jdbc','mongo'):
            if tok in text:leaks.append({'interface':i.get('id'),'leaked_token':tok});break
    return {'persistence_leakage':leaks,'persistence_ignorant':not leaks,'domain_terms_only':'repository interfaces should speak domain language (find/order), not storage language','evaluation':_ev(.75,['token scan is conservative; review interface signatures for semantic leakage'])}
def _row670(d,g):
    components,interfaces,names,viol=g
    changes=d.get('pending_changes',[])
    rank={'insert':0,'update':1,'delete':2}
    ordered=sorted([c for c in changes if isinstance(c,dict)],key=lambda c:rank.get(str(c.get('kind','')).lower(),3))
    atomic=bool(d.get('single_transaction',True))
    return {'commit_order':[c.get('id') for c in ordered],'ordering_rule':'inserts, then updates, then deletes for referential safety','single_transaction_atomicity':atomic,'rollback_covers_all_changes':atomic,'evaluation':_ev(.7 if changes else .45,['no pending_changes supplied; ordering not exercised'] if not changes else [])}

# ---------------------------------------------------------- shared: domain
def _domain_ctx(d):
    contexts=d.get('contexts',[])
    if not contexts:raise ValueError('contexts are required')
    ids={c.get('id') for c in contexts}
    collisions=[];terms=defaultdict(set)
    for c in contexts:
        for term,meaning in c.get('language',{}).items():terms[term].add(str(meaning))
    for term,meanings in terms.items():
        if len(meanings)>1:collisions.append({'term':term,'meanings':sorted(meanings)})
    events=d.get('domain_events',[])
    invalid=[e for e in events if e.get('context_id') not in ids or not e.get('past_tense_name')]
    return contexts,ids,collisions,events,invalid

def _row671(d,g):
    contexts,ids,collisions,events,invalid=g
    counts={'contexts':len(contexts),'aggregates':len(d.get('aggregates',[])),'entities':len(d.get('entities',[])),'value_objects':len(d.get('value_objects',[])),'domain_events':len(events)}
    empty=[k for k,v in counts.items() if v==0]
    return {'model_element_counts':counts,'unpopulated_element_kinds':empty,'tactical_model_completeness':not empty,'evaluation':_ev(.7,['element kinds counted, not validated against domain expert intent'])}
def _row672(d,g):
    contexts,ids,collisions,events,invalid=g
    models=defaultdict(set)
    for c in contexts:
        for m in c.get('models',[]):models[str(m)].add(c.get('id'))
    shared={m:sorted(o) for m,o in models.items() if len(o)>1}
    mappings=d.get('context_mappings',[])
    classified=[{'pair':[m.get('upstream'),m.get('downstream')],'relationship':m.get('relationship','unclassified')} for m in mappings if isinstance(m,dict)]
    return {'shared_kernel_models':shared,'context_mappings':classified,'unclassified_mappings':sum(1 for c in classified if c['relationship']=='unclassified'),'evaluation':_ev(.7,['shared models demand explicit partnership governance'])}
def _row673(d,g):
    contexts,ids,collisions,events,invalid=g
    glossaries={c.get('id'):len(c.get('language',{})) for c in contexts}
    return {'language_collisions':collisions,'glossary_sizes':glossaries,'collision_free':not collisions,'evaluation':_ev(.8,['collisions block a shared model; resolve per-context meanings before integration'])}
def _row674(d,g):
    contexts,ids,collisions,events,invalid=g
    aggregates=d.get('aggregates',[]);findings=[]
    for a in aggregates:
        if isinstance(a,dict):
            ents=a.get('entities',[]);invariants=a.get('invariants',[])
            refs=a.get('external_references',[])
            by_object=[r for r in refs if isinstance(r,dict)]
            findings.append({'aggregate':a.get('id'),'entity_count':len(ents),'invariant_count':len(invariants),'invariants_declared':bool(invariants),'external_references_by_object':len(by_object),'size_warning':len(ents)>5})
    return {'aggregate_findings':findings,'aggregates_without_invariants':[f['aggregate'] for f in findings if not f['invariants_declared']],'reference_rule':'reference other aggregates by identity only','evaluation':_ev(.7,['invariant enforcement must be verified in code review'])}
def _row675(d,g):
    contexts,ids,collisions,events,invalid=g
    entities=d.get('entities',[]);missing=[e.get('name') for e in entities if isinstance(e,dict) and not e.get('id_field')]
    return {'entities':entities,'entities_without_identity_field':missing,'identity_rule':'equality by stable identity, never by mutable attributes','id_stability':'identity assigned at creation and never changes','evaluation':_ev(.7 if entities else .45,['no entities declared'] if not entities else [])}
def _row676(d,g):
    contexts,ids,collisions,events,invalid=g
    vos=d.get('value_objects',[]);mutable=[v.get('name') for v in vos if isinstance(v,dict) and v.get('mutable')]
    no_eq=[v.get('name') for v in vos if isinstance(v,dict) and not v.get('equality_fields')]
    return {'value_objects':vos,'mutable_value_objects':mutable,'value_objects_without_structural_equality':no_eq,'rules':'immutable, side-effect-free, compared by all constituent values','evaluation':_ev(.7 if vos else .45,['no value objects declared'] if not vos else [])}
def _row677(d,g):
    contexts,ids,collisions,events,invalid=g
    non_past=[e for e in events if e.get('past_tense_name') and str(e['past_tense_name'])[0].islower() is False and not str(e['past_tense_name']).endswith(('ed','d','t','n'))]
    mutable=[e for e in events if e.get('mutable')]
    return {'domain_events':events,'invalid_events':invalid,'non_past_tense_name_candidates':[e.get('past_tense_name') for e in non_past],'mutable_events':mutable,'ordering_metadata_required':True,'evaluation':_ev(.7,['events are facts: past-tense, immutable, ordered within an aggregate stream'])}
def _row678(d,g):
    contexts,ids,collisions,events,invalid=g
    mappings=d.get('context_mappings',[]);translated=[m for m in mappings if isinstance(m,dict) and m.get('translation')]
    untranslated_collisions=[c['term'] for c in collisions if not any(c['term'] in str(m.get('translation','')) for m in translated)]
    return {'context_mappings':mappings,'mappings_with_translation':len(translated),'untranslated_collision_terms':untranslated_collisions,'acl_required':bool(untranslated_collisions),'evaluation':_ev(.7,['an ACL translates models at the boundary so foreign concepts never enter the core domain'])}
def _row679(d,g):
    contexts,ids,collisions,events,invalid=g
    ports=d.get('ports',[]);adapters=d.get('adapters',[])
    violations=[]
    for p in ports:
        if isinstance(p,dict):
            for dep in p.get('depends_on',[]):
                if any(isinstance(a,dict) and a.get('id')==dep for a in adapters):violations.append({'port':p.get('id'),'depends_on_adapter':dep})
    unpaired=[p.get('id') for p in ports if isinstance(p,dict) and not any(isinstance(a,dict) and a.get('port')==p.get('id') for a in adapters)]
    return {'ports':ports,'adapters':adapters,'direction_violations':violations,'ports_without_adapters':unpaired,'dependency_rule':'adapters depend on ports; ports never depend on adapters','evaluation':_ev(.75,['direction checked from declared depends_on edges'])}
def _row680(d,g):
    contexts,ids,collisions,events,invalid=g
    layers=d.get('layers',[])
    rank={'entities':0,'domain':0,'use_cases':1,'application':1,'interface_adapters':2,'infrastructure':3,'frameworks':3}
    violations=[]
    for l in layers:
        if isinstance(l,dict):
            inner=rank.get(str(l.get('name','')).lower())
            for dep in l.get('depends_on',[]):
                outer=rank.get(str(dep).lower())
                if inner is not None and outer is not None and outer>inner:violations.append({'layer':l.get('name'),'illegal_dependency':dep})
    return {'layers':layers,'dependency_rule_violations':violations,'rule':'dependencies point inward only','evaluation':_ev(.75 if layers else .45,['declare layers with depends_on edges for the inward-pointing check'] if not layers else [])}
def _row681(d,g):
    contexts,ids,collisions,events,invalid=g
    layers=d.get('layers',[])
    domain=[l for l in layers if isinstance(l,dict) and str(l.get('name','')).lower() in {'domain','entities','core'}]
    impure=[l.get('name') for l in domain if l.get('depends_on')]
    return {'domain_layers':[l.get('name') for l in domain],'domain_dependencies':impure,'domain_is_dependency_free':not impure,'onion_rule':'the domain core depends on nothing outward; infrastructure depends inward','evaluation':_ev(.75 if layers else .45,['declare layers to verify the dependency-free core'] if not layers else [])}
def _row682(d,g):
    contexts,ids,collisions,events,invalid=g
    ports=d.get('ports',[]);adapters=d.get('adapters',[])
    port_ids={p.get('id') for p in ports if isinstance(p,dict)}
    paired={a.get('port') for a in adapters if isinstance(a,dict)}
    return {'ports':ports,'adapters':adapters,'ports_without_adapters':sorted(port_ids-paired),'adapters_without_ports':sorted(paired-port_ids),'pairing_complete':port_ids==paired and bool(port_ids),'evaluation':_ev(.75,['every port needs at least one adapter and every adapter serves a port'])}
def _row683(d,g):
    contexts,ids,collisions,events,invalid=g
    components=d.get('components',[])
    core=[c for c in components if isinstance(c,dict) and str(c.get('region','')).lower()=='core']
    impure=[c.get('id') for c in core if c.get('side_effects')]
    shell=[c.get('id') for c in components if isinstance(c,dict) and str(c.get('region','')).lower()=='shell']
    return {'functional_core_components':[c.get('id') for c in core],'side_effects_inside_core':impure,'imperative_shell_components':shell,'purity_rule':'all effects live in the shell; the core is pure and trivially testable','evaluation':_ev(.7 if components else .4,['declare components with region=core/shell for purity analysis'] if not components else [])}
def _row684(d,g):
    contexts,ids,collisions,events,invalid=g
    storm=d.get('event_storm',[])
    seqs=[s.get('sequence') for s in storm if isinstance(s,dict) and s.get('sequence') is not None]
    ordered=seqs==sorted(seqs)
    produced={s.get('produces') for s in storm if isinstance(s,dict) and s.get('produces')}
    event_names={e.get('past_tense_name') for e in events}
    orphan_commands=sorted({s['command'] for s in storm if isinstance(s,dict) and s.get('command') and not s.get('produces')})
    return {'event_storm_entries':storm,'chronologically_ordered':ordered,'commands_without_produced_events':orphan_commands,'unmatched_domain_events':sorted(event_names-produced) if produced else [],'hotspots':d.get('hotspots',[]),'evaluation':_ev(.7,['storming output is collaborative discovery, not settled design'])}

ROW_FUNCS={635:_row635,636:_row636,637:_row637,638:_row638,639:_row639,640:_row640,641:_row641,642:_row642,643:_row643,644:_row644,645:_row645,646:_row646,647:_row647,648:_row648,649:_row649,650:_row650,651:_row651,652:_row652,653:_row653,654:_row654,655:_row655,656:_row656,657:_row657,658:_row658,659:_row659,660:_row660,661:_row661,662:_row662,663:_row663,664:_row664,665:_row665,666:_row666,667:_row667,668:_row668,669:_row669,670:_row670,671:_row671,672:_row672,673:_row673,674:_row674,675:_row675,676:_row676,677:_row677,678:_row678,679:_row679,680:_row680,681:_row681,682:_row682,683:_row683,684:_row684}

def architecture_support_635_684(fid:int,data:dict[str,Any])->dict[str,Any]:
    o=_base(fid,data)
    if fid in RELIABILITY:
        g={'sli_windows':_sli_windows(data)}
        o.update({'services':data['services'],'sli_windows':g['sli_windows'],'alerts':data.get('alerts',[]),'incident_roles':data.get('incident_roles',[]),'timeline':data.get('timeline',[]),'runbook_steps':data.get('runbook_steps',[]),'on_call':data.get('on_call',[]),'capacity_forecast':data.get('capacity_forecast',[]),'cost_options':data.get('cost_options',[]),'boundary':'Analysis and preparation only. No alert, page, remediation, capacity purchase or cost change executes here. Blameless review separates observed facts, contributing conditions and follow-up ownership.'})
    elif fid in SCHED:
        g=_sched_ctx(data)
        o.update({'dag_order':g[2],'queue_order':[j['id'] for j in g[3]],'jobs':g[0],'cron_expressions':data.get('cron_expressions',[]),'resource_limits':data.get('resource_limits',{}),'events':data.get('events',[]),'boundary':'Produces a deterministic plan only. It does not enqueue, execute, cancel or schedule jobs. Operators validate timezone, overlap, fairness, quotas, dependencies, retries and cancellation.'})
    elif fid in DELIVERY:
        g=_delivery_ctx(data)
        o.update({'delivery_analysis':g[2],'delivery_semantics':g[1].get('semantics'),'transaction_boundaries':data.get('transaction_boundaries',[]),'compensations':data.get('compensations',[]),'event_versions':data.get('event_versions',[]),'boundary':'Simulation only. Exactly-once is not claimed end-to-end without atomic boundaries and deduplication. No transaction, retry, publish, compensation or DLQ move executes here.'})
    elif fid in PATTERNS:
        g=_pattern_ctx(data)
        o.update({'components':g[0],'interfaces':g[1],'structural_violations':g[3],'failure_isolation':data.get('failure_isolation',[]),'lifecycle':data.get('lifecycle',{}),'alternatives':data.get('alternatives',[]),'boundary':'Pattern-fit review, not an instruction to force a pattern. Verify ownership, coupling, lifecycle, concurrency, failure isolation, testability and simpler alternatives before implementation.'})
    elif fid in DOMAIN:
        g=_domain_ctx(data)
        o.update({'contexts':g[0],'language_collisions':g[2],'aggregates':data.get('aggregates',[]),'entities':data.get('entities',[]),'value_objects':data.get('value_objects',[]),'domain_events':g[3],'invalid_events':g[4],'context_mappings':data.get('context_mappings',[]),'ports':data.get('ports',[]),'adapters':data.get('adapters',[]),'event_storm':data.get('event_storm',[]),'boundary':'Collaborative domain model, not settled business truth. Domain experts validate language, invariants, aggregate consistency, ownership, context boundaries, mappings, ports and event chronology.'})
    else:raise ValueError('feature_id must be 635-684')
    o.update(ROW_FUNCS[fid](data,g))
    return o
