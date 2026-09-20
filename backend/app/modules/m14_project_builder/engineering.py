"""Engineering design artifacts for Atlas Module 14 (Project Builder).

Covers features-doc rows 510-534 (Technical & Engineering foundations):
typed, evidence-bearing design documents - requirements, architecture,
API, schema, monolith/microservice/event/queue/cache/load/scale/fault/DR/
backup plans, and security/authn/authz/encryption/key-management/audit/
compliance/privacy/governance/lineage/quality designs.

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
}

_DESIGN_ARTIFACT_NOTICE = (
    "Design artifact. Describes planned work only; it is not evidence of "
    "deployment, operation, or achieved performance."
)


@dataclass(frozen=True)
class DesignDocument:
    kind: str
    row: int
    title: str
    markdown: str
    generated_at: str


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
    r"\bachieved\s+\d",
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
