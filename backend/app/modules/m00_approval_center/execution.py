"""Durable local dispatch claim. No external exactly-once or automatic unknown retry."""
from __future__ import annotations
import copy
import json
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import JSON, DateTime, String, UniqueConstraint, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from .service import ApprovalConflictError, ApprovalEffectRow, Service, _aware, _request_hash


class ExecutionUnknown(ApprovalConflictError):
    """Dispatch may have happened; reconciliation is required before any retry."""


class ExecutionRow(Base):
    __tablename__ = 'm00_execution_intents'
    __table_args__ = (UniqueConstraint('effect_id'),)
    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    effect_id: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    adapter_version: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(32))
    fence: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure: Mapped[str | None] = mapped_column(String(80), nullable=True)


def digest(view):
    return _request_hash(module_id=view['module_id'], action_type=view['action_type'],
                         payload=view['payload'], user_id=view['user_id'])


def _bind(row, view, effect_id):
    if row.tenant_id != view['user_id'] or row.effect_id != effect_id or row.request_hash != digest(view):
        raise ApprovalConflictError('execution intent does not match approved request')


def prior_result(service: Service, view: dict, effect_id: str):
    """Read successful outcome before drift checks. Never redispatch a historical permit."""
    now = service._clock()
    with service._sessions.begin() as db:
        row = db.get(ExecutionRow, view['id'])
        if row is None:
            if db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id == view['id'])) is not None:
                raise ExecutionUnknown('historical permit has no execution outcome; reconciliation required')
            return None
        _bind(row, view, effect_id)
        if row.state == 'succeeded':
            return copy.deepcopy(row.result)
        if row.state == 'dispatching' and row.lease_until is not None and _aware(row.lease_until) <= now:
            db.execute(update(ExecutionRow).where(ExecutionRow.approval_id == row.approval_id,
                ExecutionRow.state == 'dispatching', ExecutionRow.fence == row.fence,
                ExecutionRow.lease_until <= now).values(state='outcome-unknown', failure='lease-expired'), execution_options={'synchronize_session':False})
        elif row.state == 'ready':
            return None
        # Do not raise inside the transaction: expiry state must commit.
    raise ExecutionUnknown('execution is in progress or unknown; automatic retry refused')


def prepare(service: Service, view: dict, effect_id: str, adapter_version: str):
    """Permit accounting and immutable ready intent commit atomically."""
    if not isinstance(adapter_version, str) or not adapter_version or len(adapter_version) > 120:
        raise ValueError('adapter version must be nonempty and at most120 characters')
    try:
        with service._sessions.begin() as db:
            existing = db.get(ExecutionRow, view['id'])
            if existing is not None:
                _bind(existing, view, effect_id)
                if existing.adapter_version != adapter_version or existing.state != 'ready':
                    raise ExecutionUnknown('execution intent cannot be reclaimed')
                return
            # A legacy consumed permit is uncertain, not permission for a fresh intent.
            if db.scalar(select(ApprovalEffectRow).where(ApprovalEffectRow.approval_id == view['id'])) is not None:
                raise ExecutionUnknown('historical permit has no execution outcome')
            service.consume_effect(view['id'], module_id=view['module_id'], action_type=view['action_type'],
                payload=view['payload'], user_id=view['user_id'], effect_id=effect_id,
                actor='celery-worker', _session=db)
            db.add(ExecutionRow(approval_id=view['id'], tenant_id=view['user_id'], effect_id=effect_id,
                request_hash=digest(view), adapter_version=adapter_version, state='ready'))
    except (IntegrityError, ApprovalConflictError) as error:
        # A concurrent winner may have committed; recover only its exact binding.
        with service._sessions() as db:
            row = db.get(ExecutionRow, view['id'])
            if row is None:
                if isinstance(error, IntegrityError):
                    raise ApprovalConflictError("execution effect id is already used") from None
                raise error

            _bind(row, view, effect_id)
            if row.adapter_version != adapter_version or row.state != 'ready':
                raise ExecutionUnknown('concurrent execution is already claimed') from None


def claim(service: Service, view: dict, effect_id: str, *, lease_seconds: int = 60) -> str:
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
        raise ValueError('lease must be an integer from1 to3600 seconds')
    now=service._clock(); token=str(uuid4())
    with service._sessions.begin() as db:
        result=db.execute(update(ExecutionRow).where(ExecutionRow.approval_id==view['id'],
            ExecutionRow.tenant_id==view['user_id'], ExecutionRow.effect_id==effect_id,
            ExecutionRow.request_hash==digest(view), ExecutionRow.state=='ready').values(
                state='dispatching', fence=token, lease_until=now+timedelta(seconds=lease_seconds)))
        if result.rowcount != 1:
            raise ExecutionUnknown('execution already claimed; retry refused')
    return token


def verify_dispatch_claim(service: Service, approval_id: str, token: str):
    """Local last-moment fence check, NOT external fencing or provider atomicity."""
    now=service._clock()
    with service._sessions() as db:
        active=db.scalar(select(ExecutionRow.approval_id).where(ExecutionRow.approval_id==approval_id,
            ExecutionRow.state=='dispatching',ExecutionRow.fence==token,ExecutionRow.lease_until>now))
        if active is None:
            raise ExecutionUnknown('stale claim cannot dispatch; reconciliation required')


def complete(service: Service, approval_id: str, token: str, result: dict):
    if not isinstance(result,dict):
        raise TypeError('approved-action executor must return a mapping')
    # Persist only finite JSON; a malformed outcome is not a repeat authorization.
    result=json.loads(json.dumps(result, allow_nan=False))
    now=service._clock()
    with service._sessions.begin() as db:
        changed=db.execute(update(ExecutionRow).where(ExecutionRow.approval_id==approval_id,
            ExecutionRow.state=='dispatching', ExecutionRow.fence==token,
            ExecutionRow.lease_until>now).values(state='succeeded',result=result,failure=None))
        if changed.rowcount != 1:
            raise ExecutionUnknown('stale completion refused; reconciliation required')
    return copy.deepcopy(result)


def unknown(service: Service, approval_id: str, token: str):
    with service._sessions.begin() as db:
        db.execute(update(ExecutionRow).where(ExecutionRow.approval_id==approval_id,
            ExecutionRow.state=='dispatching',ExecutionRow.fence==token).values(
                state='outcome-unknown',failure='dispatch-or-result-unverified'))
