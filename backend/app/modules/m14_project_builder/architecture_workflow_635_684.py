"""Durable review workflow for architecture rows 635-684.

The workflow stores the exact input, computed analysis, content digest, and provenance.
It never performs the architecture change being analysed. Applying a reviewed record only
marks that decision artifact accepted; callers must use a separate execution system for
external effects.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .architecture_support_635_684 import architecture_support_635_684

STATES = {"draft", "review", "approved", "applied", "rolled_back", "rejected"}


class ArchitectureWorkflowError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class WorkflowRecord:
    id: str
    tenant_id: str
    actor_id: str
    row_id: int
    state: str
    input: dict[str, Any]
    analysis: dict[str, Any]
    artifact_sha256: str
    provenance: dict[str, Any]
    approval_id: str | None
    approved_by: str | None
    rollback_reason: str | None
    version: int
    created_at: str
    updated_at: str

    def view(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ArchitectureWorkflowRepository:
    """SQLite repository with tenant-keyed reads and optimistic versions."""

    def __init__(self, path: str | Path = "atlas.db") -> None:
        self.path = str(path)
        self._create()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create(self) -> None:
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS m14_architecture_workflows (
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                row_id INTEGER NOT NULL, state TEXT NOT NULL, input_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
                provenance_json TEXT NOT NULL, approval_id TEXT, approved_by TEXT,
                rollback_reason TEXT, version INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_m14_arch_workflow_tenant ON m14_architecture_workflows(tenant_id, id)")

    @staticmethod
    def _record(row: sqlite3.Row) -> WorkflowRecord:
        return WorkflowRecord(
            id=row["id"], tenant_id=row["tenant_id"], actor_id=row["actor_id"],
            row_id=row["row_id"], state=row["state"], input=json.loads(row["input_json"]),
            analysis=json.loads(row["analysis_json"]), artifact_sha256=row["artifact_sha256"],
            provenance=json.loads(row["provenance_json"]), approval_id=row["approval_id"],
            approved_by=row["approved_by"], rollback_reason=row["rollback_reason"],
            version=row["version"], created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def insert(self, record: WorkflowRecord) -> WorkflowRecord:
        with self._connect() as db:
            db.execute("""INSERT INTO m14_architecture_workflows VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                record.id, record.tenant_id, record.actor_id, record.row_id, record.state,
                _canonical(record.input), _canonical(record.analysis), record.artifact_sha256,
                _canonical(record.provenance), record.approval_id, record.approved_by,
                record.rollback_reason, record.version, record.created_at, record.updated_at,
            ))
        return record

    def get(self, tenant_id: str, record_id: str) -> WorkflowRecord:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM m14_architecture_workflows WHERE tenant_id=? AND id=?",
                (tenant_id, record_id),
            ).fetchone()
        if row is None:
            raise KeyError("architecture workflow record not found")
        return self._record(row)

    def update(self, before: WorkflowRecord, **changes: Any) -> WorkflowRecord:
        values = before.view() | changes | {"version": before.version + 1, "updated_at": _now()}
        after = WorkflowRecord(**values)
        with self._connect() as db:
            cursor = db.execute("""UPDATE m14_architecture_workflows SET
                state=?, approval_id=?, approved_by=?, rollback_reason=?, version=?, updated_at=?
                WHERE tenant_id=? AND id=? AND version=?""", (
                after.state, after.approval_id, after.approved_by, after.rollback_reason,
                after.version, after.updated_at, before.tenant_id, before.id, before.version,
            ))
            if cursor.rowcount != 1:
                raise ArchitectureWorkflowError("record changed concurrently; reload before retrying")
        return after


class ArchitectureWorkflowService:
    def __init__(self, repository: ArchitectureWorkflowRepository) -> None:
        self.repository = repository

    @staticmethod
    def _scope(tenant_id: str, actor_id: str) -> None:
        if not tenant_id.strip() or not actor_id.strip():
            raise ArchitectureWorkflowError("tenant_id and actor_id are required")

    def draft(self, tenant_id: str, actor_id: str, row_id: int, data: dict[str, Any], provenance: dict[str, Any]) -> WorkflowRecord:
        self._scope(tenant_id, actor_id)
        source_id = provenance.get("source_id")
        observed_at = provenance.get("observed_at")
        if not isinstance(source_id, str) or not source_id.strip() or not isinstance(observed_at, str) or not observed_at.strip():
            raise ArchitectureWorkflowError("provenance requires non-empty source_id and observed_at")
        analysis = architecture_support_635_684(row_id, data)
        artifact = {"row_id": row_id, "input": data, "analysis": analysis, "provenance": provenance}
        digest = hashlib.sha256(_canonical(artifact).encode()).hexdigest()
        moment = _now()
        return self.repository.insert(WorkflowRecord(
            id=str(uuid4()), tenant_id=tenant_id, actor_id=actor_id, row_id=row_id,
            state="draft", input=data, analysis=analysis, artifact_sha256=digest,
            provenance=provenance, approval_id=None, approved_by=None,
            rollback_reason=None, version=1, created_at=moment, updated_at=moment,
        ))

    def submit(self, tenant_id: str, actor_id: str, record_id: str) -> WorkflowRecord:
        record = self.repository.get(tenant_id, record_id)
        if record.actor_id != actor_id:
            raise ArchitectureWorkflowError("only the drafting actor may submit this record")
        if record.state != "draft":
            raise ArchitectureWorkflowError("only a draft may enter review")
        return self.repository.update(record, state="review")

    def approve(self, tenant_id: str, actor_id: str, record_id: str, approval_id: str) -> WorkflowRecord:
        self._scope(tenant_id, actor_id)
        if not approval_id.strip():
            raise ArchitectureWorkflowError("approval_id is required")
        record = self.repository.get(tenant_id, record_id)
        if record.state != "review":
            raise ArchitectureWorkflowError("only a record in review may be approved")
        return self.repository.update(record, state="approved", approval_id=approval_id, approved_by=actor_id)

    def apply(self, tenant_id: str, actor_id: str, record_id: str, approval_id: str) -> WorkflowRecord:
        record = self.repository.get(tenant_id, record_id)
        if record.state != "approved" or record.approval_id != approval_id:
            raise ArchitectureWorkflowError("matching approval is required before apply")
        return self.repository.update(record, state="applied")

    def rollback(self, tenant_id: str, actor_id: str, record_id: str, reason: str) -> WorkflowRecord:
        record = self.repository.get(tenant_id, record_id)
        if record.state != "applied":
            raise ArchitectureWorkflowError("only an applied decision artifact may be rolled back")
        if not reason.strip():
            raise ArchitectureWorkflowError("rollback reason is required")
        return self.repository.update(record, state="rolled_back", rollback_reason=reason)
