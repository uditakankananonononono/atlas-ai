import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m14_project_builder.architecture_support_635_684 import FEATURES,architecture_support_635_684
BASE={'system':'checkout','decision_owner':'platform-team'}
def payload(fid):
 d=dict(BASE)
 if fid<643:d|={'services':[{'id':'api'}],'windows':[{'name':'30d','total':1000,'good':995,'target':.99}],'incident_roles':['commander'],'runbook_steps':['assess']}
 elif fid<648:d|={'jobs':[{'id':'a','priority':1,'enqueued_at':'1'},{'id':'b','priority':2,'enqueued_at':'2'}],'dependencies':[{'from':'a','to':'b'}],'resource_limits':{'workers':2}}
 elif fid<658:d|={'messages':[{'id':'1','idempotency_key':'k','attempt':1},{'id':'2','idempotency_key':'k','attempt':3}],'delivery_policy':{'semantics':'at-least-once','base_delay_seconds':2,'max_delay_seconds':10,'max_attempts':3},'transaction_boundaries':['outbox']}
 elif fid<671:d|={'components':[{'id':'domain'},{'id':'adapter'}],'interfaces':[{'id':'port','consumer':'adapter','provider':'domain'}],'failure_isolation':['timeout']}
 else:d|={'contexts':[{'id':'sales','language':{'customer':'buyer'}},{'id':'support','language':{'customer':'caller'}}],'domain_events':[{'context_id':'sales','past_tense_name':'OrderPlaced'}],'aggregates':[{'id':'order'}]}
 return d
@pytest.mark.parametrize('fid',range(635,685))
def test_each_exact_ledger_row_is_implemented(fid):
 o=architecture_support_635_684(fid,payload(fid));assert o['feature_id']==fid and o['concept']==FEATURES[fid] and o['review_required'] and o['boundary']
def test_slo_and_error_budget_math_is_auditable():
 o=architecture_support_635_684(636,payload(636));w=o['sli_windows'][0];assert w['actual_sli']==.995 and w['allowed_bad_events']==10 and w['budget_remaining']==5
def test_dag_scheduler_rejects_cycles():
 d=payload(646);d['dependencies'].append({'from':'b','to':'a'})
 with pytest.raises(ValueError,match='cycle'):architecture_support_635_684(646,d)
def test_delivery_detects_duplicate_and_dlq_boundary():
 o=architecture_support_635_684(652,payload(652));assert not o['delivery_analysis'][0]['duplicate'] and o['delivery_analysis'][1]['duplicate'] and o['delivery_analysis'][1]['destination']=='dead_letter'
def test_pattern_validation_detects_unknown_component():
 d=payload(667);d['interfaces'][0]['provider']='missing';o=architecture_support_635_684(667,d);assert o['structural_violations'][0]['violation']=='unknown_component'
def test_ubiquitous_language_surfaces_context_collision():
 o=architecture_support_635_684(673,payload(673));assert o['language_collisions']==[{'term':'customer','meanings':['buyer','caller']}]
def test_negative_missing_owner_and_invalid_sli():
 with pytest.raises(ValueError):architecture_support_635_684(635,{'system':'x'})
 d=payload(635);d['windows'][0]['good']=1001
 with pytest.raises(ValueError):architecture_support_635_684(635,d)
def test_mounted_route_uses_tenant_boundary():
 r=TestClient(app).post('/api/v1/project-builder/architecture-635-684/support',headers={'x-atlas-tenant':'arch-t'},json={'feature_id':684,'data':payload(684)});assert r.status_code==200 and r.json()['tenant_id']=='arch-t' and r.json()['concept']=='Event Storming'

# ---- practitioner-depth evidence: distinctive per-row algorithms 635-684 ----
def A(fid,extra):
 d=payload(fid);d.update(extra);return architecture_support_635_684(fid,d)
def test635_slo_verdicts():
 o=A(635,{})['slo_assessment'][0];assert o['meets_target'] is True
 o=A(635,{'windows':[{'name':'30d','total':1000,'good':985,'target':.99}]})
 assert o['slo_assessment'][0]['meets_target'] is False and o['compliant_window_fraction']==0
def test636_burn_classification():
 o=A(636,{'windows':[{'name':'1h','total':1000,'good':994,'target':.99}]})
 r=o['error_budget_policy'][0];assert r['classification']=='fast_burn' and r['fast_burn_alert'] and o['any_fast_burn_alert']
 assert r['projected_windows_to_exhaustion_at_current_rate']==pytest.approx(10/6)
 gone=A(636,{'windows':[{'name':'1h','total':1000,'good':950,'target':.99}]})['error_budget_policy'][0]
 assert gone['classification']=='exhausted'
def test637_role_coverage_and_mtta():
 o=A(637,{'incident_roles':['incident commander'],'timeline':[{'id':'i1','detected_to_ack_minutes':4,'ack_to_resolve_minutes':30}]})
 assert o['role_gaps']==['communications','scribe'] and o['mean_time_to_ack_minutes']==4
def test638_unowned_action_items():
 o=A(638,{'action_items':[{'task':'add alert','owner':'sre'},{'task':'fix runbook'}],'contributing_factors':['deploy']})
 assert o['action_items_with_owners']==1 and o['unowned_action_items']==1
def test639_runbook_alert_coverage():
 o=A(639,{'alerts':[{'name':'high-error','runbook':'rb-1'},{'name':'latency'}]})
 assert o['alerts_without_runbook']==['latency'] and o['coverage_complete'] is False
def test640_rotation_fairness_and_spof():
 o=A(640,{'on_call':['a','b'],'rotation_weeks':4})
 assert [s['primary'] for s in o['rotation_schedule']]==['a','b','a','b'] and o['fairness_spread_shifts']==0 and not o['single_point_of_failure']
 assert A(640,{'on_call':['a']})['single_point_of_failure']
def test641_capacity_linear_forecast():
 o=A(641,{'usage_series':[10,20,30,40],'capacity_limit':1000})
 assert o['trend']['slope_per_period']==pytest.approx(10) and o['periods_to_capacity_limit']==pytest.approx(96) and not o['exhaustion_imminent']
 soon=A(641,{'usage_series':[10,20,30,40],'capacity_limit':100})
 assert soon['periods_to_capacity_limit']==pytest.approx(6) and soon['exhaustion_imminent']
 assert A(641,{})['evaluation']['confidence']<.5
def test642_cost_waste_ranking():
 o=A(642,{'cost_options':[{'name':'db','monthly_cost':100,'utilization':.1},{'name':'cache','monthly_cost':50,'utilization':.9}]})
 assert o['cost_options'][0]['option']=='db' and o['total_estimated_monthly_waste']==pytest.approx(95) and o['rightsizing_recommended_for']==['db']
def test643_bin_packing_assignment():
 o=A(643,{'jobs':[{'id':'a','cpu':2,'priority':1,'enqueued_at':'1'},{'id':'b','cpu':2,'priority':1,'enqueued_at':'2'}],'resource_limits':{'workers':1,'cpu_per_worker':3}})
 assert o['worker_assignment']=={'a':'worker-1'} and o['unassigned_jobs']==['b']
def test644_queue_wait_estimates():
 o=A(644,{'jobs':[{'id':'a','priority':1,'enqueued_at':'1','duration_seconds':5},{'id':'b','priority':2,'enqueued_at':'2','duration_seconds':3}]})
 assert o['queue_wait_estimates'][0]=={'job':'b','estimated_wait_seconds':0} and o['queue_wait_estimates'][1]['estimated_wait_seconds']==3 and o['total_drain_seconds']==8
def test645_parallel_waves():
 o=A(645,{'jobs':[{'id':'a'},{'id':'b'},{'id':'c'}],'dependencies':[{'from':'a','to':'c'},{'from':'b','to':'c'}]})
 assert o['execution_waves']==[{'wave':1,'parallel_jobs':['a','b']},{'wave':2,'parallel_jobs':['c']}] and o['max_parallelism']==2
def test646_critical_path():
 o=A(646,{'jobs':[{'id':'a','duration':5},{'id':'b','duration':1},{'id':'c','duration':2}],'dependencies':[{'from':'a','to':'c'},{'from':'b','to':'c'}]})
 assert o['critical_path']==['a','c'] and o['critical_path_duration']==7
def test647_cron_parse_and_overlap():
 o=A(647,{'cron_expressions':['*/15 9-17 * * *','0 9 * * *']})
 assert o['parsed_schedules'][0]['fires_per_day']==4*9 and o['overlapping_schedules']==[['*/15 9-17 * * *','0 9 * * *']]
 d=payload(647);d['cron_expressions']=['bad cron']
 with pytest.raises(ValueError):architecture_support_635_684(647,d)
def test648_event_sourcing_replay():
 o=A(648,{'events':[{'type':'Opened','payload':{'balance':0},'version':1},{'type':'Deposited','payload':{'balance':50},'version':2},{'type':'Note','payload':{'note':'x'},'version':4}]})
 assert o['replayed_state']=={'balance':50,'note':'x'} and o['version_gaps_after_position']==[2]
def test649_cqrs_separation_and_lag():
 o=A(649,{'write_models':['Order'],'read_models':['OrderSummary'],'projection_lag_seconds':2})
 assert o['separation_clean'] and o['staleness_bounded']
 dirty=A(649,{'write_models':['Order'],'read_models':['Order']})
 assert not dirty['separation_clean']
def test650_saga_compensation_order():
 o=A(650,{'saga_steps':[{'id':'book'},{'id':'pay'},{'id':'ship','status':'pending'}],'compensations':['book']})
 assert o['compensation_order']==['pay','book'] and o['steps_missing_compensation']==['pay'] and not o['saga_safe']
def test651_two_phase_blocking():
 o=A(651,{'messages':[{'id':'p1','phase':'prepared'},{'id':'p2','phase':'prepared'}]})
 assert o['all_prepared'] and o['coordinator_failure_blocks_participants'] and o['requires_participant_timeout']
def test652_idempotency_key_coverage():
 o=A(652,{})
 assert o['key_coverage']==1.0 and o['unkeyed_message_ids']==[]
 d=payload(652);d['messages'][1].pop('idempotency_key')
 assert A(652,{'messages':d['messages']})['unkeyed_message_ids']==['2']
def test653_exactly_once_feasibility():
 o=A(653,{})
 assert o['exactly_once_feasible'] and 'achievable' in o['verdict']
 d=payload(653);d['transaction_boundaries']=[]
 assert not A(653,{'transaction_boundaries':[]})['exactly_once_feasible']
def test654_at_least_once_dedup_requirement():
 o=A(654,{})
 assert o['duplicate_deliveries']==1 and o['downstream_dedup_required']
def test655_dlq_poison_detection():
 o=A(655,{'redrive_policy':{'max_redrives':2}})
 assert o['poison_message_count']==1 and o['dead_letter_messages'][0]['message_id']=='2' and o['redrive_bounded']
def test656_retry_budget():
 o=A(656,{})
 assert o['retry_budget_seconds_per_message']==pytest.approx(min(2*(1+2+4),10*3)) and o['full_jitter_recommended']
def test657_backoff_sequence_and_cap():
 o=A(657,{})
 assert o['exponential_sequence_seconds']==[2,4,8] and o['total_worst_case_delay_seconds']==14
 d=payload(657);d['delivery_policy']={'base_delay_seconds':10,'max_delay_seconds':25,'max_attempts':4}
 o=A(657,{'delivery_policy':d['delivery_policy']})
 assert o['exponential_sequence_seconds']==[10,20,25,25] and o['cap_reached_at_attempt']==3
def test658_bulkhead_blast_radius():
 o=A(658,{'pools':[{'id':'p1','components':['domain']},{'id':'p2','components':['adapter']}]})
 assert o['worst_case_blast_radius_components']==1 and o['isolation_effective']
 assert not A(658,{})['isolation_effective']
def test659_sidecar_offload():
 o=A(659,{'components':[{'id':'app'},{'id':'proxy','kind':'sidecar','provides':'mtls'}]})
 assert o['sidecar_components']==['proxy'] and o['offloaded_concerns']==['mtls']
def test660_ambassador_policy_inconsistency():
 o=A(660,{'interfaces':[{'id':'i1','consumer':'a','provider':'b','timeout_ms':100},{'id':'i2','consumer':'a','provider':'c','timeout_ms':500}],'components':[{'id':'a'},{'id':'b'},{'id':'c'}]})
 assert o['inconsistent_policies']=={'timeout_ms':['100','500']} and o['ambassador_centralization_recommended']
def test661_adapter_conformance():
 o=A(661,{'interfaces':[{'id':'port','consumer':'adapter','provider':'domain','required_methods':['find','save'],'provided_methods':['find']}]})
 assert o['non_conforming_interfaces']==['port'] and o['conformance_findings'][0]['missing_methods']==['save']
def test662_facade_coupling_reduction():
 o=A(662,{'components':[{'id':'web'},{'id':'f','kind':'facade'}],'interfaces':[{'id':'i1','consumer':'web','provider':'f'},{'id':'i2','consumer':'web','provider':'f'}]})
 assert o['coupling_reduction_ratio']==0 and o['facade_mediated_edges']==2
def test663_observer_cycle_and_fanout():
 o=A(663,{'components':[{'id':'a'},{'id':'b'}],'interfaces':[{'id':'i1','consumer':'b','provider':'a'},{'id':'i2','consumer':'a','provider':'b'}]})
 assert o['notification_cycle_detected'] and o['cascade_risk']=='high'
def test664_strategy_dispatch_coverage():
 o=A(664,{'contexts':['eu','us'],'strategies':[{'context':'eu','name':'gdpr'},{'default':True,'name':'base'}]})
 assert o['uncovered_contexts']==['us'] and not o['dispatch_complete']
def test665_factory_unknown_product():
 o=A(665,{'registered_products':['pdf'],'requested_products':['pdf','docx']})
 assert o['unregistered_requests']==['docx']
def test666_singleton_lazy_race():
 o=A(666,{'components':[{'id':'cfg','kind':'singleton','lazy':True,'thread_safe':False}]})
 assert o['lazy_initialization_race_hazards']==['cfg']
def test667_di_resolution_order():
 o=A(667,{'components':[{'id':'repo'},{'id':'svc'}],'interfaces':[{'id':'i','consumer':'svc','provider':'repo'}]})
 assert o['resolution_order']==['repo','svc']
def test668_ioc_direction():
 o=A(668,{'components':[{'id':'handler'},{'id':'framework'}],'interfaces':[{'id':'i','consumer':'framework','provider':'handler'}]})
 assert o['control_inverted']
def test669_repository_leakage():
 o=A(669,{'interfaces':[{'id':'repo','consumer':'svc','provider':'db','methods':'sql query'}]})
 assert o['persistence_leakage']==[{'interface':'repo','leaked_token':'sql'}] and not o['persistence_ignorant']
def test670_uow_commit_ordering():
 o=A(670,{'pending_changes':[{'id':'d1','kind':'delete'},{'id':'i1','kind':'insert'},{'id':'u1','kind':'update'}]})
 assert o['commit_order']==['i1','u1','d1'] and o['rollback_covers_all_changes']
def test671_element_counts():
 o=A(671,{'entities':[{'name':'e'}],'value_objects':[{'name':'v'}]})
 assert o['model_element_counts']['aggregates']==1 and o['model_element_counts']['entities']==1
def test672_shared_kernel_detection():
 o=A(672,{'contexts':[{'id':'a','language':{},'models':['Money']},{'id':'b','language':{},'models':['Money']}],'domain_events':[],'context_mappings':[{'upstream':'a','downstream':'b','relationship':'partnership'}]})
 assert o['shared_kernel_models']=={'Money':['a','b']} and o['unclassified_mappings']==0
def test673_glossary_sizes():
 o=A(673,{})
 assert o['glossary_sizes']=={'sales':1,'support':1} and not o['collision_free']
def test674_aggregate_invariants():
 o=A(674,{'aggregates':[{'id':'order','entities':['line'],'invariants':[],'external_references':[{'id':'customer'}]}]})
 f=o['aggregate_findings'][0];assert not f['invariants_declared'] and f['external_references_by_object']==1
 assert o['aggregates_without_invariants']==['order']
def test675_entity_identity():
 o=A(675,{'entities':[{'name':'user'},{'name':'order','id_field':'order_id'}]})
 assert o['entities_without_identity_field']==['user']
def test676_value_object_rules():
 o=A(676,{'value_objects':[{'name':'money','mutable':True},{'name':'email','equality_fields':['address']}]})
 assert o['mutable_value_objects']==['money'] and o['value_objects_without_structural_equality']==['money']
def test677_domain_event_rules():
 o=A(677,{'domain_events':[{'context_id':'sales','past_tense_name':'OrderPlaced'},{'context_id':'sales','past_tense_name':'ShipOrder','mutable':True}]})
 assert o['mutable_events'] and o['non_past_tense_name_candidates']==['ShipOrder']
def test678_acl_translation():
 o=A(678,{'context_mappings':[{'upstream':'sales','downstream':'support'}]})
 assert o['acl_required'] and o['untranslated_collision_terms']==['customer']
def test679_hexagonal_direction():
 o=A(679,{'ports':[{'id':'repo-port','depends_on':['pg-adapter']}],'adapters':[{'id':'pg-adapter','port':'repo-port'}]})
 assert o['direction_violations']==[{'port':'repo-port','depends_on_adapter':'pg-adapter'}]
def test680_clean_architecture_inward_rule():
 o=A(680,{'layers':[{'name':'entities','depends_on':['infrastructure']},{'name':'infrastructure','depends_on':['entities']}]})
 assert o['dependency_rule_violations']==[{'layer':'entities','illegal_dependency':'infrastructure'}]
def test681_onion_dependency_free_core():
 o=A(681,{'layers':[{'name':'domain','depends_on':['web']},{'name':'web'}]})
 assert not o['domain_is_dependency_free'] and o['domain_dependencies']==['domain']
def test682_ports_adapters_pairing():
 o=A(682,{'ports':[{'id':'p1'},{'id':'p2'}],'adapters':[{'id':'a','port':'p1'}]})
 assert o['ports_without_adapters']==['p2'] and not o['pairing_complete']
def test683_functional_core_purity():
 o=A(683,{'components':[{'id':'calc','region':'core'},{'id':'io','region':'core','side_effects':True},{'id':'api','region':'shell'}]})
 assert o['side_effects_inside_core']==['io'] and o['imperative_shell_components']==['api']
def test684_event_storming_chronology():
 o=A(684,{'event_storm':[{'sequence':2,'command':'Ship','produces':'OrderPlaced'},{'sequence':1,'command':'Place'}],'domain_events':[{'context_id':'sales','past_tense_name':'OrderPlaced'}]})
 assert o['chronologically_ordered'] is False and o['commands_without_produced_events']==['Place']

# ---- durable state, provenance, approval and rollback -----------------------
def test_workflow_persists_artifact_provenance_and_real_transitions(tmp_path):
 from app.modules.m14_project_builder.architecture_workflow_635_684 import ArchitectureWorkflowRepository,ArchitectureWorkflowService
 service=ArchitectureWorkflowService(ArchitectureWorkflowRepository(tmp_path/'workflow.db'))
 draft=service.draft('tenant-a','architect',646,payload(646),{'source_id':'owner-brief-7','observed_at':'2026-09-21T10:00:00Z'})
 assert draft.state=='draft' and len(draft.artifact_sha256)==64 and draft.provenance['source_id']=='owner-brief-7'
 review=service.submit('tenant-a','architect',draft.id)
 approved=service.approve('tenant-a','reviewer',draft.id,'approval-646')
 applied=service.apply('tenant-a','worker',draft.id,'approval-646')
 rolled=service.rollback('tenant-a','reviewer',draft.id,'replaced by measured dependency durations')
 assert [draft.version,review.version,approved.version,applied.version,rolled.version]==[1,2,3,4,5]
 assert rolled.state=='rolled_back' and rolled.rollback_reason.startswith('replaced')
 assert rolled.analysis['critical_path']==['a','b']

def test_workflow_fails_closed_on_wrong_tenant_actor_approval_and_transition(tmp_path):
 from app.modules.m14_project_builder.architecture_workflow_635_684 import ArchitectureWorkflowError,ArchitectureWorkflowRepository,ArchitectureWorkflowService
 service=ArchitectureWorkflowService(ArchitectureWorkflowRepository(tmp_path/'workflow.db'))
 record=service.draft('tenant-a','architect',635,payload(635),{'source_id':'monitor-export','observed_at':'2026-09-21T10:00:00Z'})
 with pytest.raises(KeyError):service.repository.get('tenant-b',record.id)
 with pytest.raises(ArchitectureWorkflowError,match='drafting actor'):service.submit('tenant-a','intruder',record.id)
 service.submit('tenant-a','architect',record.id)
 with pytest.raises(ArchitectureWorkflowError,match='matching approval'):service.apply('tenant-a','worker',record.id,'invented')
 service.approve('tenant-a','reviewer',record.id,'real-approval')
 with pytest.raises(ArchitectureWorkflowError,match='matching approval'):service.apply('tenant-a','worker',record.id,'wrong-approval')
 with pytest.raises(ArchitectureWorkflowError,match='applied'):service.rollback('tenant-a','reviewer',record.id,'too early')

def test_workflow_route_is_tenant_actor_scoped_and_does_not_claim_external_effect(tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path)
 client=TestClient(app); headers={'x-atlas-tenant':'tenant-route','x-atlas-actor':'architect'}
 body={'feature_id':652,'data':payload(652),'provenance':{'source_id':'queue-sample','observed_at':'2026-09-21T10:00:00Z'}}
 made=client.post('/api/v1/project-builder/architecture-635-684/workflows',headers=headers,json=body)
 assert made.status_code==201; record=made.json(); assert record['tenant_id']=='tenant-route' and record['actor_id']=='architect'
 hidden=client.get(f"/api/v1/project-builder/architecture-635-684/workflows/{record['id']}",headers={'x-atlas-tenant':'other','x-atlas-actor':'x'})
 assert hidden.status_code==404
 assert record['analysis']['boundary'].startswith('Simulation only')

def test_workflow_rejects_missing_provenance_and_invalid_scope(tmp_path):
 from app.modules.m14_project_builder.architecture_workflow_635_684 import ArchitectureWorkflowError,ArchitectureWorkflowRepository,ArchitectureWorkflowService
 service=ArchitectureWorkflowService(ArchitectureWorkflowRepository(tmp_path/'workflow.db'))
 with pytest.raises(ArchitectureWorkflowError,match='provenance'):service.draft('tenant','actor',684,payload(684),{'source_id':'x'})
 with pytest.raises(ArchitectureWorkflowError,match='tenant_id'):service.draft('','actor',684,payload(684),{'source_id':'x','observed_at':'now'})
