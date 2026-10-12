import base64,json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m17_narrative_architect.publication_gate import PublicationGateRequest,publish_through_gate
from app.modules.m17_narrative_architect.publication_key_registry import PublicationKeyRegistry,RegisterPublicationKey
import pytest

def configured(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'keys.sqlite'));Base.metadata.create_all(engine)
    registry=PublicationKeyRegistry('owner',sessionmaker(bind=engine,expire_on_commit=False))
    key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    registry.register(RegisterPublicationKey(provider='publisher',key_id='key',public_key_base64=base64.b64encode(public).decode()))
    body=PublicationGateRequest(essay_id='e',to_version='v2',revision_sha256='a'*64,acceptance_sha256='b'*64,reviewed_by_owner=True,audience_boundary='admissions',disclosure_approved=True)
    class Adapter:
        calls=0
        def receipt(self,audience,revision):
            receipt={'provider':'publisher','provider_id':'preflight-e-v2','essay_id':'e','revision_sha256':revision,'audience_boundary':audience,'published_at':'2026-10-12T00:00:00Z','key_id':'key'}
            receipt['signature_base64']=base64.b64encode(key.sign(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode())).decode()
            return receipt
        def prepare(self,audience,revision):return self.receipt(audience,revision)
        def publish(self,audience,revision):self.calls+=1;return self.receipt(audience,revision)
    return body,Adapter(),registry

def test_preflight_wrong_audience_refuses_before_publish(tmp_path):
    body,adapter,registry=configured(tmp_path)
    adapter.prepare=lambda a,r:adapter.receipt('public',r)
    with pytest.raises(ValueError):publish_through_gate(body,adapter,body.model_dump(),key_registry=registry)
    assert adapter.calls==0

def test_retired_provider_key_refuses_before_publish(tmp_path):
    body,adapter,registry=configured(tmp_path);registry.retire('publisher','key')
    with pytest.raises(ValueError,match='active'):publish_through_gate(body,adapter,body.model_dump(),key_registry=registry)
    assert adapter.calls==0

def test_exact_active_signed_preflight_and_receipt(tmp_path):
    body,adapter,registry=configured(tmp_path)
    assert publish_through_gate(body,adapter,body.model_dump(),key_registry=registry)['published']
    assert adapter.calls==1

def test_missing_preflight_or_registry_fails_closed(tmp_path):
    body,adapter,registry=configured(tmp_path)
    with pytest.raises(ValueError):publish_through_gate(body,adapter,body.model_dump())
    adapter.prepare=None
    with pytest.raises(ValueError):publish_through_gate(body,adapter,body.model_dump(),key_registry=registry)
    assert adapter.calls==0
