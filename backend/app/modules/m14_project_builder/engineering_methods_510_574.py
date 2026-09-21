"""Executable engineering design methods for additional-feature rows 510-574.

Each public function has its own input contract and computed metric. No function
claims that a proposed design is deployed. Safety, units, feasibility, and
geometry checks fail closed.
"""
from __future__ import annotations
import math
from typing import Any, Callable, Mapping

class EngineeringMethodError(ValueError): pass

def require(condition: bool, message: str) -> None:
    if not condition: raise EngineeringMethodError(message)

def _helpers(kind: str, data: Mapping[str, Any]):
    require(isinstance(data, Mapping), "data must be an object")
    required=METHOD_INPUTS[kind]
    missing=[k for k in required if k not in data]
    require(not missing, "missing required inputs: "+", ".join(missing))
    def n(key: str) -> float:
        value=data[key]; require(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value),f"{key} must be a finite number")
        require(value>=0,f"{key} must be non-negative and use the declared base unit")
        return float(value)
    def items(key: str) -> list[Any]:
        value=data[key]; require(isinstance(value,list) and len(value)>0,f"{key} must be a non-empty list"); return value
    def nums(key: str) -> list[float]:
        values=items(key); require(all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>=0 for x in values),f"{key} must contain non-negative finite numbers"); return [float(x) for x in values]
    def count(key: str) -> float:
        value=data[key]
        if isinstance(value,list): return float(len(value))
        return n(key)
    def ratio(num: float, den: float) -> float:
        require(den>0,"denominator must be positive"); require(num<=den,"numerator cannot exceed denominator"); return num/den
    def _f1(tp: float, fp: float, fn: float) -> float:
        require(tp+fp>0 and tp+fn>0,"precision and recall denominators must be positive"); p=tp/(tp+fp); r=tp/(tp+fn); return 2*p*r/(p+r) if p+r else 0.0
    return n,items,nums,count,ratio,_f1

METHOD_INPUTS={'requirements': ['stakeholder_needs', 'acceptance_criteria'], 'system_architecture': ['components', 'connections'], 'api_design': ['endpoints', 'error_responses'], 'database_schema': ['entities', 'relationships'], 'microservices': ['services', 'dependencies'], 'monolith': ['modules', 'internal_interfaces'], 'event_driven': ['events', 'consumers'], 'message_queue': ['arrival_rate', 'service_rate'], 'caching': ['hits', 'requests'], 'load_balancing': ['backend_capacities', 'request_rate'], 'auto_scaling': ['current_instances', 'target_utilization', 'observed_utilization'], 'fault_tolerance': ['component_reliabilities', 'required_reliability'], 'disaster_recovery': ['recovery_minutes', 'rto_minutes'], 'backup': ['restore_points', 'rpo_minutes', 'interval_minutes'], 'security_architecture': ['threats', 'mitigated_threats'], 'authentication': ['factors', 'session_minutes', 'max_session_minutes'], 'authorization': ['permissions', 'explicit_denies'], 'encryption': ['key_bits', 'min_key_bits'], 'key_management': ['key_age_days', 'rotation_days'], 'audit_logging': ['required_events', 'logged_events'], 'compliance': ['controls', 'implemented_controls'], 'privacy': ['collected_fields', 'necessary_fields'], 'data_governance': ['datasets', 'owned_datasets'], 'data_lineage': ['lineage_nodes', 'lineage_edges'], 'data_quality': ['valid_records', 'total_records'], 'etl_pipeline': ['input_records', 'output_records', 'rejected_records'], 'data_warehouse': ['partition_rows', 'query_rows'], 'data_lake': ['catalogued_assets', 'total_assets'], 'data_mesh': ['data_products', 'domain_owners'], 'stream_processing': ['events_processed', 'window_seconds'], 'batch_processing': ['records', 'duration_seconds'], 'lambda_architecture': ['batch_result', 'speed_result'], 'kappa_architecture': ['log_offset', 'processed_offset'], 'ml_pipeline': ['passed_gates', 'total_gates'], 'feature_store': ['online_features', 'offline_features'], 'model_registry': ['registered_versions', 'approved_versions'], 'model_monitoring': ['baseline_mean', 'current_mean', 'baseline_std'], 'ab_testing': ['control_successes', 'control_total', 'treatment_successes', 'treatment_total'], 'recommendation': ['relevant_recommendations', 'total_recommendations'], 'search_system': ['relevant_retrieved', 'retrieved'], 'ranking_system': ['relevant_positions'], 'fraud_detection': ['true_positives', 'false_positives'], 'anomaly_detection': ['value', 'baseline_mean', 'baseline_std'], 'time_series': ['actual', 'forecast'], 'nlp': ['correct_predictions', 'total_predictions'], 'computer_vision': ['intersection_area', 'union_area'], 'speech_recognition': ['word_errors', 'reference_words'], 'speech_synthesis': ['naturalness_scores'], 'machine_translation': ['matched_ngrams', 'total_ngrams'], 'text_summarization': ['supported_claims', 'total_claims'], 'question_answering': ['supported_answers', 'total_answers'], 'information_extraction': ['correct_fields', 'total_fields'], 'named_entity_recognition': ['true_positives', 'false_positives', 'false_negatives'], 'relation_extraction': ['correct_relations', 'predicted_relations'], 'sentiment_analysis': ['correct_labels', 'total_labels'], 'topic_modeling': ['topic_coherences'], 'text_classification': ['true_positives', 'false_positives', 'false_negatives'], 'document_clustering': ['intra_distances', 'inter_distances'], 'semantic_search': ['relevant_at_k', 'k'], 'knowledge_graph': ['entities', 'relations'], 'ontology_design': ['concepts', 'axioms'], 'reasoning_engine': ['derived_facts', 'input_facts'], 'planning_system': ['goal_steps', 'valid_steps'], 'scheduling_system': ['scheduled_jobs', 'total_jobs'], 'optimization_engine': ['objective_before', 'objective_after', 'constraint_violations']}
METHOD_OUTPUTS={'requirements': 'coverage_ratio', 'system_architecture': 'coupling_density', 'api_design': 'error_coverage', 'database_schema': 'relationship_density', 'microservices': 'dependency_density', 'monolith': 'interface_density', 'event_driven': 'consumer_coverage', 'message_queue': 'utilization', 'caching': 'hit_rate', 'load_balancing': 'capacity_headroom', 'auto_scaling': 'required_instances', 'fault_tolerance': 'system_reliability', 'disaster_recovery': 'rto_margin_minutes', 'backup': 'rpo_compliant', 'security_architecture': 'threat_coverage', 'authentication': 'factor_count', 'authorization': 'deny_coverage', 'encryption': 'key_strength_margin', 'key_management': 'rotation_overdue_days', 'audit_logging': 'audit_coverage', 'compliance': 'control_coverage', 'privacy': 'minimization_ratio', 'data_governance': 'ownership_coverage', 'data_lineage': 'lineage_density', 'data_quality': 'validity_rate', 'etl_pipeline': 'reconciliation_delta', 'data_warehouse': 'scan_reduction', 'data_lake': 'catalog_coverage', 'data_mesh': 'ownership_ratio', 'stream_processing': 'throughput_per_second', 'batch_processing': 'records_per_second', 'lambda_architecture': 'reconciliation_gap', 'kappa_architecture': 'consumer_lag', 'ml_pipeline': 'gate_pass_rate', 'feature_store': 'feature_parity', 'model_registry': 'approval_ratio', 'model_monitoring': 'drift_z_score', 'ab_testing': 'absolute_lift', 'recommendation': 'precision_at_k', 'search_system': 'retrieval_precision', 'ranking_system': 'mean_reciprocal_rank', 'fraud_detection': 'alert_precision', 'anomaly_detection': 'anomaly_score', 'time_series': 'mae', 'nlp': 'task_accuracy', 'computer_vision': 'intersection_over_union', 'speech_recognition': 'word_error_rate', 'speech_synthesis': 'mean_naturalness', 'machine_translation': 'ngram_precision', 'text_summarization': 'factuality_rate', 'question_answering': 'answer_support_rate', 'information_extraction': 'field_precision', 'named_entity_recognition': 'entity_f1', 'relation_extraction': 'relation_precision', 'sentiment_analysis': 'sentiment_accuracy', 'topic_modeling': 'mean_topic_coherence', 'text_classification': 'classification_f1', 'document_clustering': 'separation_ratio', 'semantic_search': 'recall_at_k', 'knowledge_graph': 'relations_per_entity', 'ontology_design': 'axioms_per_concept', 'reasoning_engine': 'inference_yield', 'planning_system': 'plan_validity', 'scheduling_system': 'schedule_coverage', 'optimization_engine': 'objective_improvement'}

def requirements(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 510: compute coverage_ratio from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("requirements",data)
    result=ratio(count("acceptance_criteria"),count("stakeholder_needs"))
    return {"row": 510, "method": "requirements", "coverage_ratio": result, "feasible": True}

def system_architecture(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 511: compute coupling_density from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("system_architecture",data)
    result=len(items("connections"))/len(items("components"))
    return {"row": 511, "method": "system_architecture", "coupling_density": result, "feasible": True}

def api_design(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 512: compute error_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("api_design",data)
    result=ratio(count("error_responses"),count("endpoints"))
    return {"row": 512, "method": "api_design", "error_coverage": result, "feasible": True}

def database_schema(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 513: compute relationship_density from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("database_schema",data)
    result=len(items("relationships"))/len(items("entities"))
    return {"row": 513, "method": "database_schema", "relationship_density": result, "feasible": True}

def microservices(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 514: compute dependency_density from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("microservices",data)
    result=len(items("dependencies"))/len(items("services"))
    return {"row": 514, "method": "microservices", "dependency_density": result, "feasible": True}

def monolith(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 515: compute interface_density from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("monolith",data)
    result=len(items("internal_interfaces"))/len(items("modules"))
    return {"row": 515, "method": "monolith", "interface_density": result, "feasible": True}

def event_driven(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 516: compute consumer_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("event_driven",data)
    result=ratio(count("consumers"),count("events"))
    return {"row": 516, "method": "event_driven", "consumer_coverage": result, "feasible": True}

def message_queue(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 517: compute utilization from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("message_queue",data)
    a=n("arrival_rate"); s=n("service_rate"); require(s>a,"service_rate must exceed arrival_rate to avoid unsafe overload"); result=a/s
    return {"row": 517, "method": "message_queue", "utilization": result, "feasible": True}

def caching(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 518: compute hit_rate from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("caching",data)
    result=ratio(count("hits"),count("requests"))
    return {"row": 518, "method": "caching", "hit_rate": result, "feasible": True}

def load_balancing(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 519: compute capacity_headroom from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("load_balancing",data)
    result=sum(nums("backend_capacities"))-n("request_rate"); require(result>=0,"request rate exceeds safe capacity")
    return {"row": 519, "method": "load_balancing", "capacity_headroom": result, "feasible": True}

def auto_scaling(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 520: compute required_instances from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("auto_scaling",data)
    c=n("current_instances"); t=n("target_utilization"); o=n("observed_utilization"); require(0<t<=1 and 0<=o<=1,"utilization must be in [0,1]"); result=max(1,math.ceil(c*o/t))
    return {"row": 520, "method": "auto_scaling", "required_instances": result, "feasible": True}

def fault_tolerance(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 521: compute system_reliability from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("fault_tolerance",data)
    vals=nums("component_reliabilities"); req=n("required_reliability"); require(all(0<=x<=1 for x in vals) and 0<=req<=1,"reliabilities must be in [0,1]"); result=math.prod(vals); require(result>=req,"unsafe reliability target is not met")
    return {"row": 521, "method": "fault_tolerance", "system_reliability": result, "feasible": True}

def disaster_recovery(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 522: compute rto_margin_minutes from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("disaster_recovery",data)
    result=n("rto_minutes")-n("recovery_minutes"); require(result>=0,"recovery plan exceeds RTO")
    return {"row": 522, "method": "disaster_recovery", "rto_margin_minutes": result, "feasible": True}

def backup(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 523: compute rpo_compliant from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("backup",data)
    require(n("interval_minutes")>0 and n("rpo_minutes")>=0,"invalid time units"); result=bool(n("restore_points")>0 and n("interval_minutes")<=n("rpo_minutes"))
    return {"row": 523, "method": "backup", "rpo_compliant": result, "feasible": True}

def security_architecture(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 524: compute threat_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("security_architecture",data)
    result=ratio(count("mitigated_threats"),count("threats"))
    return {"row": 524, "method": "security_architecture", "threat_coverage": result, "feasible": True}

def authentication(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 525: compute factor_count from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("authentication",data)
    f=items("factors"); require(n("session_minutes")<=n("max_session_minutes"),"unsafe session duration"); result=len(f)
    return {"row": 525, "method": "authentication", "factor_count": result, "feasible": True}

def authorization(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 526: compute deny_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("authorization",data)
    result=ratio(count("explicit_denies"),count("permissions"))
    return {"row": 526, "method": "authorization", "deny_coverage": result, "feasible": True}

def encryption(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 527: compute key_strength_margin from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("encryption",data)
    result=n("key_bits")-n("min_key_bits"); require(result>=0,"unsafe key strength")
    return {"row": 527, "method": "encryption", "key_strength_margin": result, "feasible": True}

def key_management(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 528: compute rotation_overdue_days from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("key_management",data)
    result=max(0.0,n("key_age_days")-n("rotation_days")); require(n("rotation_days")>0,"rotation_days must be positive")
    return {"row": 528, "method": "key_management", "rotation_overdue_days": result, "feasible": True}

def audit_logging(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 529: compute audit_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("audit_logging",data)
    result=ratio(count("logged_events"),count("required_events"))
    return {"row": 529, "method": "audit_logging", "audit_coverage": result, "feasible": True}

def compliance(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 530: compute control_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("compliance",data)
    result=ratio(count("implemented_controls"),count("controls"))
    return {"row": 530, "method": "compliance", "control_coverage": result, "feasible": True}

def privacy(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 531: compute minimization_ratio from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("privacy",data)
    result=ratio(count("necessary_fields"),count("collected_fields"))
    return {"row": 531, "method": "privacy", "minimization_ratio": result, "feasible": True}

def data_governance(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 532: compute ownership_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("data_governance",data)
    result=ratio(count("owned_datasets"),count("datasets"))
    return {"row": 532, "method": "data_governance", "ownership_coverage": result, "feasible": True}

def data_lineage(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 533: compute lineage_density from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("data_lineage",data)
    result=len(items("lineage_edges"))/len(items("lineage_nodes"))
    return {"row": 533, "method": "data_lineage", "lineage_density": result, "feasible": True}

def data_quality(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 534: compute validity_rate from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("data_quality",data)
    result=ratio(count("valid_records"),count("total_records"))
    return {"row": 534, "method": "data_quality", "validity_rate": result, "feasible": True}

def etl_pipeline(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 535: compute reconciliation_delta from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("etl_pipeline",data)
    result=n("input_records")-n("output_records")-n("rejected_records"); require(abs(result)<1e-9,"ETL record reconciliation failed")
    return {"row": 535, "method": "etl_pipeline", "reconciliation_delta": result, "feasible": True}

def data_warehouse(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 536: compute scan_reduction from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("data_warehouse",data)
    result=1-ratio(n("query_rows"),n("partition_rows"))
    return {"row": 536, "method": "data_warehouse", "scan_reduction": result, "feasible": True}

def data_lake(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 537: compute catalog_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("data_lake",data)
    result=ratio(count("catalogued_assets"),count("total_assets"))
    return {"row": 537, "method": "data_lake", "catalog_coverage": result, "feasible": True}

def data_mesh(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 538: compute ownership_ratio from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("data_mesh",data)
    result=ratio(count("domain_owners"),count("data_products"))
    return {"row": 538, "method": "data_mesh", "ownership_ratio": result, "feasible": True}

def stream_processing(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 539: compute throughput_per_second from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("stream_processing",data)
    result=n("events_processed")/n("window_seconds"); require(n("window_seconds")>0,"duration must be positive")
    return {"row": 539, "method": "stream_processing", "throughput_per_second": result, "feasible": True}

def batch_processing(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 540: compute records_per_second from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("batch_processing",data)
    result=n("records")/n("duration_seconds"); require(n("duration_seconds")>0,"duration must be positive")
    return {"row": 540, "method": "batch_processing", "records_per_second": result, "feasible": True}

def lambda_architecture(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 541: compute reconciliation_gap from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("lambda_architecture",data)
    result=abs(n("batch_result")-n("speed_result"))
    return {"row": 541, "method": "lambda_architecture", "reconciliation_gap": result, "feasible": True}

def kappa_architecture(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 542: compute consumer_lag from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("kappa_architecture",data)
    result=n("log_offset")-n("processed_offset"); require(result>=0,"processed offset cannot exceed log offset")
    return {"row": 542, "method": "kappa_architecture", "consumer_lag": result, "feasible": True}

def ml_pipeline(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 543: compute gate_pass_rate from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("ml_pipeline",data)
    result=ratio(count("passed_gates"),count("total_gates"))
    return {"row": 543, "method": "ml_pipeline", "gate_pass_rate": result, "feasible": True}

def feature_store(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 544: compute feature_parity from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("feature_store",data)
    a=set(items("online_features")); b=set(items("offline_features")); result=len(a&b)/len(a|b) if a|b else 1.0
    return {"row": 544, "method": "feature_store", "feature_parity": result, "feasible": True}

def model_registry(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 545: compute approval_ratio from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("model_registry",data)
    result=ratio(count("approved_versions"),count("registered_versions"))
    return {"row": 545, "method": "model_registry", "approval_ratio": result, "feasible": True}

def model_monitoring(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 546: compute drift_z_score from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("model_monitoring",data)
    sd=n("baseline_std"); require(sd>0,"baseline_std must be positive"); result=abs(n("current_mean")-n("baseline_mean"))/sd
    return {"row": 546, "method": "model_monitoring", "drift_z_score": result, "feasible": True}

def ab_testing(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 547: compute absolute_lift from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("ab_testing",data)
    ct=n("control_total"); tt=n("treatment_total"); require(ct>0 and tt>0,"experiment totals must be positive"); result=n("treatment_successes")/tt-n("control_successes")/ct
    return {"row": 547, "method": "ab_testing", "absolute_lift": result, "feasible": True}

def recommendation(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 548: compute precision_at_k from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("recommendation",data)
    result=ratio(count("relevant_recommendations"),count("total_recommendations"))
    return {"row": 548, "method": "recommendation", "precision_at_k": result, "feasible": True}

def search_system(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 549: compute retrieval_precision from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("search_system",data)
    result=ratio(count("relevant_retrieved"),count("retrieved"))
    return {"row": 549, "method": "search_system", "retrieval_precision": result, "feasible": True}

def ranking_system(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 550: compute mean_reciprocal_rank from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("ranking_system",data)
    p=nums("relevant_positions"); require(all(x>=1 and float(x).is_integer() for x in p),"positions must be positive integers"); result=sum(1/x for x in p)/len(p)
    return {"row": 550, "method": "ranking_system", "mean_reciprocal_rank": result, "feasible": True}

def fraud_detection(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 551: compute alert_precision from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("fraud_detection",data)
    result=ratio(count("true_positives"),n("true_positives")+n("false_positives"))
    return {"row": 551, "method": "fraud_detection", "alert_precision": result, "feasible": True}

def anomaly_detection(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 552: compute anomaly_score from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("anomaly_detection",data)
    sd=n("baseline_std"); require(sd>0,"baseline_std must be positive"); result=abs(n("value")-n("baseline_mean"))/sd
    return {"row": 552, "method": "anomaly_detection", "anomaly_score": result, "feasible": True}

def time_series(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 553: compute mae from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("time_series",data)
    a=nums("actual"); f=nums("forecast"); require(len(a)==len(f),"actual and forecast lengths differ"); result=sum(abs(x-y) for x,y in zip(a,f))/len(a)
    return {"row": 553, "method": "time_series", "mae": result, "feasible": True}

def nlp(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 554: compute task_accuracy from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("nlp",data)
    result=ratio(count("correct_predictions"),count("total_predictions"))
    return {"row": 554, "method": "nlp", "task_accuracy": result, "feasible": True}

def computer_vision(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 555: compute intersection_over_union from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("computer_vision",data)
    u=n("union_area"); require(u>0 and 0<=n("intersection_area")<=u,"invalid image geometry"); result=n("intersection_area")/u
    return {"row": 555, "method": "computer_vision", "intersection_over_union": result, "feasible": True}

def speech_recognition(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 556: compute word_error_rate from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("speech_recognition",data)
    result=ratio(count("word_errors"),count("reference_words"))
    return {"row": 556, "method": "speech_recognition", "word_error_rate": result, "feasible": True}

def speech_synthesis(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 557: compute mean_naturalness from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("speech_synthesis",data)
    v=nums("naturalness_scores"); result=sum(v)/len(v)
    return {"row": 557, "method": "speech_synthesis", "mean_naturalness": result, "feasible": True}

def machine_translation(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 558: compute ngram_precision from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("machine_translation",data)
    result=ratio(count("matched_ngrams"),count("total_ngrams"))
    return {"row": 558, "method": "machine_translation", "ngram_precision": result, "feasible": True}

def text_summarization(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 559: compute factuality_rate from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("text_summarization",data)
    result=ratio(count("supported_claims"),count("total_claims"))
    return {"row": 559, "method": "text_summarization", "factuality_rate": result, "feasible": True}

def question_answering(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 560: compute answer_support_rate from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("question_answering",data)
    result=ratio(count("supported_answers"),count("total_answers"))
    return {"row": 560, "method": "question_answering", "answer_support_rate": result, "feasible": True}

def information_extraction(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 561: compute field_precision from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("information_extraction",data)
    result=ratio(count("correct_fields"),count("total_fields"))
    return {"row": 561, "method": "information_extraction", "field_precision": result, "feasible": True}

def named_entity_recognition(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 562: compute entity_f1 from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("named_entity_recognition",data)
    tp=n("true_positives"); fp=n("false_positives"); fn=n("false_negatives"); result=_f1(tp,fp,fn)
    return {"row": 562, "method": "named_entity_recognition", "entity_f1": result, "feasible": True}

def relation_extraction(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 563: compute relation_precision from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("relation_extraction",data)
    result=ratio(count("correct_relations"),count("predicted_relations"))
    return {"row": 563, "method": "relation_extraction", "relation_precision": result, "feasible": True}

def sentiment_analysis(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 564: compute sentiment_accuracy from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("sentiment_analysis",data)
    result=ratio(count("correct_labels"),count("total_labels"))
    return {"row": 564, "method": "sentiment_analysis", "sentiment_accuracy": result, "feasible": True}

def topic_modeling(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 565: compute mean_topic_coherence from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("topic_modeling",data)
    v=nums("topic_coherences"); result=sum(v)/len(v)
    return {"row": 565, "method": "topic_modeling", "mean_topic_coherence": result, "feasible": True}

def text_classification(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 566: compute classification_f1 from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("text_classification",data)
    result=_f1(n("true_positives"),n("false_positives"),n("false_negatives"))
    return {"row": 566, "method": "text_classification", "classification_f1": result, "feasible": True}

def document_clustering(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 567: compute separation_ratio from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("document_clustering",data)
    i=nums("intra_distances"); e=nums("inter_distances"); require(sum(i)>0,"intra distances must be positive"); result=(sum(e)/len(e))/(sum(i)/len(i))
    return {"row": 567, "method": "document_clustering", "separation_ratio": result, "feasible": True}

def semantic_search(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 568: compute recall_at_k from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("semantic_search",data)
    result=ratio(count("relevant_at_k"),count("k"))
    return {"row": 568, "method": "semantic_search", "recall_at_k": result, "feasible": True}

def knowledge_graph(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 569: compute relations_per_entity from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("knowledge_graph",data)
    result=len(items("relations"))/len(items("entities"))
    return {"row": 569, "method": "knowledge_graph", "relations_per_entity": result, "feasible": True}

def ontology_design(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 570: compute axioms_per_concept from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("ontology_design",data)
    result=len(items("axioms"))/len(items("concepts"))
    return {"row": 570, "method": "ontology_design", "axioms_per_concept": result, "feasible": True}

def reasoning_engine(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 571: compute inference_yield from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("reasoning_engine",data)
    result=n("derived_facts")/n("input_facts"); require(n("input_facts")>0,"input_facts must be positive")
    return {"row": 571, "method": "reasoning_engine", "inference_yield": result, "feasible": True}

def planning_system(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 572: compute plan_validity from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("planning_system",data)
    result=ratio(count("valid_steps"),count("goal_steps"))
    return {"row": 572, "method": "planning_system", "plan_validity": result, "feasible": True}

def scheduling_system(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 573: compute schedule_coverage from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("scheduling_system",data)
    result=ratio(count("scheduled_jobs"),count("total_jobs"))
    return {"row": 573, "method": "scheduling_system", "schedule_coverage": result, "feasible": True}

def optimization_engine(data: Mapping[str, Any]) -> dict[str, Any]:
    """Row 574: compute objective_improvement from its validated design inputs."""
    n,items,nums,count,ratio,_f1=_helpers("optimization_engine",data)
    require(n("constraint_violations")==0,"infeasible optimization result"); result=n("objective_after")-n("objective_before")
    return {"row": 574, "method": "optimization_engine", "objective_improvement": result, "feasible": True}

METHODS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "requirements": requirements,
    "system_architecture": system_architecture,
    "api_design": api_design,
    "database_schema": database_schema,
    "microservices": microservices,
    "monolith": monolith,
    "event_driven": event_driven,
    "message_queue": message_queue,
    "caching": caching,
    "load_balancing": load_balancing,
    "auto_scaling": auto_scaling,
    "fault_tolerance": fault_tolerance,
    "disaster_recovery": disaster_recovery,
    "backup": backup,
    "security_architecture": security_architecture,
    "authentication": authentication,
    "authorization": authorization,
    "encryption": encryption,
    "key_management": key_management,
    "audit_logging": audit_logging,
    "compliance": compliance,
    "privacy": privacy,
    "data_governance": data_governance,
    "data_lineage": data_lineage,
    "data_quality": data_quality,
    "etl_pipeline": etl_pipeline,
    "data_warehouse": data_warehouse,
    "data_lake": data_lake,
    "data_mesh": data_mesh,
    "stream_processing": stream_processing,
    "batch_processing": batch_processing,
    "lambda_architecture": lambda_architecture,
    "kappa_architecture": kappa_architecture,
    "ml_pipeline": ml_pipeline,
    "feature_store": feature_store,
    "model_registry": model_registry,
    "model_monitoring": model_monitoring,
    "ab_testing": ab_testing,
    "recommendation": recommendation,
    "search_system": search_system,
    "ranking_system": ranking_system,
    "fraud_detection": fraud_detection,
    "anomaly_detection": anomaly_detection,
    "time_series": time_series,
    "nlp": nlp,
    "computer_vision": computer_vision,
    "speech_recognition": speech_recognition,
    "speech_synthesis": speech_synthesis,
    "machine_translation": machine_translation,
    "text_summarization": text_summarization,
    "question_answering": question_answering,
    "information_extraction": information_extraction,
    "named_entity_recognition": named_entity_recognition,
    "relation_extraction": relation_extraction,
    "sentiment_analysis": sentiment_analysis,
    "topic_modeling": topic_modeling,
    "text_classification": text_classification,
    "document_clustering": document_clustering,
    "semantic_search": semantic_search,
    "knowledge_graph": knowledge_graph,
    "ontology_design": ontology_design,
    "reasoning_engine": reasoning_engine,
    "planning_system": planning_system,
    "scheduling_system": scheduling_system,
    "optimization_engine": optimization_engine,
}

def run_engineering_method(method: str, data: Mapping[str, Any]) -> dict[str, Any]:
    require(method in METHODS, "unknown engineering method")
    return METHODS[method](data)
