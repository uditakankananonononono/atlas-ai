"""Internal M20 stream refresh signals -> SQL-authoritative M16 task status."""
import re

import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.core.database import Base
from app.modules.m20_general_cognitive_worker.event_outbox import RuntimeEventRow, payload_for, stream_for
from app.modules.m20_general_cognitive_worker.sql_repository import TaskRow, ActionRow
from app.modules.m20_general_cognitive_worker.schemas import TaskState

CONSUMER = 'm16-m20-task-status-v1'


class StreamCursorRow(Base):
    __tablename__ = 'm16_m20_stream_cursors'
    consumer = sa.Column(sa.String(80), primary_key=True)
    tenant_id = sa.Column(sa.String(120), primary_key=True)
    cursor = sa.Column(sa.String(80), nullable=False, default='0-0')


class EventReceiptRow(Base):
    __tablename__ = 'm16_m20_event_receipts'
    consumer = sa.Column(sa.String(80), primary_key=True)
    tenant_id = sa.Column(sa.String(120), primary_key=True)
    event_id = sa.Column(sa.String(64), primary_key=True)


class TaskStatusRow(Base):
    __tablename__ = 'm16_m20_task_status'
    tenant_id = sa.Column(sa.String(120), primary_key=True)
    task_id = sa.Column(sa.String(120), primary_key=True)
    state = sa.Column(sa.String(40), nullable=False)
    action_ids = sa.Column(sa.JSON, nullable=False)


class InvalidRuntimeEvent(ValueError):
    """Stops this batch with its SQL cursor unchanged; requires operator repair."""


def validate_payload(payload, owner):
    fields = {'event_id', 'tenant_id', 'task_id', 'state', 'action_ids'}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise InvalidRuntimeEvent('runtime event must contain exactly five approved fields')
    if payload['tenant_id'] != owner:
        raise InvalidRuntimeEvent('runtime event tenant differs from stream owner')
    if not isinstance(payload['event_id'], str) or not re.fullmatch('[a-f0-9]{64}', payload['event_id']):
        raise InvalidRuntimeEvent('invalid runtime event identity')
    if not isinstance(payload['task_id'], str) or not 1 <= len(payload['task_id']) <= 120:
        raise InvalidRuntimeEvent('invalid runtime task identity')
    if not isinstance(payload['state'], str) or payload['state'] not in {value.value for value in TaskState}:
        raise InvalidRuntimeEvent('invalid runtime checkpoint state')
    actions = payload['action_ids']
    if not isinstance(actions, list) or len(actions) > 10000 or any(not isinstance(value, str) or not 1 <= len(value) <= 120 for value in actions):
        raise InvalidRuntimeEvent('invalid runtime action identities')
    if actions != sorted(set(actions)):
        raise InvalidRuntimeEvent('runtime action identities must be sorted and unique')


def consume_task_status(engine, bus, tenant_id, *, limit=100):
    if engine.dialect.name != 'postgresql':
        raise ValueError('runtime subscriber requires PostgreSQL')
    if not isinstance(tenant_id, str) or not 1 <= len(tenant_id) <= 120:
        raise ValueError('subscriber tenant is required')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('subscriber limit must be 1..1000')
    projected = duplicates = 0
    with Session(engine) as db, db.begin():
        db.execute(insert(StreamCursorRow).values(consumer=CONSUMER, tenant_id=tenant_id, cursor='0-0')
                   .on_conflict_do_nothing())
        cursor = db.scalar(sa.select(StreamCursorRow).where(
            StreamCursorRow.consumer == CONSUMER, StreamCursorRow.tenant_id == tenant_id).with_for_update())
        rows = bus.read(stream_for(tenant_id), last_id=cursor.cursor, count=limit, block_ms=10)
        for item in rows:
            ident = item.get('id')
            if not isinstance(ident, str) or not re.fullmatch('[0-9]+-[0-9]+', ident):
                raise InvalidRuntimeEvent('invalid Redis stream cursor')
            if tuple(map(int, ident.split('-'))) <= tuple(map(int, cursor.cursor.split('-'))):
                raise InvalidRuntimeEvent('Redis stream cursor did not advance')
            payload = item.get('event')
            validate_payload(payload, tenant_id)
            authoritative = db.get(RuntimeEventRow, payload['event_id'])
            if authoritative is None or payload_for(authoritative) != payload:
                raise InvalidRuntimeEvent(f'event {ident} does not match authoritative SQL checkpoint')
            key = dict(consumer=CONSUMER, tenant_id=tenant_id, event_id=payload['event_id'])
            if db.get(EventReceiptRow, (CONSUMER, tenant_id, payload['event_id'])) is not None:
                duplicates += 1
            else:
                # The event is a refresh signal, NOT current-state truth.
                task = db.scalar(sa.select(TaskRow).where(TaskRow.id == payload['task_id'],
                    TaskRow.tenant_id == tenant_id).with_for_update())
                if task is None:
                    raise InvalidRuntimeEvent(f'event {ident} task authority is missing')
                if task.state not in {value.value for value in TaskState}:
                    raise InvalidRuntimeEvent(f'event {ident} current task state is invalid')
                action_ids = list(db.scalars(sa.select(ActionRow.id).where(
                    ActionRow.tenant_id == tenant_id, ActionRow.task_id == task.id).order_by(ActionRow.id)))
                projection = db.get(TaskStatusRow, (tenant_id, task.id))
                if projection is None:
                    projection = TaskStatusRow(tenant_id=tenant_id, task_id=task.id)
                    db.add(projection)
                projection.state = task.state
                projection.action_ids = action_ids
                db.add(EventReceiptRow(**key))
                projected += 1
            cursor.cursor = ident
            db.flush()
    return {'projected': projected, 'duplicates': duplicates}


def read_task_status(engine, tenant_id, *, limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('task status limit must be 1..1000')
    with Session(engine) as db:
        rows = db.scalars(sa.select(TaskStatusRow).where(TaskStatusRow.tenant_id == tenant_id)
                          .order_by(TaskStatusRow.task_id).limit(limit)).all()
        return [{'task_id': row.task_id, 'state': row.state, 'action_ids': row.action_ids} for row in rows]
