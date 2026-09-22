import base64
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.main import app
from app.modules.m12_ai_research_lab.routes import get_provider_key_registry
from app.modules.m12_ai_research_lab.provider_key_registry import ProviderKeyRegistry
C=TestClient(app);U='/api/v1/ai-research-lab/reproducible-run/provider-keys';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'}
def setup_function():
 e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(e);sessions=sessionmaker(bind=e,expire_on_commit=False);app.dependency_overrides[get_provider_key_registry]=lambda:ProviderKeyRegistry('t',sessions)
def teardown_function():app.dependency_overrides.clear()
def p(raw=b'a'*32):return {'provider':'lab','key_id':'v1','public_key_base64':base64.b64encode(raw).decode()}
def test_registers_idempotent_key_and_explicitly_retires():
 r=C.post(U,json=p(),headers=H);assert r.status_code==200 and len(r.json()['fingerprint_sha256'])==64;assert C.post(U,json=p(),headers=H).status_code==200;r=C.post(U+'/lab/v1/retire',headers=H);assert r.status_code==200 and not r.json()['active']
def test_rejects_rebinding_and_wrong_length():
 assert C.post(U,json=p(),headers=H).status_code==200;r=C.post(U,json=p(b'b'*32),headers=H);assert r.status_code==409 and 'different public key bytes' in r.text
 r=C.post(U,json=p(b'short'),headers=H);assert r.status_code==409 and 'must be 32 bytes' in r.text
