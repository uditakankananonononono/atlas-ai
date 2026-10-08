"""M20 checkpoint notifications: SQL authority, at-least-once Redis delivery."""
import hashlib
import json

import sqlalchemy as sa

from .sql_repository import Base


class RuntimeEventRow(Base):
    __tablename__ = 'm20_runtime_event_outbox'
    event_id = sa.Column(sa.String(64), primary_key=True)
    tenant_id = sa.Column(sa.String(120), nullable=False, index=True)
    task_id = sa.Column(sa.String(120), nullable=False)
    state = sa.Column(sa.String(40), nullable=False)
    action_ids = sa.Column(sa.JSON, nullable=False)
    delivered = sa.Column(sa.Boolean, nullable=False, default=False, server_default=sa.false())


def event_values(tenant_id, context, actions):
    action_ids = sorted({action.id for action in actions})
    # Same task-state/action identity produces the same ID, including replay.
    identity = json.dumps([tenant_id, context.id, context.state.value, action_ids], separators=(',', ':'))
    event_id = hashlib.sha256(identity.encode()).hexdigest()
    return dict(event_id=event_id, tenant_id=tenant_id, task_id=context.id,
                state=context.state.value, action_ids=action_ids)


def stream_for(tenant_id):
    return 'atlas:m20:events:' + hashlib.sha256(tenant_id.encode()).hexdigest()


def payload_for(row):
    return {key: getattr(row, key) for key in ('event_id', 'tenant_id', 'task_id', 'state', 'action_ids')}


def drain_events(engine, bus, *, limit=100):
    """Publish while holding row locks; crash-before-commit can duplicate event_id."""
    if engine.dialect.name != 'postgresql':
        raise ValueError('outbox delivery requires PostgreSQL row locks')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('outbox delivery limit must be 1..1000')
    delivered = 0
    from sqlalchemy.orm import Session
    with Session(engine) as session, session.begin():
        rows = session.scalars(sa.select(RuntimeEventRow).where(
            RuntimeEventRow.delivered.is_(False)).order_by(RuntimeEventRow.event_id)
            .limit(limit).with_for_update(skip_locked=True)).all()
        for row in rows:
            bus.publish(stream_for(row.tenant_id), payload_for(row))
            row.delivered = True
            delivered += 1
    return {'delivered': delivered}
