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
