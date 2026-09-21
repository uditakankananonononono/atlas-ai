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

def _num(d,k,default=None):
    v=d.get(k,default)
    if v is None:return None
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError(f'{k} must be finite')
    return float(v)
def _lst(d,k):
    v=d.get(k,[]);return v if isinstance(v,list) else [v]
def _ev(conf,unknowns):return {'confidence':conf,'unknowns':unknowns}

def _distributed_systems(d):
    services=_lst(d,'services');model=str(d['consistency_model']).lower()
    known={'strong','eventual','causal','linearizable','sequential','session'}
    classified=model if model in known else 'unclassified'
    scenarios=_lst(d,'failure_scenarios')
    coverage=[s for s in ('partition','node_crash','network_delay','clock_skew') if any(str(x).lower().replace(' ','_')==s for x in scenarios)]
    return {'services':services,'service_count':len(services),'consistency_model':d['consistency_model'],'consistency_classification':classified,'failure_scenario_coverage':coverage,'idempotency_declared':bool(d.get('idempotency_strategy')),'partition_behavior':d.get('partition_behavior','undeclared'),'evaluation':_ev(.6 if classified!='unclassified' else .35,['live failure behavior unverified','consistency model is declared, not measured'])}
def _blockchain(d):
    ntype=str(d['network_type']).lower();cons=str(d['consensus']).lower()
    recognized=ntype in {'public','private','consortium','permissioned'}
    finality='probabilistic' if any(x in cons for x in ('pow','proof-of-work','nakamoto')) else 'deterministic' if any(x in cons for x in ('bft','pos','proof-of-stake','tendermint','pbft')) else 'unspecified'
    bt=_num(d,'block_time_seconds');tpb=_num(d,'transactions_per_block')
    throughput=tpb/bt if bt and tpb else None
    return {'network_type':ntype,'consensus':d['consensus'],'state_model':d['state_model'],'network_type_recognized':recognized,'finality_model':finality,'estimated_throughput_tx_per_second':throughput,'trust_assumptions':d.get('trust_assumptions',['majority honesty assumed by default']),'key_custody_declared':bool(d.get('key_custody')),'evaluation':_ev(.55,['throughput is an upper-bound estimate, not benchmarked'] if throughput else ['no block parameters supplied; throughput unknown'])}
def _smart_contract(d):
    fns=_lst(d,'functions');invariants=_lst(d,'invariants')
    findings=[]
    for f in fns:
        if isinstance(f,dict):
            name=f.get('name','unnamed');ac=bool(f.get('access_control'));ec=bool(f.get('external_calls'));sw=bool(f.get('state_writes'))
            if ec and not f.get('reentrancy_guard'):findings.append({'function':name,'risk':'external call without declared reentrancy guard'})
            if sw and not ac:findings.append({'function':name,'risk':'state mutation without declared access control'})
            if ec and sw and f.get('calls_before_writes'):findings.append({'function':name,'risk':'checks-effects-interactions ordering violated'})
    structured=sum(1 for f in fns if isinstance(f,dict))
    return {'functions':fns,'invariants':invariants,'static_risk_findings':findings,'structured_function_count':structured,'invariant_count':len(invariants),'pre_deployment_audit_required':True,'evaluation':_ev(.5+0.3*bool(structured),['findings are from declared attributes only; source-level analysis not performed'] if structured else ['functions are opaque names; no structural risk scan possible'])}
def _zkp(d):
    public=_lst(d,'public_inputs');witness=str(d['witness_definition'])
    leaked=[p for p in public if isinstance(p,str) and p and p in witness]
    setup=str(d.get('setup','unspecified')).lower()
    return {'statement':d['statement'],'public_inputs':public,'witness_definition':witness,'witness_leakage_into_public_inputs':leaked,'separation_valid':not leaked,'setup_model':setup,'trusted_setup_required':setup in {'trusted','groth16','unspecified'},'soundness_error':_num(d,'soundness_error'),'evaluation':_ev(.6,['proof system soundness is assumed from the chosen scheme; no cryptographic audit performed'])}
def _homomorphic(d):
    scheme=str(d['scheme']).lower();ops={str(o).lower() for o in _lst(d,'supported_operations')}
    capability={'paillier':{'add'},'elgamal':{'multiply'},'bfv':{'add','multiply'},'bgv':{'add','multiply'},'ckks':{'add','multiply','approximate'},'fhew':{'add','multiply','bootstrap'},'tfhe':{'add','multiply','bootstrap'}}
    known=capability.get(scheme)
    unsupported=[] if known is None else sorted(ops-known-{'approximate','bootstrap'})
    depth=_num(d,'multiplicative_depth')
    noise={'multiplicative_depth':depth,'noise_budget_status':'unknown_without_parameters' if depth is not None else 'not_modeled'}
    return {'scheme':d['scheme'],'supported_operations':sorted(ops),'scheme_capability':sorted(known) if known else None,'unsupported_requested_operations':unsupported,'noise_budget':noise,'key_management':d['key_management'],'ciphertext_expansion_warning':True,'evaluation':_ev(.55 if known else .3,['scheme unrecognized; capability not verified'] if known is None else ['noise growth depends on unstated ring parameters'])}
def _smpc(d):
    parties=_lst(d,'parties');n=len(parties);model=str(d['threat_model']).lower()
    t=d.get('max_corrupted')
    if t is None:
        feas=None;note='corruption threshold not stated; feasibility unverified'
    else:
        t=int(_num(t and {'v':t} or {},'v') if not isinstance(t,(int,float)) else t)
        need=3*t+1 if 'malicious' in model else 2*t+1
        feas=n>=need;note=f'n={n} vs required {need} for {model} adversary at t={t}'
    return {'parties':parties,'party_count':n,'function':d['function'],'threat_model':d['threat_model'],'max_corrupted':t,'threshold_feasible':feas,'feasibility_note':note,'abort_policy':d.get('abort_policy','undeclared'),'evaluation':_ev(.6 if feas is not None else .35,['security holds only within the stated corruption threshold'])}
def _federated(d):
    clients=_lst(d,'clients');agg=str(d['aggregation']).lower();controls={str(c).lower() for c in _lst(d,'privacy_controls')}
    required={'secure aggregation','differential privacy','client sampling'}
    coverage=sorted(required&controls);missing=sorted(required-controls)
    robust='median' in agg or 'krum' in agg or 'trimmed' in agg
    return {'clients':clients,'client_count':len(clients),'aggregation':d['aggregation'],'privacy_controls':sorted(controls),'privacy_control_coverage':coverage,'privacy_control_gaps':missing,'poisoning_robust_aggregation':robust,'drift_monitoring_declared':bool(d.get('drift_monitoring')),'evaluation':_ev(.55,['privacy leakage is reduced, not eliminated; gradient inversion risk remains without secure aggregation'])}
def _edge(d):
    workloads=_lst(d,'workloads');nodes=_lst(d,'edge_nodes');offline=str(d['offline_policy'])
    placements=[]
    for w in workloads:
        if isinstance(w,dict):
            lat=_num(w,'cloud_latency_ms');edge_lat=_num(w,'edge_latency_ms')
            gain=(lat-edge_lat) if lat is not None and edge_lat is not None else None
            placements.append({'workload':w.get('name','unnamed'),'latency_gain_ms':gain,'place_at_edge':(gain>0) if gain is not None else (True if w.get('data_privacy') else None)})
        else:placements.append({'workload':w,'latency_gain_ms':None,'place_at_edge':None})
    unquantified=sum(1 for p in placements if p['latency_gain_ms'] is None)
    return {'workload_placements':placements,'edge_nodes':nodes,'offline_policy':offline,'offline_capable':offline.lower() not in {'none',''},'cloud_reconciliation':d.get('reconciliation','undeclared'),'evaluation':_ev(.6 if not unquantified else .4,[f'{unquantified} workloads lack latency measurements'] if unquantified else ['placement ignores bandwidth and power costs not supplied'])}
def _iot(d):
    devices=_lst(d,'devices');protocols=_lst(d,'protocols');boundaries=_lst(d,'trust_boundaries')
    lifecycle={'identity':bool(d.get('device_identity')),'provisioning':bool(d.get('provisioning')),'update':bool(d.get('update_mechanism')),'telemetry':True,'decommission':bool(d.get('decommission'))}
    gaps=[k for k,v in lifecycle.items() if not v]
    insecure=[p for p in protocols if str(p).lower() in {'telnet','ftp','http','mqtt-no-tls'}]
    return {'devices':devices,'protocols':protocols,'trust_boundaries':boundaries,'lifecycle_coverage':lifecycle,'lifecycle_gaps':gaps,'cleartext_or_legacy_protocols':insecure,'physical_access_threat_noted':bool(d.get('physical_threats')),'evaluation':_ev(.6 if not gaps else .45,[f'lifecycle gaps: {gaps}'] if gaps else ['firmware supply-chain risk not assessed'])}
def _embedded(d):
    mem=_num(d,'memory_budget_bytes');timing=_num(d,'timing_budget_ms')
    comps=_lst(d,'components');used=sum(_num(c,'memory_bytes',0) or 0 for c in comps if isinstance(c,dict))
    wcet=sum(_num(c,'wcet_ms',0) or 0 for c in comps if isinstance(c,dict))
    structured=any(isinstance(c,dict) for c in comps)
    return {'mcu':d['mcu'],'memory_budget_bytes':mem,'memory_allocated_bytes':used if structured else None,'memory_headroom_bytes':(mem-used) if structured else None,'memory_over_budget':bool(structured and used>mem),'timing_budget_ms':timing,'wcet_total_ms':wcet if structured else None,'timing_over_budget':bool(structured and wcet>timing),'watchdog_declared':bool(d.get('watchdog')),'update_recovery_path':d.get('update_recovery','undeclared'),'evaluation':_ev(.6 if structured else .35,['components not itemized; budgets unallocated'] if not structured else ['static allocation only; interrupt latency not modeled'])}
def _safety_critical(d):
    hazards=_lst(d,'hazards');target=str(d['safety_integrity_target']).upper()
    reqs=_lst(d,'safety_requirements')
    traced=set()
    for r in reqs:
        if isinstance(r,dict):
            for h in _lst(r,'mitigates'):traced.add(h)
    names=[h.get('name') if isinstance(h,dict) else h for h in hazards]
    untraced=[h for h in names if h not in traced] if reqs else names
    sil_ok=target in {'SIL1','SIL2','SIL3','SIL4','ASIL-A','ASIL-B','ASIL-C','ASIL-D'} or target.startswith('SIL')
    return {'hazards':hazards,'safety_integrity_target':d['safety_integrity_target'],'target_notation_recognized':sil_ok,'safety_requirements':reqs,'untraced_hazards':untraced,'traceability_complete':not untraced,'residual_risk_authority':d.get('residual_risk_authority','unassigned'),'evaluation':_ev(.6 if not untraced else .4,['certification requires independent assessment; this is a traceability check only'])}
def _formal(d):
    props=_lst(d,'properties');results=_lst(d,'proof_results')
    verdicts={'verified':0,'falsified':0,'unknown':0}
    for r in results:
        v=str(r.get('verdict') if isinstance(r,dict) else r).lower()
        verdicts[v if v in verdicts else 'unknown']+=1
    bound=d.get('bound') or d.get('depth')
    return {'specification':d['specification'],'properties':props,'property_count':len(props),'model':d['model'],'proof_verdicts':verdicts if results else None,'bounded_scope':bound,'counterexamples_returned':verdicts['falsified'] if results else None,'evaluation':_ev(.65 if results else .4,['no proof results supplied; properties unverified'] if not results else ['bounded model checking does not prove unbounded behavior'])}
def _static(d):
    rules=_lst(d,'rules');targets=_lst(d,'targets');findings=_lst(d,'findings')
    hist={}
    open_count=0
    for f in findings:
        if isinstance(f,dict):
            sev=str(f.get('severity','unknown')).lower();hist[sev]=hist.get(sev,0)+1
            if not f.get('suppressed'):open_count+=1
    return {'rules':rules,'rule_count':len(rules),'targets':targets,'severity_histogram':hist if findings else None,'open_findings':open_count if findings else None,'findings_are_candidates_not_proven_defects':True,'baseline_versioned':bool(d.get('baseline_version')),'evaluation':_ev(.6 if findings else .4,['no findings supplied; analysis not yet run'] if not findings else ['suppressions and false positives require human triage'])}
def _dynamic(d):
    targets=_lst(d,'targets');instr=_lst(d,'instrumentation');cov=d.get('coverage')
    executed=total=None
    if isinstance(cov,dict):
        executed=_num(cov,'executed_paths');total=_num(cov,'total_paths')
    ratio=(executed/total) if executed and total else None
    return {'targets':targets,'instrumentation':instr,'path_coverage_ratio':ratio,'executed_paths':executed,'total_paths':total,'unexecuted_behavior':'unknown','environment_representative':bool(d.get('production_like')),'evaluation':_ev(.6 if ratio is not None else .4,['coverage not supplied; unexecuted behavior remains unknown'] if ratio is None else ['observed behavior is environment-specific'])}
def _fuzzing(d):
    oracles=_lst(d,'oracles');crashes=_lst(d,'crashes');corpus=_lst(d,'corpus')
    seen={};unique=[]
    for c in crashes:
        key=str(c.get('stack_hash') if isinstance(c,dict) else c)
        seen[key]=seen.get(key,0)+1
        if seen[key]==1:unique.append(key)
    repro=[str(c.get('stack_hash') if isinstance(c,dict) else c) for c in crashes if isinstance(c,dict) and c.get('reproducible')]
    return {'target':d['target'],'input_model':d['input_model'],'oracles':oracles,'oracle_count':len(oracles),'corpus_size':len(corpus),'crash_clusters':{'unique':len(unique),'total':len(crashes),'duplicates':len(crashes)-len(unique)},'reproducible_crashes':len(repro),'minimization_pipeline':bool(d.get('minimizer')),'evaluation':_ev(.65 if crashes else .5,['no crash data supplied; campaign results pending'] if not crashes else ['dedup is by supplied stack hash; root-cause grouping may differ'])}
def _pbt(d):
    props=_lst(d,'properties');gens=_lst(d,'generators')
    paired=sum(1 for p in props if isinstance(p,dict) and p.get('generator')) if any(isinstance(p,dict) for p in props) else min(len(props),len(gens))
    unpaired=len(props)-paired
    return {'properties':props,'generators':gens,'property_count':len(props),'paired_properties':paired,'unpaired_properties':unpaired,'coverage_complete':unpaired==0,'shrink_enabled':bool(d.get('shrink',True)),'seed':d.get('seed'),'runs_per_property':int(_num(d,'runs',100) or 100),'evaluation':_ev(.6 if unpaired==0 else .4,[f'{unpaired} properties lack a generator'] if unpaired else ['generation quality determines bug-finding power; not measured here'])}
def _unit(d):
    units=_lst(d,'units');cases=_lst(d,'cases')
    kinds={'positive':0,'boundary':0,'error':0,'unclassified':0}
    for c in cases:
        k=str(c.get('kind') if isinstance(c,dict) else 'unclassified').lower()
        kinds[k if k in kinds else 'unclassified']+=1
    classified=sum(kinds[k] for k in ('positive','boundary','error'))
    per_unit=len(cases)/len(units) if units else 0
    balanced=classified>0 and all(kinds[k]>0 for k in ('positive','boundary','error'))
    return {'units':units,'case_count':len(cases),'cases_per_unit':per_unit,'case_kinds':kinds,'positive_boundary_error_balance':balanced,'deterministic_fixtures':bool(d.get('deterministic',True)),'evaluation':_ev(.65 if balanced else .45,['cases unclassified by kind; balance unverified'] if classified==0 else ['assertion strength not analyzed'])}
def _integration(d):
    comps=_lst(d,'components');contracts=_lst(d,'contracts')
    pairs=[(a,b) for i,a in enumerate(comps) for b in comps[i+1:]]
    covered=set()
    for c in contracts:
        if isinstance(c,dict) and c.get('between'):
            covered.add(tuple(sorted(c['between'])))
    coverage=None
    if covered and all(not isinstance(x,dict) for x in comps):
        coverage=len([p for p in pairs if tuple(sorted(p)) in covered])/len(pairs) if pairs else 1.0
    return {'components':comps,'contracts':contracts,'component_pair_count':len(pairs) if all(not isinstance(x,dict) for x in comps) else None,'contract_coverage_ratio':coverage,'version_skew_tested':bool(d.get('version_skew')),'failure_paths_exercised':bool(d.get('failure_injection')),'evaluation':_ev(.6 if coverage else .4,['contract-to-pair mapping not supplied; coverage unmeasured'] if coverage is None else ['consumer-driven contract freshness not verified'])}
def _e2e(d):
    journeys=_lst(d,'journeys');env=str(d['environment']).lower()
    critical=sum(1 for j in journeys if isinstance(j,dict) and j.get('critical')) if any(isinstance(j,dict) for j in journeys) else None
    prod_like=any(k in env for k in ('prod','staging','preprod'))
    return {'journeys':journeys,'journey_count':len(journeys),'critical_journeys':critical,'environment':d['environment'],'production_like_environment':prod_like,'data_fidelity':d.get('data_fidelity','undeclared'),'replaces_lower_levels':False,'evaluation':_ev(.6 if prod_like else .4,['environment is not production-like; results may not transfer'] if not prod_like else ['journey criticality not annotated'] if critical is None else ['flake rate not supplied'])}
def _performance(d):
    scenarios=_lst(d,'scenarios');slos=_lst(d,'slos');samples=_lst(d,'latency_samples_ms')
    out={'scenarios':scenarios,'slos':slos}
    conf=.4;unknown=['no latency samples supplied; percentiles unmeasured']
    if samples:
        xs=sorted(_num({'v':x},'v') for x in samples)
        def pct(p):
            k=(len(xs)-1)*p/100;f=math.floor(k);c=math.ceil(k)
            return xs[int(k)] if f==c else xs[f]*(c-k)+xs[c]*(k-f)
        p50,p95,p99=pct(50),pct(95),pct(99)
        out['latency_percentiles_ms']={'p50':p50,'p95':p95,'p99':p99}
        checks=[]
        for s in slos:
            m=__import__('re').match(r'p(\d+)\s*<\s*(\d+(?:\.\d+)?)\s*(ms|s)',str(s))
            if m:
                limit=float(m.group(2))*(1000 if m.group(3)=='s' else 1)
                val={50:p50,95:p95,99:p99}.get(int(m.group(1)))
                if val is not None:checks.append({'slo':s,'measured_ms':val,'limit_ms':limit,'met':val<limit})
        out['slo_compliance']=checks;conf=.7;unknown=['single-run samples; variance across runs unmeasured']
    out['reproducible_scenario']=bool(d.get('seed') or d.get('fixture'));out['evaluation']=_ev(conf,unknown)
    return out
def _load(d):
    rate=_num(d,'arrival_rate');dur=_num(d,'duration_seconds');cap=_num(d,'capacity_target')
    lat=_num(d,'mean_latency_seconds')
    offered=rate*dur
    concurrency=rate*lat if lat else None
    saturation=rate/cap if cap else None
    return {'arrival_rate_per_second':rate,'duration_seconds':dur,'offered_requests':offered,'required_concurrency_littles_law':concurrency,'capacity_target_per_second':cap,'saturation_ratio':saturation,'over_capacity':bool(saturation and saturation>1),'stop_criteria_declared':bool(d.get('stop_criteria')),'authorization_confirmed':bool(d.get('authorized_target')),'evaluation':_ev(.65 if lat else .45,['mean latency not supplied; Little\'s law concurrency unknown'] if not lat else ['steady-state arrival assumed; burstiness not modeled'])}
def _chaos(d):
    steady=str(d['steady_state']);exp=d.get('experiment');abort=_lst(d,'abort_conditions')
    measurable=any(ch.isdigit() for ch in steady) or bool(d.get('steady_state_metric'))
    scope=str(exp.get('scope') if isinstance(exp,dict) else d.get('scope',''))
    return {'steady_state_hypothesis':steady,'hypothesis_measurable':measurable,'experiment':exp,'blast_radius':scope or 'undeclared','abort_conditions':abort,'abort_conditions_present':bool(abort),'approval_recorded':bool(d.get('approval_id')),'rollback_evidence':bool(d.get('rollback_plan')),'evaluation':_ev(.6 if measurable and abort else .35,['steady-state hypothesis is not measurable'] if not measurable else [] + (['no abort conditions declared'] if not abort else []))}
def _ci(d):
    stages=[str(s).lower() for s in _lst(d,'stages')];checks=_lst(d,'required_checks')
    order=['build','test','package','publish']
    positions=[stages.index(s) for s in order if s in stages]
    ordered=positions==sorted(positions)
    gates={'tests':any('test' in str(c).lower() for c in checks),'security':any('sec' in str(c).lower() or 'scan' in str(c).lower() for c in checks),'provenance':any('prov' in str(c).lower() or 'sign' in str(c).lower() for c in checks)}
    return {'stages':stages,'stage_order_valid':ordered,'required_checks':checks,'gate_coverage':gates,'gate_gaps':sorted(k for k,v in gates.items() if not v),'reproducible_build':bool(d.get('reproducible')),'evaluation':_ev(.6 if ordered else .4,['stage order violates build->test->package->publish'] if not ordered else ['security/provenance gates recommended'] if not all(gates.values()) else [])}
def _cd(d):
    envs=_lst(d,'environments');policy=d.get('promotion_policy');rollback=d.get('rollback')
    gates=_lst(d,'promotion_gates')
    return {'environments':envs,'promotion_path_length':len(envs),'promotion_policy':policy,'per_environment_gates':gates,'immutable_artifacts':bool(d.get('immutable_artifacts')),'rollback_defined':bool(rollback),'rollback_tested':bool(d.get('rollback_tested')),'health_checks_between_promotions':bool(d.get('health_checks')),'evaluation':_ev(.6 if rollback else .3,['rollback undefined; deployment is one-way'] if not rollback else ['rollback untested'] if rollback and not d.get('rollback_tested') else [])}
def _iac(d):
    resources=_lst(d,'resources');declared=d.get('declared_state');observed=d.get('observed_state')
    drift=None
    if isinstance(declared,list) and isinstance(observed,list):
        drift=sorted(set(map(str,declared))^set(map(str,observed)))
    plaintext=[]
    for r in resources:
        text=str(r)
        if ('password' in text.lower() or 'secret' in text.lower()) and 'vault:' not in text and 'ref:' not in text:plaintext.append(str(r)[:60])
    return {'resources':resources,'resource_count':len(resources),'state_backend':d['state_backend'],'plan_review':d['plan_review'],'state_locking_declared':bool(d.get('state_locking')),'drift_detected':drift,'plaintext_secret_candidates':plaintext,'module_reuse':bool(d.get('modules')),'evaluation':_ev(.6 if drift is not None else .45,['no declared/observed state supplied; drift unmeasured'] if drift is None else ['plan output not independently reviewed here'])}
def _config_mgmt(d):
    config=d.get('configuration');schema=d.get('schema');refs=_lst(d,'secret_refs')
    typed=isinstance(schema,dict)
    violations=[]
    if typed and isinstance(config,dict):
        for k,spec in schema.items():
            want=spec.get('type') if isinstance(spec,dict) else spec
            if k in config and want in {'int','float','str','bool','list','dict'}:
                ok={'int':int,'float':(int,float),'str':str,'bool':bool,'list':list,'dict':dict}[want]
                v=config[k]
                if not isinstance(v,ok) or (want=='int' and isinstance(v,bool)):violations.append({'key':k,'expected':want,'got':type(v).__name__})
        missing=[k for k,s in schema.items() if isinstance(s,dict) and s.get('required') and k not in config]
    else:missing=[]
    plain=[r for r in refs if isinstance(r,str) and not (r.startswith('vault:') or r.startswith('ref:') or r.startswith('secret:'))]
    return {'configuration':config,'schema':schema,'schema_machine_readable':typed,'type_violations':violations,'missing_required_keys':missing,'secret_refs':refs,'plaintext_secret_refs':plain,'versioned':bool(d.get('version')),'change_audit':bool(d.get('audit_log')),'evaluation':_ev(.65 if typed else .4,['schema not machine-readable; values unvalidated'] if not typed else ['environment overlays not checked'])}
def _container(d):
    workloads=_lst(d,'workloads');checks=[str(c).lower() for c in _lst(d,'health_checks')]
    ratios=[]
    for w in workloads:
        if isinstance(w,dict):
            req=_num(w,'cpu_request');lim=_num(w,'cpu_limit')
            if req and lim:ratios.append({'workload':w.get('name','unnamed'),'limit_to_request_ratio':lim/req})
    over=sum(1 for r in ratios if r['limit_to_request_ratio']>4)
    probes={'readiness':any('readi' in c for c in checks),'liveness':any('live' in c for c in checks),'startup':any('start' in c for c in checks)}
    return {'workloads':workloads,'resources':d['resources'],'limit_request_ratios':ratios if ratios else None,'extreme_limit_request_ratios':over,'probe_coverage':probes,'probe_gaps':sorted(k for k,v in probes.items() if not v),'disruption_budget':bool(d.get('pod_disruption_budget')),'autoscaling_declared':bool(d.get('autoscaling')),'evaluation':_ev(.6 if ratios else .45,['workload resources not itemized'] if not ratios else ['liveness/startup probes recommended'] if not all(probes.values()) else [])}
def _mesh(d):
    services=_lst(d,'services');mtls=str(d.get('mtls','')).lower();policies=_lst(d,'traffic_policies')
    retries=_num(d,'max_retries');timeout=_num(d,'timeout_ms');deadline=_num(d,'deadline_ms')
    budget=None
    if retries is not None and timeout is not None and deadline is not None:
        worst=(1+retries)*timeout;budget={'worst_case_wait_ms':worst,'deadline_ms':deadline,'retry_storm_risk':worst>deadline}
    return {'services':services,'mtls_mode':mtls or 'undeclared','mtls_strict':mtls=='strict','traffic_policies':policies,'retry_budget':budget,'least_privilege_policy':bool(d.get('authorization_policies')),'evaluation':_ev(.6 if budget else .45,['retry/timeout/deadline not all supplied; storm risk unmeasured'] if budget is None else ['mTLS mode not strict'] if mtls!='strict' else [])}
def _gateway(d):
    routes=[str(r) for r in _lst(d,'routes')]
    conflicts=[]
    for i,a in enumerate(routes):
        for b in routes[i+1:]:
            if a.startswith(b.rstrip('*')) or b.startswith(a.rstrip('*')):conflicts.append(sorted([a,b]))
    unique=[list(x) for x in {tuple(c) for c in conflicts}]
    return {'routes':routes,'route_conflicts':unique,'authn':d['authn'],'authz':d['authz'],'authentication_authorization_separated':d.get('authn')!=d.get('authz'),'request_limits_declared':bool(d.get('request_limits')),'schema_validation':bool(d.get('validation')),'evaluation':_ev(.6,['route semantics beyond prefix shape not analyzed'])}
def _discovery(d):
    instances=_lst(d,'instances');ttl=_num(d,'ttl_seconds');interval=_num(d,'health_interval_seconds')
    bound=ttl+(interval or 0) if ttl is not None else None
    healthy=sum(1 for i in instances if not isinstance(i,dict) or i.get('healthy',True))
    return {'instances':instances,'instance_count':len(instances),'healthy_instances':healthy,'health_policy':d['health_policy'],'ttl_seconds':ttl,'staleness_bound_seconds':bound,'deregistration_on_partition':bool(d.get('deregister_on_partition')),'evaluation':_ev(.6 if bound else .4,['health interval not supplied; staleness bound understated'] if bound and interval is None else ['TTL missing; staleness unbounded'] if bound is None else [])}
def _quota(d):
    quotas=_lst(d,'quotas');rows=[]
    over=0
    for q in quotas:
        if isinstance(q,dict):
            limit=_num(q,'limit');used=_num(q,'used')
            head=(limit-used) if limit is not None and used is not None else None
            rows.append({'name':q.get('name'),'limit':limit,'used':used,'headroom':head,'exhausted':bool(head is not None and head<=0)})
            if head is not None and head<=0:over+=1
        else:rows.append({'name':q,'limit':None,'used':None,'headroom':None,'exhausted':None})
    return {'quotas':rows,'period':d['period'],'exhausted_quota_count':over,'atomic_accounting_required':True,'reset_semantics':d.get('reset','period_rollover'),'evaluation':_ev(.65 if any(r['headroom'] is not None for r in rows) else .45,['usage not supplied; headroom unknown'] if not any(r['headroom'] is not None for r in rows) else [])}
def _blue_green(d):
    blue=_lst(d,'blue');green=_lst(d,'green');checks=_lst(d,'switch_checks')
    parity=len(blue)==len(green)
    return {'blue':blue,'green':green,'environment_parity_by_count':parity,'switch_checks':checks,'switch_readiness':bool(checks) and parity,'atomic_switch_declared':bool(d.get('atomic_switch')),'rollback_compatibility':d.get('rollback_compatibility','undeclared'),'evaluation':_ev(.6 if parity else .4,['blue/green size mismatch; parity unverified'] if not parity else ['parity by count only; config drift not checked'])}
def _dark(d):
    hidden=_lst(d,'hidden_paths');policy=str(d.get('side_effect_policy','')).lower()
    isolated=policy in {'disabled','none','off','isolated'}
    return {'hidden_paths':hidden,'hidden_path_count':len(hidden),'side_effect_policy':d['side_effect_policy'],'side_effects_isolated':isolated,'user_visible_effects':not isolated,'separate_side_effect_controls':bool(d.get('side_effect_controls')),'evaluation':_ev(.65 if isolated else .3,['side effects not isolated; hidden code can affect users'] if not isolated else [])}
def _shadow(d):
    redaction=str(d.get('redaction','')).lower()
    redacted=redaction not in {'','none','no','false'}
    return {'source':d['source'],'shadow':d['shadow'],'redaction':d['redaction'],'redaction_enabled':redacted,'shadow_writes_isolated':bool(d.get('writes_disabled',True)),'responses_discarded':bool(d.get('responses_discarded',True)),'async_replay':bool(d.get('async',True)),'evaluation':_ev(.65 if redacted else .3,['redaction not enabled; shadow copies may carry PII'] if not redacted else [])}
def _mirror(d):
    rate=_num(d,'sampling_rate');mirrors=_lst(d,'mirrors')
    if rate is None or not 0<rate<=1:raise ValueError('sampling_rate must be within (0, 1]')
    return {'source':d['source'],'mirrors':mirrors,'sampling_rate':rate,'expected_mirrored_fraction':rate,'backpressure_isolation':bool(d.get('backpressure_isolation')),'privacy_controls':d.get('privacy_controls','undeclared'),'evaluation':_ev(.6,['destination security posture not verified'])}
def _observability(d):
    signals={str(s).lower() for s in _lst(d,'signals')};slos=_lst(d,'slos')
    required={'metrics','logs','traces'}
    gaps=sorted(required-signals)
    return {'signals':sorted(signals),'signal_gaps':gaps,'slos':slos,'slo_count':len(slos),'ownership':d['ownership'],'signals_linked_to_slos':bool(d.get('slo_mapping')),'actionable_debugging_questions':_lst(d,'debugging_questions'),'evaluation':_ev(.65 if not gaps else .45,[f'missing signals: {gaps}'] if gaps else ['SLO-to-signal linkage not mapped'] if not d.get('slo_mapping') else [])}
def _logs(d):
    sources=_lst(d,'sources');retention=_num(d,'retention_days');redaction=str(d.get('redaction','')).lower()
    if retention is None or retention<1:raise ValueError('retention_days must be positive')
    redacted=redaction not in {'','none','no','false'}
    structured=sum(1 for s in sources if isinstance(s,dict) and s.get('structured'))
    return {'sources':sources,'retention_days':retention,'retention_within_bounds':retention<=400,'redaction_enabled':redacted,'structured_source_count':structured,'correlation_ids':bool(d.get('correlation_ids')),'access_control_declared':bool(d.get('access_control')),'evaluation':_ev(.65 if redacted else .35,['redaction disabled; logs may carry secrets/PII'] if not redacted else [])}
def _dashboards(d):
    panels=_lst(d,'panels');refresh=_num(d,'refresh_seconds');slos=_lst(d,'slos')
    linked=sum(1 for p in panels if isinstance(p,dict) and (p.get('slo') or p.get('runbook'))) if any(isinstance(p,dict) for p in panels) else None
    slo_text={str(s).lower() for s in slos}
    named=[str(p).lower() for p in panels if not isinstance(p,dict)]
    coverage=sum(1 for s in slo_text if any(s in n or n in s for n in named)) if slo_text else None
    if refresh is None or refresh<1:raise ValueError('refresh_seconds must be positive')
    return {'panels':panels,'panel_count':len(panels),'audience':d['audience'],'refresh_seconds':refresh,'freshness_bounded':refresh<=300,'panels_linked_to_action':linked,'slo_panel_coverage':coverage,'units_declared':bool(d.get('units')),'evaluation':_ev(.6 if linked else .45,['panels are opaque names; SLO linkage unverified'] if linked is None else ['panels lack runbook/SLO links'] if linked==0 else [])}

SPECIAL={'consensus_algorithm':_consensus,'differential_privacy':_dp,'real_time_systems':_realtime,'circuit_breaker':_breaker,'rate_limiting':_rate,'throttling':_throttle,'canary_deployment':_canary,'distributed_tracing':_trace,'metrics_collection':_metrics,'alerting':_alerts,'feature_flags':_flags,'multi_tenancy':_tenant}
SPECIAL2={'distributed_systems':_distributed_systems,'blockchain_design':_blockchain,'smart_contract_development':_smart_contract,'zero_knowledge_proof':_zkp,'homomorphic_encryption':_homomorphic,'secure_multi_party_computation':_smpc,'federated_learning':_federated,'edge_computing':_edge,'iot_architecture':_iot,'embedded_systems':_embedded,'safety_critical_systems':_safety_critical,'formal_verification':_formal,'static_analysis':_static,'dynamic_analysis':_dynamic,'fuzzing':_fuzzing,'property_based_testing':_pbt,'unit_testing':_unit,'integration_testing':_integration,'end_to_end_testing':_e2e,'performance_testing':_performance,'load_testing':_load,'chaos_engineering':_chaos,'continuous_integration':_ci,'continuous_deployment':_cd,'infrastructure_as_code':_iac,'configuration_management':_config_mgmt,'container_orchestration':_container,'service_mesh':_mesh,'api_gateway':_gateway,'service_discovery':_discovery,'quota_management':_quota,'blue_green_deployment':_blue_green,'dark_launching':_dark,'shadow_traffic':_shadow,'traffic_mirroring':_mirror,'observability':_observability,'log_aggregation':_logs,'dashboards':_dashboards}

def platform_engineering_585_634(method:str,data:dict[str,Any])->dict[str,Any]:
    if method not in METHODS:raise ValueError(f'unsupported method: {method}')
    _validate(method,data)
    if method in SPECIAL:result=SPECIAL[method](data)
    else:result=SPECIAL2[method](data)
    return {'method':method,'capability':NAMES[method],'guidance':GUIDANCE[method],'result':result,'assumptions':data.get('assumptions',[]),'review':{'human_approval_required_for_deployment':True,'verified_in_live_environment':False},'boundary':'Architecture, analysis or test design only. It does not deploy, change infrastructure, handle production traffic, prove security, or certify safety.'}
