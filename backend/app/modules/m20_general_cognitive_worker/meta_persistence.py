"""Tenant-scoped write-through for existing meta state, not new cognition.

One atomic CAS snapshot per operator kind. Stage mutations, commit SQL, then
publish memory. SQLite acceptance only; no deployment/PostgreSQL claim. Stores
algorithm state, no scratchpads or hidden chain-of-thought. Calibration reuses
DurableCalibrationEngine and its existing table, not a duplicate store.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import json
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from .sql_repository import Base
from .metacognition import (MetaLearner,AbstractPattern,WorldModelRegistry,WorldModel,
 EpistemicCalendar,BeliefReview,CuriosityEngine)

class MetaStateRow(Base):
    __tablename__='m20_meta_state'
    tenant_id=sa.Column(sa.String(120),primary_key=True)
    kind=sa.Column(sa.String(32),primary_key=True)
    revision=sa.Column(sa.Integer,nullable=False)
    payload=sa.Column(sa.JSON,nullable=False)

class MetaRepository:
    def __init__(self,engine,*,tenant_id):
        if not isinstance(tenant_id,str) or not tenant_id.strip() or len(tenant_id)>120:raise ValueError('tenant required')
        self.engine=engine;self.tenant_id=tenant_id;self.sessions=sessionmaker(engine,expire_on_commit=False)
    def create_schema(self):
        """Explicit local test/development only; Alembic owns production DDL."""
        MetaStateRow.__table__.create(self.engine,checkfirst=True)
    def read(self,kind):
        with self.sessions() as session:
            row=session.get(MetaStateRow,(self.tenant_id,kind))
            return (row.revision,deepcopy(row.payload)) if row else (0,None)
    def _before_commit(self,session):pass
    def write(self,kind,revision,payload):
        payload=json.loads(json.dumps(payload,allow_nan=False))
        with self.sessions.begin() as session:
            if revision==0:
                try:
                    session.add(MetaStateRow(tenant_id=self.tenant_id,kind=kind,revision=1,payload=payload));session.flush()
                except sa.exc.IntegrityError as exc:raise RuntimeError('stale meta-state writer') from exc
            else:
                result=session.execute(sa.update(MetaStateRow).where(MetaStateRow.tenant_id==self.tenant_id,MetaStateRow.kind==kind,MetaStateRow.revision==revision).values(revision=revision+1,payload=payload))
                if result.rowcount!=1:raise RuntimeError('stale meta-state writer')
            self._before_commit(session)
        return revision+1

def encoded(value):
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,dict):return {k:encoded(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,set,frozenset)):return [encoded(v)for v in value]
    return value

class _Durable:
    def _change(self,operation,*args,**kwargs):
        staged=self.parent();setattr(staged,self.attribute,deepcopy(getattr(self,self.attribute)))
        result=getattr(staged,operation)(*args,**kwargs)
        revision=self.repo.write(self.kind,self._revision,self.dump(getattr(staged,self.attribute)))
        setattr(self,self.attribute,getattr(staged,self.attribute));self._revision=revision
        return deepcopy(result)
    @classmethod
    def load(cls,repo):
        instance=cls();instance.repo=repo
        instance._revision,payload=repo.read(instance.kind)
        if payload is not None:setattr(instance,instance.attribute,instance.restore(payload))
        return instance

class DurableWorldModels(_Durable,WorldModelRegistry):
    parent=WorldModelRegistry;attribute='models';kind='world'
    def dump(self,state):return {k:encoded(asdict(v))for k,v in state.items()}
    def restore(self,payload):
        result={}
        for k,v in payload.items():
            v=dict(v);v['updated_at']=datetime.fromisoformat(v['updated_at']);result[k]=WorldModel(**v)
        return result
    def register(self,*a,**k):return self._change('register',*a,**k)
    def revise(self,*a,**k):return self._change('revise',*a,**k)
    def apply_evidence(self,*a,**k):return self._change('apply_evidence',*a,**k)

class DurableEpistemicCalendar(_Durable,EpistemicCalendar):
    parent=EpistemicCalendar;attribute='beliefs';kind='calendar'
    def dump(self,state):return {k:encoded(asdict(v))for k,v in state.items()}
    def restore(self,payload):
        result={}
        for k,v in payload.items():
            v=dict(v)
            for field in ('formed_at','last_reviewed_at'):v[field]=datetime.fromisoformat(v[field])
            result[k]=BeliefReview(**v)
        return result
    def register(self,*a,**k):return self._change('register',*a,**k)
    def mark_reviewed(self,*a,**k):return self._change('mark_reviewed',*a,**k)

class DurableMetaLearner(_Durable,MetaLearner):
    parent=MetaLearner;attribute='patterns';kind='patterns'
    def dump(self,state):return [encoded(asdict(v))for v in state.values()]
    def restore(self,payload):
        result={}
        for v in payload:
            v=dict(v);v['role_sequence']=tuple(v['role_sequence']);v['domain_tokens']=frozenset(v['domain_tokens']);p=AbstractPattern(**v);result[p.role_sequence]=p
        return result
    def abstract(self,*a,**k):return self._change('abstract',*a,**k)

class DurableCuriosity(_Durable,CuriosityEngine):
    parent=CuriosityEngine;attribute='_gap_counts';kind='curiosity'
    def dump(self,state):return dict(state)
    def restore(self,payload):return dict(payload)
    def detect_gaps(self,*a,**k):return self._change('detect_gaps',*a,**k)
