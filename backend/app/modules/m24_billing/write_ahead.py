"""M24 write-ahead storage, inactive dispatcher. No provider I/O or activation API.

The cutover row is a DB-side barrier, not evidence of credential isolation. This
slice deliberately supplies no producer of an active/checked row. Real activation
requires the later checked credential/egress verifier and TEST adapter readiness.
"""
from __future__ import annotations
import copy
import hashlib
import json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from sqlalchemy import JSON,DateTime,String,Integer,CheckConstraint,UniqueConstraint,select,update,exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.modules.m00_approval_center.service import (
    Service,ApprovalRequestRow,ApprovalEffectRow,ApprovalEventRow,ApprovalConflictError,_request_hash,_aware,_view,
)

class DispatchRefused(ApprovalConflictError):pass

class CutoverRow(Base):
    __tablename__='m24_dispatch_cutover'
    __table_args__=(CheckConstraint("protocol_epoch IN (0,2)"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    protocol_epoch:Mapped[int]=mapped_column(Integer,default=0)
    state:Mapped[str]=mapped_column(String(40),default='locked')
    verification_digest:Mapped[str|None]=mapped_column(String(64),nullable=True)
    verified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class OperationRow(Base):
    __tablename__='m24_provider_operations'
    __table_args__=(UniqueConstraint('tenant_id','approval_id'),UniqueConstraint('provider_account','environment','provider_key'),
        CheckConstraint("environment = 'test'"),CheckConstraint('protocol_epoch = 2'))
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120),index=True)
    approval_id:Mapped[str]=mapped_column(String(36),index=True)
    request_hash:Mapped[str]=mapped_column(String(64))
    request:Mapped[dict]=mapped_column(JSON)
    action_type:Mapped[str]=mapped_column(String(120))
    provider_account:Mapped[str]=mapped_column(String(200))
    environment:Mapped[str]=mapped_column(String(20))
    api_version:Mapped[str]=mapped_column(String(80))
    provider_key:Mapped[str]=mapped_column(String(255))
    protocol_epoch:Mapped[int]=mapped_column(Integer,default=2)
    state:Mapped[str]=mapped_column(String(40))
    fence:Mapped[str|None]=mapped_column(String(36),nullable=True)
    lease_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    first_attempt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    dispatch_not_after:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    failure:Mapped[str|None]=mapped_column(String(80),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class AttemptRow(Base):
    __tablename__='m24_provider_attempts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    operation_id:Mapped[str]=mapped_column(String(36),index=True)
    fence:Mapped[str]=mapped_column(String(36),unique=True)
    request_hash:Mapped[str]=mapped_column(String(64))
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class OperationEventRow(Base):
    __tablename__='m24_operation_events'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    operation_id:Mapped[str]=mapped_column(String(36),index=True)
    event:Mapped[str]=mapped_column(String(80))
    actor:Mapped[str]=mapped_column(String(120))
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True))


def _text(value,name,ceiling):
    if not isinstance(value,str) or not value.strip() or len(value)>ceiling:
        raise ValueError(f'{name} must be nonempty and at most{ceiling}characters')


def _digest(row):
    return _request_hash(module_id=row.module_id,action_type=row.action_type,payload=row.payload,user_id=row.user_id)


def _permit_key(tenant,approval):
    return 'm24-v2:'+hashlib.sha256(json.dumps([tenant,approval],separators=(',',':')).encode()).hexdigest()


def _out(row):
    return {name:copy.deepcopy(getattr(row,name)) for name in ('id','tenant_id','approval_id','request_hash','request','action_type',
        'provider_account','environment','api_version','provider_key','state','fence','result','failure','first_attempt_at','dispatch_not_after')}

class OperationRepository:
    def __init__(self,approvals:Service):
        self.approvals=approvals;self.sessions=approvals._sessions;self.clock=approvals._clock

    def prepare(self,approval_id,tenant_id,*,provider_account,environment,api_version,actor,provider_key=None):
        for value,name,limit in ((provider_account,'provider_account',200),(api_version,'api_version',80),(actor,'actor',120)):
            _text(value,name,limit)
        if environment!='test':raise DispatchRefused('M24 live mode is not enabled')
        if provider_key is not None:_text(provider_key,'provider_key',255)
        now=self.clock()
        try:
            with self.sessions.begin() as db:
                # Write-lock the approval before reading binding/permit, serializes competing reservations.
                locked=db.execute(update(ApprovalRequestRow).where(ApprovalRequestRow.id==approval_id,
                    ApprovalRequestRow.user_id==tenant_id,ApprovalRequestRow.module_id==24).values(status=ApprovalRequestRow.status))
                if locked.rowcount!=1:raise ApprovalConflictError('approved tenant-bound M24 request required')
                approval=db.get(ApprovalRequestRow,approval_id)
                digest=_digest(approval)
                prior=db.scalar(select(OperationRow).where(OperationRow.approval_id==approval_id,OperationRow.tenant_id==tenant_id))
                if prior:
                    if prior.request_hash!=digest or prior.provider_account!=provider_account or prior.environment!=environment or prior.api_version!=api_version or (provider_key is not None and prior.provider_key!=provider_key):
                        raise ApprovalConflictError('operation binding differs')
                    return _out(prior)
                if approval.expires_at is not None and _aware(approval.expires_at)<=now:
                    raise ApprovalConflictError('M24 approval deadline elapsed')
                if db.get(LegacyQuarantineRow,approval_id) is not None:
                    raise DispatchRefused('legacy M24 operation requires reconciliation')
                if approval.action_type not in {'create_subscription_checkout','cancel_subscription','issue_invoice'}:
                    raise ApprovalConflictError('unsupported M24 operation')
                # One shared Module0 permit validator, joined to this transaction.
                key=_permit_key(tenant_id,approval_id)
                self.approvals.consume_effect(approval_id,module_id=24,action_type=approval.action_type,
                    payload=copy.deepcopy(approval.payload),user_id=tenant_id,effect_id=key,actor=actor,_session=db)
                operation=OperationRow(id=str(uuid4()),tenant_id=tenant_id,approval_id=approval_id,request_hash=digest,
                    request=copy.deepcopy(approval.payload),action_type=approval.action_type,provider_account=provider_account,
                    environment=environment,api_version=api_version,provider_key=provider_key or approval_id,
                    protocol_epoch=2,state='prepared',created_at=now)
                db.add(operation)
                db.flush()  # Intent INSERT precedes dependent snapshot, still inside one transaction.
                self._add_snapshot(db,operation,approval)
                db.add(OperationEventRow(operation_id=operation.id,event='prepared',actor=actor,at=now))
                db.flush();result=_out(operation)
            return result  # committed; if acknowledgment failed caller must read back, never invoke provider here
        except IntegrityError:
            raise ApprovalConflictError('operation reservation conflict') from None

    def _add_snapshot(self,db,operation,approval):
        """Domain snapshot hook runs inside the permit+intent transaction."""

    def get(self,operation_id,tenant_id):
        with self.sessions() as db:
            row=db.get(OperationRow,operation_id)
            if row is None or row.tenant_id!=tenant_id:raise KeyError(operation_id)
            return _out(row)

    def claim(self,operation_id,tenant_id,*,protocol_epoch,lease_seconds=60):
        if protocol_epoch!=2 or type(protocol_epoch) is not int:raise DispatchRefused('old protocol cannot claim M24 operations')
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:raise ValueError('invalid lease')
        # A forged DB digest is not a checked credential/egress verification.
        # Until a real checker+TEST readiness integration exists, even active-looking rows refuse.
        require_dispatch_ready()
        now=self.clock();fence=str(uuid4())
        with self.sessions.begin() as db:
            cutover=exists(select(CutoverRow.id).where(CutoverRow.id==1,CutoverRow.protocol_epoch==2,
                CutoverRow.state=='verified-active',CutoverRow.verification_digest.is_not(None),CutoverRow.verified_at.is_not(None)))
            changed=db.execute(update(OperationRow).where(OperationRow.id==operation_id,OperationRow.tenant_id==tenant_id,
                OperationRow.protocol_epoch==2,OperationRow.state=='prepared',cutover).values(
                    state='dispatching',fence=fence,lease_until=now+timedelta(seconds=lease_seconds),
                    first_attempt_at=now,dispatch_not_after=now+timedelta(hours=12)))
            if changed.rowcount!=1:raise DispatchRefused('cutover not checked or operation not claimable')
            row=db.get(OperationRow,operation_id)
            db.add(AttemptRow(id=str(uuid4()),operation_id=operation_id,fence=fence,request_hash=row.request_hash,started_at=now))
            db.add(OperationEventRow(operation_id=operation_id,event='dispatch-reserved',actor='m24-worker',at=now))
        return fence

class LegacyQuarantineRow(Base):
    __tablename__='m24_legacy_quarantine'
    approval_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120))
    classification:Mapped[str]=mapped_column(String(80))
    approval_time:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    recorded_result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    inventoried_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))


def cutover_inventory(sessions):
    """Counts are evidence, not activation. Legacy quarantined records are never dispatchable."""
    from sqlalchemy import func
    with sessions() as db:
        return dict(db.execute(select(LegacyQuarantineRow.classification,func.count()).group_by(LegacyQuarantineRow.classification)).all())


def require_dispatch_ready():
    """No ready adapter/cutover verifier in slice1. Env flags cannot authorize dispatch."""
    raise DispatchRefused('M24 dispatch disabled: checked credential/egress cutover and TEST adapter readiness required')
