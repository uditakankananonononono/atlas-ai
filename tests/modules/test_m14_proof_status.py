from app.modules.m14_project_builder.acceptance_trace import build_proof_status
def test_proof_status_never_promotes_code_or_tests_to_live():
 x=build_proof_status([{'id':'r1','artifact_sha256':'a'*64,'test_name':'t','test_status':'passed'},{'id':'r2','artifact_sha256':'b'*64,'test_name':'t2','test_status':'passed','live_receipt_id':'receipt','live_status':'passed'}]);assert x['counts']=={'total':2,'code_complete':2,'test_complete':2,'live_acceptance_complete':1,'fully_verified':1};assert x['requirements'][0]['blockers']==['missing_or_failed_live_acceptance'];assert len(x['proof_sha256'])==64
def test_proof_status_rejects_duplicate_ids():
 import pytest
 with pytest.raises(ValueError,match='unique'):build_proof_status([{'id':'x'},{'id':'x'}])
