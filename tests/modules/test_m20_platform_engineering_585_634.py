import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.platform_engineering_585_634 import METHODS,REQUIRED,GUIDANCE,platform_engineering_585_634
from app.modules.m20_general_cognitive_worker.routes import router
P=platform_engineering_585_634

def sample(method):
 d={k:f'{k}-value' for k in REQUIRED[method]}
 list_fields={'nodes':[1],'services':['a'],'functions':['f'],'invariants':['i'],'supported_operations':['add'],'parties':['a','b'],'clients':['c'],'privacy_controls':['secure aggregation'],'workloads':['w'],'edge_nodes':['e'],'devices':['d'],'protocols':['mqtt'],'trust_boundaries':['device/cloud'],'tasks':[{'wcet_ms':1,'period_ms':10}],'hazards':['h'],'properties':['p'],'rules':['r'],'targets':['t'],'instrumentation':['asan'],'oracles':['crash'],'generators':['g'],'units':['u'],'cases':['c'],'components':['a'],'contracts':['api'],'journeys':['j'],'scenarios':['s'],'slos':['p95<1s'],'abort_conditions':['errors'],'stages':['test'],'required_checks':['test'],'environments':['staging'],'resources':['r'],'configuration':{'a':1},'secret_refs':['vault:x'],'health_checks':['ready'],'traffic_policies':['timeout'],'routes':['/x'],'instances':['i'],'quotas':[{'name':'api','limit':1}],'shared_resources':['db'],'blue':['v1'],'green':['v2'],'switch_checks':['healthy'],'steps':[1,5,20,100],'success_metrics':['errors'],'rollback_thresholds':['errors>1%'],'flags':[{'name':'x','owner':'o','expires_at':'tomorrow','default':False}],'hidden_paths':['new'],'mirrors':['shadow'],'signals':['metrics'],'slos':['availability'],'spans':[{'span_id':'root'}],'metrics':[{'name':'requests','type':'counter','unit':'requests','labels':['route']}],'sources':['app'],'rules':[{'name':'down','owner':'ops','runbook':'url','severity':'critical','condition':'up==0'}],'runbooks':['url'],'panels':['slo']}
 for k,v in list_fields.items():
  if k in d:d[k]=v
 numeric={'nodes':4,'quorum_size':3,'epsilon':1,'sensitivity':1,'memory_budget_bytes':1024,'timing_budget_ms':10,'failure_threshold':3,'window_size':10,'open_seconds':5,'limit':100,'window_seconds':60,'sustained_rate':10,'burst':20,'ttl_seconds':30,'arrival_rate':10,'duration_seconds':60,'capacity_target':20,'period':'month','sampling_rate':.1,'retention_days':30,'refresh_seconds':30}
 for k,v in numeric.items():
  if k in d:d[k]=v
 d.update({'fault_model':'crash'} if method=='consensus_algorithm' else {})
 if method=='differential_privacy':d['mechanism']='laplace'
 if method=='real_time_systems':d['scheduling_policy']='rate_monotonic'
 if method=='multi_tenancy':d.update(isolation_model='row',tenant_key='tenant_id')
 if method=='distributed_tracing':d['propagation_format']='tracecontext'
 if method=='metrics_collection':d['scrape_or_push']='scrape'
 if method=='alerting':d['routes']=['pager']
 return d

def test_exact_50_rows_and_concept_specific_guidance():
 assert len(METHODS)==50 and len(set(GUIDANCE.values()))==50 and set(METHODS)==set(REQUIRED)==set(GUIDANCE)

@pytest.mark.parametrize('method',METHODS)
def test_each_row_has_executable_schema_and_concept_guidance(method):
 o=P(method,sample(method));assert o['method']==method and len(o['guidance'])>40 and o['review']['verified_in_live_environment'] is False
 assert o['result']

@pytest.mark.parametrize('method',METHODS)
def test_each_row_rejects_missing_required_input(method):
 d=sample(method);d.pop(REQUIRED[method][0]);
 with pytest.raises(ValueError,match='missing required fields'):P(method,d)

def test_consensus_checks_quorum_and_fault_model():
 assert P('consensus_algorithm',{'nodes':4,'fault_model':'byzantine','faults_tolerated':1,'quorum_size':3})['result']['model_feasible']
 assert not P('consensus_algorithm',{'nodes':3,'fault_model':'byzantine','faults_tolerated':1,'quorum_size':2})['result']['model_feasible']
def test_differential_privacy_calibrates_laplace_and_rejects_bad_epsilon():
 assert P('differential_privacy',{'epsilon':2,'mechanism':'laplace','sensitivity':6})['result']['laplace_scale']==3
 with pytest.raises(ValueError):P('differential_privacy',{'epsilon':0,'mechanism':'laplace','sensitivity':1})
def test_realtime_utilization_and_rm_bound():
 r=P('real_time_systems',{'tasks':[{'wcet_ms':1,'period_ms':4},{'wcet_ms':1,'period_ms':5}],'scheduling_policy':'rate_monotonic'})['result'];assert r['total_utilization']==.45 and r['sufficient_schedulability']
def test_circuit_breaker_validity():assert not P('circuit_breaker',{'failure_threshold':11,'window_size':10,'open_seconds':5})['result']['valid']
def test_rate_limit_and_throttle_mechanics():
 assert P('rate_limiting',{'limit':120,'window_seconds':60,'key':'tenant'})['result']['average_rate_per_second']==2
 assert P('throttling',{'sustained_rate':10,'burst':50})['result']['burst_duration_at_sustained_seconds']==5
def test_tenant_isolation_surfaces_are_comprehensive():assert 'queues' in P('multi_tenancy',sample('multi_tenancy'))['result']['required_surfaces']
def test_canary_rejects_nonmonotonic_steps_in_analysis():assert not P('canary_deployment',{'steps':[10,5],'success_metrics':['e'],'rollback_thresholds':['e>1']})['result']['monotonic']
def test_feature_flag_staleness():
 d=sample('feature_flags');d['flags']=[{'name':'old','default':False}];assert P('feature_flags',d)['result']['stale_names']==['old']
def test_trace_detects_orphan():
 d=sample('distributed_tracing');d['spans']=[{'span_id':'a'},{'span_id':'b','parent_span_id':'missing'}];assert P('distributed_tracing',d)['result']['orphan_span_ids']==['b']
def test_metric_cardinality_guard():
 d=sample('metrics_collection');d['metrics']=[{'name':'bad','type':'counter','unit':'x','labels':['user_id']}];assert P('metrics_collection',d)['result']['invalid_or_high_cardinality_metric_names']==['bad']
def test_alert_actionability():
 d=sample('alerting');d['rules']=[{'name':'bad','condition':'x'}];assert P('alerting',d)['result']['unactionable_rule_names']==['bad']
def test_route_is_mounted_and_bad_payload_is_422():
 app=FastAPI();app.include_router(router);c=TestClient(app)
 assert c.post('/api/modules/20/platform-engineering/585-634/analyze',json={'method':'rate_limiting','data':{'limit':10,'window_seconds':1,'key':'ip'}}).status_code==200
 assert c.post('/api/modules/20/platform-engineering/585-634/analyze',json={'method':'rate_limiting','data':{}}).status_code==422

# ---- practitioner-depth evidence for the 38 formerly-generic rows ----

def test_distributed_systems_classifies_consistency_and_failure_coverage():
 o=P('distributed_systems',{'services':['a','b'],'consistency_model':'eventual','failure_scenarios':['partition','node_crash']})['result']
 assert o['consistency_classification']=='eventual' and o['failure_scenario_coverage']==['partition','node_crash']
 weak=P('distributed_systems',{'services':['a'],'consistency_model':'custom'})['result']
 assert weak['consistency_classification']=='unclassified' and weak['evaluation']['confidence']<.5
def test_blockchain_finality_and_throughput_estimation():
 o=P('blockchain_design',{'network_type':'public','consensus':'proof-of-work','state_model':'utxo','block_time_seconds':600,'transactions_per_block':3000})['result']
 assert o['finality_model']=='probabilistic' and o['estimated_throughput_tx_per_second']==5
 bft=P('blockchain_design',{'network_type':'consortium','consensus':'pbft','state_model':'account'})['result']
 assert bft['finality_model']=='deterministic' and bft['estimated_throughput_tx_per_second'] is None
def test_smart_contract_flags_missing_guards_and_access_control():
 o=P('smart_contract_development',{'functions':[{'name':'withdraw','external_calls':True,'state_writes':True,'calls_before_writes':True},{'name':'owner_only','state_writes':True,'access_control':True}],'invariants':['balance>=0']})['result']
 risks=[f['risk'] for f in o['static_risk_findings']]
 assert 'checks-effects-interactions ordering violated' in risks and 'external call without declared reentrancy guard' in risks
 assert not any(f['function']=='owner_only' for f in o['static_risk_findings'])
def test_zkp_detects_witness_leakage_into_public_inputs():
 o=P('zero_knowledge_proof',{'statement':'x=hash(w)','public_inputs':['x'],'witness_definition':'w','setup':'groth16'})['result']
 assert o['separation_valid'] and o['trusted_setup_required']
 leak=P('zero_knowledge_proof',{'statement':'y','public_inputs':['w'],'witness_definition':'the witness w'})['result']
 assert not leak['separation_valid'] and leak['witness_leakage_into_public_inputs']==['w']
def test_homomorphic_capability_and_noise_budget():
 o=P('homomorphic_encryption',{'scheme':'paillier','supported_operations':['add','multiply'],'key_management':'hsm','multiplicative_depth':2})['result']
 assert o['unsupported_requested_operations']==['multiply'] and o['noise_budget']['multiplicative_depth']==2
 unknown=P('homomorphic_encryption',{'scheme':'custom','supported_operations':['add'],'key_management':'kms'})['result']
 assert unknown['scheme_capability'] is None and unknown['evaluation']['confidence']<.4
def test_smpc_corruption_threshold_feasibility():
 o=P('secure_multi_party_computation',{'parties':['a','b','c','d'],'function':'sum','threat_model':'malicious','max_corrupted':1})['result']
 assert o['threshold_feasible'] and 'n=4 vs required 4' in o['feasibility_note']
 short=P('secure_multi_party_computation',{'parties':['a','b'],'function':'sum','threat_model':'malicious','max_corrupted':1})['result']
 assert short['threshold_feasible'] is False
 unstated=P('secure_multi_party_computation',{'parties':['a','b'],'function':'f','threat_model':'semi_honest'})['result']
 assert unstated['threshold_feasible'] is None
def test_federated_privacy_control_gaps_and_robust_aggregation():
 o=P('federated_learning',{'clients':['c1'],'aggregation':'fedavg-median','privacy_controls':['secure aggregation']})['result']
 assert 'differential privacy' in o['privacy_control_gaps'] and o['poisoning_robust_aggregation']
def test_edge_placement_uses_measured_latency_gain():
 o=P('edge_computing',{'workloads':[{'name':'vision','cloud_latency_ms':200,'edge_latency_ms':20},{'name':'batch'}],'edge_nodes':['e1'],'offline_policy':'store-and-forward'})['result']
 assert o['workload_placements'][0]['latency_gain_ms']==180 and o['workload_placements'][0]['place_at_edge']
 assert o['workload_placements'][1]['place_at_edge'] is None and o['offline_capable']
def test_iot_lifecycle_gaps_and_legacy_protocols():
 o=P('iot_architecture',{'devices':['d'],'protocols':['mqtt','telnet'],'trust_boundaries':['device/cloud'],'device_identity':'x509','update_mechanism':'ota'})['result']
 assert o['lifecycle_gaps']==['provisioning','decommission'] and o['cleartext_or_legacy_protocols']==['telnet']
def test_embedded_budget_accounting_over_budget_detection():
 o=P('embedded_systems',{'mcu':'m4','memory_budget_bytes':1024,'timing_budget_ms':10,'components':[{'name':'rtos','memory_bytes':800,'wcet_ms':6},{'name':'app','memory_bytes':300,'wcet_ms':5}]})['result']
 assert o['memory_over_budget'] and o['memory_headroom_bytes']==-76 and o['timing_over_budget']
def test_safety_critical_hazard_traceability():
 o=P('safety_critical_systems',{'hazards':['overrun','stale-data'],'safety_integrity_target':'SIL2','safety_requirements':[{'id':'sr1','mitigates':['overrun']}]})['result']
 assert o['untraced_hazards']==['stale-data'] and not o['traceability_complete'] and o['target_notation_recognized']
def test_formal_verification_verdict_counts_and_bounded_scope():
 o=P('formal_verification',{'specification':'tla','properties':['p1','p2'],'model':'state-machine','proof_results':[{'verdict':'verified'},{'verdict':'falsified'}],'bound':10})['result']
 assert o['proof_verdicts']=={'verified':1,'falsified':1,'unknown':0} and o['counterexamples_returned']==1 and o['bounded_scope']==10
def test_static_analysis_severity_histogram_and_open_findings():
 o=P('static_analysis',{'rules':['r1'],'targets':['src'],'findings':[{'severity':'high'},{'severity':'high','suppressed':True},{'severity':'low'}]})['result']
 assert o['severity_histogram']=={'high':2,'low':1} and o['open_findings']==2
def test_dynamic_analysis_path_coverage_ratio():
 o=P('dynamic_analysis',{'targets':['svc'],'instrumentation':['asan'],'coverage':{'executed_paths':30,'total_paths':40}})['result']
 assert o['path_coverage_ratio']==.75 and o['unexecuted_behavior']=='unknown'
def test_fuzzing_crash_dedup_by_stack_hash():
 o=P('fuzzing',{'target':'parser','input_model':'grammar','oracles':['crash'],'crashes':[{'stack_hash':'a','reproducible':True},{'stack_hash':'a'},{'stack_hash':'b'}]})['result']
 assert o['crash_clusters']=={'unique':2,'total':3,'duplicates':1} and o['reproducible_crashes']==1
def test_property_based_generator_pairing():
 o=P('property_based_testing',{'properties':[{'name':'rev','generator':'lists'},{'name':'id'}],'generators':['lists'],'runs':500})['result']
 assert o['unpaired_properties']==1 and not o['coverage_complete'] and o['runs_per_property']==500
def test_unit_testing_case_kind_balance():
 o=P('unit_testing',{'units':['u'],'cases':[{'kind':'positive'},{'kind':'boundary'},{'kind':'error'}]})['result']
 assert o['positive_boundary_error_balance'] and o['cases_per_unit']==3
 thin=P('unit_testing',{'units':['u','v'],'cases':[{'kind':'positive'}]})['result']
 assert not thin['positive_boundary_error_balance'] and thin['case_kinds']['positive']==1
def test_integration_contract_coverage_ratio():
 o=P('integration_testing',{'components':['a','b','c'],'contracts':[{'between':['a','b']}]})['result']
 assert o['component_pair_count']==3 and o['contract_coverage_ratio']==1/3
def test_e2e_production_likeness_and_critical_counts():
 o=P('end_to_end_testing',{'journeys':[{'name':'checkout','critical':True},{'name':'about'}],'environment':'staging'})['result']
 assert o['critical_journeys']==1 and o['production_like_environment']
 weak=P('end_to_end_testing',{'journeys':['j'],'environment':'dev-laptop'})['result']
 assert not weak['production_like_environment'] and weak['evaluation']['confidence']<.5
def test_performance_percentiles_and_slo_compliance():
 samples=[10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,2000]
 o=P('performance_testing',{'scenarios':['browse'],'slos':['p95<1s'],'latency_samples_ms':samples})['result']
 assert o['latency_percentiles_ms']['p50']==105 and o['latency_percentiles_ms']['p99']>1000
 assert o['slo_compliance']==[{'slo':'p95<1s','measured_ms':o['latency_percentiles_ms']['p95'],'limit_ms':1000,'met':True}]
def test_load_littles_law_and_saturation():
 o=P('load_testing',{'arrival_rate':10,'duration_seconds':60,'capacity_target':20,'mean_latency_seconds':.5})['result']
 assert o['required_concurrency_littles_law']==5 and o['saturation_ratio']==.5 and not o['over_capacity']
 over=P('load_testing',{'arrival_rate':30,'duration_seconds':60,'capacity_target':20})['result']
 assert over['over_capacity'] and over['required_concurrency_littles_law'] is None
def test_chaos_measurability_and_abort_conditions():
 o=P('chaos_engineering',{'steady_state':'p99 < 500ms','experiment':{'scope':'single az'},'abort_conditions':['errors>1%']})['result']
 assert o['hypothesis_measurable'] and o['abort_conditions_present'] and o['blast_radius']=='single az'
 vague=P('chaos_engineering',{'steady_state':'system is healthy','experiment':{},'abort_conditions':['stop']})['result']
 assert not vague['hypothesis_measurable'] and vague['evaluation']['confidence']<.5
def test_ci_stage_order_and_gate_gaps():
 o=P('continuous_integration',{'stages':['build','test','package'],'required_checks':['unit tests','security scan']})['result']
 assert o['stage_order_valid'] and o['gate_gaps']==['provenance']
 bad=P('continuous_integration',{'stages':['test','build'],'required_checks':['test']})['result']
 assert not bad['stage_order_valid']
def test_cd_rollback_and_promotion_path():
 o=P('continuous_deployment',{'environments':['staging','prod'],'promotion_policy':'gated','rollback':'previous artifact','rollback_tested':True})['result']
 assert o['rollback_defined'] and o['promotion_path_length']==2
 with pytest.raises(ValueError):P('continuous_deployment',{'environments':['prod'],'promotion_policy':'auto','rollback':''})
 untested=P('continuous_deployment',{'environments':['prod'],'promotion_policy':'auto','rollback':'previous artifact'})['result']
 assert untested['rollback_defined'] and not untested['rollback_tested'] and 'rollback untested' in untested['evaluation']['unknowns']
def test_iac_drift_and_plaintext_secret_scan():
 o=P('infrastructure_as_code',{'resources':['db password=hunter2','cache'],'state_backend':'s3+lock','plan_review':'required','declared_state':['db','cache'],'observed_state':['db','cache','extra-vm']})['result']
 assert o['drift_detected']==['extra-vm'] and o['plaintext_secret_candidates']
def test_config_schema_validation_and_secret_ref_hygiene():
 o=P('configuration_management',{'configuration':{'port':'8080','workers':4},'schema':{'port':{'type':'int','required':True},'workers':{'type':'int'},'host':{'type':'str','required':True}},'secret_refs':['vault:db','AKIA123PLAINTEXT']})['result']
 assert {'key':'port','expected':'int','got':'str'} in o['type_violations'] and o['missing_required_keys']==['host']
 assert o['plaintext_secret_refs']==['AKIA123PLAINTEXT']
def test_container_probe_gaps_and_limit_ratios():
 o=P('container_orchestration',{'workloads':[{'name':'api','cpu_request':.5,'cpu_limit':4}],'resources':['r'],'health_checks':['readiness']})['result']
 assert o['limit_request_ratios'][0]['limit_to_request_ratio']==8 and o['extreme_limit_request_ratios']==1
 assert o['probe_gaps']==['liveness','startup']
def test_mesh_retry_storm_budget():
 o=P('service_mesh',{'services':['a'],'mtls':'strict','traffic_policies':['timeout'],'max_retries':3,'timeout_ms':1000,'deadline_ms':2000})['result']
 assert o['retry_budget']['retry_storm_risk'] and o['mtls_strict']
 safe=P('service_mesh',{'services':['a'],'mtls':'strict','traffic_policies':['timeout'],'max_retries':1,'timeout_ms':500,'deadline_ms':2000})['result']
 assert not safe['retry_budget']['retry_storm_risk']
def test_gateway_route_conflict_detection():
 o=P('api_gateway',{'routes':['/api','/api/users','/static'],'authn':'oidc','authz':'rbac'})['result']
 assert o['route_conflicts']==[['/api','/api/users']] and o['authentication_authorization_separated']
def test_discovery_staleness_bound():
 o=P('service_discovery',{'instances':['i1','i2'],'health_policy':'http-200','ttl_seconds':30,'health_interval_seconds':10})['result']
 assert o['staleness_bound_seconds']==40 and o['healthy_instances']==2
def test_quota_headroom_and_exhaustion():
 o=P('quota_management',{'quotas':[{'name':'api','limit':100,'used':100},{'name':'jobs','limit':10,'used':3}],'period':'month'})['result']
 assert o['quotas'][0]['exhausted'] and o['quotas'][1]['headroom']==7 and o['exhausted_quota_count']==1
def test_blue_green_parity_and_switch_readiness():
 o=P('blue_green_deployment',{'blue':['v1'],'green':['v2'],'switch_checks':['healthy']})['result']
 assert o['switch_readiness'] and o['environment_parity_by_count']
def test_dark_launch_requires_isolated_side_effects():
 o=P('dark_launching',{'hidden_paths':['new'],'side_effect_policy':'disabled'})['result']
 assert o['side_effects_isolated'] and not o['user_visible_effects']
 live=P('dark_launching',{'hidden_paths':['new'],'side_effect_policy':'live'})['result']
 assert not live['side_effects_isolated'] and live['user_visible_effects'] and live['evaluation']['confidence']<.4
def test_shadow_traffic_redaction_gate():
 o=P('shadow_traffic',{'source':'prod','shadow':'staging','redaction':'pii-scrubbed'})['result']
 assert o['redaction_enabled']
 unsafe=P('shadow_traffic',{'source':'prod','shadow':'staging','redaction':'none'})['result']
 assert not unsafe['redaction_enabled'] and unsafe['evaluation']['confidence']<.4
def test_traffic_mirroring_sampling_bounds():
 with pytest.raises(ValueError):P('traffic_mirroring',{'source':'lb','mirrors':['m'],'sampling_rate':0})
 with pytest.raises(ValueError):P('traffic_mirroring',{'source':'lb','mirrors':['m'],'sampling_rate':1.5})
 assert P('traffic_mirroring',{'source':'lb','mirrors':['m'],'sampling_rate':.1})['result']['expected_mirrored_fraction']==.1
def test_observability_signal_gap_detection():
 o=P('observability',{'signals':['metrics'],'slos':['availability'],'ownership':'team-a'})['result']
 assert o['signal_gaps']==['logs','traces']
 full=P('observability',{'signals':['metrics','logs','traces'],'slos':['a'],'ownership':'t'})['result']
 assert full['signal_gaps']==[]
def test_log_aggregation_retention_and_redaction():
 o=P('log_aggregation',{'sources':['app'],'retention_days':30,'redaction':'scrub-secrets'})['result']
 assert o['redaction_enabled'] and o['retention_within_bounds']
 with pytest.raises(ValueError):P('log_aggregation',{'sources':['a'],'retention_days':0,'redaction':'x'})
def test_dashboard_freshness_and_slo_coverage():
 o=P('dashboards',{'panels':['availability','latency'],'audience':'oncall','refresh_seconds':60,'slos':['availability']})['result']
 assert o['freshness_bounded'] and o['slo_panel_coverage']==1
 with pytest.raises(ValueError):P('dashboards',{'panels':['p'],'audience':'a','refresh_seconds':0})

# ---- stateful project lifecycle, provenance, exact approval and rollback ----
from app.modules.m20_general_cognitive_worker.platform_engineering_585_634 import PlatformWorkflowStore, WorkflowIdentity, ROW_BY_METHOD


def test_platform_workflow_exact_approval_transition_and_rollback():
 store=PlatformWorkflowStore(); owner=WorkflowIdentity('tenant-a','owner')
 proposed=store.propose(owner,'rate_limiting',{'limit':10,'window_seconds':1,'key':'tenant'},source_ids=['design-doc:7'])
 assert proposed['state']=='awaiting_approval' and proposed['row_id']==619
 with pytest.raises(ValueError,match='hash'):store.approve(owner,proposed['workflow_id'],artifact_sha256='wrong',decision='approve')
 approved=store.approve(owner,proposed['workflow_id'],artifact_sha256=proposed['artifacts'][0]['artifact_sha256'],decision='approve')
 assert approved['state']=='approved'
 applied=store.apply(owner,proposed['workflow_id']);assert applied['state']=='applied_in_atlas_only' and not applied['external_effects_executed']
 rolled=store.rollback(owner,proposed['workflow_id'],reason='metric regression');assert rolled['state']=='rolled_back_in_atlas_only'
 assert [e['event'] for e in rolled['history']]==['proposed','approved','applied_in_atlas_only','rolled_back_in_atlas_only']


def test_platform_workflow_tenant_and_actor_isolation():
 store=PlatformWorkflowStore(); owner=WorkflowIdentity('tenant-a','owner')
 proposed=store.propose(owner,'observability',sample('observability'),source_ids=['slo:1'])
 with pytest.raises(KeyError):store.view(WorkflowIdentity('tenant-b','owner'),proposed['workflow_id'])
 with pytest.raises(PermissionError):store.approve(WorkflowIdentity('tenant-a','intruder'),proposed['workflow_id'],artifact_sha256=proposed['artifacts'][0]['artifact_sha256'],decision='approve')


def test_platform_workflow_requires_provenance_and_rejects_apply_without_approval():
 store=PlatformWorkflowStore(); owner=WorkflowIdentity('tenant-a','owner')
 with pytest.raises(ValueError,match='provenance'):store.propose(owner,'dashboards',sample('dashboards'),source_ids=[])
 proposed=store.propose(owner,'dashboards',sample('dashboards'),source_ids=['dashboard-spec'])
 with pytest.raises(ValueError,match='approval'):store.apply(owner,proposed['workflow_id'])
 assert proposed['artifacts'][0]['provenance']['fabricated_external_evidence'] is False


def _row_lifecycle_test(method):
 def test():
  store=PlatformWorkflowStore(); identity=WorkflowIdentity('tenant-row',f'actor-{ROW_BY_METHOD[method]}')
  proposed=store.propose(identity,method,sample(method),source_ids=[f'requirement:{ROW_BY_METHOD[method]}'])
  assert proposed['row_id']==ROW_BY_METHOD[method]
  assert proposed['artifacts'][0]['analysis']==P(method,sample(method))['result']
  assert proposed['artifacts'][0]['provenance']['derived_by']==f'row-{ROW_BY_METHOD[method]}:{method}'
 return test

for _method in METHODS:
 globals()[f'test_row_{ROW_BY_METHOD[_method]}_{_method}_workflow_artifact']=_row_lifecycle_test(_method)
