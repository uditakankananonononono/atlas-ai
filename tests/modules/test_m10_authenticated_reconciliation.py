"""Evidence verification resolves reviewer keys from the tenant registry only."""
import base64, hashlib, json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import app
from app.modules.m10_email_assistant import reviewer_key_registry as rk
from app.modules.m10_email_assistant.routes import get_reviewer_key_registry

C = TestClient(app); U = '/api/v1/email-assistant/promise-state-reconciliation/evidence/verify'; H = {'X-Atlas-Tenant': 't', 'X-Atlas-Actor': 'owner'}
KEY = {}


def setup_function():
    e = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool); Base.metadata.create_all(e)
    reg = rk.ReviewerKeyRegistry('t', sessionmaker(bind=e, expire_on_commit=False), actor_id='owner')
    private = Ed25519PrivateKey.generate(); raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    fp = hashlib.sha256(raw).hexdigest()
    reg.register(rk.RegisterReviewerKey(reviewer_id='owner', key_id='owner-v1', public_key_base64=base64.b64encode(raw).decode(),
                 proof_signature_base64=base64.b64encode(private.sign(rk.enrollment_statement('t', 'owner', 'owner-v1', fp))).decode()))
    KEY['private'] = private
    app.dependency_overrides[get_reviewer_key_registry] = lambda: reg


def teardown_function():
    app.dependency_overrides.clear()


def payload():
    raw = b'I sent it'; a = {'reviewer_id': 'owner', 'decision_sha256': 'a' * 64, 'key_id': 'owner-v1'}
    a['signature_base64'] = base64.b64encode(KEY['private'].sign(json.dumps(a, sort_keys=True, separators=(',', ':')).encode())).decode()
    return {'messages': [{'message_id': 'm', 'content_base64': base64.b64encode(raw).decode(), 'content_sha256': hashlib.sha256(raw).hexdigest()}], 'attestations': [a]}


def test_verifies_source_bytes_and_reviewer_attestation():
    r = C.post(U, json=payload(), headers=H); assert r.status_code == 200; b = r.json()
    assert b['valid'] and b['reviewers'][0]['signature_verified'] and b['messages'][0]['byte_count'] == 9


def test_rejects_tampered_bytes_signature_and_unknown_key():
    p = payload(); p['messages'][0]['content_base64'] = base64.b64encode(b'bad').decode(); r = C.post(U, json=p, headers=H); assert r.status_code == 422 and 'byte hash mismatch' in r.text
    p = payload(); p['attestations'][0]['decision_sha256'] = 'b' * 64; r = C.post(U, json=p, headers=H); assert r.status_code == 422 and 'invalid reviewer signature' in r.text
    p = payload(); p['attestations'][0]['key_id'] = 'other'; r = C.post(U, json=p, headers=H); assert r.status_code == 422 and 'untrusted reviewer' in r.text
