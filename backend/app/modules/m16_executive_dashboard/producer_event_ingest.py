from __future__ import annotations
import base64,hashlib,json
from datetime import datetime,timezone
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import JSON,DateTime,String,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column,sessionmaker
from app.core.database import Base,SessionLocal,engine
from .asymmetric_proof_events import SignedProofEvent
from .producer_key_registry import ProducerKeyRegistry
class ProducerEventRow(Base):
 __tablename__='m16_producer_events';__table_args__=(UniqueConstraint('tenant_id','producer','event_id'),)
 id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True);tenant_id:Mapped[str]=mapped_column(String(120),index=True);producer:Mapped[str]=mapped_column(String(200));event_id:Mapped[str]=mapped_column(String(200),index=True);key_id:Mapped[str]=mapped_column(String(200));fingerprint_sha256:Mapped[str]=mapped_column(String(64));event_sha256:Mapped[str]=mapped_column(String(64));payload:Mapped[dict]=mapped_column(JSON);persisted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
def canonical_event_bytes(event:SignedProofEvent)->bytes:
 return json.dumps(event.model_dump(mode='json',exclude={'signature_base64','signature_hmac_sha256'}),sort_keys=True,separators=(',',':')).encode()
class ProducerEventIngest:
 """Authenticates signed producer events against the governed key registry and persists them append-only."""
 def __init__(self,tenant_id:str,sessions:sessionmaker=SessionLocal,registry:ProducerKeyRegistry|None=None):self.tenant_id=tenant_id;self.sessions=sessions;self.registry=registry or ProducerKeyRegistry(tenant_id,sessions);Base.metadata.create_all(engine)
 def _authenticate(self,event:SignedProofEvent):
  key=self.registry.get(event.producer,event.key_id)
  if key is None:raise ValueError(f'unregistered producer key: {event.producer}/{event.key_id}')
  if not key.active:raise ValueError(f'producer key retired: {event.producer}/{event.key_id}')
  registered_at=key.created_at
  if registered_at.tzinfo is None:registered_at=registered_at.replace(tzinfo=timezone.utc)
  if event.issued_at<registered_at:raise ValueError(f'event issued before producer key registration: {event.event_id}')
  canonical=canonical_event_bytes(event)
  try:public=Ed25519PublicKey.from_public_bytes(key.public_key);signature=base64.b64decode(event.signature_base64,validate=True)
  except Exception as exc:raise ValueError('invalid producer signature encoding') from exc
  try:public.verify(signature,canonical)
  except InvalidSignature as exc:raise ValueError(f'invalid producer event signature: {event.event_id}') from exc
  return key,canonical,hashlib.sha256(canonical).hexdigest()
 def ingest_batch(self,events:list[SignedProofEvent])->dict:
  authenticated=[(event,*self._authenticate(event)) for event in events]
  stored=[]
  for event,key,canonical,digest in authenticated:
   with self.sessions.begin() as db:
    row=db.scalar(select(ProducerEventRow).where(ProducerEventRow.tenant_id==self.tenant_id,ProducerEventRow.producer==event.producer,ProducerEventRow.event_id==event.event_id))
    if row:
     if row.event_sha256!=digest:raise ValueError(f'conflicting payload for immutable event: {event.event_id}')
     stored.append({'event_id':row.event_id,'producer':row.producer,'duplicate':True,'event_sha256':row.event_sha256,'persisted_at':row.persisted_at.isoformat()});continue
    row=ProducerEventRow(tenant_id=self.tenant_id,producer=event.producer,event_id=event.event_id,key_id=event.key_id,fingerprint_sha256=key.fingerprint_sha256,event_sha256=digest,payload=json.loads(canonical.decode()),persisted_at=datetime.now(timezone.utc));db.add(row);db.flush()
    stored.append({'event_id':row.event_id,'producer':row.producer,'duplicate':False,'event_sha256':row.event_sha256,'persisted_at':row.persisted_at.isoformat()})
  return {'valid':True,'ingested_events':stored,'boundary':'Authenticates each producer event with the governed tenant-scoped key registry and persists it append-only under (tenant, producer, event_id). Exact repeats are idempotent; a different payload under the same event_id conflicts. It does not subscribe to producers, inspect proof bytes, or deploy.'}
 def get_event(self,producer:str,event_id:str):
  with self.sessions() as db:return db.scalar(select(ProducerEventRow).where(ProducerEventRow.tenant_id==self.tenant_id,ProducerEventRow.producer==producer,ProducerEventRow.event_id==event_id))
 def list_events(self,producer:str|None=None)->list[dict]:
  with self.sessions() as db:
   q=select(ProducerEventRow).where(ProducerEventRow.tenant_id==self.tenant_id)
   if producer:q=q.where(ProducerEventRow.producer==producer)
   rows=db.scalars(q.order_by(ProducerEventRow.id)).all()
   return [{'producer':r.producer,'event_id':r.event_id,'key_id':r.key_id,'fingerprint_sha256':r.fingerprint_sha256,'event_sha256':r.event_sha256,'persisted_at':r.persisted_at.isoformat()} for r in rows]
