"""Fail-closed cross-module workflows for Atlas integration proofs.

The workflows deliberately stop at a durable human-review request.  They do
not send, publish, submit, or otherwise produce an external side effect.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import Service as ApprovalService
from app.modules.m14_project_builder.artifacts import (
    ArtifactRecord,
    KindRegistry,
    KindSpec,
    build_manifest,
    validate_artifact,
)
from app.modules.m17_advice_essay.in_memory_repository import InMemoryModule17Repository
from app.modules.m17_advice_essay.schemas import AdviceSource, EssayBrief, IdentityMaterial
from app.modules.m17_advice_essay.service import AdviceEssayService
from app.modules.m20_general_cognitive_worker.htn_planner import HTNPlanner, PlannerModel
from app.modules.m20_general_cognitive_worker.schemas import Risk, ToolSpec
from app.modules.m20_general_cognitive_worker.safety import ConstitutionalRules, SafetyGate
from app.modules.m20_general_cognitive_worker.tools import ToolDispatcher, ToolRegistry


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewState(str):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class DocumentVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(min_length=1, max_length=120)
    document_id: UUID
    version: int = Field(ge=1)
    parent_version_id: UUID | None = None
    content: str = Field(min_length=1, max_length=100_000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    student_authored: bool
    created_at: datetime = Field(default_factory=_now)


class EssayWorkflowRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    owner_id: UUID
    advice_sources: list[AdviceSource] = Field(min_length=1, max_length=25)
    identity_materials: list[IdentityMaterial] = Field(min_length=1, max_length=25)
    prompt: str = Field(min_length=1, max_length=5000)
    word_limit: int = Field(ge=50, le=5000)
    student_draft: str = Field(min_length=1, max_length=100_000)
    student_authored: bool

    @model_validator(mode="after")
    def ownership_is_consistent(self) -> "EssayWorkflowRequest":
        resources = [*self.advice_sources, *self.identity_materials]
        if any(item.owner_id != self.owner_id for item in resources):
            raise ValueError("all advice and identity material must belong to the owner")
        if not self.student_authored:
            raise ValueError("essay workflow accepts only student-authored draft text")
        return self


class EssayWorkflowResult(BaseModel):
    tenant_id: str
    document_version: DocumentVersion
    concept_ids: list[UUID]
    critique_findings: int = Field(ge=0)
    advice_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: list[str]
    approval_id: str
    review_state: str = ReviewState.PENDING
    external_side_effects: bool = False


class VersionStore:
    """Tenant-scoped, append-only document version store."""

    def __init__(self) -> None:
        self._versions: dict[UUID, list[DocumentVersion]] = {}

    def append(
        self,
        *,
        tenant_id: str,
        content: str,
        student_authored: bool,
        document_id: UUID | None = None,
    ) -> DocumentVersion:
        if not student_authored:
            raise ValueError("generated prose cannot be stored as student-authored")
        document_id = document_id or uuid4()
        history = self._versions.setdefault(document_id, [])
        if history and history[0].tenant_id != tenant_id:
            raise PermissionError("tenant mismatch")
        previous = history[-1] if history else None
        version = DocumentVersion(
            tenant_id=tenant_id,
            document_id=document_id,
            version=len(history) + 1,
            parent_version_id=previous.id if previous else None,
            content=content,
            content_sha256=sha256(content.encode("utf-8")).hexdigest(),
            student_authored=True,
        )
        history.append(version)
        return version.model_copy(deep=True)

    def get(self, tenant_id: str, document_id: UUID, version: int) -> DocumentVersion:
        history = self._versions.get(document_id, [])
        if not history or history[0].tenant_id != tenant_id:
            raise KeyError(document_id)
        if version < 1 or version > len(history):
            raise KeyError(version)
        return history[version - 1].model_copy(deep=True)


class EssayReviewWorkflow:
    def __init__(self, approvals: ApprovalService, versions: VersionStore | None = None) -> None:
        self.approvals = approvals
        self.versions = versions or VersionStore()
        self._approval_bindings: dict[str, tuple[str, UUID, int]] = {}

    def start(self, request: EssayWorkflowRequest) -> EssayWorkflowResult:
        repository = InMemoryModule17Repository()
        service = AdviceEssayService(repository)
        for source in request.advice_sources:
            service.ingest_source(source)
        tips = service.compile_advice(request.owner_id)
        for material in request.identity_materials:
            service.add_identity_material(material)
        concepts = service.create_concepts(EssayBrief(
            owner_id=request.owner_id,
            prompt=request.prompt,
            word_limit=request.word_limit,
            material_ids=[item.id for item in request.identity_materials],
            requested_concepts=min(3, len(request.identity_materials) + 1),
        ))
        critique = service.critique(request.owner_id, request.prompt, request.student_draft)
        version = self.versions.append(
            tenant_id=request.tenant_id,
            content=request.student_draft,
            student_authored=request.student_authored,
        )
        approval = self.approvals.submit(
            module_id=17,
            action_type="review_student_essay_version",
            payload={
                "document_id": str(version.document_id),
                "version": version.version,
                "content_sha256": version.content_sha256,
                "concept_ids": [str(item.id) for item in concepts],
                "critique_findings": len(critique.findings),
            },
            user_id=request.tenant_id,
        )
        self._approval_bindings[approval["id"]] = (
            request.tenant_id, version.document_id, version.version,
        )
        confidence = sum(tip.confidence for tip in tips) / len(tips) if tips else 0.0
        uncertainty = sorted({caveat for tip in tips for caveat in tip.caveats})
        if critique.findings:
            uncertainty.append("The student draft still has critique findings to review.")
        return EssayWorkflowResult(
            tenant_id=request.tenant_id,
            document_version=version,
            concept_ids=[item.id for item in concepts],
            critique_findings=len(critique.findings),
            advice_confidence=confidence,
            uncertainty=uncertainty,
            approval_id=approval["id"],
        )

    def review_state(self, *, tenant_id: str, approval_id: str) -> str:
        binding = self._approval_bindings.get(approval_id)
        if binding is None or binding[0] != tenant_id:
            raise KeyError(approval_id)
        approval = self.approvals.get(approval_id)
        if approval["user_id"] != tenant_id:
            raise PermissionError("tenant mismatch")
        return str(approval["status"].value)


class LocalToolDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk: Risk = Risk.READ
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    max_retries: int = Field(default=1, ge=1, le=3)


class CognitiveWorkflowRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=5000)
    context: str = Field(default="", max_length=20_000)
    project_id: str = Field(min_length=1, max_length=120)
    max_tool_calls: int = Field(default=5, ge=1, le=25)
    allowed_tools: set[str] = Field(min_length=1, max_length=25)


class EvidenceItem(BaseModel):
    step_id: str
    tool: str
    succeeded: bool
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: str = Field(max_length=500)


class CognitiveWorkflowResult(BaseModel):
    tenant_id: str
    task_id: str
    plan_steps: int = Field(ge=1)
    tool_calls: int = Field(ge=0)
    evidence: list[EvidenceItem]
    artifact: dict[str, Any]
    artifact_quality: float = Field(ge=0.0, le=1.0)
    approval_id: str
    review_state: str = ReviewState.PENDING
    uncertainty: list[str]
    external_side_effects: bool = False


LocalToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class CognitiveEvidenceWorkflow:
    """Runs bounded, local M20 plans and stops at an M0 artifact review gate."""

    def __init__(self, approvals: ApprovalService, planner_model: PlannerModel) -> None:
        self.approvals = approvals
        self.planner = HTNPlanner(model=planner_model)
        self._tools: dict[str, tuple[LocalToolDefinition, LocalToolHandler]] = {}
        self._approval_bindings: dict[str, tuple[str, str]] = {}

    def register_local_tool(self, definition: LocalToolDefinition, handler: LocalToolHandler) -> None:
        if definition.risk in {Risk.EXTERNAL, Risk.IRREVERSIBLE}:
            raise ValueError("cross-module proof permits only local read/reversible tools")
        if definition.name in self._tools:
            raise ValueError(f"duplicate tool: {definition.name}")
        self._tools[definition.name] = (definition, handler)

    async def run(self, request: CognitiveWorkflowRequest) -> CognitiveWorkflowResult:
        plan = self.planner.decompose(request.goal, context=request.context)
        if len(plan) > request.max_tool_calls:
            raise ValueError("decomposition exceeds tool-call budget")
        task_id = str(uuid4())
        registry = ToolRegistry()
        results: dict[str, dict[str, Any]] = {}
        for name in request.allowed_tools:
            if name not in self._tools:
                raise ValueError(f"allowed tool is not registered: {name}")
            definition, handler = self._tools[name]

            async def recording_handler(arguments: dict[str, Any], *, _name=name, _handler=handler) -> dict[str, Any]:
                value = await _handler(arguments)
                if not isinstance(value, dict):
                    raise TypeError("local tool handlers must return dictionaries")
                results[_name] = value
                return value

            registry.register(ToolSpec(
                name=name,
                description=definition.description,
                parameters=definition.parameters,
                risk=definition.risk,
                timeout_seconds=definition.timeout_seconds,
                max_retries=definition.max_retries,
            ), recording_handler)
        dispatcher = ToolDispatcher(registry, SafetyGate(rules=ConstitutionalRules()))
        evidence: list[EvidenceItem] = []
        succeeded: set[str] = set()
        pending = {node.id: node for node in plan}
        while pending:
            ready = [node for node in plan if node.id in pending and all(dep in succeeded for dep in node.depends_on)]
            if not ready:
                raise ValueError("plan cannot make progress")
            for node in ready:
                if not node.tool or node.tool not in request.allowed_tools:
                    raise ValueError(f"plan requested disallowed or missing tool: {node.tool!r}")
                if node.risk in {Risk.EXTERNAL, Risk.IRREVERSIBLE}:
                    raise ValueError("plan contains an external or irreversible step")
                record = await dispatcher.dispatch(node.tool, node.arguments, task_id=task_id)
                value = results[node.tool]
                canonical = repr(sorted(value.items())).encode("utf-8")
                evidence.append(EvidenceItem(
                    step_id=node.id,
                    tool=node.tool,
                    succeeded=record.succeeded,
                    result_sha256=sha256(canonical).hexdigest(),
                    summary=record.result_summary,
                ))
                if not record.succeeded:
                    raise RuntimeError(f"tool failed: {node.tool}")
                succeeded.add(node.id)
                del pending[node.id]
                if len(evidence) > request.max_tool_calls:
                    raise ValueError("tool-call budget exceeded")
        payload = CognitiveWorkflowResult.model_json_schema().__repr__().encode("utf-8")
        evidence_payload = "\n".join(item.model_dump_json() for item in evidence).encode("utf-8")
        payload = evidence_payload or payload
        registry_kinds = KindRegistry()
        registry_kinds.register(KindSpec(
            "workflow_evidence",
            required_provenance=("generator", "created_at", "goal_sha256"),
            reproducibility_keys=("generator", "goal_sha256"),
        ))
        artifact = build_manifest(
            project_id=request.project_id,
            task_id=task_id,
            kind="workflow_evidence",
            uri=f"workspace://{request.tenant_id}/{task_id}/evidence.jsonl",
            payload=payload,
            provenance={
                "generator": "m20-cognitive-evidence-workflow/v1",
                "created_at": _now().isoformat(),
                "goal_sha256": sha256(request.goal.encode("utf-8")).hexdigest(),
                "tenant_id": request.tenant_id,
            },
            registry=registry_kinds,
        )
        quality = validate_artifact(artifact, payload=payload, registry=registry_kinds)
        if not quality.passed:
            raise RuntimeError("artifact validation failed")
        approval = self.approvals.submit(
            module_id=20,
            action_type="approve_bounded_workflow_artifact",
            payload={
                "artifact_id": artifact.id,
                "artifact_sha256": artifact.sha256,
                "task_id": task_id,
                "tool_calls": len(evidence),
            },
            user_id=request.tenant_id,
        )
        self._approval_bindings[approval["id"]] = (request.tenant_id, artifact.id)
        uncertainty = []
        if len(evidence) == 1:
            uncertainty.append("Artifact is supported by one tool result; independent corroboration is absent.")
        return CognitiveWorkflowResult(
            tenant_id=request.tenant_id,
            task_id=task_id,
            plan_steps=len(plan),
            tool_calls=len(evidence),
            evidence=evidence,
            artifact={
                "id": artifact.id,
                "kind": artifact.kind,
                "uri": artifact.uri,
                "sha256": artifact.sha256,
                "provenance": dict(artifact.provenance),
            },
            artifact_quality=quality.score,
            approval_id=approval["id"],
            uncertainty=uncertainty,
        )

    def review_state(self, *, tenant_id: str, approval_id: str, artifact_id: str) -> str:
        binding = self._approval_bindings.get(approval_id)
        if binding != (tenant_id, artifact_id):
            raise KeyError(approval_id)
        approval = self.approvals.get(approval_id)
        if approval["user_id"] != tenant_id:
            raise PermissionError("tenant mismatch")
        return str(approval["status"].value)
