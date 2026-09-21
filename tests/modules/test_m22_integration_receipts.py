import pytest
from app.core.approvals import ApprovalStore
from app.modules.m22_tools_hub.service import Service,Candidate
def setup():
 s=Service(ApprovalStore(),[]);c=Candidate('Safe','https://example.org','safe','official',security=.9);s.candidates[c.id]=c;p=s.propose_install(c.id,'api',{},['read']);return s,c,p
def evidence(c,p):return {'operation_id':'op-1','artifact_sha256':'a'*64,'manifest_digest':'b'*64,'installed_at':'2026-09-22T00:00:00Z','receipt_path':'receipts/op-1.json','approval_id':p.approval_id,'candidate_id':c.id,'backup_id':'backup-1'}
def test_integration_receipt_binds_proposal_candidate_hashes_and_rollback():
 s,c,p=setup();out=s.mark_integrated(p.id,evidence(c,p));r=out['evidence']
 assert r['verified_binding'] and r['rollback_available'] and 'not independently verified' in r['execution_claim']
def test_integration_receipt_rejects_missing_or_cross_proposal_evidence():
 s,c,p=setup();e=evidence(c,p);e['approval_id']='other'
 with pytest.raises(ValueError,match='approval'):s.mark_integrated(p.id,e)
 e=evidence(c,p);del e['manifest_digest']
 with pytest.raises(ValueError,match='missing'):s.mark_integrated(p.id,e)
