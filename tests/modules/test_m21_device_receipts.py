from dataclasses import asdict
import pytest
from app.modules.m21_claire.local_client_protocol import PairingService,AuditChain
def paired():
 p=PairingService();c=p.challenge();d=p.confirm(c.server_nonce,c.code,'lab-pc','sha256:fingerprint',{'commands'});return p,d
def test_paired_device_receipt_verifies_hash_chain_and_terminal_result():
 p,d=paired();chain=AuditChain(d.id);chain.append('a','approved',{'preview':'run qc'});chain.append('a','completed',{'exit_code':0,'output_sha256':'a'*64})
 out=p.verify_receipt(d.id,[asdict(x) for x in chain.events])
 assert out['events_verified']==2 and out['receipt_complete'] and len(out['chain_head'])==64
 assert 'does not attest' in out['boundary']
def test_receipt_rejects_tampering_and_revoked_device():
 p,d=paired();chain=AuditChain(d.id);e=asdict(chain.append('a','completed',{'ok':True}));e['payload']['ok']=False
 with pytest.raises(ValueError,match='hash mismatch'):p.verify_receipt(d.id,[e])
 p.revoke(d.id)
 with pytest.raises(ValueError,match='revoked'):p.verify_receipt(d.id,[asdict(chain.events[0])])
