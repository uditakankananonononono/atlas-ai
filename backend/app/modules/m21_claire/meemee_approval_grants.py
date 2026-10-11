"""Expiring, revocable, constraint-bound approval grants, ported from meemee
`approvals.py` (C4 meemee-merge).

Semantics preserved from meemee@50e7605: ISO 8601 expiry normalization (naive
read as UTC), finite-JSON constraint validation, and exact constraint matching
that keeps booleans distinct from numbers. Atlas core has an approval *queue*;
meemee adds standing per-tool grants with argument constraints, which Claire
needs for repeated approved actions. Hermetic in-memory store.
"""
from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone


def normalize_expiry(value: str | None) -> str | None:
    """Canonical UTC ISO 8601 form of a grant expiry.

    Naive timestamps are read as UTC. Anything that is not ISO 8601 raises
    ValueError, so a typo can never become a grant that silently never (or
    always) expires.
    """
    if value is None:
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("expires_at must be an ISO 8601 timestamp") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def utc_moment(now: datetime | None = None) -> datetime:
    """``now`` (default: the current time) as an aware UTC datetime; naive values are read as UTC."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def validate_constraints(value: dict | None) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("argument_constraints must be an object")

    def valid(item):
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float) and math.isfinite(item):
            return
        if isinstance(item, list):
            for child in item:
                valid(child)
            return
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            for child in item.values():
                valid(child)
            return
        raise ValueError("argument_constraints must contain finite JSON values")

    valid(value)


def constraints_match(constraints: dict | None, arguments: dict | None) -> bool:
    """Exact JSON-value constraints, keeping booleans distinct from numbers."""
    if constraints is None:
        return True
    try:
        validate_constraints(constraints)
    except ValueError:
        return False
    supplied = {} if arguments is None else arguments
    if not isinstance(supplied, dict):
        return False

    def equal(left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return type(left) is type(right) and left == right
        if isinstance(left, dict):
            return isinstance(right, dict) and left.keys() == right.keys() and all(
                equal(value, right[key]) for key, value in left.items())
        if isinstance(left, list):
            return isinstance(right, list) and len(left) == len(right) and all(
                equal(a, b) for a, b in zip(left, right))
        if isinstance(left, (int, float)):
            return isinstance(right, (int, float)) and (not isinstance(right, float) or math.isfinite(right)) and left == right
        return type(left) is type(right) and left == right

    return all(key in supplied and equal(value, supplied[key]) for key, value in constraints.items())


class ApprovalGrantStore:
    """Persistent-style, revocable, expiring per-principal grants for exact tool names."""

    def __init__(self):
        self.lock = threading.RLock()
        self._grants: dict[tuple[str, str], dict] = {}

    def grant(self, principal: str, tool: str, granted_by: str, expires_at: str | None = None,
              argument_constraints: dict | None = None) -> None:
        if not principal or not tool or not granted_by:
            raise ValueError("principal, tool and granted_by are required")
        validate_constraints(argument_constraints)
        expires_at = normalize_expiry(expires_at)
        with self.lock:
            self._grants[(principal, tool)] = {
                "principal": principal, "tool": tool,
                "granted_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at, "revoked_at": None, "granted_by": granted_by,
                "argument_constraints": argument_constraints,
            }

    def allows(self, principal: str, tool: str, now: datetime | None = None,
               arguments: dict | None = None) -> bool:
        current = utc_moment(now).isoformat()
        with self.lock:
            grant = self._grants.get((principal, tool))
        if grant is None or grant["revoked_at"] is not None:
            return False
        if grant["expires_at"] is not None and grant["expires_at"] <= current:
            return False
        return constraints_match(grant["argument_constraints"], arguments)

    def revoke(self, principal: str, tool: str) -> bool:
        with self.lock:
            grant = self._grants.get((principal, tool))
            if grant is None or grant["revoked_at"] is not None:
                return False
            grant["revoked_at"] = datetime.now(timezone.utc).isoformat()
            return True

    def active_count(self, principal: str, now: datetime | None = None) -> int:
        current = utc_moment(now).isoformat()
        with self.lock:
            return sum(
                1 for (owner, _), grant in self._grants.items()
                if owner == principal and grant["revoked_at"] is None
                and (grant["expires_at"] is None or grant["expires_at"] > current)
            )

    def list(self, principal: str) -> list[dict]:
        with self.lock:
            rows = [dict(grant) for (owner, _), grant in self._grants.items() if owner == principal]
        return sorted(rows, key=lambda grant: grant["tool"])

    def delete_principal(self, principal: str) -> int:
        """Remove every standing tool grant, active or revoked, held by a principal."""
        with self.lock:
            keys = [key for key in self._grants if key[0] == principal]
            for key in keys:
                del self._grants[key]
            return len(keys)
