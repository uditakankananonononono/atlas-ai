"""Durable, one-attempt claims. A claim is not proof a provider accepted a post.

Each approval and each schedule can be claimed only once within its tenant.
The ledger is never reset automatically. A crash after commit may mean no post,
partial post, or completed post. Keep that schedule closed for reconciliation.
"""
from __future__ import annotations

import json
from sqlalchemy import Column, String, Table, Text, UniqueConstraint, cast, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError


def claim_table(metadata):
    name = "m06_social_dispatch_claims"
    if name in metadata.tables:
        return metadata.tables[name]
    return Table(
        name, metadata,
        Column("tenant_id", String(120), nullable=False),
        Column("schedule_id", String(36), nullable=False),
        Column("approval_id", String(36), nullable=False),
        UniqueConstraint("tenant_id", "schedule_id"),
        UniqueConstraint("tenant_id", "approval_id", name="uq_m06_dispatch_approval"),
    )


class DispatchClaimSchemaError(RuntimeError):
    """A preexisting ledger needs an explicit non-destructive schema migration."""


def require_approval_constraint(connection, claims):
    constraints = inspect(connection).get_unique_constraints(claims.name, schema=claims.schema)
    if not any(set(c.get("column_names") or ()) == {"tenant_id", "approval_id"}
               for c in constraints):
        raise DispatchClaimSchemaError(
            "publishing disabled: dispatch ledger requires tenant/approval uniqueness; "
            "reconcile existing attempts and apply an explicit migration")


class _ClaimLost(Exception):
    pass


def claim_sql_schedule(sessions, schedules, claims, tenant_id, expected):
    """Commit a snapshot CAS plus unique schedule claim before any HTTP effect.

    Compare the DB's own JSON text to itself in the UPDATE predicate. This
    avoids depending on Python/DB JSON key order or PostgreSQL JSON equality.
    The full expected record must still match, including approval and status.
    Failed CAS rolls back the ledger insert; an existing claim fails closed.
    """
    if expected.get("status") != "approved" or not expected.get("approval_id"):
        return False
    scope = (schedules.c.tenant_id == tenant_id,
             schedules.c.item_id == expected["id"])
    try:
        with sessions.begin() as db:
            require_approval_constraint(db.connection(), claims)
            row = db.execute(select(cast(schedules.c.data, Text)).where(
                *scope, schedules.c.status == "approved")).first()
            if row is None:
                return False
            raw = row[0]
            current = json.loads(raw)
            if json.dumps(current, sort_keys=True, allow_nan=False) != json.dumps(
                    expected, sort_keys=True, allow_nan=False):
                return False
            db.execute(insert(claims).values(
                tenant_id=tenant_id, schedule_id=expected["id"],
                approval_id=expected["approval_id"]))
            claimed = dict(current, status="dispatching", failure="publish_outcome_unconfirmed")
            changed = db.execute(update(schedules).where(
                *scope, schedules.c.status == "approved",
                cast(schedules.c.data, Text) == raw).values(
                    status="dispatching", data=claimed))
            if changed.rowcount != 1:
                raise _ClaimLost()
        return True
    except (_ClaimLost, IntegrityError):
        # Duplicate claim or other integrity failure must never dispatch.
        return False
