"""Append-only resumable checkpoints, ported from meemee `checkpoints.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: monotonic per-run sequence, canonical-JSON
state documents with SHA-256 checksums verified on every read, idempotency keys
that replay identical content and conflict on different content, and resume().
Hermetic in-memory port.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class CheckpointConflict(RuntimeError):
    pass


class CheckpointStore:
    """Per-principal run journals with monotonic sequence and idempotent writes."""

    def __init__(self):
        self.lock = threading.RLock()
        self._runs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    def save(self, principal: str, run_id: str, goal_id: str, phase: str,
             state: dict[str, Any], *, expected_sequence: int | None = None,
             idempotency_key: str | None = None) -> dict[str, Any]:
        if not all(isinstance(x, str) and x.strip() for x in (principal, run_id, goal_id, phase)):
            raise ValueError("principal, run, goal and phase are required")
        document = _canonical(state)
        digest = hashlib.sha256(document.encode()).hexdigest()
        with self.lock:
            run_key = (principal, run_id)
            if idempotency_key:
                existing = self._by_key.get((principal, run_id, idempotency_key))
                if existing is not None:
                    if (existing["goal_id"], existing["phase"], existing["state_sha256"]) != (goal_id, phase, digest):
                        raise CheckpointConflict("idempotency key was used for different checkpoint content")
                    return self._row(existing)
            history = self._runs.setdefault(run_key, [])
            current = history[-1]["sequence"] if history else 0
            if expected_sequence is not None and expected_sequence != current:
                raise CheckpointConflict(f"sequence conflict: expected {expected_sequence}, actual {current}")
            checkpoint = {
                "id": uuid.uuid4().hex, "principal": principal, "run_id": run_id,
                "goal_id": goal_id, "sequence": current + 1, "phase": phase,
                "state": document, "state_sha256": digest,
                "idempotency_key": idempotency_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            history.append(checkpoint)
            if idempotency_key:
                self._by_key[(principal, run_id, idempotency_key)] = checkpoint
            return self._row(checkpoint)

    def latest(self, principal: str, run_id: str) -> dict[str, Any] | None:
        with self.lock:
            history = self._runs.get((principal, run_id), [])
            return self._row(history[-1]) if history else None

    def get(self, principal: str, run_id: str, sequence: int) -> dict[str, Any]:
        with self.lock:
            for checkpoint in self._runs.get((principal, run_id), []):
                if checkpoint["sequence"] == sequence:
                    return self._row(checkpoint)
        raise KeyError((run_id, sequence))

    def history(self, principal: str, run_id: str, *, after: int = 0) -> list[dict[str, Any]]:
        with self.lock:
            return [self._row(c) for c in self._runs.get((principal, run_id), []) if c["sequence"] > after]

    def resume(self, principal: str, run_id: str) -> dict[str, Any]:
        checkpoint = self.latest(principal, run_id)
        if checkpoint is None:
            raise KeyError(run_id)
        return {"run_id": run_id, "goal_id": checkpoint["goal_id"],
                "next_sequence": checkpoint["sequence"] + 1,
                "phase": checkpoint["phase"], "state": checkpoint["state"],
                "checkpoint_id": checkpoint["id"]}

    @staticmethod
    def _row(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        digest = hashlib.sha256(result["state"].encode()).hexdigest()
        if not hmac.compare_digest(digest, result["state_sha256"]):
            raise ValueError("checkpoint state checksum mismatch")
        result["state"] = json.loads(result["state"])
        return result
