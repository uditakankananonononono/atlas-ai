"""Engineering design artifacts for Atlas Module 14 (Project Builder).

Covers features-doc rows 510-559 (Technical & Engineering):
typed, evidence-bearing design documents. Rows 510-534: requirements,
architecture, API, schema, monolith/microservice/event/queue/cache/load/
scale/fault/DR/backup plans, and security/authn/authz/encryption/key-
management/audit/compliance/privacy/governance/lineage/quality designs.
Rows 535-559: data engineering (ETL, warehouse, lake, mesh, stream/batch,
lambda/kappa), ML infrastructure (pipelines, feature store, registry,
monitoring, experiments), and applied-AI designs (recommendation, search,
ranking, fraud, anomaly, time-series, NLP, CV, speech, translation,
summarization). Rows 560-584: language understanding (QA, extraction,
NER, relations, sentiment, topics, classification, clustering, semantic
search), knowledge and reasoning (KG, ontology, reasoning, planning,
scheduling, optimization, simulation), and engine/protocol designs (game,
physics, render, audio, network, protocol, compression, error correction,
cryptographic protocol).

Every design kind maps to exactly one features-doc row. Generation is
deterministic scaffolding derived from project context (the LLM planner can
refine content afterward); validation enforces required sections, rejects
placeholders, rejects operational-state claims (a design artifact is never
evidence of deployment), and rejects embedded secrets. Validated documents
register through the module's existing fail-closed artifact pipeline with
provenance, so they flow through the same DAG, budget, and approval model
as every other project artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Mapping, Optional, Tuple


class EngineeringError(ValueError):
    """Base error for engineering design artifacts."""


class UnknownDesignKindError(EngineeringError):
    """Design kind is not registered."""


@dataclass(frozen=True)
class DesignKindSpec:
    """Registry entry for one design artifact kind."""

    kind: str
    row: int  # features-doc row id
    title: str
    required_sections: Tuple[str, ...]


DESIGN_KINDS: Tuple[DesignKindSpec, ...] = (
    DesignKindSpec("requirements", 510, "Requirements Gathering", (
        "Purpose", "Stakeholders", "Functional Requirements",
        "Non-Functional Requirements", "Constraints", "Acceptance Criteria",
        "Open Questions",
    )),
    DesignKindSpec("system_architecture", 511, "System Architecture Design", (
        "Overview", "Components", "Responsibilities", "Data Flow",
        "Technology Choices", "Trade-offs", "Risks",
    )),
    DesignKindSpec("api_design", 512, "API Design", (
        "Overview", "Resources", "Endpoints", "Request and Response Schemas",
        "Error Model", "Versioning", "Authentication",
    )),
    DesignKindSpec("database_schema", 513, "Database Schema Design", (
        "Entities", "Relationships", "Constraints", "Indexes",
        "Migration Plan", "Data Retention",
    )),
    DesignKindSpec("microservices", 514, "Microservices Design", (
        "Service Boundaries", "Contracts", "Data Ownership", "Communication",
        "Deployment Units", "Failure Isolation",
    )),
    DesignKindSpec("monolith", 515, "Monolith Design", (
        "Module Structure", "Layering", "Shared Kernel",
        "Internal Interfaces", "Scaling Approach",
    )),
    DesignKindSpec("event_driven", 516, "Event-Driven Architecture", (
        "Events", "Producers", "Consumers", "Ordering", "Idempotency",
        "Schema Evolution",
    )),
    DesignKindSpec("message_queue", 517, "Message Queue Design", (
        "Queues and Topics", "Producers", "Consumers", "Delivery Semantics",
        "Dead-Letter Handling", "Backpressure",
    )),
    DesignKindSpec("caching", 518, "Caching Strategy", (
        "Cached Data", "Cache Layers", "Invalidation", "TTLs",
        "Consistency Guarantees",
    )),
    DesignKindSpec("load_balancing", 519, "Load Balancing", (
        "Traffic Profile", "Balancing Algorithm", "Health Checks",
        "Session Handling", "Failover",
    )),
    DesignKindSpec("auto_scaling", 520, "Auto-Scaling", (
        "Metrics", "Scaling Policies", "Limits", "Cooldowns", "Cost Bounds",
    )),
    DesignKindSpec("fault_tolerance", 521, "Fault Tolerance", (
        "Failure Modes", "Redundancy", "Retries and Timeouts",
        "Circuit Breaking", "Degradation Strategy",
    )),
    DesignKindSpec("disaster_recovery", 522, "Disaster Recovery", (
        "RTO Target", "RPO Target", "Recovery Dependencies",
        "Recovery Runbook", "Testing Schedule",
    )),
    DesignKindSpec("backup", 523, "Backup Strategy", (
        "Data Inventory", "Backup Types", "Schedule", "Retention",
        "Backup Encryption", "Restore Testing",
    )),
    DesignKindSpec("security_architecture", 524, "Security Architecture", (
        "Trust Boundaries", "Threat Model", "Controls",
        "Defense in Depth", "Security Monitoring",
    )),
    DesignKindSpec("authentication", 525, "Authentication Design", (
        "Identity Sources", "Credential Types", "Multi-Factor Authentication",
        "Session Management", "Account Recovery",
    )),
    DesignKindSpec("authorization", 526, "Authorization Design", (
        "Roles", "Permissions", "Policy Enforcement Points", "Default Deny",
        "Grant Auditing",
    )),
    DesignKindSpec("encryption", 527, "Encryption Implementation", (
        "Data Classification", "At-Rest Encryption", "In-Transit Encryption",
        "Algorithm Choices", "Rotation Plan",
    )),
    DesignKindSpec("key_management", 528, "Key Management", (
        "Key Types", "Key Storage", "Rotation", "Access Control",
        "Revocation",
    )),
    DesignKindSpec("audit_logging", 529, "Audit Logging", (
        "Audited Events", "Log Schema", "Retention", "Tamper Protection",
        "Log Access Control",
    )),
    DesignKindSpec("compliance", 530, "Compliance Implementation", (
        "Applicable Regulations", "Control Mapping", "Evidence Collection",
        "Review Cadence",
    )),
    DesignKindSpec("privacy", 531, "Privacy by Design", (
        "Data Inventory", "Lawful Basis", "Data Minimization", "Consent",
        "Retention and Deletion", "Impact Assessment",
    )),
    DesignKindSpec("data_governance", 532, "Data Governance", (
        "Ownership", "Classification", "Policies", "Stewardship",
        "Quality Gates",
    )),
    DesignKindSpec("data_lineage", 533, "Data Lineage", (
        "Sources", "Transformations", "Destinations", "Capture Method",
        "Provenance Fields",
    )),
    DesignKindSpec("data_quality", 534, "Data Quality", (
        "Quality Dimensions", "Validation Rules", "Monitoring",
        "Remediation", "Service Level Targets",
    )),
    # --- Rows 535-559: data engineering, ML infrastructure, applied AI ------
    DesignKindSpec("etl_pipeline", 535, "ETL Pipeline Design", (
        "Sources", "Extraction", "Transformations", "Load Targets",
        "Scheduling", "Data Validation", "Recovery",
    )),
    DesignKindSpec("data_warehouse", 536, "Data Warehouse Design", (
        "Schema Model", "Layering", "Partitioning", "Query Patterns",
        "Load Strategy", "Access Control",
    )),
    DesignKindSpec("data_lake", 537, "Data Lake Design", (
        "Storage Layout", "Zones", "File Formats", "Catalog", "Retention",
        "Access Control",
    )),
    DesignKindSpec("data_mesh", 538, "Data Mesh Design", (
        "Domains", "Data Products", "Ownership", "Federated Governance",
        "Self-Serve Platform", "Interoperability Standards",
    )),
    DesignKindSpec("stream_processing", 539, "Stream Processing", (
        "Sources", "Topology", "Windowing", "State Management",
        "Delivery Semantics", "Late Data", "Scaling",
    )),
    DesignKindSpec("batch_processing", 540, "Batch Processing", (
        "Jobs", "Scheduling", "Partitioning", "Resource Allocation",
        "Retry Policy", "Output Contracts",
    )),
    DesignKindSpec("lambda_architecture", 541, "Lambda Architecture", (
        "Batch Layer", "Speed Layer", "Serving Layer", "Reconciliation",
        "Operational Complexity", "Trade-offs",
    )),
    DesignKindSpec("kappa_architecture", 542, "Kappa Architecture", (
        "Immutable Log", "Reprocessing", "Serving Views",
        "Schema Evolution", "Trade-offs",
    )),
    DesignKindSpec("ml_pipeline", 543, "Machine Learning Pipeline", (
        "Pipeline Stages", "Data Versioning", "Training Procedure",
        "Evaluation Gates", "Model Promotion", "Orchestration",
        "Reproducibility",
    )),
    DesignKindSpec("feature_store", 544, "Feature Store Design", (
        "Feature Definitions", "Offline Store", "Online Store",
        "Point-in-Time Correctness", "Feature Versioning", "Monitoring",
    )),
    DesignKindSpec("model_registry", 545, "Model Registry", (
        "Versioning Scheme", "Metadata", "Stage Transitions", "Lineage",
        "Approval Gates", "Rollback",
    )),
    DesignKindSpec("model_monitoring", 546, "Model Monitoring", (
        "Monitored Signals", "Drift Detection", "Data Quality Checks",
        "Alerting", "Retraining Triggers", "Baselines",
    )),
    DesignKindSpec("ab_testing", 547, "A/B Testing Infrastructure", (
        "Experiment Lifecycle", "Assignment", "Metrics",
        "Statistical Power", "Guardrails", "Ramp Plan",
    )),
    DesignKindSpec("recommendation", 548, "Recommendation System", (
        "Candidate Generation", "Ranking", "Features", "Feedback Loop",
        "Cold Start", "Offline Evaluation",
    )),
    DesignKindSpec("search_system", 549, "Search System", (
        "Indexing", "Query Understanding", "Retrieval", "Ranking",
        "Relevance Evaluation", "Latency Budget",
    )),
    DesignKindSpec("ranking_system", 550, "Ranking System", (
        "Features", "Model Choice", "Training Data", "Online Serving",
        "Bias Controls", "Evaluation",
    )),
    DesignKindSpec("fraud_detection", 551, "Fraud Detection", (
        "Fraud Taxonomy", "Signals", "Rules and Models", "Decisioning",
        "Review Workflow", "False Positive Budget",
    )),
    DesignKindSpec("anomaly_detection", 552, "Anomaly Detection", (
        "Baselines", "Detection Methods", "Sensitivity Tuning",
        "Alert Routing", "Feedback Loop",
    )),
    DesignKindSpec("time_series", 553, "Time Series Forecasting", (
        "Data Characteristics", "Model Choice", "Validation Strategy",
        "Horizon and Granularity", "Backtesting",
    )),
    DesignKindSpec("nlp", 554, "Natural Language Processing", (
        "Tasks", "Data Sources", "Model Choice", "Evaluation",
        "Latency Budget", "Safety Filters",
    )),
    DesignKindSpec("computer_vision", 555, "Computer Vision", (
        "Tasks", "Data Sources", "Model Choice", "Evaluation",
        "Preprocessing", "Safety and Consent",
    )),
    DesignKindSpec("speech_recognition", 556, "Speech Recognition", (
        "Audio Inputs", "Model Choice", "Language Support", "Evaluation",
        "Streaming vs Batch",
    )),
    DesignKindSpec("speech_synthesis", 557, "Speech Synthesis", (
        "Voices", "Model Choice", "Text Normalization", "Evaluation",
        "Consent and Disclosure",
    )),
    DesignKindSpec("machine_translation", 558, "Machine Translation", (
        "Language Pairs", "Model Choice", "Domain Adaptation",
        "Evaluation", "Human Review",
    )),
    DesignKindSpec("text_summarization", 559, "Text Summarization", (
        "Input Constraints", "Model Choice", "Evaluation",
        "Factuality Controls", "Latency Budget",
    )),
    # --- Rows 560-584: language understanding, knowledge/reasoning, engines -
    DesignKindSpec("question_answering", 560, "Question Answering", (
        "Question Types", "Answer Sources", "Retrieval and Reading",
        "Answer Validation", "Fallback Behavior", "Evaluation",
    )),
    DesignKindSpec("information_extraction", 561, "Information Extraction", (
        "Target Schema", "Source Documents", "Extraction Methods",
        "Confidence Scoring", "Human Verification", "Evaluation",
    )),
    DesignKindSpec("named_entity_recognition", 562, "Named Entity Recognition", (
        "Entity Types", "Labeling Guidelines", "Training Data",
        "Model Choice", "Evaluation", "Edge Cases",
    )),
    DesignKindSpec("relation_extraction", 563, "Relation Extraction", (
        "Relation Types", "Entity Linking", "Extraction Approach",
        "Confidence Scoring", "Evaluation",
    )),
    DesignKindSpec("sentiment_analysis", 564, "Sentiment Analysis", (
        "Sentiment Taxonomy", "Data Sources", "Model Choice",
        "Aspect Handling", "Evaluation", "Bias Controls",
    )),
    DesignKindSpec("topic_modeling", 565, "Topic Modeling", (
        "Corpus Scope", "Method Choice", "Topic Granularity", "Labeling",
        "Stability Checks", "Evaluation",
    )),
    DesignKindSpec("text_classification", 566, "Text Classification", (
        "Label Set", "Training Data", "Model Choice", "Thresholds",
        "Evaluation", "Drift Handling",
    )),
    DesignKindSpec("document_clustering", 567, "Document Clustering", (
        "Representation", "Algorithm Choice", "Cluster Count",
        "Quality Checks", "Labeling", "Evaluation",
    )),
    DesignKindSpec("semantic_search", 568, "Semantic Search", (
        "Embedding Model", "Index Structure", "Hybrid Retrieval",
        "Reranking", "Latency Budget", "Evaluation",
    )),
    DesignKindSpec("knowledge_graph", 569, "Knowledge Graph Construction", (
        "Entity Resolution", "Schema", "Ingestion Sources", "Storage",
        "Query Interface", "Quality Checks",
    )),
    DesignKindSpec("ontology_design", 570, "Ontology Design", (
        "Concept Hierarchy", "Properties", "Constraints",
        "Naming Conventions", "Versioning", "Alignment",
    )),
    DesignKindSpec("reasoning_engine", 571, "Reasoning Engine", (
        "Knowledge Representation", "Inference Rules",
        "Conflict Resolution", "Explainability", "Performance Bounds",
    )),
    DesignKindSpec("planning_system", 572, "Planning System", (
        "State Model", "Action Model", "Planner Choice", "Plan Validation",
        "Replanning", "Failure Handling",
    )),
    DesignKindSpec("scheduling_system", 573, "Scheduling System", (
        "Resources", "Constraints", "Objective Function", "Solver Choice",
        "Rescheduling", "Fairness",
    )),
    DesignKindSpec("optimization_engine", 574, "Optimization Engine", (
        "Decision Variables", "Objective Function", "Constraints",
        "Solver Choice", "Feasibility Handling", "Sensitivity Analysis",
    )),
    DesignKindSpec("simulation_engine", 575, "Simulation Engine", (
        "Model Scope", "State Representation", "Time Advancement",
        "Randomness Control", "Validation", "Scenario Management",
    )),
    DesignKindSpec("game_engine", 576, "Game Engine", (
        "Game Loop", "Entity Model", "Input Handling",
        "State Synchronization", "Asset Pipeline", "Performance Budget",
    )),
    DesignKindSpec("physics_engine", 577, "Physics Engine", (
        "Simulation Domain", "Numerical Methods", "Collision Handling",
        "Determinism", "Performance Budget", "Validation",
    )),
    DesignKindSpec("rendering_engine", 578, "Rendering Engine", (
        "Render Pipeline", "Scene Representation", "Lighting Model",
        "Asset Formats", "Performance Budget", "Platform Targets",
    )),
    DesignKindSpec("audio_engine", 579, "Audio Engine", (
        "Audio Graph", "Formats and Codecs", "Latency Budget", "Mixing",
        "Spatial Audio", "Device Handling",
    )),
    DesignKindSpec("networking_stack", 580, "Networking Stack", (
        "Topology", "Transport Choices", "Addressing", "Reliability",
        "Security Controls", "Capacity Plan",
    )),
    DesignKindSpec("protocol_design", 581, "Protocol Design", (
        "Message Formats", "State Machine", "Versioning", "Error Handling",
        "Security", "Conformance Testing",
    )),
    DesignKindSpec("compression", 582, "Compression Algorithm", (
        "Data Profile", "Algorithm Choice", "Compression Levels",
        "Integrity Checks", "Benchmark Protocol", "Compatibility",
    )),
    DesignKindSpec("error_correction", 583, "Error Correction", (
        "Error Model", "Code Choice", "Redundancy Budget",
        "Decoding Strategy", "Failure Behavior", "Validation",
    )),
    DesignKindSpec("cryptographic_protocol", 584, "Cryptographic Protocol", (
        "Security Goals", "Threat Model", "Primitives", "Key Exchange",
        "Formal Analysis", "Implementation Pitfalls",
    )),
)

_BY_KIND: Dict[str, DesignKindSpec] = {s.kind: s for s in DESIGN_KINDS}
_BY_ROW: Dict[int, DesignKindSpec] = {s.row: s for s in DESIGN_KINDS}


def list_design_kinds() -> Tuple[str, ...]:
    return tuple(s.kind for s in DESIGN_KINDS)


def spec_for_kind(kind: str) -> DesignKindSpec:
    try:
        return _BY_KIND[kind]
    except KeyError as exc:
        raise UnknownDesignKindError(
            f"unknown design kind {kind!r}; available: "
            + ", ".join(list_design_kinds())
        ) from exc


def spec_for_row(row: int) -> DesignKindSpec:
    try:
        return _BY_ROW[row]
    except KeyError as exc:
        raise UnknownDesignKindError(
            f"no design kind for features-doc row {row}; "
            f"covered rows: {min(_BY_ROW)}-{max(_BY_ROW)}"
        ) from exc


# --- Generation -------------------------------------------------------------

_SECTION_GUIDANCE: Mapping[str, str] = {
    "Purpose": "Why this system exists and what success looks like.",
    "Stakeholders": "Who uses, builds, and operates the system.",
    "Functional Requirements": "What the system must do, stated verifiably.",
    "Non-Functional Requirements": "Performance, reliability, usability bounds.",
    "Constraints": "Budget, time, platform, and policy constraints.",
    "Acceptance Criteria": "Measurable conditions for accepting each requirement.",
    "Open Questions": "Unresolved decisions that need an owner and a date.",
    "Overview": "High-level summary and context.",
    "Components": "The major parts and what each one owns.",
    "Responsibilities": "Which component answers for which behavior.",
    "Data Flow": "How data moves between components.",
    "Technology Choices": "Selected technologies and why.",
    "Trade-offs": "Alternatives considered and reasons rejected.",
    "Risks": "What can go wrong and mitigations.",
    "Resources": "The nouns the API exposes.",
    "Endpoints": "Methods, paths, and purpose of each endpoint.",
    "Request and Response Schemas": "Typed shapes with field constraints.",
    "Error Model": "Error codes, shapes, and retry guidance.",
    "Versioning": "How the API evolves without breaking clients.",
    "Authentication": "How callers prove identity on every request.",
    "Entities": "The data entities and their fields.",
    "Relationships": "Cardinality and ownership between entities.",
    "Constraints": "Keys, uniqueness, and integrity rules.",
    "Indexes": "Indexes justified by query patterns.",
    "Migration Plan": "How schema changes roll out safely.",
    "Data Retention": "What is kept, for how long, and why.",
    "Service Boundaries": "Where one service ends and another begins.",
    "Contracts": "The agreements between services.",
    "Data Ownership": "Which service owns which data.",
    "Communication": "Synchronous vs asynchronous interactions.",
    "Deployment Units": "What ships independently.",
    "Failure Isolation": "How one service's failure is contained.",
    "Module Structure": "Modules inside the single deployable.",
    "Layering": "Allowed dependency directions between layers.",
    "Shared Kernel": "Code shared across modules and how it is governed.",
    "Internal Interfaces": "Boundaries between modules.",
    "Scaling Approach": "How the monolith scales as load grows.",
    "Events": "The events, their schemas, and their meaning.",
    "Producers": "Who emits each event and when.",
    "Consumers": "Who reacts to each event and how.",
    "Ordering": "Ordering guarantees and where they matter.",
    "Idempotency": "How duplicate delivery is handled safely.",
    "Schema Evolution": "How event schemas change without breakage.",
    "Queues and Topics": "The channels and their purposes.",
    "Delivery Semantics": "At-most-once, at-least-once, or exactly-once.",
    "Dead-Letter Handling": "What happens to messages that keep failing.",
    "Backpressure": "How producers are slowed when consumers lag.",
    "Cached Data": "What is cached and why it is safe to cache.",
    "Cache Layers": "Client, edge, application, and database layers.",
    "Invalidation": "How stale entries are removed.",
    "TTLs": "Time-to-live per data class with justification.",
    "Consistency Guarantees": "What staleness callers may observe.",
    "Traffic Profile": "Expected volume, shape, and seasonality.",
    "Balancing Algorithm": "How requests are distributed.",
    "Health Checks": "How unhealthy instances are detected.",
    "Session Handling": "Sticky sessions vs shared state.",
    "Failover": "What happens when an instance or zone dies.",
    "Metrics": "The signals that trigger scaling.",
    "Scaling Policies": "Rules for adding and removing capacity.",
    "Limits": "Minimum and maximum capacity bounds.",
    "Cooldowns": "Stabilization periods between actions.",
    "Cost Bounds": "The maximum spend scaling may cause.",
    "Failure Modes": "The ways each component can fail.",
    "Redundancy": "Duplication that survives single failures.",
    "Retries and Timeouts": "Bounded retry policy per call type.",
    "Circuit Breaking": "How cascading failure is cut off.",
    "Degradation Strategy": "What is shed first under load.",
    "RTO Target": "How quickly service must be restored.",
    "RPO Target": "How much data loss is tolerable.",
    "Recovery Dependencies": "What recovery itself depends on.",
    "Recovery Runbook": "Step-by-step restore procedure.",
    "Testing Schedule": "When recovery is rehearsed.",
    "Data Inventory": "The data that needs backup protection.",
    "Backup Types": "Full, incremental, and snapshot strategy.",
    "Schedule": "When backups run.",
    "Retention": "How long backups are kept.",
    "Backup Encryption": "How backups are protected at rest.",
    "Restore Testing": "How restores are verified.",
    "Trust Boundaries": "Where trust changes hands.",
    "Threat Model": "Adversaries, assets, and attack paths.",
    "Controls": "Preventive, detective, and corrective controls.",
    "Defense in Depth": "Layered controls for the same asset.",
    "Security Monitoring": "What is watched and alerted on.",
    "Identity Sources": "Where identities come from.",
    "Credential Types": "Passwords, passkeys, tokens, certificates.",
    "Multi-Factor Authentication": "Where MFA is required.",
    "Session Management": "Issue, refresh, expire, and revoke sessions.",
    "Account Recovery": "Regaining access without weakening security.",
    "Roles": "The roles and what each represents.",
    "Permissions": "Actions each role may perform.",
    "Policy Enforcement Points": "Where checks are enforced.",
    "Default Deny": "Anything not granted is refused.",
    "Grant Auditing": "How grants are recorded and reviewed.",
    "Data Classification": "Sensitivity levels of stored data.",
    "At-Rest Encryption": "How stored data is encrypted.",
    "In-Transit Encryption": "How moving data is encrypted.",
    "Algorithm Choices": "Approved algorithms and key sizes.",
    "Rotation Plan": "How and when keys and certs rotate.",
    "Key Types": "Master, data, and signing keys.",
    "Key Storage": "Managed KMS/HSM; keys are never embedded in artifacts.",
    "Rotation": "Rotation schedule per key type.",
    "Access Control": "Who may use which key for what.",
    "Revocation": "How compromised keys are retired.",
    "Audited Events": "The actions that must leave a record.",
    "Log Schema": "Actor, action, subject, timestamp, outcome.",
    "Tamper Protection": "How log integrity is preserved.",
    "Log Access Control": "Who may read audit logs.",
    "Applicable Regulations": "Which rules apply and why.",
    "Control Mapping": "Each regulation mapped to concrete controls.",
    "Evidence Collection": "How compliance evidence is gathered.",
    "Review Cadence": "When compliance is reassessed.",
    "Lawful Basis": "Why each data class may be processed.",
    "Data Minimization": "Only what is needed is collected.",
    "Consent": "How consent is obtained and withdrawn.",
    "Retention and Deletion": "Deletion timelines and enforcement.",
    "Impact Assessment": "Privacy risks and mitigations.",
    "Ownership": "Who owns each data asset.",
    "Classification": "How data is classified and labeled.",
    "Policies": "Rules for handling each class.",
    "Stewardship": "Who maintains quality and definitions.",
    "Quality Gates": "Checks data must pass before use.",
    "Sources": "Where data originates.",
    "Transformations": "Each step that changes the data.",
    "Destinations": "Where data ends up.",
    "Capture Method": "How lineage is recorded.",
    "Provenance Fields": "The fields every record carries.",
    "Quality Dimensions": "Accuracy, completeness, freshness, consistency.",
    "Validation Rules": "Concrete checks per data class.",
    "Monitoring": "How quality is measured continuously.",
    "Remediation": "What happens when quality fails.",
    "Service Level Targets": "Numeric quality targets.",
    "Extraction": "How data is pulled from each source and at what cadence.",
    "Load Targets": "Where transformed data lands and its schema there.",
    "Scheduling": "When jobs run, their dependencies, and SLAs.",
    "Data Validation": "Checks data must pass between stages.",
    "Recovery": "How failed runs are retried and replayed.",
    "Schema Model": "Star/snowflake layout and rationale.",
    "Partitioning": "How tables are partitioned and clustered.",
    "Query Patterns": "The analytical queries the design optimizes for.",
    "Load Strategy": "Full vs incremental loads and merge semantics.",
    "Storage Layout": "Bucket/prefix layout and lifecycle rules.",
    "Zones": "Raw, curated, and consumption zones and their contracts.",
    "File Formats": "Formats and compaction strategy per zone.",
    "Catalog": "How datasets are registered and discovered.",
    "Domains": "Bounded data domains and their boundaries.",
    "Data Products": "Products each domain publishes and their contracts.",
    "Federated Governance": "Global standards enforced across domains.",
    "Self-Serve Platform": "Shared tooling domains build on.",
    "Interoperability Standards": "Schemas, identifiers, and protocols shared across products.",
    "Topology": "The processing graph: operators and their connections.",
    "Windowing": "Window types, sizes, and triggers per computation.",
    "State Management": "Where operator state lives and how it recovers.",
    "Late Data": "How late and out-of-order events are handled.",
    "Scaling": "How throughput growth is absorbed.",
    "Jobs": "The batch jobs, their inputs, and their outputs.",
    "Resource Allocation": "Compute and memory budgets per job.",
    "Retry Policy": "Bounded retries and failure escalation per job.",
    "Output Contracts": "The guarantees every job output satisfies.",
    "Batch Layer": "The immutable master dataset and batch views.",
    "Speed Layer": "How recent data is covered before batch catches up.",
    "Serving Layer": "How batch and speed views merge for queries.",
    "Reconciliation": "How the two layers agree and conflicts resolve.",
    "Operational Complexity": "The cost of running two stacks, mitigated.",
    "Immutable Log": "The append-only log as the system of record.",
    "Reprocessing": "How history is replayed when logic changes.",
    "Serving Views": "Materialized views derived from the log.",
    "Pipeline Stages": "Ingest, validate, train, evaluate, register, ship.",
    "Data Versioning": "How datasets are versioned and linked to runs.",
    "Training Procedure": "Environment, config, and resource plan for training.",
    "Evaluation Gates": "Metric thresholds a model must pass to advance.",
    "Model Promotion": "How a candidate moves through stages to release.",
    "Orchestration": "How stages are scheduled, retried, and observed.",
    "Reproducibility": "How any run can be recreated exactly.",
    "Feature Definitions": "Canonical definitions and owners per feature.",
    "Offline Store": "Bulk historical features for training.",
    "Online Store": "Low-latency features for inference.",
    "Point-in-Time Correctness": "How training sets avoid leakage.",
    "Feature Versioning": "How feature changes roll out safely.",
    "Versioning Scheme": "How model versions are named and ordered.",
    "Metadata": "What is recorded per version: metrics, data, code, approvals.",
    "Stage Transitions": "States a version moves through and who moves it.",
    "Lineage": "Links from a model to its data, code, and experiments.",
    "Approval Gates": "Sign-offs required before each stage change.",
    "Rollback": "How a bad release is reverted.",
    "Monitored Signals": "Inputs, outputs, and outcomes watched per model.",
    "Drift Detection": "Statistical drift checks on features and predictions.",
    "Data Quality Checks": "Freshness, null, and distribution checks upstream.",
    "Alerting": "Thresholds, routing, and on-call ownership.",
    "Retraining Triggers": "Conditions that queue a retrain.",
    "Baselines": "Reference distributions and models for comparison.",
    "Experiment Lifecycle": "Draft, review, launch, analyze, decide.",
    "Assignment": "How units are randomized and kept consistent.",
    "Statistical Power": "Sample size and duration planning.",
    "Guardrails": "Metrics that stop an experiment automatically.",
    "Ramp Plan": "Staged exposure increase with checkpoints.",
    "Candidate Generation": "Recall sources: collaborative, content, trends.",
    "Ranking": "How candidates are ordered for a user.",
    "Features": "User, item, and context features used.",
    "Feedback Loop": "How interactions update the system.",
    "Cold Start": "Strategy for new users and new items.",
    "Offline Evaluation": "Replay and metric evaluation before any exposure.",
    "Indexing": "Document ingestion, analyzers, and index structure.",
    "Query Understanding": "Parsing, spelling, synonyms, and intent.",
    "Retrieval": "How candidate documents are fetched.",
    "Relevance Evaluation": "Labels, judgments, and relevance metrics.",
    "Latency Budget": "Per-stage latency targets for the query path.",
    "Model Choice": "Model family selected and why.",
    "Training Data": "Source, labeling, and volume of training data.",
    "Online Serving": "How ranked results are produced at request time.",
    "Bias Controls": "How exposure and ordering bias is limited.",
    "Evaluation": "Metrics, datasets, and review protocol.",
    "Fraud Taxonomy": "Fraud types the system targets.",
    "Signals": "Behavioral, device, and network signals used.",
    "Rules and Models": "Deterministic rules alongside learned models.",
    "Decisioning": "Allow, review, or block: thresholds and actions.",
    "Review Workflow": "How flagged cases reach human reviewers.",
    "False Positive Budget": "The tolerated false-positive rate and its cost.",
    "Detection Methods": "Statistical and learned detectors per signal.",
    "Sensitivity Tuning": "How thresholds balance alerts vs misses.",
    "Alert Routing": "Where anomalies go and who acts on them.",
    "Data Characteristics": "Trend, seasonality, and noise profile.",
    "Validation Strategy": "Time-aware splits that prevent leakage.",
    "Horizon and Granularity": "How far ahead and at what resolution.",
    "Backtesting": "Rolling-origin evaluation protocol.",
    "Tasks": "The language tasks covered and their scope.",
    "Data Sources": "Corpora, licenses, and coverage.",
    "Safety Filters": "How harmful inputs and outputs are screened.",
    "Preprocessing": "Resize, normalize, and augment steps.",
    "Safety and Consent": "Consent for image use and content screening.",
    "Audio Inputs": "Sample rates, channels, and noise conditions.",
    "Language Support": "Languages and dialects covered.",
    "Streaming vs Batch": "Where each transcription mode applies.",
    "Voices": "Voice catalog, licensing, and selection.",
    "Text Normalization": "Numbers, dates, and abbreviations expanded before synthesis.",
    "Consent and Disclosure": "Voice consent and synthetic-speech disclosure.",
    "Language Pairs": "Supported pairs and their quality bar.",
    "Domain Adaptation": "Glossaries and fine-tuning per domain.",
    "Human Review": "Where human post-editing fits.",
    "Input Constraints": "Length, language, and format limits.",
    "Factuality Controls": "How summaries are kept faithful to source.",
    "Question Types": "Factoid, list, and reasoning questions in scope.",
    "Answer Sources": "Corpora and knowledge bases answers come from.",
    "Retrieval and Reading": "How evidence is found and answers extracted.",
    "Answer Validation": "How answers are checked before presentation.",
    "Fallback Behavior": "What happens when no confident answer exists.",
    "Target Schema": "The structured fields extraction must produce.",
    "Source Documents": "Document types and their formats.",
    "Extraction Methods": "Rules, models, and where each applies.",
    "Confidence Scoring": "How extraction confidence is computed and used.",
    "Human Verification": "Where low-confidence output gets human review.",
    "Entity Types": "The entity classes recognized and their boundaries.",
    "Labeling Guidelines": "Annotation rules that keep labels consistent.",
    "Edge Cases": "Nested, partial, and ambiguous mentions and their handling.",
    "Relation Types": "The relations extracted and their signatures.",
    "Entity Linking": "How mentions resolve to canonical entities.",
    "Extraction Approach": "Pipeline vs joint extraction and why.",
    "Sentiment Taxonomy": "Labels and intensity scale used.",
    "Aspect Handling": "How per-aspect sentiment is separated.",
    "Corpus Scope": "The documents included and excluded.",
    "Method Choice": "Technique selected and alternatives rejected.",
    "Topic Granularity": "How many topics and how that is chosen.",
    "Labeling": "How topics and clusters get human-readable names.",
    "Stability Checks": "How topic stability across runs is verified.",
    "Label Set": "The classes, their definitions, and exclusivity rules.",
    "Thresholds": "Decision thresholds per class and their rationale.",
    "Drift Handling": "How distribution shift is detected and absorbed.",
    "Representation": "How documents become vectors or features.",
    "Algorithm Choice": "Clustering algorithm and why it fits.",
    "Cluster Count": "How the number of clusters is chosen.",
    "Quality Checks": "How output correctness is verified.",
    "Embedding Model": "Embedding model selected and its dimensions.",
    "Index Structure": "Vector index type and its recall/latency profile.",
    "Hybrid Retrieval": "How lexical and vector signals combine.",
    "Reranking": "Second-stage ordering of retrieved candidates.",
    "Entity Resolution": "How duplicate entities are merged.",
    "Schema": "Node and edge types with their properties.",
    "Ingestion Sources": "Where graph facts come from.",
    "Storage": "Graph store choice and layout.",
    "Query Interface": "How consumers query the graph.",
    "Concept Hierarchy": "Classes and their is-a structure.",
    "Properties": "Relations and attributes per concept.",
    "Naming Conventions": "Identifier and label rules.",
    "Alignment": "Mapping to external vocabularies.",
    "Knowledge Representation": "How facts and rules are encoded.",
    "Inference Rules": "The deduction rules supported.",
    "Conflict Resolution": "How contradictory facts are handled.",
    "Explainability": "How conclusions trace back to premises.",
    "Performance Bounds": "Complexity limits and termination guarantees.",
    "State Model": "How the world state is represented.",
    "Action Model": "Actions, preconditions, and effects.",
    "Planner Choice": "Planning algorithm and why it fits.",
    "Plan Validation": "How a candidate plan is checked before use.",
    "Replanning": "When and how plans are revised mid-execution.",
    "Failure Handling": "What happens when no plan exists or a step fails.",
    "Resources": "The resources allocated and their capacities.",
    "Objective Function": "What the solver maximizes or minimizes.",
    "Solver Choice": "Solver selected and why it fits the problem class.",
    "Rescheduling": "How disruptions trigger partial replans.",
    "Fairness": "How allocation fairness is defined and enforced.",
    "Decision Variables": "The variables the optimizer controls.",
    "Feasibility Handling": "What happens when constraints cannot all hold.",
    "Sensitivity Analysis": "How answers change with input perturbation.",
    "Model Scope": "What the simulation includes and abstracts away.",
    "State Representation": "The simulated state and its granularity.",
    "Time Advancement": "Fixed-step vs event-driven time.",
    "Randomness Control": "Seeds and reproducibility of runs.",
    "Validation": "How the artifact's correctness is checked.",
    "Scenario Management": "How scenarios are defined, stored, and compared.",
    "Game Loop": "Tick structure, update order, and timing.",
    "Entity Model": "Entity-component layout and ownership.",
    "Input Handling": "Input sampling, buffering, and latency.",
    "State Synchronization": "How state stays consistent across views or peers.",
    "Asset Pipeline": "How assets are imported, processed, and loaded.",
    "Performance Budget": "Frame-time and memory budgets per subsystem.",
    "Simulation Domain": "Bodies, forces, and constraints modeled.",
    "Numerical Methods": "Integrators and solvers used, with stability notes.",
    "Collision Handling": "Broad and narrow phase collision design.",
    "Determinism": "Where deterministic replay is required and how.",
    "Render Pipeline": "Stages from scene data to pixels.",
    "Scene Representation": "Scene graph and spatial structures.",
    "Lighting Model": "Shading and lighting approach.",
    "Asset Formats": "Mesh, texture, and material formats.",
    "Platform Targets": "Hardware and API targets with fallbacks.",
    "Audio Graph": "Nodes and routing of the audio pipeline.",
    "Formats and Codecs": "Supported formats and decode strategy.",
    "Mixing": "Buses, levels, and dynamics processing.",
    "Spatial Audio": "Positioning model and its cost.",
    "Device Handling": "Output device selection and failover.",
    "Transport Choices": "Protocols per traffic class and why.",
    "Addressing": "Naming and addressing scheme.",
    "Reliability": "Retransmission, ordering, and loss handling.",
    "Security Controls": "Network-layer protections.",
    "Capacity Plan": "Bandwidth and connection budgets.",
    "Message Formats": "Wire format, framing, and field encoding.",
    "State Machine": "Protocol states and legal transitions.",
    "Error Handling": "How errors are signaled and recovered.",
    "Security": "Authentication and integrity protection in-protocol.",
    "Conformance Testing": "How implementations are checked against the spec.",
    "Data Profile": "The data compressed and its redundancy shape.",
    "Compression Levels": "Speed/ratio levels exposed and their defaults.",
    "Integrity Checks": "How corruption is detected on decode.",
    "Benchmark Protocol": "Corpora and metrics for comparison runs.",
    "Compatibility": "Interoperability with existing decoders.",
    "Error Model": "The corruption patterns defended against.",
    "Code Choice": "Error-correcting code selected and why.",
    "Redundancy Budget": "Overhead added and its cost.",
    "Decoding Strategy": "Hard vs soft decision decoding.",
    "Failure Behavior": "What happens beyond correction capacity.",
    "Security Goals": "Confidentiality, integrity, and authentication targets.",
    "Primitives": "Approved primitives; never novel constructions.",
    "Key Exchange": "How session keys are established and rotated.",
    "Formal Analysis": "How the protocol is verified against its goals.",
    "Implementation Pitfalls": "Known misuse traps and their guards.",
}



_DESIGN_ARTIFACT_NOTICE = (
    "Design artifact. Describes planned work only; it is not evidence of "
    "deployment, operation, trained models, or achieved performance."
)


@dataclass(frozen=True)
class DesignDocument:
    kind: str
    row: int
    title: str
    markdown: str
    generated_at: str
    evaluation: Dict[str, object] = field(default_factory=dict)
    uncertainty: Dict[str, object] = field(default_factory=dict)


def generate_design(
    kind: str,
    project_goal: str,
    context: Optional[Mapping[str, str]] = None,
    generated_at: Optional[datetime] = None,
) -> DesignDocument:
    """Generate a deterministic design scaffold for a kind.

    Content is honest scaffolding: every section names what it must contain,
    seeded with the project goal and any caller-supplied context notes.
    """
    spec = spec_for_kind(kind)
    stamp = (generated_at or datetime.now(timezone.utc)).isoformat()
    context = dict(context or {})
    lines = [
        f"# {spec.title}",
        "",
        f"- **Project goal:** {project_goal}",
        f"- **Design kind:** {spec.kind} (features-doc row {spec.row})",
        f"- **Generated:** {stamp}",
        f"- **Status:** {_DESIGN_ARTIFACT_NOTICE}",
        "",
    ]
    for section in spec.required_sections:
        lines.append(f"## {section}")
        lines.append("")
        guidance = _SECTION_GUIDANCE.get(section, f"{section} for this design.")
        note = context.get(section, "").strip()
        lines.append(f"{guidance}")
        if note:
            lines.append("")
            lines.append(f"Project note: {note}")
        lines.append("")
    return DesignDocument(
        kind=spec.kind, row=spec.row, title=spec.title,
        markdown="\n".join(lines), generated_at=stamp,
        evaluation={"required_sections": list(spec.required_sections), "context_sections_supplied": sorted(context), "validation_required": True},
        uncertainty={"level": "not_quantified", "drivers": ["design assumptions", "unimplemented system", "unmeasured workload and operating conditions"], "deployment_or_performance_claimed": False},
    )


# --- Validation ---------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(
    r"\b(TBD|TODO|FIXME|XXX)\b|<placeholder|\bto be (decided|determined|filled)\b|"
    r"lorem ipsum",
    re.IGNORECASE,
)
# A design document must never claim a running system.
_OPERATIONAL_CLAIM_RE = re.compile(
    r"\b(is|are|was|were|currently)\s+(deployed|live|running|serving|operational)\b|"
    r"\bin production\b|\b\d+(\.\d+)?\s?%\s*(uptime|availability|sla)\b|"
    r"\bachieved\s+\d|"
    r"\b\d+(\.\d+)?\s?%\s*(accuracy|precision|recall|f1|auc|wer|bleu|rouge)\b|"
    r"\b(f1|auc|accuracy|precision|recall|wer|bleu|rouge)\s*(of|=|was|is)\s*\d|"
    r"\bwe (trained|measured|evaluated|benchmarked|tested)\b",
    re.IGNORECASE,
)
# Secrets never belong in an artifact. Patterns cover private keys, common
# cloud key formats, and inline credential assignments with real values.
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(
        r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|"
        r"private[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9/+_.\-]{12,}['\"]?"
    ),
)


@dataclass(frozen=True)
class DesignFinding:
    check: str
    severity: str  # "error" | "warning"
    message: str
    remediation: str


@dataclass(frozen=True)
class DesignValidationReport:
    kind: str
    row: int
    passed: bool
    score: float
    findings: Tuple[DesignFinding, ...]
    remediation: Tuple[str, ...]

    def to_quality_result(self) -> Dict[str, object]:
        return {
            "passed": self.passed,
            "score": self.score,
            "findings": [f.message for f in self.findings],
            "remediation": list(self.remediation),
        }


def _section_bodies(markdown: str) -> Dict[str, str]:
    """Split markdown into '## Section' -> body text (until next heading)."""
    sections: Dict[str, str] = {}
    current: Optional[str] = None
    body: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(body).strip()
            current = line[3:].strip()
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = "\n".join(body).strip()
    return sections


def validate_design(document: DesignDocument) -> DesignValidationReport:
    """Validate a design document against its kind's contract."""
    spec = spec_for_kind(document.kind)
    findings = []
    sections = _section_bodies(document.markdown)
    for required in spec.required_sections:
        if required not in sections:
            findings.append(DesignFinding(
                check="section_present", severity="error",
                message=f"missing required section: {required!r}",
                remediation=f"add a '## {required}' section",
            ))
        elif not sections[required]:
            findings.append(DesignFinding(
                check="section_nonempty", severity="error",
                message=f"section {required!r} is empty",
                remediation="fill the section with real content",
            ))
    placeholder_hits = sorted(set(
        m.group(0) for m in _PLACEHOLDER_RE.finditer(document.markdown)
    ))
    if placeholder_hits:
        findings.append(DesignFinding(
            check="no_placeholders", severity="error",
            message="placeholder markers found: " + ", ".join(placeholder_hits),
            remediation="replace every placeholder with concrete content",
        ))
    operational_hits = sorted(set(
        m.group(0) for m in _OPERATIONAL_CLAIM_RE.finditer(document.markdown)
    ))
    if operational_hits:
        findings.append(DesignFinding(
            check="no_operational_claims", severity="error",
            message=(
                "design artifact claims operational state: "
                + ", ".join(operational_hits)
            ),
            remediation=(
                "remove deployment/uptime claims; a design document only "
                "describes planned work"
            ),
        ))
    secret_hits = sum(
        1 for pattern in _SECRET_PATTERNS if pattern.search(document.markdown)
    )
    if secret_hits:
        findings.append(DesignFinding(
            check="no_secrets", severity="error",
            message=f"possible embedded secrets detected ({secret_hits} patterns)",
            remediation=(
                "remove all credentials; reference a key manager by name, "
                "never embed values"
            ),
        ))
    errors = sum(1 for f in findings if f.severity == "error")
    score = max(0.0, 1.0 - 0.25 * errors)
    return DesignValidationReport(
        kind=spec.kind, row=spec.row, passed=errors == 0, score=round(score, 6),
        findings=tuple(findings),
        remediation=tuple(dict.fromkeys(f.remediation for f in findings)),
    )
