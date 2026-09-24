import base64,json
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m16_executive_dashboard.routes import get_producer_event_ingest,get_producer_key_registry,get_producer_pull_adapter
from app.modules.m16_executive_dashboard.producer_key_registry import ProducerKeyRegistry
from app.modules.m16_executive_dashboard.producer_event_ingest import ProducerEventIngest
from app.modules.m16_executive_dashboard.producer_pull_adapter import ProducerPullAdapter
from app.modules.m16_executive_dashboard.asymmetric_proof_events import SignedProofEvent
from app.modules.m16_executive_dashboard.producer_event_ingest import canonical_event_bytes
C=TestClient(app)
KEYS='/api/v1/executive-dashboard/proof-gaps/producer-keys';INGEST='/api/v1/executive-dashboard/proof-gaps/events/ingest';LIST='/api/v1/executive-dashboard/proof-gaps/events/ingested';PULL='/api/v1/executive-dashboard/proof-gaps/events/pull'
H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
PRIV=Ed25519PrivateKey.generate();PUB=PRIV.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
OTHER_PRIV=Ed25519PrivateKey.generate()
S={}
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);S['sessions']=sessions
 app.dependency_overrides[get_producer_key_registry]=lambda:ProducerKeyRegistry('t',sessions)
 app.dependency_overrides[get_producer_event_ingest]=lambda:ProducerEventIngest('t',sessions)
 app.dependency_overrides[get_producer_pull_adapter]=lambda:ProducerPullAdapter(ProducerEventIngest('t',sessions))
def teardown_function():app.dependency_overrides.clear();S.clear()
def register_key(raw=PUB,producer='ci',key_id='v1'):
 return C.post(KEYS,json={'producer':producer,'key_id':key_id,'public_key_base64':base64.b64encode(raw).decode()},headers=H)
def event(priv=PRIV,event_id='e1',producer='ci',key_id='v1',proof='a'*64,issued_at=None):
 e={'event_id':event_id,'producer':producer,'module_id':'16','requirement_id':'r1','event_type':'deployment_receipt','proof_sha256':proof,'deployment_version':'1.0','environment':'prod','issued_at':issued_at or datetime.now(timezone.utc).isoformat(),'key_id':key_id}
 model=SignedProofEvent(signature_base64='x',**e);out=model.model_dump(mode='json',exclude={'signature_base64','signature_hmac_sha256'})
 out['signature_base64']=base64.b64encode(priv.sign(canonical_event_bytes(model))).decode();return out
def ingest(events):return C.post(INGEST,json={'events':events},headers=H)
def test_registers_key_and_ingests_signed_event():
 assert register_key().status_code==200;r=ingest([event()]);assert r.status_code==200,r.text
 b=r.json();assert b['valid'] and b['tenant_id']=='t' and b['ingested_events'][0]['duplicate'] is False
 listed=C.get(LIST,headers=H).json()['events'];assert len(listed)==1 and listed[0]['event_id']=='e1' and len(listed[0]['fingerprint_sha256'])==64
def test_exact_repeat_is_idempotent_and_stays_immutable():
 register_key();same=event();assert ingest([same]).status_code==200
 r=ingest([same]);assert r.status_code==200 and r.json()['ingested_events'][0]['duplicate'] is True
 assert len(C.get(LIST,headers=H).json()['events'])==1
def test_conflicting_payload_under_same_event_id_rejected():
 register_key();assert ingest([event()]).status_code==200
 r=ingest([event(proof='b'*64)]);assert r.status_code==409 and 'conflicting payload for immutable event' in r.text
 rows=C.get(LIST,headers=H).json()['events'];assert len(rows)==1
def test_forged_signature_rejected_and_never_persisted():
 register_key();forged=event(priv=OTHER_PRIV)
 r=ingest([forged]);assert r.status_code==409 and 'invalid producer event signature' in r.text
 assert C.get(LIST,headers=H).json()['events']==[]
def test_unregistered_key_rejected():
 r=ingest([event()]);assert r.status_code==409 and 'unregistered producer key' in r.text
 assert C.get(LIST,headers=H).json()['events']==[]
def test_retired_key_rejected():
 register_key();assert C.post(KEYS+'/ci/v1/retire',headers=H).status_code==200
 r=ingest([event()]);assert r.status_code==409 and 'producer key retired' in r.text
 assert C.get(LIST,headers=H).json()['events']==[]
def test_receipt_issued_before_key_registration_rejected():
 register_key()
 r=ingest([event(issued_at='2001-01-01T00:00:00+00:00')]);assert r.status_code==409 and 'issued before producer key registration' in r.text
 assert C.get(LIST,headers=H).json()['events']==[]
def test_tenant_isolation():
 register_key();assert ingest([event()]).status_code==200
 sessions=S['sessions']
 app.dependency_overrides[get_producer_key_registry]=lambda:ProducerKeyRegistry('other',sessions)
 app.dependency_overrides[get_producer_event_ingest]=lambda:ProducerEventIngest('other',sessions)
 assert C.get(LIST,headers=H).json()['events']==[]
 r=ingest([event()]);assert r.status_code==409 and 'unregistered producer key' in r.text
def test_pull_adapter_fails_closed_when_unconfigured():
 r=C.post(PULL,headers=H);assert r.status_code==409 and 'not configured' in r.text
def test_pull_adapter_ingests_configured_subscription():
 register_key();sessions=S['sessions'];batch=[event(event_id='e9')]
 app.dependency_overrides[get_producer_pull_adapter]=lambda:ProducerPullAdapter(ProducerEventIngest('t',sessions),fetcher=lambda:{'events':batch})
 r=C.post(PULL,headers=H);assert r.status_code==200,r.text
 b=r.json();assert b['pulled']==1 and b['ingested_events'][0]['event_id']=='e9'
 assert [x['event_id'] for x in C.get(LIST,headers=H).json()['events']]==['e9']
