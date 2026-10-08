"""Real Ed25519 device-authorship verification; no fabricated signed receipts."""
import pytest
from pydantic import ValidationError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.modules.m13_browser_agent.pc_daemon.receipts import ReceiptChain
from app.modules.m13_browser_agent.session_bridge.registry import PairingError
from app.modules.m13_browser_agent.session_bridge.routes import ReceiptIn, verify_receipt
from test_m13_session_bridge_registry import registry, _keypair
from types import SimpleNamespace

def pair(reg):
    key,pem=_keypair();c=reg.create_challenge('tenant-a')
    d=reg.confirm_pairing(c['server_nonce'],c['code'],name='PC',public_key=pem,capabilities=['navigate'])
    chain=ReceiptChain(d['device_id']);chain.append('cmd','completed',{'url':'https://example.test'})
    return d,key,chain.events

@pytest.mark.parametrize('mode',['missing','wrong_key','malformed'])
def test_unsigned_or_foreign_receipts_refused(registry,mode):
    d,key,events=pair(registry)
    sig=None if mode=='missing' else 'invalid' if mode=='malformed' else Ed25519PrivateKey.generate().sign(events[-1]['event_hash'].encode()).hex()
    with pytest.raises(PairingError,match='signature'):
        if sig is None: registry.verify_receipt(d['device_id'],events)
        else: registry.verify_receipt(d['device_id'],events,sig)

def test_valid_signature_and_rehashed_tampering(registry):
    d,key,events=pair(registry);sig=key.sign(events[-1]['event_hash'].encode()).hex()
    result=registry.verify_receipt(d['device_id'],events,sig)
    assert result['events_verified']==1 and result['receipt_complete']
    forged=ReceiptChain(d['device_id']);forged.append('cmd','completed',{'url':'https://attacker.test'})
    with pytest.raises(PairingError,match='signature'): registry.verify_receipt(d['device_id'],forged.events,sig)

def test_route_signature_required_and_forwarded(registry):
    with pytest.raises(ValidationError): ReceiptIn(events=[{}])
    d,key,events=pair(registry);sig=key.sign(events[-1]['event_hash'].encode()).hex()
    result=verify_receipt(d['device_id'],ReceiptIn(events=events,signature=sig),SimpleNamespace(tenant_id='tenant-a'),registry)
    assert result['chain_head']==events[-1]['event_hash']
