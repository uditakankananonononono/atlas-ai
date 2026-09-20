"""Repository contracts and a lock-protected in-memory implementation."""
from __future__ import annotations
from copy import deepcopy
from threading import RLock
from typing import Protocol
from .models import ApplicationWorkspace, StagedBrowserAction


class ConflictError(RuntimeError): pass
class NotFoundError(KeyError): pass


class CompetitionRepository(Protocol):
    def save_workspace(self, workspace: ApplicationWorkspace, expected_version: int | None = None) -> ApplicationWorkspace: ...
    def get_workspace(self, workspace_id: str) -> ApplicationWorkspace: ...
    def save_action(self, action: StagedBrowserAction) -> StagedBrowserAction: ...
    def get_action(self, action_id: str) -> StagedBrowserAction: ...


class InMemoryCompetitionRepository:
    def __init__(self) -> None:
        self._workspaces: dict[str, ApplicationWorkspace] = {}
        self._actions: dict[str, StagedBrowserAction] = {}
        self._lock = RLock()

    def save_workspace(self, workspace: ApplicationWorkspace, expected_version: int | None = None) -> ApplicationWorkspace:
        with self._lock:
            old = self._workspaces.get(workspace.id)
            if expected_version is not None:
                actual = old.version if old else 0
                if actual != expected_version:
                    raise ConflictError(f"workspace version is {actual}, expected {expected_version}")
                workspace.version = actual + 1
            self._workspaces[workspace.id] = deepcopy(workspace)
            return deepcopy(workspace)

    def get_workspace(self, workspace_id: str) -> ApplicationWorkspace:
        with self._lock:
            try: return deepcopy(self._workspaces[workspace_id])
            except KeyError: raise NotFoundError(workspace_id)

    def save_action(self, action: StagedBrowserAction) -> StagedBrowserAction:
        with self._lock:
            self._actions[action.id] = deepcopy(action)
            return deepcopy(action)

    def get_action(self, action_id: str) -> StagedBrowserAction:
        with self._lock:
            try: return deepcopy(self._actions[action_id])
            except KeyError: raise NotFoundError(action_id)
