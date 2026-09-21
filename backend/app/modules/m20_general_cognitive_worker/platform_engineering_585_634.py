"""Executable architecture review for distributed, secure, testing, delivery and ops rows 585-634."""
from __future__ import annotations
import hashlib, math
from collections import Counter
from typing import Any

METHODS=['consensus_algorithm','distributed_systems','blockchain_design','smart_contract_development','zero_knowledge_proof','homomorphic_encryption','secure_multi_party_computation','differential_privacy','federated_learning','edge_computing','iot_architecture','embedded_systems','real_time_systems','safety_critical_systems','formal_verification','static_analysis','dynamic_analysis','fuzzing','property_based_testing','unit_testing','integration_testing','end_to_end_testing','performance_testing','load_testing','chaos_engineering','continuous_integration','continuous_deployment','infrastructure_as_code','configuration_management','container_orchestration','service_mesh','api_gateway','service_discovery','circuit_breaker','rate_limiting','throttling','quota_management','multi_tenancy','blue_green_deployment','canary_deployment','feature_flags','dark_launching','shadow_traffic','traffic_mirroring','observability','distributed_tracing','metrics_collection','log_aggregation','alerting','dashboards']
NAMES={m:m.replace('_',' ').title() for m in METHODS}

REQUIRED={
'consensus_algorithm':['nodes','fault_model','quorum_size'],'distributed_systems':['services','consistency_model'],'blockchain_design':['network_type','consensus','state_model'],'smart_contract_development':['functions','invariants'],'zero_knowledge_proof':['statement','public_inputs','witness_definition'],'homomorphic_encryption':['scheme','supported_operations','key_management'],'secure_multi_party_computation':['parties','function','threat_model'],'differential_privacy':['epsilon','mechanism','sensitivity'],'federated_learning':['clients','aggregation','privacy_controls'],'edge_computing':['workloads','edge_nodes','offline_policy'],'iot_architecture':['devices','protocols','trust_boundaries'],'embedded_systems':['mcu','memory_budget_bytes','timing_budget_ms'],'real_time_systems':['tasks','scheduling_policy'],'safety_critical_systems':['hazards','safety_integrity_target'],'formal_verification':['specification','properties','model'],'static_analysis':['rules','targets'],'dynamic_analysis':['targets','instrumentation'],'fuzzing':['target','input_model','oracles'],'property_based_testing':['properties','generators'],'unit_testing':['units','cases'],'integration_testing':['components','contracts'],'end_to_end_testing':['journeys','environment'],'performance_testing':['scenarios','slos'],'load_testing':['arrival_rate','duration_seconds','capacity_target'],'chaos_engineering':['steady_state','experiment','abort_conditions'],'continuous_integration':['stages','required_checks'],'continuous_deployment':['environments','promotion_policy','rollback'],'infrastructure_as_code':['resources','state_backend','plan_review'],'configuration_management':['configuration','schema','secret_refs'],'container_orchestration':['workloads','resources','health_checks'],'service_mesh':['services','mtls','traffic_policies'],'api_gateway':['routes','authn','authz'],'service_discovery':['instances','health_policy','ttl_seconds'],'circuit_breaker':['failure_threshold','window_size','open_seconds'],'rate_limiting':['limit','window_seconds','key'],'throttling':['sustained_rate','burst'],'quota_management':['quotas','period'],'multi_tenancy':['isolation_model','tenant_key','shared_resources'],'blue_green_deployment':['blue','green','switch_checks'],'canary_deployment':['steps','success_metrics','rollback_thresholds'],'feature_flags':['flags','owners','expiry_policy'],'dark_launching':['hidden_paths','side_effect_policy'],'shadow_traffic':['source','shadow','redaction'],'traffic_mirroring':['source','mirrors','sampling_rate'],'observability':['signals','slos','ownership'],'distributed_tracing':['spans','propagation_format'],'metrics_collection':['metrics','scrape_or_push'],'log_aggregation':['sources','retention_days','redaction'],'alerting':['rules','routes','runbooks'],'dashboards':['panels','audience','refresh_seconds']}

GUIDANCE={
'consensus_algorithm':'Model safety, liveness, quorum intersection, leader change and stated crash/Byzantine assumptions.',
'distributed_systems':'State consistency, availability, partition behavior, idempotency and failure recovery explicitly.',
'blockchain_design':'Define trust, finality, state transition, fees, upgrades, key custody and chain-specific threats.',
'smart_contract_development':'Check access control, reentrancy, arithmetic, oracle, upgrade and invariant risks before deployment.',
'zero_knowledge_proof':'Separate statement, public inputs and witness; bind transcript/domain and select a trusted-setup model.',
'homomorphic_encryption':'Match supported operations and depth to scheme; track noise, precision and key lifecycle.',
'secure_multi_party_computation':'Fix corruption threshold, honest/malicious model, leakage, abort and output-recipient policy.',
'differential_privacy':'Budget epsilon/delta by composition; calibrate sensitivity and never call anonymization guaranteed.',
'federated_learning':'Treat aggregation, poisoning, drift, privacy leakage, client sampling and secure aggregation separately.',
'edge_computing':'Place work by latency, bandwidth, privacy, power and offline behavior, with cloud reconciliation.',
'iot_architecture':'Inventory identity, provisioning, update, protocol, telemetry, commands, physical access and trust boundaries.',
'embedded_systems':'Budget flash/RAM/CPU/power, interrupts, peripherals, watchdog and update/recovery paths.',
'real_time_systems':'Analyze worst-case execution, deadlines, jitter, priority inversion and schedulability.',
'safety_critical_systems':'Trace hazards to safety requirements, independence, evidence, verification and residual-risk authority.',
'formal_verification':'Define model, assumptions and machine-checkable properties; report bounded scope and counterexamples.',
'static_analysis':'Version rules, suppressions and baselines; distinguish findings from proven defects.',
'dynamic_analysis':'Record executed paths, instrumentation and environment; unexecuted behavior remains unknown.',
'fuzzing':'Specify corpus, generator, oracle, sanitizer, minimization and reproducible crash triage.',
'property_based_testing':'Generate domain-valid data, shrink failures and check universal properties across seeds.',
'unit_testing':'Isolate one unit, deterministic fixtures, positive/boundary/error cases and meaningful assertions.',
'integration_testing':'Exercise real component contracts, version skew, failure paths and data boundaries.',
'end_to_end_testing':'Test critical user journeys in production-like conditions without replacing lower-level tests.',
'performance_testing':'Measure latency distribution, throughput and resource use against stated SLO under reproducible scenarios.',
'load_testing':'Ramp realistic arrivals, observe saturation and errors, define stop criteria and avoid unauthorized targets.',
'chaos_engineering':'Hypothesis-led failure injection with blast radius, abort conditions, approvals and recovery evidence.',
'continuous_integration':'Reproducible build, tests, security, artifact provenance and required gates on every change.',
'continuous_deployment':'Promote immutable artifacts through environments with approvals, health checks and tested rollback.',
'infrastructure_as_code':'Declarative reviewed plans, remote locked state, drift checks, modules and no plaintext secrets.',
'configuration_management':'Typed/versioned config, environment overlays, secret references, validation and change audit.',
'container_orchestration':'Requests/limits, probes, disruption budgets, placement, autoscaling, identity and rollout policy.',
'service_mesh':'Use mTLS identity, least-privilege policy, telemetry and bounded retries/timeouts without retry storms.',
'api_gateway':'Centralize routing, auth, request limits, validation and observability without confusing authentication and authorization.',
'service_discovery':'Use health-aware registration, bounded staleness, TTL and deregistration under partitions.',
'circuit_breaker':'Trip on a bounded window, fail fast while open, probe half-open and preserve fallback semantics.',
'rate_limiting':'Enforce a precise key/window/limit atomically and return explicit retry metadata.',
'throttling':'Shape sustained and burst traffic with queue/drop behavior and fairness.',
'quota_management':'Track consumable allocation by tenant and period with atomic accounting and reset semantics.',
'multi_tenancy':'Enforce identity-derived tenant isolation in data, cache, jobs, logs, keys and resource fairness.',
'blue_green_deployment':'Run two complete environments, validate inactive, switch atomically and preserve rollback compatibility.',
'canary_deployment':'Increase exposure in guarded steps using baseline-comparable metrics and automatic rollback.',
'feature_flags':'Typed flags with owner, audience, safe default, audit, expiry and kill switch.',
'dark_launching':'Deploy hidden code paths with no user-visible effects and separately controlled side effects.',
'shadow_traffic':'Replay redacted copies asynchronously; shadow responses and writes never reach users or production state.',
'traffic_mirroring':'Copy a bounded sample with privacy controls, backpressure isolation and explicit destinations.',
'observability':'Join metrics, logs and traces to SLOs, ownership and actionable debugging questions.',
'distributed_tracing':'Propagate trace context, preserve parentage, sample deliberately and avoid sensitive attributes.',
'metrics_collection':'Define type, unit, labels and ownership; prevent high-cardinality dimensions and preserve scrape health.',
'log_aggregation':'Structure, timestamp, correlate, redact, retain and control access to centralized logs.',
'alerting':'Alert on actionable symptoms with severity, deduplication, routing, runbook and escalation.',
'dashboards':'Design audience-specific SLO and diagnostic panels with units, freshness, ownership and links to action.'}

def _validate(method,d):
    missing=[k for k in REQUIRED[method] if k not in d or d[k] in (None,'',[])];
    if missing: raise ValueError('missing required fields: '+', '.join(missing))

def _consensus(d):
    n=int(d['nodes']); f=int(d.get('faults_tolerated',0)); q=int(d['quorum_size']); model=d['fault_model']; need=3*f+1 if model=='byzantine' else 2*f+1
    return {'nodes':n,'faults_tolerated':f,'minimum_nodes':need,'quorum_size':q,'quorum_intersection':2*q>n,'model_feasible':n>=need and 2*q>n}
def _dp(d):
    e=float(d['epsilon']); sens=float(d['sensitivity']); mech=d['mechanism'];
    if e<=0:raise ValueError('epsilon must be > 0')
    return {'epsilon':e,'delta':float(d.get('delta',0)),'mechanism':mech,'laplace_scale':sens/e if mech=='laplace' else None,'privacy_not_anonymity_guarantee':True}
def _realtime(d):
    rows=[]
    for t in d['tasks']:
        u=float(t['wcet_ms'])/float(t['period_ms']);rows.append({**t,'utilization':u,'deadline_met_by_wcet':float(t['wcet_ms'])<=float(t.get('deadline_ms',t['period_ms']))})
    total=sum(x['utilization'] for x in rows); n=len(rows); policy=d['scheduling_policy']; bound=n*(2**(1/n)-1) if n else 0
    return {'tasks':rows,'total_utilization':total,'rm_sufficient_bound':bound,'sufficient_schedulability':policy!='rate_monotonic' or total<=bound}
def _breaker(d): return {'states':['closed','open','half_open'],'failure_threshold':int(d['failure_threshold']),'window_size':int(d['window_size']),'open_seconds':float(d['open_seconds']),'valid':0<int(d['failure_threshold'])<=int(d['window_size']) and float(d['open_seconds'])>0}
def _rate(d):
    limit=int(d['limit']); window=float(d['window_seconds']);return {'limit':limit,'window_seconds':window,'key':d['key'],'average_rate_per_second':limit/window,'atomic_enforcement_required':True,'retry_after_required':True}
def _throttle(d):
    r=float(d['sustained_rate']);b=float(d['burst']);return {'token_bucket':{'refill_per_second':r,'capacity':b},'burst_duration_at_sustained_seconds':b/r,'queue_policy':d.get('queue_policy','reject')}
def _canary(d):
    steps=[float(x) for x in d['steps']];return {'steps':steps,'monotonic':steps==sorted(steps) and all(0<x<=100 for x in steps),'success_metrics':d['success_metrics'],'rollback_thresholds':d['rollback_thresholds'],'automatic_rollback_required':True}
def _trace(d):
    spans=d['spans'];ids={s['span_id'] for s in spans};roots=[s['span_id'] for s in spans if not s.get('parent_span_id')];orphans=[s['span_id'] for s in spans if s.get('parent_span_id') and s['parent_span_id'] not in ids]
    return {'span_count':len(spans),'root_span_ids':roots,'orphan_span_ids':orphans,'valid_tree':len(roots)==1 and not orphans,'propagation_format':d['propagation_format']}
def _metrics(d):
    bad=[]
    for m in d['metrics']:
        if not m.get('type') or not m.get('unit') or any(x in {'user_id','request_id','email'} for x in m.get('labels',[])):bad.append(m.get('name'))
    return {'metrics':d['metrics'],'invalid_or_high_cardinality_metric_names':bad,'mode':d['scrape_or_push']}
def _alerts(d):
    rows=[]
    for r in d['rules']:rows.append({**r,'actionable':bool(r.get('owner') and r.get('runbook') and r.get('severity') and r.get('condition'))})
    return {'rules':rows,'unactionable_rule_names':[r.get('name') for r in rows if not r['actionable']],'routes':d['routes'],'runbooks':d['runbooks']}
def _flags(d):
    rows=[]
    for f in d['flags']:rows.append({**f,'stale':not bool(f.get('owner') and f.get('expires_at')),'safe_default_present':'default' in f})
    return {'flags':rows,'stale_names':[x.get('name') for x in rows if x['stale']]}
def _tenant(d): return {'isolation_model':d['isolation_model'],'tenant_key':d['tenant_key'],'shared_resources':d['shared_resources'],'required_surfaces':['database','cache','object_store','queues','logs','metrics','keys','rate_limits'],'identity_derived_tenant_required':True}
def _generic(method,d):
    return {'design':{k:d[k] for k in REQUIRED[method]},'risks':d.get('risks',[]),'controls':d.get('controls',[]),'acceptance_criteria':d.get('acceptance_criteria',[]),'evidence':d.get('evidence',[]),'implementation_status':'design_only'}
SPECIAL={'consensus_algorithm':_consensus,'differential_privacy':_dp,'real_time_systems':_realtime,'circuit_breaker':_breaker,'rate_limiting':_rate,'throttling':_throttle,'canary_deployment':_canary,'distributed_tracing':_trace,'metrics_collection':_metrics,'alerting':_alerts,'feature_flags':_flags,'multi_tenancy':_tenant}

def platform_engineering_585_634(method:str,data:dict[str,Any])->dict[str,Any]:
    if method not in METHODS:raise ValueError(f'unsupported method: {method}')
    _validate(method,data); result=SPECIAL.get(method,lambda d:_generic(method,d))(data)
    return {'method':method,'capability':NAMES[method],'guidance':GUIDANCE[method],'result':result,'assumptions':data.get('assumptions',[]),'review':{'human_approval_required_for_deployment':True,'verified_in_live_environment':False},'boundary':'Architecture, analysis or test design only. It does not deploy, change infrastructure, handle production traffic, prove security, or certify safety.'}
