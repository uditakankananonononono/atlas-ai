"""Tenant-bound service wiring for the measured autonomy runtime."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.models import ApprovalStatus
from app.modules.m00_approval_center.service import default_service
from app.modules.m25_knowledge_copilot.artifact_events import ArtifactEventStore

from .agi_evaluation import AGIProvenanceRecorder, CrossDomainTransferBenchmark, TransferCase
from .agi_runtime import AutonomousGoalEngine, PersistentWorldModel
from .safety import ApprovalGate
from .schemas import ApprovalGateDecision, ApprovalGateRequest


class ModuleZeroGCWApprovalGate(ApprovalGate):
    """Maps the GCW protocol to Module 0 without losing tenant or payload."""

    def __init__(self, tenant_id: str, center=None) -> None:
        self.tenant_id = tenant_id
        self.center = center or default_service()

    def request(self, request: ApprovalGateRequest) -> str:
        view = self.center.submit(
            module_id=request.module_id, action_type=request.action_type,
            user_id=self.tenant_id,
            ttl_seconds=(int((request.expires_at-request.created_at).total_seconds())
                         if request.expires_at else None),
            payload={**request.payload, "gcw_request_id": request.id,
                     "summary": request.summary, "risk": request.risk.value,
                     "task_id": request.task_id},
        )
        return str(view["id"])

    def decision(self, approval_id: str) -> ApprovalGateDecision:
        view = self.center.get(approval_id)
        if view.get("user_id") != self.tenant_id:
            return ApprovalGateDecision.PENDING
        return {ApprovalStatus.APPROVED.value: ApprovalGateDecision.APPROVED,
                ApprovalStatus.DENIED.value: ApprovalGateDecision.REJECTED,
                ApprovalStatus.EXPIRED.value: ApprovalGateDecision.EXPIRED}.get(
                    str(view["status"]), ApprovalGateDecision.PENDING)


class AGIRuntimeService:
    """One tenant's durable world model, bounded goals and evaluations."""

    STRATEGIES = {
        "sum_items": lambda problem: sum(problem["items"]),
        "sorted_items": lambda problem: sorted(problem["items"]),
        "identity": lambda problem: problem["value"],
    }

    def __init__(self, tenant_id: str, *, data_dir: str | None = None,
                 approval_gate: ApprovalGate | None = None,
                 producer_version: str | None = None) -> None:
        root = Path(data_dir or os.getenv("ATLAS_AGI_DATA_DIR", "/tmp/atlas-agi"))
        root.mkdir(parents=True, exist_ok=True)
        self.tenant_id = tenant_id
        self.world = PersistentWorldModel(str(root / "world.sqlite"), tenant_id)
        self.approvals = approval_gate or ModuleZeroGCWApprovalGate(tenant_id)
        self.goals = AutonomousGoalEngine(self.approvals)
        self.events = ArtifactEventStore(root / "events.sqlite")
        self.provenance = AGIProvenanceRecorder(
            self.events, tenant_id, producer_version or os.getenv("ATLAS_VERSION", "development"),
        )

    def evaluate_transfer(self, *, strategy: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
        if strategy not in self.STRATEGIES:
            raise KeyError(strategy)
        typed = [TransferCase(**case) for case in cases]
        report = CrossDomainTransferBenchmark(typed).run(self.STRATEGIES[strategy])
        stored = self.provenance.record(
            artifact_kind="cross_domain_transfer_evaluation", artifact=report,
            source_refs=[{"uri": f"atlas://m20/strategies/{strategy}"}],
        )
        return {**report, "provenance_event_id": stored["event"]["event_id"],
                "artifact_sha256": stored["event"]["content_sha256"]}
