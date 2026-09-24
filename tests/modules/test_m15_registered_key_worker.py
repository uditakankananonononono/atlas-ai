"""M15 approved worker: registered Ed25519 receipt keys, atomic approval consumption, append-only receipts."""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.models import ApprovalStatus
from app.modules.m15_document_generator import routes
from app.modules.m15_document_generator.approved_worker import ApprovedPublicationJob
from app.modules.m15_document_generator.provider_key_registry import (
    PublicationProviderKeyRegistry, PublicationProviderKeyRow, RegisterPublicationProviderKey)
from app.modules.m15_document_generator.publication_receipt_store import PublicationReceiptStore
from app.modules.m15_document_generator.registered_key_worker import RegisteredKeyPublicationWorker

T = 't1'
DOC = b'%PDF-1.4 approved render bytes'
SHA = hashlib.sha256(DOC).hexdigest()


def pub(key):
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


class Approvals:
    def __init__(self):
        self.items = {}

    def add(self, aid, status=ApprovalStatus.APPROVED, tenant=T, **payload):
        base = {'tenant_id': tenant, 'version_id': 'v1', 'format': 'pdf', 'content_hash': SHA}
        self.items[aid] = SimpleNamespace(status=status, user_id=tenant, payload={**base, **payload})

    def get(self, aid, user_id=None):
        a = self.items.get(aid)
        return a if a and a.user_id == user_id else None


class Renderer:
    def __init__(self, log):
        self.log = log

    def render(self, version_id, fmt):
        self.log.append(('render', version_id, fmt))
        return DOC


class Uploader:
    def __init__(self, log, key, key_id='k1', provider='s3', uploaded_at=None, forge=False):
        self.log, self.key, self.key_id, self.provider = log, key, key_id, provider
        self.uploaded_at, self.forge = uploaded_at, forge

    def upload_private(self, object_key, data):
        self.log.append(('upload', object_key))
        r = {'approval_id': object_key.split('/')[-1], 'version_id': 'v1', 'provider': self.provider,
             'object_key': object_key, 'access': 'private', 'download_url': 'https://objects.example/' + object_key,
             'published_sha256': hashlib.sha256(data).hexdigest(), 'byte_size': len(data),
             'uploaded_at': (self.uploaded_at or datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat().replace('+00:00', 'Z'),
             'key_id': self.key_id}
        canonical = json.dumps(r, sort_keys=True, separators=(',', ':')).encode()
        signer = Ed25519PrivateKey.generate() if self.forge else self.key
        r['signature_base64'] = base64.b64encode(signer.sign(canonical)).decode()
        return r


@pytest.fixture
def env():
    e = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    sessions = sessionmaker(bind=e, expire_on_commit=False)
    key = Ed25519PrivateKey.generate()
    registry = PublicationProviderKeyRegistry(T, sessions)
    registry.register(RegisterPublicationProviderKey(provider='s3', key_id='k1', public_key_base64=pub(key)))
    approvals = Approvals()
    log = []
    store = PublicationReceiptStore(T, sessions)
    return SimpleNamespace(sessions=sessions, key=key, registry=registry, approvals=approvals, log=log, store=store)


def job(aid='a1'):
    return ApprovedPublicationJob(approval_id=aid, version_id='v1', format='pdf', expected_content_hash=SHA,
                                  object_key=f'{T}/docs/{aid}')


def worker(env, **up):
    return RegisteredKeyPublicationWorker(T, env.approvals, Renderer(env.log), Uploader(env.log, env.key, **up),
                                          env.sessions, env.store)


def test_happy_path_renders_uploads_verifies_and_stores_receipt(env):
    env.approvals.add('a1')
    out = worker(env).run(job())
    assert out['verified'] and out['signature_algorithm'] == 'Ed25519' and out['access'] == 'private'
    assert out['published_sha256'] == SHA and len(out['key_fingerprint_sha256']) == 64
    assert env.log == [('render', 'v1', 'pdf'), ('upload', f'{T}/docs/a1')]
    row = env.store.get('a1')
    assert row.published_sha256 == SHA and row.payload['signature_base64'] == out['signature_base64']


def test_forged_signature_rejected(env):
    env.approvals.add('a1')
    with pytest.raises(ValueError, match='invalid provider receipt signature'):
        worker(env, forge=True).run(job())
    assert env.store.get('a1') is None


def test_unregistered_key_rejected(env):
    env.approvals.add('a1')
    with pytest.raises(ValueError, match='not registered'):
        worker(env, key_id='k-unknown').run(job())
    env.approvals.add('a2')
    with pytest.raises(ValueError, match='not registered'):
        worker(env, provider='other-provider').run(job('a2'))


def test_key_registered_for_other_tenant_rejected(env):
    other = Ed25519PrivateKey.generate()
    PublicationProviderKeyRegistry('t2', env.sessions).register(
        RegisterPublicationProviderKey(provider='s3', key_id='k2', public_key_base64=pub(other)))
    env.approvals.add('a1')
    w = RegisteredKeyPublicationWorker(T, env.approvals, Renderer(env.log), Uploader(env.log, other, key_id='k2'),
                                       env.sessions, env.store)
    with pytest.raises(ValueError, match='not registered'):
        w.run(job())


def test_retired_key_rejected(env):
    env.registry.retire('s3', 'k1')
    env.approvals.add('a1')
    with pytest.raises(ValueError, match='retired'):
        worker(env).run(job())
    assert env.store.get('a1') is None


def test_receipt_issued_before_key_registration_rejected(env):
    env.approvals.add('a1')
    with pytest.raises(ValueError, match='before the provider key was registered'):
        worker(env, uploaded_at=datetime.now(timezone.utc) - timedelta(days=1)).run(job())


def test_tampered_registered_key_bytes_fail_fingerprint_pin(env):
    with env.sessions.begin() as db:
        row = db.query(PublicationProviderKeyRow).filter_by(tenant_id=T, key_id='k1').one()
        row.public_key = base64.b64decode(pub(Ed25519PrivateKey.generate()))
    env.approvals.add('a1')
    with pytest.raises(ValueError, match='pinned fingerprint'):
        worker(env).run(job())


def test_registry_rejects_rebinding_key_id(env):
    with pytest.raises(ValueError, match='different public key bytes'):
        env.registry.register(RegisterPublicationProviderKey(provider='s3', key_id='k1',
                                                             public_key_base64=pub(Ed25519PrivateKey.generate())))


def test_approval_replay_refused_without_second_effect(env):
    env.approvals.add('a1')
    worker(env).run(job())
    env.log.clear()
    with pytest.raises(ValueError, match='replay refused'):
        worker(env).run(job())
    assert env.log == []


def test_approval_consumed_before_effect_even_if_upload_fails(env):
    env.approvals.add('a1')
    w = worker(env)

    class Boom:
        def upload_private(self, *a):
            assert w.is_consumed('a1'), 'approval must be consumed before the effect'
            raise RuntimeError('upload failed')
    w.uploader = Boom()
    with pytest.raises(RuntimeError):
        w.run(job())
    with pytest.raises(ValueError, match='replay refused'):
        worker(env).run(job())


@pytest.mark.parametrize('setup', [
    lambda a: None,
    lambda a: a.add('a1', status=ApprovalStatus.PENDING),
    lambda a: a.add('a1', status=ApprovalStatus.DENIED),
    lambda a: a.add('a1', tenant='t2'),
    lambda a: a.add('a1', content_hash='0' * 64),
    lambda a: a.add('a1', version_id='v2'),
    lambda a: a.add('a1', format='docx'),
])
def test_render_and_upload_only_after_matching_approval(env, setup):
    setup(env.approvals)
    w = worker(env)
    with pytest.raises(ValueError, match='approval'):
        w.run(job())
    assert env.log == [] and not w.is_consumed('a1')


def test_receipt_cannot_be_replaced(env):
    env.approvals.add('a1')
    out = worker(env).run(job())
    forged = {**out, 'published_sha256': '1' * 64, 'signature_base64': 'AAAA'}
    with pytest.raises(ValueError, match='immutable'):
        env.store.persist(forged)
    assert env.store.get('a1').published_sha256 == SHA


def test_route_executes_through_registered_worker(env):
    env.approvals.add('a1')
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.tenant] = lambda: T
    app.dependency_overrides[routes.get_registered_publication_worker] = lambda: worker(env)
    c = TestClient(app)
    body = job().model_dump()
    r = c.post('/document-generator/publication-worker/registered/execute', json=body)
    assert r.status_code == 200 and r.json()['verified'] and r.json()['tenant_id'] == T
    r = c.post('/document-generator/publication-worker/registered/execute', json=body)
    assert r.status_code == 409 and 'replay refused' in r.text
