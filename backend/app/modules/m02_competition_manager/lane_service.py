"""Competition application orchestration and approval-safe execution."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from typing import Any, Callable, Mapping, Protocol

from .models import (ActionState, ApplicationStatus, ApplicationWorkspace, ChecklistItem,
                     StagedBrowserAction, StatusObservation, TERMINAL_STATUSES, utcnow)
from .parser import parse_competition_document
from .repository import CompetitionRepository


class ApprovalVerifier(Protocol):
    def verify(self, approval_id: str, *, action_id: str, payload_digest: str) -> bool: ...


class BrowserExecutor(Protocol):
    def execute(self, action: str, target_url: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...


_ALLOWED_TRANSITIONS = {
    ApplicationStatus.DISCOVERED: {ApplicationStatus.PREPARING, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.PREPARING: {ApplicationStatus.READY, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.READY: {ApplicationStatus.PREPARING, ApplicationStatus.STAGED, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.STAGED: {ApplicationStatus.SUBMITTED, ApplicationStatus.READY, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.SUBMITTED: {ApplicationStatus.ACCEPTED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.ACCEPTED: set(), ApplicationStatus.REJECTED: set(), ApplicationStatus.WITHDRAWN: set(),
}


def payload_digest(action: str, target_url: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps({"action": action, "target_url": target_url, "payload": payload}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class CompetitionManager:
    def __init__(self, repository: CompetitionRepository) -> None:
        self.repo = repository
        self._observations: dict[str, list[StatusObservation]] = {}

    def create_workspace(self, competition_id: str, title: str, sources: list[dict[str, str]]) -> ApplicationWorkspace:
        if not competition_id.strip() or not title.strip() or not sources:
            raise ValueError("competition_id, title and at least one source are required")
        facts = []
        for source in sources:
            facts.extend(parse_competition_document(source["text"], source["id"], url=source.get("url")))
        workspace = ApplicationWorkspace(competition_id=competition_id, title=title, source_ids=[s["id"] for s in sources], facts=facts)
        material_names: set[str] = set()
        for fact in facts:
            if fact.kind == "material" and fact.value["name"] not in material_names:
                material_names.add(fact.value["name"])
                workspace.checklist.append(ChecklistItem(title=f"Prepare {fact.value['name']}", required=fact.value["required"], evidence_ids=[fact.evidence.source_id]))
        deadline = next((f for f in facts if f.kind == "deadline"), None)
        if deadline:
            due = datetime.fromisoformat(deadline.value)
            for item in workspace.checklist: item.due_at = due
        workspace.status = ApplicationStatus.PREPARING
        return self.repo.save_workspace(workspace)

    def add_checklist_item(self, workspace_id: str, title: str, *, required: bool = True, dependency_ids: set[str] | None = None) -> ChecklistItem:
        ws = self.repo.get_workspace(workspace_id); version = ws.version
        deps = dependency_ids or set()
        known = {item.id for item in ws.checklist}
        missing = deps - known
        if missing: raise ValueError(f"unknown dependencies: {sorted(missing)}")
        item = ChecklistItem(title=title, required=required, dependency_ids=set(deps))
        ws.checklist.append(item); ws.updated_at = utcnow()
        self.repo.save_workspace(ws, expected_version=version)
        return item

    def complete_item(self, workspace_id: str, item_id: str, *, material_ref: str | None = None) -> ApplicationWorkspace:
        ws = self.repo.get_workspace(workspace_id); version = ws.version
        by_id = {i.id: i for i in ws.checklist}
        if item_id not in by_id: raise KeyError(item_id)
        item = by_id[item_id]
        blocked = [dep for dep in item.dependency_ids if not by_id[dep].completed]
        if blocked: raise ValueError(f"incomplete dependencies: {blocked}")
        item.completed = True
        if material_ref: ws.materials[item_id] = material_ref
        if ws.required_complete() and ws.status == ApplicationStatus.PREPARING: ws.status = ApplicationStatus.READY
        ws.updated_at = utcnow()
        return self.repo.save_workspace(ws, expected_version=version)

    def transition(self, workspace_id: str, status: ApplicationStatus) -> ApplicationWorkspace:
        ws = self.repo.get_workspace(workspace_id); version = ws.version
        if status not in _ALLOWED_TRANSITIONS[ws.status]: raise ValueError(f"invalid transition {ws.status.value} -> {status.value}")
        if status == ApplicationStatus.READY and not ws.required_complete(): raise ValueError("required checklist items are incomplete")
        ws.status = status; ws.updated_at = utcnow()
        return self.repo.save_workspace(ws, expected_version=version)

    def stage_browser_action(self, workspace_id: str, action: str, target_url: str, payload: dict[str, Any]) -> StagedBrowserAction:
        ws = self.repo.get_workspace(workspace_id); version = ws.version
        if ws.status != ApplicationStatus.READY: raise ValueError("workspace must be ready before staging")
        if action not in {"fill_form", "upload_materials", "submit_application", "withdraw_application"}: raise ValueError("unsupported browser action")
        if not target_url.startswith("https://"): raise ValueError("target_url must use https")
        staged = StagedBrowserAction(application_id=workspace_id, action=action, target_url=target_url, payload=dict(payload))
        staged.payload_digest = payload_digest(action, target_url, payload)
        self.repo.save_action(staged)
        ws.staged_actions.append(staged.id); ws.status = ApplicationStatus.STAGED; ws.updated_at = utcnow()
        self.repo.save_workspace(ws, expected_version=version)
        return staged

    def approve_action(self, action_id: str, approval_id: str, verifier: ApprovalVerifier) -> StagedBrowserAction:
        action = self.repo.get_action(action_id)
        if action.state != ActionState.APPROVAL_REQUIRED: raise ValueError("action is not awaiting approval")
        if not verifier.verify(approval_id, action_id=action.id, payload_digest=action.payload_digest): raise PermissionError("approval is invalid or out of scope")
        action.approval_id = approval_id; action.approved_digest = action.payload_digest; action.state = ActionState.APPROVED; action.updated_at = utcnow()
        return self.repo.save_action(action)

    def execute_action(self, action_id: str, executor: BrowserExecutor) -> StagedBrowserAction:
        action = self.repo.get_action(action_id)
        if action.state != ActionState.APPROVED: raise PermissionError("approved action required")
        current = payload_digest(action.action, action.target_url, action.payload)
        if current != action.approved_digest: raise PermissionError("action changed after approval")
        action.state = ActionState.EXECUTING; action.updated_at = utcnow(); self.repo.save_action(action)
        try:
            action.result = executor.execute(action.action, action.target_url, action.payload)
            action.state = ActionState.SUCCEEDED
            if action.action == "submit_application":
                ws = self.repo.get_workspace(action.application_id); version = ws.version
                if ws.status != ApplicationStatus.STAGED: raise ValueError("workspace is no longer staged")
                ws.status = ApplicationStatus.SUBMITTED; ws.updated_at = utcnow(); self.repo.save_workspace(ws, expected_version=version)
        except Exception as exc:
            action.state = ActionState.FAILED; action.error = str(exc); action.updated_at = utcnow(); self.repo.save_action(action); raise
        action.updated_at = utcnow(); return self.repo.save_action(action)

    def record_status_observation(self, observation: StatusObservation) -> ApplicationWorkspace:
        ws = self.repo.get_workspace(observation.application_id)
        history = self._observations.setdefault(ws.id, [])
        if history and observation.observed_at < history[-1].observed_at: raise ValueError("stale status observation")
        if ws.status in TERMINAL_STATUSES and observation.status != ws.status: raise ValueError("terminal status cannot change")
        if observation.status != ws.status:
            if observation.status not in _ALLOWED_TRANSITIONS[ws.status]: raise ValueError("observed status is not a valid transition")
            version = ws.version; ws.status = observation.status; ws.updated_at = utcnow(); ws = self.repo.save_workspace(ws, expected_version=version)
        history.append(observation)
        return ws

    def status_history(self, workspace_id: str) -> list[StatusObservation]:
        self.repo.get_workspace(workspace_id)
        return list(self._observations.get(workspace_id, []))
