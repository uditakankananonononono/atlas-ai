import pytest
from app.modules.m20_general_cognitive_worker.execution_truth import execution_truth_ledger
def test_truth_ledger_preserves_all_states_and_counts_claimed_verified_fraction():
 out=execution_truth_ledger([{'id':'p','claim':'workflow drafted','state':'planned'},{'id':'s','claim':'model run','state':'simulated'},{'id':'e','claim':'message sent','state':'externally_executed','evidence_ids':['receipt']},{'id':'v','claim':'result reproduced','state':'independently_verified','evidence_ids':['report'],'verifier':'lab-b'}])
 assert out['counts']=={'planned':1,'simulated':1,'externally_executed':1,'independently_verified':1}
 assert out['claimed_verified_fraction']==.25 and out['items'][0]['state']=='planned'
 assert 'never promoted' in out['boundary']
def test_truth_ledger_blocks_execution_or_verification_without_evidence():
 with pytest.raises(ValueError,match='evidence_ids'):execution_truth_ledger([{'id':'x','claim':'sent','state':'externally_executed'}])
 with pytest.raises(ValueError,match='verifier'):execution_truth_ledger([{'id':'x','claim':'checked','state':'independently_verified','evidence_ids':['r']}])


def test_fabricated_evidence_labels_are_never_independent_verification():
 out=execution_truth_ledger([{'id':'f','claim':'never actually run','state':'independently_verified','evidence_ids':['invented-artifact'],'verifier':'invented-lab'}])
 assert out['status']=='supplied_claim_rollup_only' and out['evidence_verified'] is False
 assert out['highest_claimed_state']=='independently_verified'
 assert out['items'][0]['state_is_caller_claim'] and out['items'][0]['evidence_verified'] is False
 assert 'highest_observed_state' not in out and 'verified_fraction' not in out


def test_frontend_contract_fixture_is_generated_from_current_backend_shape():
 import json
 from pathlib import Path
 fixture=Path(__file__).resolve().parents[2]/'frontend/components/fixtures/claimed-execution-ledger.json'
 out=execution_truth_ledger([{'id':'s','claim':'Draft checklist','state':'independently_verified','evidence_ids':['invented-evidence'],'verifier':'unverified-label'}])
 assert json.loads(fixture.read_text())==out
